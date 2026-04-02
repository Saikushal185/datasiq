from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from backend.app.core.config import Settings, get_settings
from backend.app.core.database import get_engine, get_session_maker
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


def _encoded_answer(*, correct_option_id: str, options: list[tuple[str, str]]) -> str:
    return json.dumps(
        {
            "correctOptionId": correct_option_id,
            "options": [{"id": option_id, "text": text} for option_id, text in options],
        }
    )


def _sqlite_path_from_url(database_url: str) -> Path | None:
    prefix = "sqlite+aiosqlite:///"
    if not database_url.startswith(prefix):
        return None
    return Path(database_url.removeprefix(prefix))


async def ensure_local_dev_environment(
    *,
    settings: Settings | None = None,
    engine: AsyncEngine | None = None,
    session_maker: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    runtime_settings = settings or get_settings()
    if not runtime_settings.dev_seed_data:
        return

    sqlite_path = _sqlite_path_from_url(runtime_settings.database_url)
    if sqlite_path is not None:
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    active_engine = engine or get_engine()
    active_session_maker = session_maker or get_session_maker()

    async with active_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    await seed_demo_data(active_session_maker, settings=runtime_settings)


async def seed_demo_data(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    settings: Settings,
) -> None:
    async with session_maker() as session:
        user = await session.scalar(select(User).where(User.clerk_id == settings.dev_auth_clerk_id))
        if user is None:
            user = User(
                id=uuid4(),
                clerk_id=settings.dev_auth_clerk_id,
                email=settings.dev_auth_email,
                current_streak=12,
                longest_streak=21,
                freeze_tokens_remaining=2,
                last_activity_date=date.today() - timedelta(days=1),
            )
            session.add(user)
            await session.flush()
        elif user.email != settings.dev_auth_email:
            user.email = settings.dev_auth_email

        topic_count = await session.scalar(select(func.count()).select_from(Topic))
        progress_count = await session.scalar(
            select(func.count()).select_from(UserTopicProgress).where(UserTopicProgress.user_id == user.id)
        )
        if (topic_count or 0) > 0 and (progress_count or 0) > 0:
            await session.commit()
            return

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
        reviewed_at = datetime.now(timezone.utc) - timedelta(days=2)
        next_review_at = datetime.now(timezone.utc) - timedelta(hours=1)

        session.add_all(
            [
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
        session.add_all(
            [
                UserTopicProgress(
                    user_id=user.id,
                    topic_id=topic.id,
                    status=TopicProgressStatus.COMPLETED,
                    mastery_score=0.91,
                ),
                UserTopicProgress(
                    user_id=user.id,
                    topic_id=topic_two.id,
                    status=TopicProgressStatus.AVAILABLE,
                    mastery_score=0.24,
                ),
                UserTopicProgress(
                    user_id=user.id,
                    topic_id=topic_three.id,
                    status=TopicProgressStatus.LOCKED,
                    mastery_score=0.0,
                ),
                FlashcardReview(
                    user_id=user.id,
                    card_id=review_card.id,
                    rating=FlashcardReviewRating.OKAY,
                    interval_days=2,
                    stability=2.0,
                    difficulty_fsrs=2.3,
                    reviewed_at=reviewed_at,
                    next_review_at=next_review_at,
                ),
            ]
        )
        await session.commit()
