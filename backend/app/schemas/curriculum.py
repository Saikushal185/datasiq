from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class GenerateCardsRequest(BaseModel):
    topicId: UUID
    cardCount: int = Field(default=12, ge=1, le=50)
    notes: str | None = None


class GenerateCardsResponse(BaseModel):
    status: Literal["completed"]
    topicId: UUID
    topicTitle: str
    requestedCount: int
    generatedCards: int
    generatedOptions: int
