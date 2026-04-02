from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import Settings
from backend.app.models.db import (
    Flashcard,
    FlashcardCardType,
    FlashcardDifficulty,
    FlashcardOption,
    Topic,
)


CLAUDE_MODEL = "claude-3-5-haiku-latest"
DEFAULT_MAX_OUTPUT_TOKENS = 4096


class FlashcardGenerationError(RuntimeError):
    """Raised when the curriculum generation flow cannot complete."""


class FlashcardGenerationConfigurationError(FlashcardGenerationError):
    """Raised when generation is requested without valid Anthropic settings."""


class GeneratedFlashcardOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    is_correct: bool


class GeneratedFlashcard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_type: FlashcardCardType
    difficulty: FlashcardDifficulty
    front: str
    back: str
    options: list[GeneratedFlashcardOption] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_card_shape(self) -> "GeneratedFlashcard":
        if self.card_type == FlashcardCardType.MCQ:
            if len(self.options) < 2:
                raise ValueError("MCQ flashcards require at least two options.")
            correct_option_count = sum(1 for option in self.options if option.is_correct)
            if correct_option_count != 1:
                raise ValueError("MCQ flashcards require exactly one correct option.")
        elif self.options:
            raise ValueError("Only MCQ flashcards may include options.")
        return self


class GeneratedFlashcardBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic_id: UUID
    topic_title: str
    requested_count: int = Field(ge=1, le=50)
    cards: list[GeneratedFlashcard]

    @model_validator(mode="after")
    def validate_card_count(self) -> "GeneratedFlashcardBatch":
        if len(self.cards) != self.requested_count:
            raise ValueError("The generated card count must match the requested count.")
        return self


class PersistedFlashcardGenerationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic_id: UUID
    topic_title: str
    requested_count: int
    generated_cards: int
    generated_options: int


def build_flashcard_generation_prompt(
    *,
    topic: Topic,
    card_count: int,
    notes: str | None,
) -> Any:
    from langchain_core.prompts import ChatPromptTemplate

    system_prompt = (
        "You generate curriculum flashcards for a learning platform.\n"
        "Return a single valid JSON object and nothing else.\n"
        "Do not wrap the JSON in markdown or add commentary."
    )
    human_prompt = (
        "Topic id: {topic_id}\n"
        "Topic title: {topic_title}\n"
        "Topic difficulty: {topic_difficulty}\n"
        "Topic description: {topic_description}\n"
        "Requested card count: {card_count}\n"
        "Instructor notes: {notes}\n\n"
        "Create exactly {card_count} flashcards.\n"
        "Use a healthy mix of recall, mcq, and fill_blank cards.\n"
        "Keep questions aligned to the topic difficulty and avoid ambiguity.\n"
        "For mcq cards, include exactly four options and exactly one correct option.\n"
        "For recall and fill_blank cards, keep options empty.\n\n"
        "Return JSON in this shape:\n"
        "{\n"
        '  \"topic_id\": \"<uuid>\",\n'
        '  \"topic_title\": \"<string>\",\n'
        '  \"requested_count\": <integer>,\n'
        '  \"cards\": [\n'
        "    {\n"
        '      \"card_type\": \"recall|mcq|fill_blank\",\n'
        '      \"difficulty\": \"easy|medium|hard\",\n'
        '      \"front\": \"<string>\",\n'
        '      \"back\": \"<string>\",\n'
        '      \"options\": [{\"text\": \"<string>\", \"is_correct\": true}]\n'
        "    }\n"
        "  ]\n"
        "}"
    )
    return ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", human_prompt),
        ]
    ).partial(
        topic_id=str(topic.id),
        topic_title=topic.title,
        topic_difficulty=topic.difficulty.value,
        topic_description=topic.description or "No description provided.",
        card_count=card_count,
        notes=notes or "None",
    )


async def generate_topic_flashcards(
    *,
    topic: Topic,
    card_count: int,
    notes: str | None,
    settings: Settings,
) -> GeneratedFlashcardBatch:
    if not settings.anthropic_api_key:
        raise FlashcardGenerationConfigurationError("ANTHROPIC_API_KEY is not configured.")

    from anthropic import Anthropic

    prompt = build_flashcard_generation_prompt(topic=topic, card_count=card_count, notes=notes)
    prompt_value = prompt.format_prompt()
    messages = prompt_value.to_messages()
    system_parts = [message.content for message in messages if getattr(message, "type", "") == "system"]
    user_messages = [
        {"role": "user", "content": message.content}
        for message in messages
        if getattr(message, "type", "") == "human"
    ]
    client = Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
        temperature=0.2,
        system="\n\n".join(part for part in system_parts if isinstance(part, str)) or None,
        messages=user_messages,
    )
    raw_json = _extract_text_payload(response).strip()

    try:
        return GeneratedFlashcardBatch.model_validate_json(raw_json)
    except ValidationError as exc:
        raise FlashcardGenerationError("Claude returned an invalid flashcard payload.") from exc


async def persist_generated_flashcards(
    session: AsyncSession,
    *,
    topic: Topic,
    batch: GeneratedFlashcardBatch,
) -> PersistedFlashcardGenerationResult:
    if batch.topic_id != topic.id:
        raise FlashcardGenerationError("Generated flashcards do not match the requested topic.")

    cards: list[Flashcard] = []
    options: list[FlashcardOption] = []
    for generated_card in batch.cards:
        card = Flashcard(
            id=uuid4(),
            topic_id=topic.id,
            card_type=generated_card.card_type,
            difficulty=generated_card.difficulty,
            front=generated_card.front,
            back=generated_card.back,
        )
        cards.append(card)
        options.extend(
            FlashcardOption(
                card_id=card.id,
                option_text=generated_option.text,
                is_correct=generated_option.is_correct,
            )
            for generated_option in generated_card.options
        )

    session.add_all(cards)
    session.add_all(options)
    await session.commit()

    return PersistedFlashcardGenerationResult(
        topic_id=topic.id,
        topic_title=topic.title,
        requested_count=batch.requested_count,
        generated_cards=len(cards),
        generated_options=len(options),
    )


def _extract_text_payload(response: Any) -> str:
    content = getattr(response, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
            else:
                text = getattr(block, "text", None)
            if isinstance(text, str) and text:
                chunks.append(text)
        if chunks:
            return "".join(chunks)
    raise FlashcardGenerationError("Claude response did not contain any text output.")
