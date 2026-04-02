from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TypedDict


class FSRSReviewResult(TypedDict):
    interval_days: int
    stability: float
    difficulty_fsrs: float
    next_review_at: datetime


def compute_next_review(rating: str, stability: float, difficulty: float, interval: int) -> FSRSReviewResult:
    ease_map = {"forgot": 1.2, "hard": 1.5, "okay": 2.0, "easy": 2.8}
    if rating not in ease_map:
        raise ValueError(f"Unsupported rating: {rating}")

    if rating == "forgot":
        new_interval = 1
        new_stability = max(stability * 0.5, 1.0)
    else:
        multiplier = ease_map[rating]
        new_interval = max(1, round(interval * multiplier))
        new_stability = stability * multiplier

    new_difficulty = max(1.3, difficulty + (0.1 if rating == "forgot" else -0.05))
    next_review_at = datetime.now(timezone.utc) + timedelta(days=new_interval)
    return {
        "interval_days": new_interval,
        "stability": new_stability,
        "difficulty_fsrs": new_difficulty,
        "next_review_at": next_review_at,
    }
