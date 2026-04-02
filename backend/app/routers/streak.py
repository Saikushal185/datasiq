from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import get_current_user
from backend.app.core.database import get_db_session
from backend.app.core.redis import UpstashRedisConfigurationError, build_session_key, get_ephemeral_json, set_ephemeral_json
from backend.app.models.db import StreakEvent, StreakEventType, User
from backend.app.schemas.streak import (
    StreakActionResponse,
    StreakGraceWindowResponse,
    StreakRageModalResponse,
    StreakRecoverRequest,
    StreakRecoveryResponse,
    StreakResponse,
    WeeklyBarDayResponse,
)
from backend.app.services.streak_service import RECOVERY_REVIEWS_REQUIRED, StreakState, evaluate_streak, to_ist_date
from backend.app.services.streak_service import apply_study_activity


router = APIRouter(prefix="/streak", tags=["streak"])
RECOVERY_SESSION_TTL_SECONDS = 60 * 60 * 24


def _build_streak_response(*, state: StreakState, now_utc: datetime) -> StreakResponse:
    return StreakResponse(
        currentStreak=state.current_streak,
        longestStreak=state.longest_streak,
        freezeTokensRemaining=state.freeze_tokens_remaining,
        freezeApplied=state.freeze_applied,
        todayCompleted=state.today_completed,
        lastActivityDate=state.last_activity_date.isoformat() if state.last_activity_date is not None else None,
        protectedStreakDate=state.protected_streak_date.isoformat() if state.protected_streak_date is not None else None,
        graceWindow=StreakGraceWindowResponse(
            active=state.grace_window.active,
            expiresAt=state.grace_window.expires_at,
            missedDate=state.grace_window.missed_date.isoformat() if state.grace_window.missed_date is not None else None,
        ),
        recovery=StreakRecoveryResponse(
            eligible=state.recovery.eligible,
            thresholdMet=state.recovery.threshold_met,
            applied=state.recovery.applied,
            reviewsRequired=state.recovery.reviews_required,
            reviewsCompleted=state.recovery.reviews_completed,
            reviewsRemaining=state.recovery.reviews_remaining,
        ),
        rageModal=StreakRageModalResponse(
            show=state.rage_modal_eligible,
            reason="Your streak is recoverable." if state.rage_modal_eligible else "",
            cta="Recover my streak (20 cards)" if state.rage_modal_eligible else "",
        ),
        weeklyBar=_build_weekly_bar(state=state, now_utc=now_utc),
    )


