"use client";

import type { FlashcardReviewRating } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

type RatingButtonsProps = {
  onRate: (rating: FlashcardReviewRating) => void;
  middleRating?: Exclude<FlashcardReviewRating, "forgot" | "easy">;
  pendingRating?: FlashcardReviewRating | null;
  disabled?: boolean;
  className?: string;
};

function RatingButtons({ onRate, middleRating = "okay", pendingRating, disabled = false, className }: RatingButtonsProps) {
  const isBusy = disabled || pendingRating !== null;
  const middleLabel = middleRating === "hard" ? "Hard" : "Okay";

  return (
    <div className={cn("grid gap-3 sm:grid-cols-3", className)}>
      <Button
        type="button"
        variant="danger"
        size="lg"
        className="w-full rounded-[1.25rem]"
        disabled={isBusy}
        onClick={() => onRate("forgot")}
      >
        Forgot
      </Button>
      <Button
        type="button"
        variant="secondary"
        size="lg"
        className="w-full rounded-[1.25rem]"
        disabled={isBusy}
        onClick={() => onRate(middleRating)}
      >
        <span className="flex flex-col leading-none">
          <span>{middleLabel}</span>
          <span className="text-[0.7rem] font-normal text-secondary-foreground/70">Middle confidence</span>
        </span>
      </Button>
      <Button
        type="button"
        size="lg"
        className="w-full rounded-[1.25rem]"
        disabled={isBusy}
        onClick={() => onRate("easy")}
      >
        Easy
      </Button>
    </div>
  );
}

export { RatingButtons };
