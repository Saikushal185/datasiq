from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from backend.app.core.auth import get_current_user
from backend.app.core.database import get_db_session
from backend.app.core.redis import UpstashRedisConfigurationError, build_session_key, get_ephemeral_json, set_ephemeral_json
from backend.app.models.db import (
    Flashcard,
    FlashcardCardType,
    FlashcardDifficulty,
    FlashcardOption,
    FlashcardReview,
    FlashcardReviewRating,
    Topic,
    TopicProgressStatus,
    User,
    UserTopicProgress,
)
from backend.app.schemas.flashcards import (
    FlashcardCardResponse,
    FlashcardOptionResponse,
    FlashcardReviewRequest,
    FlashcardReviewResponse,
    FlashcardReviewStateResponse,
    FlashcardTopicSummaryResponse,
    FlashcardsBlitzResponse,
    FlashcardsBossResponse,
    FlashcardsDueResponse,
)
from backend.app.services import fsrs_service
from backend.app.services.streak_service import apply_study_activity, evaluate_streak


router = APIRouter(prefix="/flashcards", tags=["flashcards"])
DEFAULT_INITIAL_INTERVAL_DAYS = 1
DEFAULT_INITIAL_STABILITY = 2.5
DEFAULT_INITIAL_DIFFICULTY = 2.5
RECOVERY_SESSION_TTL_SECONDS = 60 * 60 * 24


def _review_state() -> FlashcardReviewStateResponse:
    return FlashcardReviewStateResponse(
        dueNow=True,
        streakBonus=True,
        ratingOptions=[
            FlashcardReviewRating.FORGOT,
            FlashcardReviewRating.HARD,
            FlashcardReviewRating.OKAY,
            FlashcardReviewRating.EASY,
        ],
    )