@router.get("", response_model=StreakResponse)
async def get_streak(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StreakResponse:
    user = await _load_user(session, user_id=current_user.id)
    now_utc = datetime.now(timezone.utc)
    reviews_completed = await _get_recovery_reviews_completed(user_id=user.id)
    state = evaluate_streak(
        current_streak=user.current_streak,
        longest_streak=user.longest_streak,
        last_activity_at=user.last_activity_date,
        freeze_tokens_remaining=user.freeze_tokens_remaining,
        now_utc=now_utc,
        recovery_reviews_completed=reviews_completed,
    )
    return _build_streak_response(state=state, now_utc=now_utc)


@router.post("/freeze", response_model=StreakActionResponse)
async def use_streak_freeze(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StreakActionResponse:
    user = await _load_user(session, user_id=current_user.id)
    now_utc = datetime.now(timezone.utc)
    reviews_completed = await _get_recovery_reviews_completed(user_id=user.id)
    state = evaluate_streak(
        current_streak=user.current_streak,
        longest_streak=user.longest_streak,
        last_activity_at=user.last_activity_date,
        freeze_tokens_remaining=user.freeze_tokens_remaining,
        now_utc=now_utc,
        recovery_reviews_completed=reviews_completed,
    )
    if not state.grace_window.active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No missed day is eligible for a freeze.")
    if user.freeze_tokens_remaining <= 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No freeze tokens are available.")

    updated_state = evaluate_streak(
        current_streak=user.current_streak,
        longest_streak=user.longest_streak,
        last_activity_at=user.last_activity_date,
        freeze_tokens_remaining=user.freeze_tokens_remaining - 1,
        now_utc=now_utc,
        freeze_used=True,
        recovery_reviews_completed=reviews_completed,
    )
    protected_date = _require_protected_date(updated_state)

    user.current_streak = updated_state.current_streak
    user.longest_streak = updated_state.longest_streak
    user.last_activity_date = protected_date
    user.freeze_tokens_remaining = updated_state.freeze_tokens_remaining
    session.add(
        StreakEvent(
            user_id=user.id,
            event_type=StreakEventType.FROZEN,
            event_date=protected_date,
            streak_value_at_event=updated_state.current_streak,
        )
    )
    await session.commit()

    return StreakActionResponse(
        action="freeze",
        message="A freeze token was reserved for your missed day.",
        streak=_build_streak_response(state=updated_state, now_utc=now_utc),
    )


@router.post("/recover", response_model=StreakActionResponse)
async def recover_streak(
    payload: StreakRecoverRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StreakActionResponse:
    user = await _load_user(session, user_id=current_user.id)
    now_utc = datetime.now(timezone.utc)
    session_reviews_completed = await _get_recovery_reviews_completed(user_id=user.id)
    state = evaluate_streak(
        current_streak=user.current_streak,
        longest_streak=user.longest_streak,
        last_activity_at=user.last_activity_date,
        freeze_tokens_remaining=user.freeze_tokens_remaining,
        now_utc=now_utc,
        recovery_reviews_completed=session_reviews_completed,
    )
    if not state.recovery.eligible:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No streak recovery is currently available.")
    if not state.recovery.threshold_met:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Recovery requires {RECOVERY_REVIEWS_REQUIRED} flashcard reviews in one session.",
        )

    protected_date = _require_protected_date(state)
    study_activity = apply_study_activity(
        current_streak=state.current_streak,
        longest_streak=state.longest_streak,
        last_activity_at=protected_date,
        now_utc=now_utc,
    )
    user.current_streak = study_activity.current_streak
    user.longest_streak = study_activity.longest_streak
    user.last_activity_date = study_activity.last_activity_date
    session.add(
        StreakEvent(
            user_id=user.id,
            event_type=StreakEventType.RECOVERED,
            event_date=study_activity.last_activity_date,
            streak_value_at_event=study_activity.current_streak,
        )
    )
    await session.commit()
    await _set_recovery_session_state(
        user_id=user.id,
        payload={"reviewsCompleted": session_reviews_completed, "applied": True},
    )

    response_state = replace(
        state,
        current_streak=study_activity.current_streak,
        longest_streak=study_activity.longest_streak,
        last_activity_date=study_activity.last_activity_date,
        protected_streak_date=study_activity.last_activity_date,
        today_completed=True,
        streak_broken=False,
    )

    return StreakActionResponse(
        action="recover",
        message="Recovery progress updated for this session.",
        streak=_build_streak_response(state=response_state, now_utc=now_utc),
    )


async def _load_user(session: AsyncSession, *, user_id: object) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user


async def _get_recovery_reviews_completed(*, user_id: object) -> int:
    try:
        payload = await get_ephemeral_json(_recovery_session_key(user_id))
    except UpstashRedisConfigurationError:
        return 0

    if not isinstance(payload, dict):
        return 0
    reviews_completed = payload.get("reviewsCompleted")
    if isinstance(reviews_completed, int) and reviews_completed >= 0:
        return reviews_completed
    return 0


async def _set_recovery_session_state(*, user_id: object, payload: dict[str, object]) -> None:
    try:
        await set_ephemeral_json(
            _recovery_session_key(user_id),
            payload,
            ttl_seconds=RECOVERY_SESSION_TTL_SECONDS,
        )
    except UpstashRedisConfigurationError:
        return None


def _recovery_session_key(user_id: object) -> str:
    return build_session_key(user_id, "recovery")


def _require_protected_date(state: StreakState) -> date:
    if state.protected_streak_date is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No streak date was protected.")
    return state.protected_streak_date


def _build_weekly_bar(*, state: StreakState, now_utc: datetime) -> list[WeeklyBarDayResponse]:
    today = to_ist_date(now_utc)
    days = [today - timedelta(days=offset) for offset in range(4, -1, -1)]
    bar: list[WeeklyBarDayResponse] = []
    recent_done_dates = {
        state.last_activity_date,
        state.protected_streak_date,
    }
    for day in days:
        cell_state = "idle"
        if day == today:
            cell_state = "done" if state.today_completed else "today"
        elif day in recent_done_dates:
            cell_state = "done"
        elif state.grace_window.missed_date == day:
            cell_state = "warning"
        bar.append(WeeklyBarDayResponse(date=day.isoformat(), label=day.strftime("%a"), state=cell_state))
    return bar
