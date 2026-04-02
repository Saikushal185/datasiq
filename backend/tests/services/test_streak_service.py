from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services import streak_service


def test_evaluate_streak_uses_ist_dates_instead_of_utc_dates() -> None:
    result = streak_service.evaluate_streak(
        current_streak=5,
        longest_streak=9,
        last_activity_at=datetime(2026, 3, 27, 18, 29, tzinfo=timezone.utc),
        freeze_tokens_remaining=1,
        now_utc=datetime(2026, 3, 27, 18, 31, tzinfo=timezone.utc),
    )

    assert result.last_activity_date == date(2026, 3, 27)
    assert result.protected_streak_date == date(2026, 3, 27)
    assert result.today_completed is False
    assert result.grace_window.active is False
    assert result.streak_broken is False


@pytest.mark.parametrize(
    ("now_utc", "expected_active", "expected_broken"),
    [
        (datetime(2026, 3, 28, 18, 29, 59, tzinfo=timezone.utc), True, False),
        (datetime(2026, 3, 28, 18, 30, 0, tzinfo=timezone.utc), False, True),
    ],
)
def test_evaluate_streak_tracks_the_ist_grace_cutoff(
    now_utc: datetime,
    expected_active: bool,
    expected_broken: bool,
) -> None:
    result = streak_service.evaluate_streak(
        current_streak=8,
        longest_streak=10,
        last_activity_at=date(2026, 3, 26),
        freeze_tokens_remaining=1,
        now_utc=now_utc,
    )

    assert result.grace_window.missed_date == date(2026, 3, 27)
    assert result.grace_window.expires_at == datetime(2026, 3, 28, 18, 29, 59, 999999, tzinfo=timezone.utc)
    assert result.grace_window.active is expected_active
    assert result.streak_broken is expected_broken
    assert result.recovery.eligible is expected_active
    assert result.recovery.threshold_met is False
    assert result.recovery.applied is False


@pytest.mark.parametrize(
    ("now_utc", "expected_replenished", "expected_tokens"),
    [
        (datetime(2026, 3, 29, 18, 29, 59, tzinfo=timezone.utc), False, 0),
        (datetime(2026, 3, 29, 18, 30, 0, tzinfo=timezone.utc), True, 1),
    ],
)
def test_apply_weekly_freeze_replenishment_uses_monday_midnight_ist(
    now_utc: datetime,
    expected_replenished: bool,
    expected_tokens: int,
) -> None:
    result = streak_service.apply_weekly_freeze_replenishment(
        freeze_tokens_remaining=0,
        now_utc=now_utc,
        last_replenished_at=datetime(2026, 3, 22, 18, 30, tzinfo=timezone.utc),
    )

    assert result.replenished is expected_replenished
    assert result.tokens_remaining == expected_tokens
    assert result.replenished_at == (
        datetime(2026, 3, 29, 18, 30, tzinfo=timezone.utc) if expected_replenished else None
    )


def test_evaluate_streak_freeze_usage_preserves_a_missed_day() -> None:
    result = streak_service.evaluate_streak(
        current_streak=6,
        longest_streak=6,
        last_activity_at=date(2026, 3, 26),
        freeze_tokens_remaining=0,
        now_utc=datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc),
        freeze_used=True,
    )

    assert result.current_streak == 7
    assert result.longest_streak == 7
    assert result.last_activity_date == date(2026, 3, 26)
    assert result.protected_streak_date == date(2026, 3, 27)
    assert result.grace_window.active is False
    assert result.streak_broken is False
    assert result.freeze_applied is True
    assert result.freeze_tokens_remaining == 0
    assert result.rage_modal_eligible is False


@pytest.mark.parametrize(
    ("now_utc", "expected_rage_modal", "expected_grace_active"),
    [
        (datetime(2026, 3, 28, 18, 29, 59, tzinfo=timezone.utc), False, True),
        (datetime(2026, 3, 28, 18, 30, 0, tzinfo=timezone.utc), True, False),
    ],
)
def test_evaluate_streak_only_shows_rage_modal_after_grace_expires(
    now_utc: datetime,
    expected_rage_modal: bool,
    expected_grace_active: bool,
) -> None:
    result = streak_service.evaluate_streak(
        current_streak=4,
        longest_streak=7,
        last_activity_at=date(2026, 3, 26),
        freeze_tokens_remaining=1,
        now_utc=now_utc,
    )

    assert result.grace_window.active is expected_grace_active
    assert result.rage_modal_eligible is expected_rage_modal


def test_evaluate_streak_applies_recovery_during_active_grace() -> None:
    result = streak_service.evaluate_streak(
        current_streak=9,
        longest_streak=12,
        last_activity_at=date(2026, 3, 26),
        freeze_tokens_remaining=1,
        now_utc=datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc),
        recovery_reviews_completed=20,
    )

    assert result.current_streak == 10
    assert result.longest_streak == 12
    assert result.last_activity_date == date(2026, 3, 26)
    assert result.protected_streak_date == date(2026, 3, 27)
    assert result.grace_window.active is False
    assert result.streak_broken is False
    assert result.recovery.eligible is True
    assert result.recovery.threshold_met is True
    assert result.recovery.applied is True
    assert result.today_completed is True


def test_evaluate_streak_does_not_apply_recovery_after_grace_expiry() -> None:
    result = streak_service.evaluate_streak(
        current_streak=9,
        longest_streak=12,
        last_activity_at=date(2026, 3, 26),
        freeze_tokens_remaining=1,
        now_utc=datetime(2026, 3, 28, 18, 30, 0, tzinfo=timezone.utc),
        recovery_reviews_completed=20,
    )

    assert result.current_streak == 0
    assert result.last_activity_date == date(2026, 3, 26)
    assert result.protected_streak_date == date(2026, 3, 26)
    assert result.streak_broken is True
    assert result.recovery.eligible is False
    assert result.recovery.threshold_met is True
    assert result.recovery.applied is False
