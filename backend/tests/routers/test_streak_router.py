from __future__ import annotations

from datetime import date, datetime, timezone
import os
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("CLERK_SECRET_KEY", "sk_test_123")

from backend.app.core.auth import get_current_user
from backend.app.core.database import get_db_session
from backend.app.main import create_app
from backend.app.models.db import Base, StreakEvent, StreakEventType, User
from backend.app.routers import streak as streak_router


pytestmark = pytest.mark.asyncio


class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz: timezone | None = None) -> datetime:
        return cls(2026, 3, 28, 12, 0, 0, tzinfo=tz or timezone.utc)


class IstBoundaryDateTime(datetime):
    @classmethod
    def now(cls, tz: timezone | None = None) -> datetime:
        return cls(2026, 3, 28, 18, 45, 0, tzinfo=tz or timezone.utc)


class RecoveryDateTime(datetime):
    @classmethod
    def now(cls, tz: timezone | None = None) -> datetime:
        return cls(2026, 3, 28, 12, 0, 0, tzinfo=tz or timezone.utc)


async def _build_session_factory() -> tuple[async_sessionmaker[AsyncSession], object, Path]:
    temp_directory = Path("backend/.tmp-test-db")
    temp_directory.mkdir(exist_ok=True)
    database_path = temp_directory / f"streak-router-{uuid4().hex}.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine, database_path


