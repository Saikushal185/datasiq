from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core.config import get_settings
from backend.app.core.database import get_session_maker
from backend.app.models.db import Topic
from backend.app.services.ai_service import (
    FlashcardGenerationConfigurationError,
    FlashcardGenerationError,
    generate_topic_flashcards,
    persist_generated_flashcards,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate curriculum flashcards for a topic.")
    parser.add_argument("--topic-id", required=True, type=UUID, help="Topic UUID to generate cards for.")
    parser.add_argument("--card-count", type=int, default=12, help="Number of cards to generate.")
    parser.add_argument("--notes", default=None, help="Optional instructor notes to steer generation.")
    return parser


async def _run(topic_id: UUID, card_count: int, notes: str | None) -> dict[str, object]:
    settings = get_settings()
    session_maker = get_session_maker()
    async with session_maker() as session:
        topic = await session.get(Topic, topic_id)
        if topic is None:
            raise FlashcardGenerationError("Topic not found.")

        generated_batch = await generate_topic_flashcards(
            topic=topic,
            card_count=card_count,
            notes=notes,
            settings=settings,
        )
        persisted = await persist_generated_flashcards(session, topic=topic, batch=generated_batch)

    return persisted.model_dump(mode="json")


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        summary = asyncio.run(_run(args.topic_id, args.card_count, args.notes))
    except FlashcardGenerationConfigurationError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    except FlashcardGenerationError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1

    print(json.dumps(summary, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
