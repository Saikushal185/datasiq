from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from backend.app.models.db import TopicDifficulty, TopicProgressStatus


class ProgressTopicResponse(BaseModel):
    id: str
    title: str
    orderIndex: int
    difficulty: TopicDifficulty
    status: TopicProgressStatus
    masteryScore: float
    lastStudiedAt: datetime | None = None


class ProgressPathResponse(BaseModel):
    topics: list[ProgressTopicResponse]
    currentTopicId: str | None = None


class ProgressStatsTopicResponse(BaseModel):
    topicId: str
    title: str
    masteryScore: float
    status: TopicProgressStatus


class ProgressStatsResponse(BaseModel):
    currentStreak: int
    longestStreak: int
    cardsDueToday: int
    topics: list[ProgressStatsTopicResponse]
