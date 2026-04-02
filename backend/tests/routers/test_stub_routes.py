from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.core.auth import get_current_user
from backend.app.core.config import get_settings
from backend.app.core.database import get_db_session
from backend.app.main import create_app
from backend.app.models.db import (
    Base,
    Flashcard,
    FlashcardCardType,
    FlashcardDifficulty,
    FlashcardOption,
    FlashcardReview,
    FlashcardReviewRating,
    Quiz,
    QuizQuestion,
    QuizQuestionType,
    Topic,
    TopicDifficulty,
    TopicProgressStatus,
    User,
    UserTopicProgress,
)
from backend.app.routers import flashcards as flashcards_router
from backend.app.routers import progress as progress_router
from backend.app.routers import quiz as quiz_router
from backend.app.routers import streak as streak_router
from backend.app.services import fsrs_service
from backend.app.services.ai_service import (
    GeneratedFlashcard,
    GeneratedFlashcardBatch,
    GeneratedFlashcardOption,
)


async def _seed_curriculum_topic(session_factory: async_sessionmaker[AsyncSession]) -> dict[str, object]:
    user = User(id=uuid4(), clerk_id="user_curriculum_admin", email="admin@example.com")
    topic = Topic(
        id=uuid4(),
        title="SQL Basics",
        description="Introductory SQL prompts",
        order_index=1,
        difficulty=TopicDifficulty.BEGINNER,
    )

    async with session_factory() as session:
        session.add_all([user, topic])
        await session.commit()

    return {"user": user, "topic_id": topic.id}


os.environ.setdefault("CLERK_SECRET_KEY", "sk_test_123")


def _build_user() -> User:
    return User(clerk_id="user_stub_123", email="learner@example.com")


def _build_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = _build_user
    return TestClient(app)


class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz: timezone | None = None) -> datetime:
        return cls(2026, 3, 28, 12, 0, 0, tzinfo=tz or timezone.utc)


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
    database_path = temp_directory / f"stub-routes-{uuid4().hex}.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine, database_path