@router.get("/due", response_model=FlashcardsDueResponse)
async def get_due_flashcards(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> FlashcardsDueResponse:
    due_cards = await _load_due_cards(session, user_id=current_user.id, now_utc=datetime.now(timezone.utc))
    focus_topic = _build_session_focus(due_cards)
    return FlashcardsDueResponse(
        cards=[_card_to_response(card, include_review_state=True) for card in due_cards],
        totalDue=len(due_cards),
        sessionFocus=f"Focus on {focus_topic} before your next quiz." if focus_topic else "No cards are due right now.",
    )


@router.get("/blitz", response_model=FlashcardsBlitzResponse)
async def get_blitz_flashcards(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> FlashcardsBlitzResponse:
    topic = await _load_blitz_topic(session, user_id=current_user.id)
    cards = await _load_topic_cards(
        session,
        topic_id=topic.id if topic is not None else None,
        card_type=FlashcardCardType.MCQ,
        limit=10,
    )
    return FlashcardsBlitzResponse(
        topicId=str(topic.id) if topic is not None else "",
        durationSeconds=60,
        streakMultiplier=max(1, current_user.current_streak // 5),
        cards=[_card_to_response(card) for card in cards],
    )


@router.get("/boss/{topicId}", response_model=FlashcardsBossResponse)
async def get_boss_round(
    topicId: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> FlashcardsBossResponse:
    topic_id = _parse_uuid(topicId, detail="Invalid topic id.")
    topic = await session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")

    progress = await session.scalar(
        select(UserTopicProgress).where(
            UserTopicProgress.user_id == current_user.id,
            UserTopicProgress.topic_id == topic_id,
        )
    )
    cards = await _load_topic_cards(session, topic_id=topic_id, card_type=None, limit=15)
    return FlashcardsBossResponse(
        topic=FlashcardTopicSummaryResponse(
            id=str(topic.id),
            title=topic.title,
            completed=progress is not None and progress.status == TopicProgressStatus.COMPLETED,
        ),
        passThreshold=0.8,
        cards=[_card_to_response(card) for card in cards],
        revisitConcepts=[],
    )


@router.post("/review", response_model=FlashcardReviewResponse)
async def submit_flashcard_review(
    payload: FlashcardReviewRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> FlashcardReviewResponse:
    user = await session.get(User, current_user.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    card_id = _parse_uuid(payload.cardId, detail="Invalid card id.")
    card = await session.get(Flashcard, card_id)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flashcard not found.")

    reviewed_at = _coerce_utc(datetime.now(timezone.utc))
    streak_state = evaluate_streak(
        current_streak=user.current_streak,
        longest_streak=user.longest_streak,
        last_activity_at=user.last_activity_date,
        freeze_tokens_remaining=user.freeze_tokens_remaining,
        now_utc=reviewed_at,
        recovery_reviews_completed=0,
    )
    latest_review = await session.scalar(
        select(FlashcardReview)
        .where(
            FlashcardReview.user_id == user.id,
            FlashcardReview.card_id == card_id,
        )
        .order_by(FlashcardReview.reviewed_at.desc())
    )
    scheduling = fsrs_service.compute_next_review(
        payload.rating,
        stability=latest_review.stability if latest_review is not None else DEFAULT_INITIAL_STABILITY,
        difficulty=latest_review.difficulty_fsrs if latest_review is not None else DEFAULT_INITIAL_DIFFICULTY,
        interval=latest_review.interval_days if latest_review is not None else DEFAULT_INITIAL_INTERVAL_DAYS,
    )
    session.add(
        FlashcardReview(
            user_id=user.id,
            card_id=card.id,
            rating=payload.rating,
            next_review_at=scheduling["next_review_at"],
            stability=scheduling["stability"],
            difficulty_fsrs=scheduling["difficulty_fsrs"],
            interval_days=scheduling["interval_days"],
            reviewed_at=reviewed_at,
        )
    )
    if streak_state.grace_window.active:
        reviews_completed_this_session = await _increment_recovery_session_reviews(user_id=user.id)
    else:
        activity = apply_study_activity(
            current_streak=user.current_streak,
            longest_streak=user.longest_streak,
            last_activity_at=user.last_activity_date,
            now_utc=reviewed_at,
        )
        user.current_streak = activity.current_streak
        user.longest_streak = activity.longest_streak
        user.last_activity_date = activity.last_activity_date
        reviews_completed_this_session = None
    await session.commit()

    celebrate = payload.rating == FlashcardReviewRating.EASY
    return FlashcardReviewResponse(
        cardId=payload.cardId,
        rating=payload.rating,
        nextReviewAt=scheduling["next_review_at"],
        intervalDays=scheduling["interval_days"],
        celebrate=celebrate,
        xpAwarded=25 if celebrate else 15,
        reviewsCompletedThisSession=reviews_completed_this_session,
    )


def _card_to_response(card: Flashcard, *, include_review_state: bool = False) -> FlashcardCardResponse:
    return FlashcardCardResponse(
        id=str(card.id),
        topicId=str(card.topic_id),
        topicTitle=card.topic.title if card.topic is not None else "",
        cardType=card.card_type,
        difficulty=card.difficulty,
        front=card.front,
        back=card.back,
        options=[_option_to_response(option) for option in card.options],
        xpReward=25 if card.difficulty == FlashcardDifficulty.HARD else 15,
        reviewState=_review_state() if include_review_state else None,
    )


def _option_to_response(option: FlashcardOption) -> FlashcardOptionResponse:
    return FlashcardOptionResponse(id=str(option.id), text=option.option_text)


def _build_session_focus(cards: list[Flashcard]) -> str | None:
    if not cards:
        return None

    topic_counts = Counter(card.topic.title for card in cards if card.topic is not None)
    return topic_counts.most_common(1)[0][0] if topic_counts else None


async def _load_due_cards(session: AsyncSession, *, user_id: UUID, now_utc: datetime) -> list[Flashcard]:
    cards = await _load_flashcards(
        session,
        where_clause=select(Flashcard.id),
    )
    due_cards: list[Flashcard] = []
    for card in cards:
        latest_review = _latest_review_for_user(card, user_id=user_id)
        if latest_review is None or _coerce_utc(latest_review.next_review_at) <= now_utc:
            due_cards.append(card)
    return due_cards


async def _load_blitz_topic(session: AsyncSession, *, user_id: UUID) -> Topic | None:
    topic_statement = (
        select(Topic)
        .join(UserTopicProgress, UserTopicProgress.topic_id == Topic.id)
        .where(
            UserTopicProgress.user_id == user_id,
            UserTopicProgress.status.in_(
                [TopicProgressStatus.IN_PROGRESS, TopicProgressStatus.AVAILABLE, TopicProgressStatus.COMPLETED]
            ),
        )
        .order_by(Topic.order_index)
    )
    topic = await session.scalar(topic_statement)
    if topic is not None:
        return topic
    return await session.scalar(select(Topic).order_by(Topic.order_index))


async def _load_topic_cards(
    session: AsyncSession,
    *,
    topic_id: UUID | None,
    card_type: FlashcardCardType | None,
    limit: int,
) -> list[Flashcard]:
    statement: Select[tuple[Flashcard]] = (
        select(Flashcard)
        .join(Flashcard.topic)
        .options(joinedload(Flashcard.topic), selectinload(Flashcard.options))
        .order_by(func.random())
        .limit(limit)
    )
    if topic_id is not None:
        statement = statement.where(Flashcard.topic_id == topic_id)
    if card_type is not None:
        statement = statement.where(Flashcard.card_type == card_type)
    return list((await session.scalars(statement)).unique())


async def _load_flashcards(
    session: AsyncSession,
    *,
    where_clause: Select[tuple[UUID]],
) -> list[Flashcard]:
    del where_clause
    statement = (
        select(Flashcard)
        .join(Flashcard.topic)
        .options(joinedload(Flashcard.topic), selectinload(Flashcard.options), selectinload(Flashcard.reviews))
        .order_by(Topic.order_index, Flashcard.created_at, Flashcard.id)
    )
    return list((await session.scalars(statement)).unique())


def _latest_review_for_user(card: Flashcard, *, user_id: UUID) -> FlashcardReview | None:
    user_reviews = [review for review in card.reviews if review.user_id == user_id]
    if not user_reviews:
        return None
    return max(user_reviews, key=lambda review: _coerce_utc(review.reviewed_at))


def _parse_uuid(raw_value: str, *, detail: str) -> UUID:
    try:
        return UUID(raw_value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail) from exc


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def _increment_recovery_session_reviews(*, user_id: object) -> int | None:
    try:
        payload = await get_ephemeral_json(_recovery_session_key(user_id))
    except UpstashRedisConfigurationError:
        return None

    existing_payload = payload if isinstance(payload, dict) else {}
    reviews_completed = existing_payload.get("reviewsCompleted")
    current_reviews = reviews_completed if isinstance(reviews_completed, int) and reviews_completed >= 0 else 0
    next_reviews = current_reviews + 1
    updated_payload = dict(existing_payload)
    updated_payload["reviewsCompleted"] = next_reviews
    await set_ephemeral_json(
        _recovery_session_key(user_id),
        updated_payload,
        ttl_seconds=RECOVERY_SESSION_TTL_SECONDS,
    )
    return next_reviews


def _recovery_session_key(user_id: object) -> str:
    return build_session_key(user_id, "recovery")
