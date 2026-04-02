from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import get_current_user, require_admin_secret
from backend.app.core.config import Settings, get_settings
from backend.app.core.database import get_db_session
from backend.app.models.db import Topic, User
from backend.app.schemas.curriculum import GenerateCardsRequest, GenerateCardsResponse
from backend.app.services.ai_service import (
    FlashcardGenerationConfigurationError,
    FlashcardGenerationError,
    GeneratedFlashcardBatch,
    generate_topic_flashcards,
    persist_generated_flashcards,
)


router = APIRouter(prefix="/curriculum", tags=["curriculum"])


@router.post("/generate-cards", response_model=GenerateCardsResponse)
async def generate_cards(
    payload: GenerateCardsRequest,
    _current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    _admin_guard: None = Depends(require_admin_secret),
) -> GenerateCardsResponse:
    topic = await session.get(Topic, payload.topicId)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")

    try:
        generated_batch = await generate_topic_flashcards(
            topic=topic,
            card_count=payload.cardCount,
            notes=payload.notes,
            settings=settings,
        )
        persisted = await persist_generated_flashcards(session, topic=topic, batch=_coerce_generation_batch(generated_batch))
    except FlashcardGenerationConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except FlashcardGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return GenerateCardsResponse(
        status="completed",
        topicId=persisted.topic_id,
        topicTitle=persisted.topic_title,
        requestedCount=persisted.requested_count,
        generatedCards=persisted.generated_cards,
        generatedOptions=persisted.generated_options,
    )


def _coerce_generation_batch(batch: GeneratedFlashcardBatch | dict[str, object]) -> GeneratedFlashcardBatch:
    if isinstance(batch, GeneratedFlashcardBatch):
        return batch
    try:
        return GeneratedFlashcardBatch.model_validate(batch)
    except ValidationError as exc:
        raise FlashcardGenerationError("Claude returned an invalid flashcard payload.") from exc
