from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import os
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("CLERK_SECRET_KEY", "sk_test_123")

from backend.app.core.auth import get_current_user
from backend.app.core.database import get_db_session
from backend.app.main import create_app
from backend.app.models.db import (
    Base,
    Flashcard,
    FlashcardCardType,
    FlashcardDifficulty,
    FlashcardReview,
    FlashcardReviewRating,
    Topic,
    TopicDifficulty,
    User,
)
from backend.app.routers import flashcards as flashcards_router
from backend.app.services import fsrs_service


pytestmark = pytest.mark.asyncio


class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz: timezone | None = None) -> datetime:
        return cls(2026, 3, 27, 10, 30, 0, tzinfo=tz or timezone.utc)


class GraceWindowDateTime(datetime):
    @classmethod
    def now(cls, tz: timezone | None = None) -> datetime:
        return cls(2026, 3, 28, 12, 0, 0, tzinfo=tz or timezone.utc)


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def _build_session_factory() -> tuple[async_sessionmaker[AsyncSession], object, Path]:
    temp_directory = Path("backend/.tmp-test-db")
    temp_directory.mkdir(exist_ok=True)
    database_path = temp_directory / f"flashcards-router-{uuid4().hex}.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine, database_path


@pytest_asyncio.fixture
async def flashcards_harness(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    session_factory, engine, database_path = await _build_session_factory()
    current_user = User(
        id=uuid4(),
        clerk_id="user_flashcards_test",
        email="learner@example.com",
        current_streak=7,
        longest_streak=11,
        freeze_tokens_remaining=2,
    )
    session_state = {"reviewsCompleted": 2}

    async with session_factory() as session:
        session.add(current_user)
        await session.commit()

    async def override_get_db_session():
        async with session_factory() as session:
            yield session

    async def override_get_current_user() -> User:
        return current_user

    app = create_app()
    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_current_user] = override_get_current_user

    monkeypatch.setattr(fsrs_service, "datetime", FixedDateTime)
    monkeypatch.setattr(flashcards_router, "datetime", FixedDateTime)

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

    monkeypatch.setattr(flashcards_router, "get_ephemeral_json", fake_get_ephemeral_json, raising=False)
    monkeypatch.setattr(flashcards_router, "set_ephemeral_json", fake_set_ephemeral_json, raising=False)

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


async def _seed_due_cards(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    user_id: UUID,
) -> dict[str, UUID]:
    topic_due = Topic(
        id=uuid4(),
        title="Aggregations",
        description="Grouped queries",
        order_index=1,
        difficulty=TopicDifficulty.BEGINNER,
    )
    topic_future = Topic(
        id=uuid4(),
        title="Window Functions",
        description="Ranking and partitions",
        order_index=2,
        difficulty=TopicDifficulty.INTERMEDIATE,
    )
    due_without_review = Flashcard(
        id=uuid4(),
        topic_id=topic_due.id,
        card_type=FlashcardCardType.RECALL,
        difficulty=FlashcardDifficulty.EASY,
        front="Which clause filters grouped rows?",
        back="HAVING filters grouped rows.",
    )
    due_with_review = Flashcard(
        id=uuid4(),
        topic_id=topic_due.id,
        card_type=FlashcardCardType.RECALL,
        difficulty=FlashcardDifficulty.MEDIUM,
        front="What does COUNT(*) return?",
        back="It counts rows, including duplicates and NULLs in other columns.",
    )
    future_card = Flashcard(
        id=uuid4(),
        topic_id=topic_future.id,
        card_type=FlashcardCardType.RECALL,
        difficulty=FlashcardDifficulty.HARD,
        front="What does ROW_NUMBER() do?",
        back="It numbers rows within the ordered partition.",
    )

    async with session_factory() as session:
        session.add_all([topic_due, topic_future, due_without_review, due_with_review, future_card])
        session.add_all(
            [
                FlashcardReview(
                    user_id=user_id,
                    card_id=due_with_review.id,
                    rating=FlashcardReviewRating.OKAY,
                    interval_days=5,
                    stability=3.0,
                    difficulty_fsrs=1.8,
                    reviewed_at=FixedDateTime.now(timezone.utc) - timedelta(days=3),
                    next_review_at=FixedDateTime.now(timezone.utc) - timedelta(minutes=15),
                ),
                FlashcardReview(
                    user_id=user_id,
                    card_id=future_card.id,
                    rating=FlashcardReviewRating.EASY,
                    interval_days=14,
                    stability=8.0,
                    difficulty_fsrs=1.5,
                    reviewed_at=FixedDateTime.now(timezone.utc) - timedelta(days=1),
                    next_review_at=FixedDateTime.now(timezone.utc) + timedelta(days=7),
                ),
            ]
        )
        await session.commit()

    return {
        "due_without_review": due_without_review.id,
        "due_with_review": due_with_review.id,
        "future_card": future_card.id,
    }


async def _seed_review_card(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    user_id: UUID,
) -> UUID:
    topic = Topic(
        id=uuid4(),
        title="Joins",
        description="Join patterns",
        order_index=3,
        difficulty=TopicDifficulty.BEGINNER,
    )
    card = Flashcard(
        id=uuid4(),
        topic_id=topic.id,
        card_type=FlashcardCardType.RECALL,
        difficulty=FlashcardDifficulty.MEDIUM,
        front="When would you use a LEFT JOIN?",
        back="When you need every row from the left side, matched when possible.",
    )

    async with session_factory() as session:
        session.add_all([topic, card])
        session.add(
            FlashcardReview(
                user_id=user_id,
                card_id=card.id,
                rating=FlashcardReviewRating.OKAY,
                interval_days=7,
                stability=4.0,
                difficulty_fsrs=2.5,
                reviewed_at=FixedDateTime.now(timezone.utc) - timedelta(days=7),
                next_review_at=FixedDateTime.now(timezone.utc) - timedelta(hours=1),
            )
        )
        await session.commit()

    return card.id


