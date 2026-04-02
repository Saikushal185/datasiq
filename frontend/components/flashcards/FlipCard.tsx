"use client";

import type { FlashcardCardType, FlashcardDifficulty } from "@/lib/api";
import { cn } from "@/lib/utils";

type FlipCardProps = {
  front: string;
  back: string;
  hint?: string | null;
  topicTitle?: string;
  cardType?: FlashcardCardType;
  difficulty?: FlashcardDifficulty;
  flipped: boolean;
  onFlip: () => void;
  className?: string;
};

function FlipCard({
  front,
  back,
  hint,
  topicTitle,
  cardType,
  difficulty,
  flipped,
  onFlip,
  className
}: FlipCardProps) {
  return (
    <div className={cn("flashcard-stage", className)}>
      <button type="button" aria-pressed={flipped} onClick={onFlip} className="group relative block w-full text-left outline-none">
        <div
          className="flashcard-inner relative h-[24rem] w-full rounded-[1.75rem] border border-border/70 bg-white/80 shadow-soft"
          style={{ transform: flipped ? "rotateY(180deg)" : "rotateY(0deg)" }}
        >
          <div className="flashcard-face absolute inset-0 flex flex-col justify-between rounded-[1.75rem] bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(245,249,252,0.9))] p-5 sm:p-6">
            <div className="flex items-center justify-between gap-3">
              <div className="flex flex-wrap gap-2">
                {topicTitle ? <span className="flashcard-chip">{topicTitle}</span> : null}
                {cardType ? <span className="flashcard-chip">{cardType.replace("_", " ")}</span> : null}
              </div>
              {difficulty ? <span className="flashcard-chip capitalize">{difficulty}</span> : null}
            </div>

            <div className="flex flex-1 items-center justify-center px-1 py-8 text-center">
              <div className="max-w-xl space-y-4">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Prompt</p>
                <p className="text-2xl font-semibold leading-tight tracking-tight text-foreground sm:text-3xl">{front}</p>
                {hint ? <p className="text-sm leading-6 text-muted-foreground">{hint}</p> : null}
                <p className="text-xs text-muted-foreground">Tap to flip the card.</p>
              </div>
            </div>
          </div>

          <div className="flashcard-face flashcard-face-back absolute inset-0 flex flex-col justify-between rounded-[1.75rem] bg-[linear-gradient(180deg,rgba(15,118,110,0.98),rgba(10,90,84,0.96))] p-5 text-white sm:p-6">
            <div className="flex items-center justify-between gap-3">
              <span className="flashcard-chip border-white/15 bg-white/10 text-white/80">Answer</span>
              {difficulty ? <span className="flashcard-chip border-white/15 bg-white/10 text-white/80 capitalize">{difficulty}</span> : null}
            </div>

            <div className="flex flex-1 items-center justify-center px-1 py-8 text-center">
              <div className="max-w-xl space-y-4">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-white/75">Back side</p>
                <p className="text-2xl font-semibold leading-tight tracking-tight sm:text-3xl">{back}</p>
                <p className="text-sm leading-6 text-white/75">Rate yourself once you’ve processed the answer.</p>
              </div>
            </div>
          </div>
        </div>
      </button>
    </div>
  );
}

export { FlipCard };
