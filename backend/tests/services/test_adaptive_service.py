from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from backend.app.models.db import TopicProgressStatus
from backend.app.services.adaptive_service import (
    AdaptiveQuizOutcome,
    TopicProgressSnapshot,
    compute_weighted_mastery,
    evaluate_quiz_attempt,
    select_next_topic_to_unlock,
)


def test_compute_weighted_mastery_uses_only_the_most_recent_three_scores() -> None:
    mastery = compute_weighted_mastery([0.1, 0.2, 0.4, 1.0])

    assert mastery == pytest.approx(0.66)


def test_compute_weighted_mastery_returns_zero_for_empty_history() -> None:
    assert compute_weighted_mastery([]) == 0.0


def test_select_next_topic_to_unlock_picks_the_immediate_next_topic() -> None:
    current_topic_id = UUID("11111111-1111-1111-1111-111111111111")
    next_topic = TopicProgressSnapshot(
        topic_id=UUID("22222222-2222-2222-2222-222222222222"),
        order_index=2,
        status=TopicProgressStatus.LOCKED,
    )
    later_topic = TopicProgressSnapshot(
        topic_id=UUID("33333333-3333-3333-3333-333333333333"),
        order_index=4,
        status=TopicProgressStatus.LOCKED,
    )

    selected = select_next_topic_to_unlock([next_topic, later_topic], current_order_index=1)

    assert selected is next_topic
    assert selected.topic_id != current_topic_id


def test_evaluate_quiz_attempt_regresses_and_unlocks_by_score_thresholds() -> None:
    current_topic_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    ordered_topics = [
        TopicProgressSnapshot(
            topic_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            order_index=2,
            status=TopicProgressStatus.LOCKED,
        ),
        TopicProgressSnapshot(
            topic_id=UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
            order_index=3,
            status=TopicProgressStatus.AVAILABLE,
        ),
    ]

    outcome = evaluate_quiz_attempt(
        topic_id=current_topic_id,
        current_status=TopicProgressStatus.COMPLETED,
        current_order_index=1,
        quiz_scores=[0.9, 0.85, 0.82],
        ordered_topics=ordered_topics,
    )

    assert isinstance(outcome, AdaptiveQuizOutcome)
    assert outcome.topic_id == current_topic_id
    assert outcome.latest_score == pytest.approx(0.82)
    assert outcome.mastery_score == pytest.approx(0.845)
    assert outcome.updated_status == TopicProgressStatus.COMPLETED
    assert outcome.next_topic is not None
    assert outcome.next_topic.topic_id == UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    assert outcome.should_unlock_next_topic is True
    assert outcome.recent_scores == (0.9, 0.85, 0.82)


def test_evaluate_quiz_attempt_regresses_to_in_progress_on_low_score() -> None:
    outcome = evaluate_quiz_attempt(
        topic_id=UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
        current_status=TopicProgressStatus.COMPLETED,
        current_order_index=1,
        quiz_scores=[0.75, 0.55],
        ordered_topics=[
            TopicProgressSnapshot(
                topic_id=UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
                order_index=2,
                status=TopicProgressStatus.LOCKED,
            )
        ],
    )

    assert outcome.updated_status == TopicProgressStatus.IN_PROGRESS
    assert outcome.should_unlock_next_topic is False
