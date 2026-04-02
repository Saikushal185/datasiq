from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.auth import get_current_user
from backend.app.core.database import get_db_session
from backend.app.models.db import Flashcard, FlashcardReview, Topic, TopicProgressStatus, User, UserTopicProgress
from backend.app.schemas.progress import (
    ProgressPathResponse,
    ProgressStatsResponse,
    ProgressStatsTopicResponse,
    ProgressTopicResponse,
)


router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/path", response_model=ProgressPathResponse)
async def get_progress_path(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProgressPathResponse:
    topics, progress_by_topic_id = await _load_topics_with_progress(session, user_id=current_user.id)
    path_topics = [
        ProgressTopicResponse(
            id=str(topic.id),
            title=topic.title,
            orderIndex=topic.order_index,
            difficulty=topic.difficulty,
            status=progress_by_topic_id.get(topic.id, _default_progress_state()).status,
            masteryScore=progress_by_topic_id.get(topic.id, _default_progress_state()).mastery_score,
            lastStudiedAt=progress_by_topic_id.get(topic.id, _default_progress_state()).last_studied_at,
        )
        for topic in topics
    ]
    current_topic = next(
        (topic for topic in path_topics if topic.status in {TopicProgressStatus.AVAILABLE, TopicProgressStatus.IN_PROGRESS}),
        None,
    )
    return ProgressPathResponse(
        currentTopicId=current_topic.id if current_topic is not None else None,
        topics=path_topics,
    )


@router.get("/stats", response_model=ProgressStatsResponse)
async def get_progress_stats(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProgressStatsResponse:
    topics, progress_by_topic_id = await _load_topics_with_progress(session, user_id=current_user.id)
    cards_due_today = await _count_due_cards(session, user_id=current_user.id, now_utc=datetime.now(timezone.utc))
    return ProgressStatsResponse(
        currentStreak=current_user.current_streak,
        longestStreak=current_user.longest_streak,
        cardsDueToday=cards_due_today,
        topics=[
            ProgressStatsTopicResponse(
                topicId=str(topic.id),
                title=topic.title,
                masteryScore=progress_by_topic_id.get(topic.id, _default_progress_state()).mastery_score,
                status=progress_by_topic_id.get(topic.id, _default_progress_state()).status,
            )
            for topic in topics
        ],
    )


async def _load_topics_with_progress(
    session: AsyncSession,
    *,
    user_id: object,
) -> tuple[list[Topic], dict[object, UserTopicProgress]]:
    topics = list(await session.scalars(select(Topic).order_by(Topic.order_index)))
    progress_entries = list(
        await session.scalars(select(UserTopicProgress).where(UserTopicProgress.user_id == user_id))
    )
    return topics, {entry.topic_id: entry for entry in progress_entries}


async def _count_due_cards(session: AsyncSession, *, user_id: object, now_utc: datetime) -> int:
    cards = list(
        await session.scalars(
            select(Flashcard).options(selectinload(Flashcard.reviews))
        )
    )
    total_due = 0
    for card in cards:
        latest_review = _latest_review_for_user(card.reviews, user_id=user_id)
        if latest_review is None or _coerce_utc(latest_review.next_review_at) <= now_utc:
            total_due += 1
    return total_due


def _latest_review_for_user(reviews: list[FlashcardReview], *, user_id: object) -> FlashcardReview | None:
    user_reviews = [review for review in reviews if review.user_id == user_id]
    if not user_reviews:
        return None
    return max(user_reviews, key=lambda review: _coerce_utc(review.reviewed_at))


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _default_progress_state() -> UserTopicProgress:
    return UserTopicProgress(
        user_id=UUID(int=0),
        topic_id=UUID(int=0),
        status=TopicProgressStatus.LOCKED,
        mastery_score=0.0,
    )