@pytest_asyncio.fixture
async def streak_harness(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    session_factory, engine, database_path = await _build_session_factory()
    current_user = User(
        id=uuid4(),
        clerk_id="user_streak_test",
        email="learner@example.com",
        current_streak=9,
        longest_streak=12,
        freeze_tokens_remaining=2,
        last_activity_date=date(2026, 3, 26),
    )
    session_state = {"reviewsCompleted": 8}

    async with session_factory() as session:
        session.add(current_user)
        await session.commit()

    async def override_get_db_session():
        async with session_factory() as session:
            yield session

    async def override_get_current_user() -> User:
        return current_user

    async def fake_get_ephemeral_json(_key: str, *, settings: object | None = None) -> dict[str, int]:
        return dict(session_state)

    async def fake_set_ephemeral_json(
        _key: str,
        value: object,
        *,
        ttl_seconds: int,
        settings: object | None = None,
    ) -> None:
        assert ttl_seconds > 0
        if isinstance(value, dict):
            session_state.clear()
            session_state.update(value)

    monkeypatch.setattr(streak_router, "datetime", FixedDateTime)
    monkeypatch.setattr(streak_router, "get_ephemeral_json", fake_get_ephemeral_json, raising=False)
    monkeypatch.setattr(streak_router, "set_ephemeral_json", fake_set_ephemeral_json, raising=False)

    app = create_app()
    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield {
            "client": client,
            "session_factory": session_factory,
            "session_state": session_state,
            "user": current_user,
        }

    await engine.dispose()
    database_path.unlink(missing_ok=True)


async def test_get_streak_returns_db_state_and_recovery_progress(streak_harness: dict[str, object]) -> None:
    client = streak_harness["client"]

    response = await client.get("/api/v1/streak")

    assert response.status_code == 200
    payload = response.json()
    assert payload["currentStreak"] == 9
    assert payload["longestStreak"] == 12
    assert payload["freezeTokensRemaining"] == 2
    assert payload["lastActivityDate"] == "2026-03-26"
    assert payload["graceWindow"]["active"] is True
    assert payload["graceWindow"]["expiresAt"] == "2026-03-28T18:29:59.999999Z"
    assert payload["recovery"]["eligible"] is True
    assert payload["recovery"]["reviewsCompleted"] == 8
    assert payload["recovery"]["reviewsRemaining"] == 12
    assert payload["rageModal"]["show"] is False


async def test_get_streak_weekly_bar_uses_ist_today_at_utc_boundary(
    streak_harness: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = streak_harness["client"]
    monkeypatch.setattr(streak_router, "datetime", IstBoundaryDateTime)

    response = await client.get("/api/v1/streak")

    assert response.status_code == 200
    payload = response.json()
    assert payload["weeklyBar"][-1]["date"] == "2026-03-29"
    assert payload["weeklyBar"][-1]["state"] == "today"


async def test_freeze_endpoint_consumes_token_and_persists_streak_event(
    streak_harness: dict[str, object],
) -> None:
    client = streak_harness["client"]
    session_factory = streak_harness["session_factory"]
    current_user = streak_harness["user"]

    response = await client.post("/api/v1/streak/freeze")

    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "freeze"
    assert payload["streak"]["freezeTokensRemaining"] == 1
    assert payload["streak"]["currentStreak"] == 10

    async with session_factory() as session:
        refreshed_user = await session.get(User, current_user.id)
        events = list(
            await session.scalars(
                select(StreakEvent).where(StreakEvent.user_id == current_user.id).order_by(StreakEvent.event_date)
            )
        )

    assert refreshed_user is not None
    assert refreshed_user.freeze_tokens_remaining == 1
    assert refreshed_user.current_streak == 10
    assert refreshed_user.longest_streak == 12
    assert refreshed_user.last_activity_date == date(2026, 3, 27)
    assert len(events) == 1
    assert events[0].event_type == StreakEventType.FROZEN
    assert events[0].event_date == date(2026, 3, 27)
    assert events[0].streak_value_at_event == 10


async def test_recover_endpoint_rejects_sessions_below_twenty_reviews(
    streak_harness: dict[str, object],
) -> None:
    client = streak_harness["client"]
    session_factory = streak_harness["session_factory"]
    session_state = streak_harness["session_state"]
    current_user = streak_harness["user"]
    session_state["reviewsCompleted"] = 19

    response = await client.post("/api/v1/streak/recover", json={"reviewsCompleted": 19})

    assert response.status_code == 409
    assert response.json()["detail"] == "Recovery requires 20 flashcard reviews in one session."

    async with session_factory() as session:
        refreshed_user = await session.get(User, current_user.id)
        events = list(await session.scalars(select(StreakEvent).where(StreakEvent.user_id == current_user.id)))

    assert refreshed_user is not None
    assert refreshed_user.current_streak == 9
    assert refreshed_user.last_activity_date == date(2026, 3, 26)
    assert events == []


async def test_recover_endpoint_rejects_spoofed_client_review_counts(
    streak_harness: dict[str, object],
) -> None:
    client = streak_harness["client"]
    session_factory = streak_harness["session_factory"]
    current_user = streak_harness["user"]

    response = await client.post("/api/v1/streak/recover", json={"reviewsCompleted": 20})

    assert response.status_code == 409
    assert response.json()["detail"] == "Recovery requires 20 flashcard reviews in one session."

    async with session_factory() as session:
        refreshed_user = await session.get(User, current_user.id)
        events = list(await session.scalars(select(StreakEvent).where(StreakEvent.user_id == current_user.id)))

    assert refreshed_user is not None
    assert refreshed_user.current_streak == 9
    assert refreshed_user.last_activity_date == date(2026, 3, 26)
    assert events == []


async def test_recover_endpoint_persists_today_as_latest_activity_day(
    streak_harness: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = streak_harness["client"]
    session_factory = streak_harness["session_factory"]
    session_state = streak_harness["session_state"]
    current_user = streak_harness["user"]
    monkeypatch.setattr(streak_router, "datetime", RecoveryDateTime)
    session_state["reviewsCompleted"] = 20

    response = await client.post("/api/v1/streak/recover", json={"reviewsCompleted": 0})

    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "recover"
    assert payload["streak"]["currentStreak"] == 11
    assert payload["streak"]["lastActivityDate"] == "2026-03-28"

    async with session_factory() as session:
        refreshed_user = await session.get(User, current_user.id)
        events = list(
            await session.scalars(
                select(StreakEvent).where(StreakEvent.user_id == current_user.id).order_by(StreakEvent.event_date)
            )
        )

    assert refreshed_user is not None
    assert refreshed_user.current_streak == 11
    assert refreshed_user.last_activity_date == date(2026, 3, 28)
    assert len(events) == 1
    assert events[0].event_type == StreakEventType.RECOVERED
    assert events[0].event_date == date(2026, 3, 28)
    assert events[0].streak_value_at_event == 11
