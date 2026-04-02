from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence
from typing import Final
from uuid import UUID

from backend.app.models.db import TopicProgressStatus

MASTER_SCORE_WINDOW: Final[int] = 3
MASTER_WEIGHTS: Final[tuple[float, float, float]] = (0.2, 0.3, 0.5)
LOW_SCORE_THRESHOLD: Final[float] = 0.6
HIGH_SCORE_THRESHOLD: Final[float] = 0.8


@dataclass(frozen=True, slots=True)
class TopicProgressSnapshot:
    topic_id: UUID
    order_index: int
    status: TopicProgressStatus


@dataclass(frozen=True, slots=True)
class AdaptiveQuizOutcome:
    topic_id: UUID
    latest_score: float
    mastery_score: float
    updated_status: TopicProgressStatus
    next_topic: TopicProgressSnapshot | None
    should_unlock_next_topic: bool
    recent_scores: tuple[float, ...]


def _validate_score(score: float) -> float:
    if not 0.0 <= score <= 1.0:
        raise ValueError("Quiz scores must be between 0.0 and 1.0.")
    return score


def compute_weighted_mastery(scores: Sequence[float]) -> float:
    recent_scores = tuple(_validate_score(score) for score in scores[-MASTER_SCORE_WINDOW:])
    if not recent_scores:
        return 0.0

    weights = MASTER_WEIGHTS[-len(recent_scores) :]
    total_weight = sum(weights)
    weighted_total = sum(score * weight for score, weight in zip(recent_scores, weights))
    return weighted_total / total_weight


def determine_topic_status_after_attempt(
    *,
    latest_score: float,
    current_status: TopicProgressStatus,
) -> TopicProgressStatus:
    score = _validate_score(latest_score)
    if score < LOW_SCORE_THRESHOLD:
        return TopicProgressStatus.IN_PROGRESS
    return current_status


def select_next_topic_to_unlock(
    ordered_topics: Sequence[TopicProgressSnapshot],
    *,
    current_order_index: int,
) -> TopicProgressSnapshot | None:
    next_topics = [topic for topic in ordered_topics if topic.order_index > current_order_index]
    if not next_topics:
        return None
    return min(next_topics, key=lambda topic: topic.order_index)


def should_unlock_next_topic(
    *,
    latest_score: float,
    next_topic: TopicProgressSnapshot | None,
) -> bool:
    score = _validate_score(latest_score)
    return next_topic is not None and next_topic.status == TopicProgressStatus.LOCKED and score >= HIGH_SCORE_THRESHOLD


def evaluate_quiz_attempt(
    *,
    topic_id: UUID,
    current_status: TopicProgressStatus,
    current_order_index: int,
    quiz_scores: Sequence[float],
    ordered_topics: Sequence[TopicProgressSnapshot],
) -> AdaptiveQuizOutcome:
    if not quiz_scores:
        raise ValueError("At least one quiz score is required.")

    normalized_scores = tuple(_validate_score(score) for score in quiz_scores)
    latest_score = normalized_scores[-1]
    mastery_score = compute_weighted_mastery(normalized_scores)
    updated_status = determine_topic_status_after_attempt(
        latest_score=latest_score,
        current_status=current_status,
    )
    next_topic = select_next_topic_to_unlock(
        list(ordered_topics),
        current_order_index=current_order_index,
    )

    return AdaptiveQuizOutcome(
        topic_id=topic_id,
        latest_score=latest_score,
        mastery_score=mastery_score,
        updated_status=updated_status,
        next_topic=next_topic,
        should_unlock_next_topic=should_unlock_next_topic(
            latest_score=latest_score,
            next_topic=next_topic,
        ),
        recent_scores=normalized_scores[-MASTER_SCORE_WINDOW:],
    )