async def test_get_due_flashcards_returns_only_due_cards_from_db(flashcards_harness: dict[str, object]) -> None:
    session_factory = flashcards_harness["session_factory"]
    current_user = flashcards_harness["user"]
    client = flashcards_harness["client"]
    card_ids = await _seed_due_cards(session_factory, user_id=current_user.id)

    response = await client.get("/api/v1/flashcards/due")

    assert response.status_code == 200
    payload = response.json()
    returned_ids = {card["id"] for card in payload["cards"]}
    assert returned_ids == {str(card_ids["due_without_review"]), str(card_ids["due_with_review"])}
    assert payload["totalDue"] == 2
    assert str(card_ids["future_card"]) not in returned_ids
    assert payload["cards"][0]["reviewState"]["ratingOptions"] == ["forgot", "hard", "okay", "easy"]
    assert "Aggregations" in payload["sessionFocus"]


async def test_review_endpoint_persists_review_and_returns_next_review(
    flashcards_harness: dict[str, object],
) -> None:
    session_factory = flashcards_harness["session_factory"]
    session_state = flashcards_harness["session_state"]
    current_user = flashcards_harness["user"]
    client = flashcards_harness["client"]
    card_id = await _seed_review_card(session_factory, user_id=current_user.id)

    response = await client.post(
        "/api/v1/flashcards/review",
        json={"cardId": str(card_id), "rating": "easy", "elapsedMs": 4800},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["cardId"] == str(card_id)
    assert payload["rating"] == "easy"
    assert payload["intervalDays"] == 20
    assert payload["nextReviewAt"] == "2026-04-16T10:30:00Z"
    assert payload["celebrate"] is True
    assert payload["xpAwarded"] == 25
    assert payload["reviewsCompletedThisSession"] is None

    async with session_factory() as session:
        review_count = await session.scalar(
            select(func.count()).select_from(FlashcardReview).where(
                FlashcardReview.user_id == current_user.id,
                FlashcardReview.card_id == card_id,
            )
        )
        refreshed_user = await session.get(User, current_user.id)
        latest_review = await session.scalar(
            select(FlashcardReview)
            .where(
                FlashcardReview.user_id == current_user.id,
                FlashcardReview.card_id == card_id,
            )
            .order_by(FlashcardReview.reviewed_at.desc())
        )

    assert review_count == 2
    assert refreshed_user is not None
    assert refreshed_user.last_activity_date == date(2026, 3, 27)
    assert latest_review is not None
    assert latest_review.rating == FlashcardReviewRating.EASY
    assert latest_review.interval_days == 20
    assert _coerce_utc(latest_review.next_review_at) == FixedDateTime.now(timezone.utc) + timedelta(days=20)
    assert session_state["reviewsCompleted"] == 2


async def test_review_endpoint_advances_normal_streak_without_touching_recovery_session(
    flashcards_harness: dict[str, object],
) -> None:
    session_factory = flashcards_harness["session_factory"]
    session_state = flashcards_harness["session_state"]
    current_user = flashcards_harness["user"]
    client = flashcards_harness["client"]
    card_id = await _seed_review_card(session_factory, user_id=current_user.id)

    async with session_factory() as session:
        user = await session.get(User, current_user.id)
        assert user is not None
        user.current_streak = 7
        user.longest_streak = 11
        user.last_activity_date = date(2026, 3, 26)
        await session.commit()

    response = await client.post(
        "/api/v1/flashcards/review",
        json={"cardId": str(card_id), "rating": "okay", "elapsedMs": 2100},
    )

    assert response.status_code == 200

    async with session_factory() as session:
        refreshed_user = await session.get(User, current_user.id)

    assert refreshed_user is not None
    assert refreshed_user.current_streak == 8
    assert refreshed_user.longest_streak == 11
    assert refreshed_user.last_activity_date == date(2026, 3, 27)
    assert session_state["reviewsCompleted"] == 2


async def test_review_endpoint_keeps_grace_window_open_until_recovery(
    flashcards_harness: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = flashcards_harness["session_factory"]
    session_state = flashcards_harness["session_state"]
    current_user = flashcards_harness["user"]
    client = flashcards_harness["client"]
    card_id = await _seed_review_card(session_factory, user_id=current_user.id)

    async with session_factory() as session:
        user = await session.get(User, current_user.id)
        assert user is not None
        user.current_streak = 9
        user.longest_streak = 12
        user.last_activity_date = date(2026, 3, 26)
        await session.commit()

    monkeypatch.setattr(flashcards_router, "datetime", GraceWindowDateTime)
    monkeypatch.setattr(fsrs_service, "datetime", GraceWindowDateTime)
    session_state["reviewsCompleted"] = 19

    response = await client.post(
        "/api/v1/flashcards/review",
        json={"cardId": str(card_id), "rating": "hard", "elapsedMs": 3000},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["reviewsCompletedThisSession"] == 20

    async with session_factory() as session:
        refreshed_user = await session.get(User, current_user.id)

    assert refreshed_user is not None
    assert refreshed_user.current_streak == 9
    assert refreshed_user.longest_streak == 12
    assert refreshed_user.last_activity_date == date(2026, 3, 26)
    assert session_state["reviewsCompleted"] == 20
