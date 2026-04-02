from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
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
    TopicProgressStatus,
    User,
    UserTopicProgress,
)


pytestmark = pytest.mark.asyncio


async def _build_session_factory() -> tuple[async_sessionmaker[AsyncSession], object, Path]:
    temp_directory = Path("backend/.tmp-test-db")
    temp_directory.mkdir(exist_ok=True)
    database_path = temp_directory / f"progress-router-{uuid4().hex}.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine, database_path


@pytest_asyncio.fixture
async def progress_harness() -> dict[str, object]:
    session_factory, engine, database_path = await _build_session_factory()
    current_user = User(
        id=uuid4(),
        clerk_id="user_progress_test",
        email="learner@example.com",
        current_streak=7,
        longest_streak=10,
        freeze_tokens_remaining=1,
    )
    topic_one = Topic(
        id=uuid4(),
        title="SQL Basics",
        description="Foundational SQL",
        order_index=1,
        difficulty=TopicDifficulty.BEGINNER,
    )
    topic_two = Topic(
        id=uuid4(),
        title="Window Functions",
        description="Ranking and partitions",
        order_index=2,
        difficulty=TopicDifficulty.INTERMEDIATE,
    )
    topic_three = Topic(
        id=uuid4(),
        title="Query Optimization",
        description="Execution plans",
        order_index=3,
        difficulty=TopicDifficulty.ADVANCED,
    )
    due_card = Flashcard(
        id=uuid4(),
        topic_id=topic_two.id,
        card_type=FlashcardCardType.RECALL,
        difficulty=FlashcardDifficulty.MEDIUM,
        front="What does ROW_NUMBER() do?",
        back="It numbers rows in a partition.",
    )
    future_card = Flashcard(
        id=uuid4(),
        topic_id=topic_three.id,
        card_type=FlashcardCardType.RECALL,
        difficulty=FlashcardDifficulty.HARD,
        front="Why inspect an execution plan?",
        back="To see how the database will execute the query.",
    )

    async with session_factory() as session:
        session.add_all([current_user, topic_one, topic_two, topic_three, due_card, future_card])
        session.add_all(
            [
                UserTopicProgress(
                    user_id=current_user.id,
                    topic_id=topic_one.id,
                    status=TopicProgressStatus.COMPLETED,
                    mastery_score=0.95,
                    last_studied_at=datetime(2026, 3, 25, 8, 0, tzinfo=timezone.utc),
                ),
                UserTopicProgress(
                    user_id=current_user.id,
                    topic_id=topic_two.id,
                    status=TopicProgressStatus.AVAILABLE,
                    mastery_score=0.61,
                    last_studied_at=datetime(2026, 3, 26, 8, 0, tzinfo=timezone.utc),
                ),
                UserTopicProgress(
                    user_id=current_user.id,
                    topic_id=topic_three.id,
                    status=TopicProgressStatus.LOCKED,
                    mastery_score=0.0,
                ),
                FlashcardReview(
                    user_id=current_user.id,
                    card_id=due_card.id,
                    rating=FlashcardReviewRating.OKAY,
                    interval_days=3,
                    stability=2.5,
                    difficulty_fsrs=2.0,
                    reviewed_at=datetime(2026, 3, 25, 9, 0, tzinfo=timezone.utc),
                    next_review_at=datetime(2026, 3, 27, 9, 0, tzinfo=timezone.utc),
                ),
                FlashcardReview(
                    user_id=current_user.id,
                    card_id=future_card.id,
                    rating=FlashcardReviewRating.EASY,
                    interval_days=7,
                    stability=4.5,
                    difficulty_fsrs=1.8,
                    reviewed_at=datetime(2026, 3, 26, 9, 0, tzinfo=timezone.utc),
                    next_review_at=datetime(2026, 4, 5, 9, 0, tzinfo=timezone.utc),
                ),
            ]
        )
        await session.commit()

    async def override_get_db_session():
        async with session_factory() as session:
            yield session

    async def override_get_current_user() -> User:
        return current_user

    app = create_app()
    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield {
            "client": client,
            "topic_one_id": topic_one.id,
            "topic_two_id": topic_two.id,
            "topic_three_id": topic_three.id,
        }

    await engine.dispose()
    database_path.unlink(missing_ok=True)


async def test_progress_path_returns_ordered_topics_with_current_topic(progress_harness: dict[str, object]) -> None:
    client = progress_harness["client"]

    response = await client.get("/api/v1/progress/path")

    assert response.status_code == 200
    payload = response.json()
    assert [topic["status"] for topic in payload["topics"]] == ["completed", "available", "locked"]
    assert payload["currentTopicId"] == str(progress_harness["topic_two_id"])
    assert [topic["orderIndex"] for topic in payload["topics"]] == [1, 2, 3]


async def test_progress_stats_returns_streak_due_count_and_mastery(progress_harness: dict[str, object]) -> None:
    client = progress_harness["client"]

    response = await client.get("/api/v1/progress/stats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["currentStreak"] == 7
    assert payload["longestStreak"] == 10
    assert payload["cardsDueToday"] == 1
    assert payload["topics"][0]["topicId"] == str(progress_harness["topic_one_id"])
    assert payload["topics"][1]["masteryScore"] == pytest.approx(0.61)
    assert payload["topics"][2]["status"] == "locked"
