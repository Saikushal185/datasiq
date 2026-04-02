from __future__ import annotations

from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("CLERK_SECRET_KEY", "sk_test_123")

from backend.app.core.auth import get_current_user
from backend.app.core.database import get_db_session
from backend.app.main import create_app
from backend.app.models.db import (
    Base,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    QuizQuestionType,
    Topic,
    TopicDifficulty,
    TopicProgressStatus,
    User,
    UserTopicProgress,
)
from backend.app.routers import quiz as quiz_router


pytestmark = pytest.mark.asyncio


class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz: timezone | None = None) -> datetime:
        return cls(2026, 3, 27, 10, 30, 0, tzinfo=tz or timezone.utc)


def _encoded_answer(*, correct_option_id: str, options: list[tuple[str, str]]) -> str:
    return json.dumps(
        {
            "correctOptionId": correct_option_id,
            "options": [{"id": option_id, "text": text} for option_id, text in options],
        }
    )


async def _build_session_factory() -> tuple[async_sessionmaker[AsyncSession], object, Path]:
    temp_directory = Path("backend/.tmp-test-db")
    temp_directory.mkdir(exist_ok=True)
    database_path = temp_directory / f"quiz-router-{uuid4().hex}.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine, database_path


@pytest_asyncio.fixture
async def quiz_harness() -> dict[str, object]:
    session_factory, engine, database_path = await _build_session_factory()
    current_user = User(
        id=uuid4(),
        clerk_id="user_quiz_test",
        email="learner@example.com",
        current_streak=4,
        longest_streak=9,
        freeze_tokens_remaining=1,
    )
    current_topic = Topic(
        id=uuid4(),
        title="SQL Basics",
        description="Foundational SQL prompts",
        order_index=1,
        difficulty=TopicDifficulty.BEGINNER,
    )
    next_topic = Topic(
        id=uuid4(),
        title="Window Functions",
        description="Partitions and ranking",
        order_index=2,
        difficulty=TopicDifficulty.INTERMEDIATE,
    )
    quiz = Quiz(
        id=uuid4(),
        topic_id=current_topic.id,
        title="SQL Basics Checkpoint",
        pass_threshold=0.7,
    )
    question_joins = QuizQuestion(
        id=uuid4(),
        quiz_id=quiz.id,
        question_type=QuizQuestionType.MCQ,
        question_text="Which join returns only rows with matches on both tables?",
        correct_answer=_encoded_answer(
            correct_option_id="option-inner-join",
            options=[
                ("option-inner-join", "INNER JOIN"),
                ("option-left-join", "LEFT JOIN"),
                ("option-right-join", "RIGHT JOIN"),
                ("option-cross-join", "CROSS JOIN"),
            ],
        ),
        explanation="INNER JOIN keeps only matching rows from both tables.",
    )
    question_null = QuizQuestion(
        id=uuid4(),
        quiz_id=quiz.id,
        question_type=QuizQuestionType.CODE_OUTPUT,
        question_text="SELECT * FROM users WHERE deleted_at ____;",
        correct_answer=_encoded_answer(
            correct_option_id="option-is-null",
            options=[
                ("option-equals-null", "= NULL"),
                ("option-is-null", "IS NULL"),
                ("option-not-null", "NOT NULL"),
                ("option-bang-null", "!= NULL"),
            ],
        ),
        explanation="Use IS NULL because NULL is not comparable with = in SQL.",
    )

    async with session_factory() as session:
        session.add_all([current_user, current_topic, next_topic, quiz, question_joins, question_null])
        session.add_all(
            [
                UserTopicProgress(
                    user_id=current_user.id,
                    topic_id=current_topic.id,
                    status=TopicProgressStatus.IN_PROGRESS,
                    mastery_score=0.4,
                ),
                UserTopicProgress(
                    user_id=current_user.id,
                    topic_id=next_topic.id,
                    status=TopicProgressStatus.LOCKED,
                    mastery_score=0.0,
                ),
                QuizAttempt(
                    user_id=current_user.id,
                    quiz_id=quiz.id,
                    score=0.55,
                    passed=False,
                    attempted_at=datetime(2026, 3, 24, 10, 0, tzinfo=timezone.utc),
                ),
                QuizAttempt(
                    user_id=current_user.id,
                    quiz_id=quiz.id,
                    score=0.7,
                    passed=True,
                    attempted_at=datetime(2026, 3, 25, 10, 0, tzinfo=timezone.utc),
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
            "session_factory": session_factory,
            "user": current_user,
            "quiz_id": quiz.id,
            "topic_id": current_topic.id,
            "next_topic_id": next_topic.id,
            "question_joins_id": question_joins.id,
            "question_null_id": question_null.id,
        }

    await engine.dispose()
    database_path.unlink(missing_ok=True)


async def test_get_quiz_returns_db_backed_questions_with_options(quiz_harness: dict[str, object]) -> None:
    client = quiz_harness["client"]
    topic_id = quiz_harness["topic_id"]

    response = await client.get(f"/api/v1/quiz/{topic_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(quiz_harness["quiz_id"])
    assert payload["topic"]["id"] == str(topic_id)
    question_types = {question["questionType"] for question in payload["questions"]}
    assert question_types == {"mcq", "code_output"}
    assert len(payload["questions"][0]["options"]) == 4
    assert "correctOptionId" not in payload["questions"][0]


async def test_submit_quiz_unlocks_next_topic_and_updates_mastery(quiz_harness: dict[str, object]) -> None:
    client = quiz_harness["client"]
    session_factory = quiz_harness["session_factory"]
    current_user = quiz_harness["user"]
    quiz_id = quiz_harness["quiz_id"]
    topic_id = quiz_harness["topic_id"]
    next_topic_id = quiz_harness["next_topic_id"]
    payload = {
        "answers": {
            str(quiz_harness["question_joins_id"]): "option-inner-join",
            str(quiz_harness["question_null_id"]): "option-is-null",
        }
    }

    response = await client.post(f"/api/v1/quiz/{quiz_id}/submit", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["quizId"] == str(quiz_id)
    assert body["passed"] is True
    assert body["score"] == pytest.approx(1.0)
    assert body["recommendedAction"] == "unlock_next_topic"

    async with session_factory() as session:
        attempts = list(
            await session.scalars(
                select(QuizAttempt)
                .where(QuizAttempt.user_id == current_user.id, QuizAttempt.quiz_id == quiz_id)
                .order_by(QuizAttempt.attempted_at)
            )
        )
        current_progress = await session.scalar(
            select(UserTopicProgress).where(
                UserTopicProgress.user_id == current_user.id,
                UserTopicProgress.topic_id == topic_id,
            )
        )
        next_progress = await session.scalar(
            select(UserTopicProgress).where(
                UserTopicProgress.user_id == current_user.id,
                UserTopicProgress.topic_id == next_topic_id,
            )
        )

    assert len(attempts) == 3
    assert attempts[-1].passed is True
    assert current_progress is not None
    assert current_progress.mastery_score == pytest.approx(0.82)
    assert current_progress.status == TopicProgressStatus.IN_PROGRESS
    assert next_progress is not None
    assert next_progress.status == TopicProgressStatus.AVAILABLE


async def test_submit_quiz_regresses_topic_on_low_score(quiz_harness: dict[str, object]) -> None:
    client = quiz_harness["client"]
    session_factory = quiz_harness["session_factory"]
    current_user = quiz_harness["user"]
    quiz_id = quiz_harness["quiz_id"]
    topic_id = quiz_harness["topic_id"]
    payload = {
        "answers": {
            str(quiz_harness["question_joins_id"]): "option-left-join",
            str(quiz_harness["question_null_id"]): "option-equals-null",
        }
    }

    response = await client.post(f"/api/v1/quiz/{quiz_id}/submit", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["passed"] is False
    assert body["recommendedAction"] == "review_flashcards"

    async with session_factory() as session:
        current_progress = await session.scalar(
            select(UserTopicProgress).where(
                UserTopicProgress.user_id == current_user.id,
                UserTopicProgress.topic_id == topic_id,
            )
        )

    assert current_progress is not None
    assert current_progress.status == TopicProgressStatus.IN_PROGRESS


async def test_submit_quiz_advances_normal_streak_and_last_activity(
    quiz_harness: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = quiz_harness["client"]
    session_factory = quiz_harness["session_factory"]
    current_user = quiz_harness["user"]
    quiz_id = quiz_harness["quiz_id"]
    topic_id = quiz_harness["topic_id"]
    payload = {
        "answers": {
            str(quiz_harness["question_joins_id"]): "option-inner-join",
            str(quiz_harness["question_null_id"]): "option-is-null",
        }
    }

    monkeypatch.setattr(quiz_router, "datetime", FixedDateTime)

    async with session_factory() as session:
        user = await session.get(User, current_user.id)
        assert user is not None
        user.current_streak = 4
        user.longest_streak = 6
        user.last_activity_date = date(2026, 3, 26)
        await session.commit()

    response = await client.post(f"/api/v1/quiz/{quiz_id}/submit", json=payload)

    assert response.status_code == 200

    async with session_factory() as session:
        refreshed_user = await session.get(User, current_user.id)
        current_progress = await session.scalar(
            select(UserTopicProgress).where(
                UserTopicProgress.user_id == current_user.id,
                UserTopicProgress.topic_id == topic_id,
            )
        )

    assert refreshed_user is not None
    assert refreshed_user.current_streak == 5
    assert refreshed_user.longest_streak == 6
    assert refreshed_user.last_activity_date == date(2026, 3, 27)
    assert current_progress is not None
    assert current_progress.last_studied_at == datetime(2026, 3, 27, 10, 30)
