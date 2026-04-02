from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services import fsrs_service


@pytest.mark.parametrize(
    ("rating", "stability", "difficulty", "interval", "expected_interval", "expected_stability", "expected_difficulty"),
    [
        ("forgot", 2.0, 2.0, 7, 1, 1.0, 2.1),
        ("hard", 2.0, 2.0, 7, 10, 3.0, 1.95),
        ("okay", 3.0, 1.31, 7, 14, 6.0, 1.3),
        ("easy", 4.0, 2.5, 7, 20, 11.2, 2.45),
    ],
)
def test_compute_next_review_transitions(
    rating: str,
    stability: float,
    difficulty: float,
    interval: int,
    expected_interval: int,
    expected_stability: float,
    expected_difficulty: float,
) -> None:
    result = fsrs_service.compute_next_review(rating, stability, difficulty, interval)

    assert result["interval_days"] == expected_interval
    assert result["stability"] == pytest.approx(expected_stability)
    assert result["difficulty_fsrs"] == pytest.approx(expected_difficulty)


def test_compute_next_review_sets_next_review_at_using_the_new_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return cls(2026, 3, 27, 10, 30, 0, tzinfo=tz or timezone.utc)

    monkeypatch.setattr(fsrs_service, "datetime", FixedDateTime)

    result = fsrs_service.compute_next_review("easy", 4.0, 2.5, 7)

    assert result["next_review_at"].tzinfo == timezone.utc
    assert result["next_review_at"] == FixedDateTime.now(timezone.utc) + timedelta(days=20)


def test_compute_next_review_rejects_invalid_rating() -> None:
    with pytest.raises(ValueError, match="Unsupported rating"):
        fsrs_service.compute_next_review("invalid", 2.0, 2.0, 7)
