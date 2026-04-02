from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StreakSchemaModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StreakGraceWindowResponse(StreakSchemaModel):
    active: bool
    expiresAt: datetime | None = None
    missedDate: str | None = None


class StreakRecoveryResponse(StreakSchemaModel):
    eligible: bool
    thresholdMet: bool = False
    applied: bool = False
    reviewsRequired: int
    reviewsCompleted: int
    reviewsRemaining: int


class StreakRageModalResponse(StreakSchemaModel):
    show: bool
    reason: str
    cta: str


class WeeklyBarDayResponse(StreakSchemaModel):
    date: str
    label: str
    state: Literal["done", "today", "warning", "idle"]


class StreakResponse(StreakSchemaModel):
    currentStreak: int
    longestStreak: int
    freezeTokensRemaining: int
    freezeApplied: bool = False
    todayCompleted: bool
    lastActivityDate: str | None = None
    protectedStreakDate: str | None = None
    graceWindow: StreakGraceWindowResponse
    recovery: StreakRecoveryResponse
    rageModal: StreakRageModalResponse
    weeklyBar: list[WeeklyBarDayResponse]


class StreakRecoverRequest(StreakSchemaModel):
    reviewsCompleted: int = Field(ge=0)


class StreakActionResponse(StreakSchemaModel):
    action: Literal["freeze", "recover"]
    message: str
    streak: StreakResponse
