from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.db import FlashcardCardType, FlashcardDifficulty, FlashcardReviewRating


class FlashcardSchemaModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class FlashcardOptionResponse(FlashcardSchemaModel):
    id: str
    text: str


class FlashcardReviewStateResponse(FlashcardSchemaModel):
    dueNow: bool
    streakBonus: bool
    ratingOptions: list[FlashcardReviewRating]


class FlashcardCardResponse(FlashcardSchemaModel):
    id: str
    topicId: str
    topicTitle: str
    cardType: FlashcardCardType
    difficulty: FlashcardDifficulty
    front: str
    back: str
    hint: str | None = None
    options: list[FlashcardOptionResponse] = Field(default_factory=list)
    xpReward: int
    reviewState: FlashcardReviewStateResponse | None = None


class FlashcardsDueResponse(FlashcardSchemaModel):
    cards: list[FlashcardCardResponse]
    totalDue: int
    sessionFocus: str


class FlashcardsBlitzResponse(FlashcardSchemaModel):
    topicId: str
    durationSeconds: int
    streakMultiplier: int
    cards: list[FlashcardCardResponse]


class FlashcardTopicSummaryResponse(FlashcardSchemaModel):
    id: str
    title: str
    completed: bool


class FlashcardsBossResponse(FlashcardSchemaModel):
    topic: FlashcardTopicSummaryResponse
    passThreshold: float
    cards: list[FlashcardCardResponse]
    revisitConcepts: list[str]


class FlashcardReviewRequest(FlashcardSchemaModel):
    cardId: str
    rating: FlashcardReviewRating
    elapsedMs: int = Field(ge=0)


class FlashcardReviewResponse(FlashcardSchemaModel):
    cardId: str
    rating: FlashcardReviewRating
    nextReviewAt: datetime
    intervalDays: int
    celebrate: bool
    xpAwarded: int
    reviewsCompletedThisSession: int | None = None
