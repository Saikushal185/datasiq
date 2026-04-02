from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

import pytz


IST = pytz.timezone("Asia/Kolkata")
RECOVERY_REVIEWS_REQUIRED = 20


@dataclass(frozen=True, slots=True)
class GraceWindow:
    active: bool
    expires_at: datetime | None
    missed_date: date | None


@dataclass(frozen=True, slots=True)
class RecoveryStatus:
    eligible: bool
    threshold_met: bool
    applied: bool
    reviews_required: int
    reviews_completed: int
    reviews_remaining: int


@dataclass(frozen=True, slots=True)
class FreezeTokenRefresh:
    tokens_remaining: int
    replenished: bool
    replenished_at: datetime | None


@dataclass(frozen=True, slots=True)
class StudyActivityUpdate:
    current_streak: int
    longest_streak: int
    last_activity_date: date


@dataclass(frozen=True, slots=True)
class StreakState:
    current_streak: int
    longest_streak: int
    last_activity_date: date | None
    protected_streak_date: date | None
    today_completed: bool
    streak_broken: bool
    freeze_tokens_remaining: int
    freeze_applied: bool
    grace_window: GraceWindow
    recovery: RecoveryStatus
    rage_modal_eligible: bool


def to_ist_date(value: datetime | date) -> date:
    if isinstance(value, datetime):
        return _require_aware(value, "value").astimezone(IST).date()

    return value


def apply_weekly_freeze_replenishment(
    *,
    freeze_tokens_remaining: int,
    now_utc: datetime,
    last_replenished_at: datetime | date | None,
    weekly_allowance: int = 1,
    max_tokens: int | None = None,
) -> FreezeTokenRefresh:
    current_week_start = _ist_week_start(_require_aware(now_utc, "now_utc"))
    if last_replenished_at is None:
        return FreezeTokenRefresh(
            tokens_remaining=freeze_tokens_remaining,
            replenished=False,
            replenished_at=None,
        )

    previous_week_start = _ist_week_start(_coerce_to_ist_datetime(last_replenished_at))
    weeks_elapsed = max(0, (current_week_start.date() - previous_week_start.date()).days // 7)
    if weeks_elapsed == 0:
        return FreezeTokenRefresh(
            tokens_remaining=freeze_tokens_remaining,
            replenished=False,
            replenished_at=None,
        )

    replenished_tokens = freeze_tokens_remaining + (weekly_allowance * weeks_elapsed)
    if max_tokens is not None:
        replenished_tokens = min(replenished_tokens, max_tokens)

    return FreezeTokenRefresh(
        tokens_remaining=replenished_tokens,
        replenished=True,
        replenished_at=current_week_start.astimezone(timezone.utc),
    )


def apply_study_activity(
    *,
    current_streak: int,
    longest_streak: int,
    last_activity_at: datetime | date | None,
    now_utc: datetime,
) -> StudyActivityUpdate:
    now = _require_aware(now_utc, "now_utc")
    today_ist = now.astimezone(IST).date()
    last_activity_date = None if last_activity_at is None else to_ist_date(last_activity_at)

    if last_activity_date == today_ist:
        return StudyActivityUpdate(
            current_streak=current_streak,
            longest_streak=max(longest_streak, current_streak),
            last_activity_date=today_ist,
        )

    if last_activity_date is None:
        next_streak = 1
    elif last_activity_date == today_ist - timedelta(days=1):
        next_streak = max(1, current_streak + 1)
    else:
        next_streak = 1

    return StudyActivityUpdate(
        current_streak=next_streak,
        longest_streak=max(longest_streak, next_streak),
        last_activity_date=today_ist,
    )


def evaluate_streak(
    *,
    current_streak: int,
    longest_streak: int,
    last_activity_at: datetime | date | None,
    freeze_tokens_remaining: int,
    now_utc: datetime,
    freeze_used: bool = False,
    recovery_reviews_completed: int = 0,
) -> StreakState:
    now = _require_aware(now_utc, "now_utc")
    today_ist = now.astimezone(IST).date()
    last_activity_date = None if last_activity_at is None else to_ist_date(last_activity_at)
    reviews_completed = max(0, recovery_reviews_completed)
    pre_action_grace_window = _build_grace_window(now=now, protected_date=last_activity_date)
    recovery_threshold_met = reviews_completed >= RECOVERY_REVIEWS_REQUIRED
    freeze_applied = freeze_used and pre_action_grace_window.active
    recovery_eligible = pre_action_grace_window.active and not freeze_applied
    recovery_applied = recovery_eligible and recovery_threshold_met

    effective_streak = current_streak
    effective_longest = max(longest_streak, current_streak)
    protected_date = last_activity_date

    if protected_date is not None and (freeze_applied or recovery_applied):
        protected_date = protected_date + timedelta(days=1)
        effective_streak += 1
        effective_longest = max(effective_longest, effective_streak)

    grace_window = _build_grace_window(now=now, protected_date=protected_date)
    streak_broken = protected_date is not None and not grace_window.active and grace_window.missed_date is not None
    if streak_broken:
        effective_streak = 0

    recovery = RecoveryStatus(
        eligible=recovery_eligible,
        threshold_met=recovery_threshold_met,
        applied=recovery_applied,
        reviews_required=RECOVERY_REVIEWS_REQUIRED,
        reviews_completed=reviews_completed,
        reviews_remaining=max(0, RECOVERY_REVIEWS_REQUIRED - reviews_completed),
    )

    return StreakState(
        current_streak=effective_streak,
        longest_streak=effective_longest,
        last_activity_date=last_activity_date,
        protected_streak_date=protected_date,
        today_completed=last_activity_date == today_ist or recovery_applied,
        streak_broken=streak_broken,
        freeze_tokens_remaining=freeze_tokens_remaining,
        freeze_applied=freeze_applied,
        grace_window=grace_window,
        recovery=recovery,
        rage_modal_eligible=streak_broken and not freeze_applied,
    )


def _build_grace_window(*, now: datetime, protected_date: date | None) -> GraceWindow:
    if protected_date is None:
        return GraceWindow(active=False, expires_at=None, missed_date=None)

    today_ist = now.astimezone(IST).date()
    gap = (today_ist - protected_date).days
    if gap < 2:
        return GraceWindow(active=False, expires_at=None, missed_date=None)

    missed_date = protected_date + timedelta(days=1)
    expires_at = _ist_end_of_day(protected_date + timedelta(days=2)).astimezone(timezone.utc)
    return GraceWindow(
        active=now <= expires_at,
        expires_at=expires_at,
        missed_date=missed_date,
    )


def _coerce_to_ist_datetime(value: datetime | date) -> datetime:
    if isinstance(value, datetime):
        return _require_aware(value, "value").astimezone(IST)

    return IST.localize(datetime.combine(value, time.min))


def _ist_end_of_day(day: date) -> datetime:
    return IST.localize(datetime.combine(day, time(23, 59, 59, 999999)))


def _ist_week_start(value: datetime) -> datetime:
    local_value = value.astimezone(IST)
    monday = local_value.date() - timedelta(days=local_value.weekday())
    return IST.localize(datetime.combine(monday, time.min))


def _require_aware(value: datetime, argument_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{argument_name} must be timezone-aware")

    return value


__all__ = [
    "IST",
    "RECOVERY_REVIEWS_REQUIRED",
    "FreezeTokenRefresh",
    "GraceWindow",
    "RecoveryStatus",
    "StreakState",
    "StudyActivityUpdate",
    "apply_weekly_freeze_replenishment",
    "apply_study_activity",
    "evaluate_streak",
    "to_ist_date",
]