async def _seed_stub_contract_data(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, object]:
    user = User(
        id=uuid4(),
        clerk_id="user_stub_contracts",
        email="learner@example.com",
        current_streak=12,
        longest_streak=21,
        freeze_tokens_remaining=2,
        last_activity_date=date(2026, 3, 26),
    )
    topic = Topic(
        id=uuid4(),
        title="SQL Basics",
        description="Introductory SQL prompts",
        order_index=1,
        difficulty=TopicDifficulty.BEGINNER,
    )
    topic_two = Topic(
        id=uuid4(),
        title="Window Functions",
        description="Partitions and ranking",
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
    review_card = Flashcard(
        id=uuid4(),
        topic_id=topic.id,
        card_type=FlashcardCardType.RECALL,
        difficulty=FlashcardDifficulty.EASY,
        front="What clause filters aggregated rows?",
        back="HAVING filters aggregated rows.",
    )
    due_card = Flashcard(
        id=uuid4(),
        topic_id=topic.id,
        card_type=FlashcardCardType.RECALL,
        difficulty=FlashcardDifficulty.MEDIUM,
        front="What does COUNT(*) return?",
        back="It returns the number of rows.",
    )
    blitz_cards: list[Flashcard] = []
    flashcard_options: list[FlashcardOption] = []
    for index in range(15):
        card = Flashcard(
            id=uuid4(),
            topic_id=topic.id,
            card_type=FlashcardCardType.MCQ,
            difficulty=FlashcardDifficulty.MEDIUM,
            front=f"MCQ prompt #{index + 1}",
            back="INNER JOIN returns matching rows.",
        )
        blitz_cards.append(card)
        flashcard_options.extend(
            [
                FlashcardOption(card_id=card.id, option_text="INNER JOIN", is_correct=True),
                FlashcardOption(card_id=card.id, option_text="LEFT JOIN", is_correct=False),
                FlashcardOption(card_id=card.id, option_text="RIGHT JOIN", is_correct=False),
                FlashcardOption(card_id=card.id, option_text="CROSS JOIN", is_correct=False),
            ]
        )
    quiz = Quiz(
        id=uuid4(),
        topic_id=topic.id,
        title="SQL Basics Checkpoint",
        pass_threshold=0.7,
    )
    quiz_question_joins = QuizQuestion(
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
    quiz_question_null = QuizQuestion(
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
        session.add_all(
            [
                user,
                topic,
                topic_two,
                topic_three,
                review_card,
                due_card,
                *blitz_cards,
                *flashcard_options,
                quiz,
                quiz_question_joins,
                quiz_question_null,
            ]
        )
        session.add(
            UserTopicProgress(
                user_id=user.id,
                topic_id=topic.id,
                status=TopicProgressStatus.COMPLETED,
                mastery_score=0.91,
            )
        )
        session.add(
            UserTopicProgress(
                user_id=user.id,
                topic_id=topic_two.id,
                status=TopicProgressStatus.LOCKED,
                mastery_score=0.0,
            )
        )
        session.add(
            UserTopicProgress(
                user_id=user.id,
                topic_id=topic_three.id,
                status=TopicProgressStatus.LOCKED,
                mastery_score=0.0,
            )
        )
        session.add(
            FlashcardReview(
                user_id=user.id,
                card_id=review_card.id,
                rating=FlashcardReviewRating.OKAY,
                interval_days=2,
                stability=2.0,
                difficulty_fsrs=2.3,
                reviewed_at=FixedDateTime.now(timezone.utc) - timedelta(days=2),
                next_review_at=FixedDateTime.now(timezone.utc) - timedelta(hours=1),
            )
        )
        await session.commit()

    return {
        "user": user,
        "topic_id": str(topic.id),
        "topic_two_id": str(topic_two.id),
        "review_card_id": str(review_card.id),
        "quiz_id": str(quiz.id),
        "quiz_question_joins_id": str(quiz_question_joins.id),
        "quiz_question_null_id": str(quiz_question_null.id),
    }


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/api/v1/flashcards/due", None),
        ("GET", "/api/v1/flashcards/blitz", None),
        ("GET", "/api/v1/flashcards/boss/topic-sql-basics", None),
        (
            "POST",
            "/api/v1/flashcards/review",
            {"cardId": "card-recall-1", "rating": "easy", "elapsedMs": 4800},
        ),
        ("GET", "/api/v1/quiz/topic-sql-basics", None),
        (
            "POST",
            "/api/v1/quiz/quiz-sql-basics-1/submit",
            {"answers": {"question-joins": "option-inner-join", "question-null": "option-is-null"}},
        ),
        ("GET", "/api/v1/progress/path", None),
        ("GET", "/api/v1/progress/stats", None),
        ("GET", "/api/v1/streak", None),
        ("POST", "/api/v1/streak/freeze", None),
        ("POST", "/api/v1/streak/recover", {"reviewsCompleted": 20}),
    ],
)
def test_user_stub_endpoints_require_auth(
    method: str,
    path: str,
    payload: dict[str, Any] | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_123")
    client = TestClient(create_app())

    response = client.request(method, path, json=payload)

    assert response.status_code == 401


def test_flashcards_quiz_progress_and_streak_stub_contracts(monkeypatch: pytest.MonkeyPatch) -> None:
    session_factory, engine, database_path = asyncio.run(_build_session_factory())
    seeded = asyncio.run(_seed_stub_contract_data(session_factory))
    session_state = {"reviewsCompleted": 8}

    async def override_get_db_session():
        async with session_factory() as session:
            yield session

    async def override_get_current_user() -> User:
        return seeded["user"]

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

    monkeypatch.setattr(fsrs_service, "datetime", FixedDateTime)
    monkeypatch.setattr(flashcards_router, "datetime", FixedDateTime)
    monkeypatch.setattr(progress_router, "datetime", FixedDateTime)
    monkeypatch.setattr(quiz_router, "datetime", FixedDateTime)
    monkeypatch.setattr(streak_router, "datetime", FixedDateTime)
    monkeypatch.setattr(flashcards_router, "get_ephemeral_json", fake_get_ephemeral_json, raising=False)
    monkeypatch.setattr(flashcards_router, "set_ephemeral_json", fake_set_ephemeral_json, raising=False)
    monkeypatch.setattr(streak_router, "get_ephemeral_json", fake_get_ephemeral_json, raising=False)
    monkeypatch.setattr(streak_router, "set_ephemeral_json", fake_set_ephemeral_json, raising=False)

    app = create_app()
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db_session] = override_get_db_session
    client = TestClient(app)

    due_response = client.get("/api/v1/flashcards/due")
    assert due_response.status_code == 200
    due_payload = due_response.json()
    assert due_payload["totalDue"] == len(due_payload["cards"])
    assert due_payload["cards"][0]["topicId"] == seeded["topic_id"]
    assert due_payload["cards"][0]["cardType"] == "recall"
    assert due_payload["cards"][0]["reviewState"]["ratingOptions"] == ["forgot", "hard", "okay", "easy"]

    blitz_response = client.get("/api/v1/flashcards/blitz")
    assert blitz_response.status_code == 200
    blitz_payload = blitz_response.json()
    assert blitz_payload["durationSeconds"] == 60
    assert len(blitz_payload["cards"]) == 10
    assert blitz_payload["cards"][0]["cardType"] == "mcq"
    assert len(blitz_payload["cards"][0]["options"]) == 4
    assert "correctOptionId" not in blitz_payload["cards"][0]

    boss_response = client.get(f"/api/v1/flashcards/boss/{seeded['topic_id']}")
    assert boss_response.status_code == 200
    boss_payload = boss_response.json()
    assert boss_payload["passThreshold"] == 0.8
    assert boss_payload["topic"]["id"] == seeded["topic_id"]
    assert len(boss_payload["cards"]) == 15
    assert "correctOptionId" not in boss_payload["cards"][0]

    review_response = client.post(
        "/api/v1/flashcards/review",
        json={"cardId": seeded["review_card_id"], "rating": "easy", "elapsedMs": 4800},
    )
    assert review_response.status_code == 200
    review_payload = review_response.json()
    assert review_payload["cardId"] == seeded["review_card_id"]
    assert review_payload["rating"] == "easy"
    assert review_payload["intervalDays"] > 0
    assert review_payload["celebrate"] is True

    quiz_response = client.get(f"/api/v1/quiz/{seeded['topic_id']}")
    assert quiz_response.status_code == 200
    quiz_payload = quiz_response.json()
    assert quiz_payload["id"] == seeded["quiz_id"]
    assert quiz_payload["topic"]["id"] == seeded["topic_id"]
    assert {question["questionType"] for question in quiz_payload["questions"]} == {"mcq", "code_output"}

    submit_response = client.post(
        f"/api/v1/quiz/{seeded['quiz_id']}/submit",
        json={
            "answers": {
                seeded["quiz_question_joins_id"]: "option-inner-join",
                seeded["quiz_question_null_id"]: "option-is-null",
            }
        },
    )
    assert submit_response.status_code == 200
    submit_payload = submit_response.json()
    assert submit_payload["quizId"] == seeded["quiz_id"]
    assert submit_payload["passed"] is True
    assert submit_payload["breakdown"][0]["isCorrect"] is True
    assert submit_payload["recommendedAction"] == "unlock_next_topic"

    progress_path_response = client.get("/api/v1/progress/path")
    assert progress_path_response.status_code == 200
    progress_path_payload = progress_path_response.json()
    assert progress_path_payload["topics"][0]["status"] == "completed"
    assert progress_path_payload["topics"][1]["status"] == "available"
    assert progress_path_payload["topics"][2]["status"] == "locked"
    assert progress_path_payload["currentTopicId"] == seeded["topic_two_id"]

    progress_stats_response = client.get("/api/v1/progress/stats")
    assert progress_stats_response.status_code == 200
    progress_stats_payload = progress_stats_response.json()
    assert progress_stats_payload["currentStreak"] == 12
    assert progress_stats_payload["cardsDueToday"] == 16
    assert progress_stats_payload["topics"][1]["status"] == "available"

    streak_response = client.get("/api/v1/streak")
    assert streak_response.status_code == 200
    streak_payload = streak_response.json()
    assert streak_payload["currentStreak"] == 12
    assert streak_payload["rageModal"]["show"] is False
    assert len(streak_payload["weeklyBar"]) == 5

    freeze_response = client.post("/api/v1/streak/freeze")
    assert freeze_response.status_code == 200
    freeze_payload = freeze_response.json()
    assert freeze_payload["action"] == "freeze"
    assert freeze_payload["streak"]["currentStreak"] == 13

    client.close()
    asyncio.run(engine.dispose())
    database_path.unlink(missing_ok=True)

    recover_session_factory, recover_engine, recover_database_path = asyncio.run(_build_session_factory())
    recover_seeded = asyncio.run(_seed_stub_contract_data(recover_session_factory))
    recover_session_state = {"reviewsCompleted": 20}

    async def override_recover_db_session():
        async with recover_session_factory() as session:
            yield session

    async def override_recover_current_user() -> User:
        return recover_seeded["user"]

    async def fake_recover_get_ephemeral_json(_key: str, *, settings: object | None = None) -> dict[str, int]:
        return dict(recover_session_state)

    async def fake_recover_set_ephemeral_json(
        _key: str,
        value: object,
        *,
        ttl_seconds: int,
        settings: object | None = None,
    ) -> None:
        assert ttl_seconds > 0
        if isinstance(value, dict):
            recover_session_state.clear()
            recover_session_state.update(value)

    monkeypatch.setattr(streak_router, "get_ephemeral_json", fake_recover_get_ephemeral_json, raising=False)
    monkeypatch.setattr(streak_router, "set_ephemeral_json", fake_recover_set_ephemeral_json, raising=False)

    recover_app = create_app()
    recover_app.dependency_overrides[get_current_user] = override_recover_current_user
    recover_app.dependency_overrides[get_db_session] = override_recover_db_session
    recover_client = TestClient(recover_app)

    recover_response = recover_client.post("/api/v1/streak/recover", json={"reviewsCompleted": 20})
    assert recover_response.status_code == 200
    recover_payload = recover_response.json()
    assert recover_payload["action"] == "recover"
    assert recover_payload["streak"]["recovery"]["eligible"] is True
    assert recover_payload["streak"]["recovery"]["reviewsRemaining"] == 0

    recover_client.close()
    asyncio.run(recover_engine.dispose())
    recover_database_path.unlink(missing_ok=True)


@pytest.mark.parametrize(
    "payload",
    [
        {"answers": {"question-joins": "option-inner-join"}},
        {"answers": {"question-joins": "option-inner-join", "question-null": ""}},
    ],
)
def test_quiz_submit_rejects_incomplete_submissions(payload: dict[str, Any]) -> None:
    client = _build_client()

    response = client.post("/api/v1/quiz/quiz-sql-basics-1/submit", json=payload)

    assert response.status_code == 422


def test_curriculum_route_generates_and_persists_flashcards(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_SECRET", "admin-secret")
    get_settings.cache_clear()

    session_factory, engine, database_path = asyncio.run(_build_session_factory())
    seeded = asyncio.run(_seed_curriculum_topic(session_factory))

    async def override_get_db_session():
        async with session_factory() as session:
            yield session

    async def override_get_current_user() -> User:
        return seeded["user"]

    async def fake_generate_topic_flashcards(
        *,
        topic: Topic,
        card_count: int,
        notes: str | None,
        settings: object | None,
    ) -> GeneratedFlashcardBatch:
        del settings
        assert card_count == 3
        assert notes == "Focus on joins"
        assert topic.id == seeded["topic_id"]
        return GeneratedFlashcardBatch(
            topic_id=topic.id,
            topic_title=topic.title,
            requested_count=3,
            cards=[
                GeneratedFlashcard(
                    card_type="mcq",
                    difficulty="easy",
                    front="Which clause filters grouped rows?",
                    back="HAVING filters grouped rows.",
                    options=[
                        GeneratedFlashcardOption(text="WHERE", is_correct=False),
                        GeneratedFlashcardOption(text="HAVING", is_correct=True),
                        GeneratedFlashcardOption(text="ORDER BY", is_correct=False),
                        GeneratedFlashcardOption(text="GROUP BY", is_correct=False),
                    ],
                ),
                GeneratedFlashcard(
                    card_type="recall",
                    difficulty="medium",
                    front="What does COUNT(*) return?",
                    back="The number of rows.",
                ),
                GeneratedFlashcard(
                    card_type="fill_blank",
                    difficulty="hard",
                    front="SELECT * FROM users WHERE email ____ NULL;",
                    back="Use IS NOT NULL to exclude NULL values.",
                ),
            ],
        )

    monkeypatch.setattr("backend.app.routers.curriculum.generate_topic_flashcards", fake_generate_topic_flashcards)

    app = create_app()
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db_session] = override_get_db_session
    client = TestClient(app)

    forbidden_response = client.post(
        "/api/v1/curriculum/generate-cards",
        json={"topicId": str(seeded["topic_id"]), "cardCount": 3, "notes": "Focus on joins"},
    )
    assert forbidden_response.status_code == 403

    response = client.post(
        "/api/v1/curriculum/generate-cards",
        json={"topicId": str(seeded["topic_id"]), "cardCount": 3, "notes": "Focus on joins"},
        headers={"x-admin-secret": "admin-secret"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["topicId"] == str(seeded["topic_id"])
    assert payload["generatedCards"] == 3
    assert payload["generatedOptions"] == 4

    async def _assert_db_state() -> None:
        async with session_factory() as session:
            card_count = await session.scalar(select(func.count()).select_from(Flashcard).where(Flashcard.topic_id == seeded["topic_id"]))
            option_count = await session.scalar(select(func.count()).select_from(FlashcardOption).join(Flashcard).where(Flashcard.topic_id == seeded["topic_id"]))
            persisted_topic = await session.get(Topic, seeded["topic_id"])

        assert persisted_topic is not None
        assert card_count == 3
        assert option_count == 4

    asyncio.run(_assert_db_state())

    client.close()
    asyncio.run(engine.dispose())
    database_path.unlink(missing_ok=True)
    get_settings.cache_clear()
