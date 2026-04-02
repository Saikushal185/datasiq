"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import confetti from "canvas-confetti";
import Link from "next/link";
import { RefreshCcw, Sparkles, TimerReset } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { FlipCard } from "@/components/flashcards/FlipCard";
import { RatingButtons } from "@/components/flashcards/RatingButtons";
import { useDueFlashcardsQuery, useRecoverStreakMutation, useStreakQuery, useSubmitFlashcardReviewMutation } from "@/lib/queries";
import type { FlashcardCardResponse, FlashcardReviewRating } from "@/lib/api";
import { RECOVERY_BANNER_PARAM, shouldShowRecoveryBanner } from "@/lib/streak-utils";

function FlashcardsLoadingState() {
  return (
    <main className="page-shell">
      <section className="space-y-4">
        <Skeleton className="h-5 w-28" />
        <Skeleton className="h-10 w-72 max-w-full" />
        <Skeleton className="h-4 w-96 max-w-full" />
      </section>
      <div className="mt-6 space-y-4">
        <Skeleton className="h-2.5 w-full" />
        <Skeleton className="h-[24rem] w-full rounded-[1.75rem]" />
        <div className="grid gap-3 sm:grid-cols-3">
          <Skeleton className="h-11 rounded-[1.25rem]" />
          <Skeleton className="h-11 rounded-[1.25rem]" />
          <Skeleton className="h-11 rounded-[1.25rem]" />
        </div>
      </div>
    </main>
  );
}

function FlashcardsPageContent() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const dueQuery = useDueFlashcardsQuery();
  const streakQuery = useStreakQuery();
  const reviewMutation = useSubmitFlashcardReviewMutation();
  const recoverMutation = useRecoverStreakMutation();
  const [visibleCards, setVisibleCards] = useState<FlashcardCardResponse[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [busyRating, setBusyRating] = useState<FlashcardReviewRating | null>(null);
  const [elapsedStartedAt, setElapsedStartedAt] = useState<number | null>(null);
  const initialQueueSizeRef = useRef(0);
  const seededCardsSignatureRef = useRef<string | null>(null);

  useEffect(() => {
    if (!dueQuery.data?.cards) {
      return;
    }

    const nextSignature = dueQuery.data.cards.map((card) => card.id).join("|");
    const shouldResetSessionQueue =
      seededCardsSignatureRef.current === null || (seededCardsSignatureRef.current === "" && nextSignature !== "");

    if (seededCardsSignatureRef.current === nextSignature) {
      return;
    }

    if (shouldResetSessionQueue) {
      initialQueueSizeRef.current = dueQuery.data.totalDue;
    }

    seededCardsSignatureRef.current = nextSignature;
    setVisibleCards(dueQuery.data.cards);
    setCurrentIndex(0);
    setFlipped(false);
    setElapsedStartedAt(null);
    setBusyRating(null);
  }, [dueQuery.data?.cards]);

  useEffect(() => {
    if (currentIndex >= visibleCards.length && visibleCards.length > 0) {
      setCurrentIndex(visibleCards.length - 1);
    }
  }, [currentIndex, visibleCards.length]);

  const activeCard = visibleCards[currentIndex];
  const sessionFocus = dueQuery.data?.sessionFocus ?? "No cards are due right now.";
  const totalDue = dueQuery.data?.totalDue ?? 0;
  const sessionQueueSize = Math.max(initialQueueSizeRef.current, totalDue);
  const totalReviewed = Math.max(sessionQueueSize - visibleCards.length, 0);
  const showRecoveryBanner = shouldShowRecoveryBanner(searchParams.get(RECOVERY_BANNER_PARAM));
  const recoveryReviewsRequired = streakQuery.data?.recovery.reviewsRequired ?? 20;
  const isHydratingVisibleCards = seededCardsSignatureRef.current === null && (dueQuery.data?.cards.length ?? 0) > 0;
  const recoveryBanner = showRecoveryBanner ? (
    <div className="rounded-[1.5rem] border border-danger/20 bg-danger/10 px-5 py-4 text-sm text-danger shadow-soft">
      Recovery session armed. Clear {recoveryReviewsRequired} cards in one streak-saving push to recover the missed day before the grace window closes.
    </div>
  ) : null;

  useEffect(() => {
    if (!activeCard || !flipped || elapsedStartedAt !== null) {
      return;
    }

    setElapsedStartedAt(Date.now());
  }, [activeCard, elapsedStartedAt, flipped]);

  const handleFlip = () => {
    setFlipped((current) => {
      const next = !current;
      if (!next) {
        setElapsedStartedAt(null);
      }
      return next;
    });
  };

  const goToNextCard = () => {
    setVisibleCards((current) => current.filter((_, index) => index !== currentIndex));
    setCurrentIndex(0);
    setFlipped(false);
    setElapsedStartedAt(null);
    setBusyRating(null);
  };

  const handleRate = async (rating: FlashcardReviewRating) => {
    if (!activeCard || reviewMutation.isPending) {
      return;
    }

    setBusyRating(rating);
    const elapsedMs = elapsedStartedAt === null ? 0 : Date.now() - elapsedStartedAt;

    try {
      const response = await reviewMutation.mutateAsync({
        cardId: activeCard.id,
        rating,
        elapsedMs
      });

      if (rating === "easy" || response.celebrate) {
        void confetti({
          particleCount: 120,
          spread: 68,
          origin: { y: 0.72 }
        });
      }

      if (
        showRecoveryBanner &&
        !streakQuery.data?.recovery.applied &&
        response.reviewsCompletedThisSession !== null &&
        response.reviewsCompletedThisSession >= recoveryReviewsRequired
      ) {
        try {
          await recoverMutation.mutateAsync({
            reviewsCompleted: response.reviewsCompletedThisSession
          });
          router.replace(pathname);
        } catch {
          // Keep the user on the review flow and surface the backend message below.
        }
      }

      goToNextCard();
    } finally {
      setBusyRating(null);
    }
  };

  if (dueQuery.isLoading) {
    return <FlashcardsLoadingState />;
  }

  if (isHydratingVisibleCards) {
    return <FlashcardsLoadingState />;
  }

  if (dueQuery.isError) {
    return (
      <main className="page-shell">
        <div className="error-state mx-auto mt-8 max-w-xl">
          <Sparkles className="h-10 w-10 text-danger" />
          <div className="space-y-1">
            <h1 className="text-xl font-semibold">We couldn't load your due cards</h1>
            <p className="text-sm text-muted-foreground">
              The flashcard queue failed to load. You can retry or come back once the backend is ready.
            </p>
          </div>
          <Button type="button" variant="outline" onClick={() => void dueQuery.refetch()}>
            Retry queue
          </Button>
        </div>
      </main>
    );
  }

  if (!dueQuery.isLoading && !dueQuery.isError && visibleCards.length === 0) {
    return (
      <main className="page-shell">
        {recoveryBanner}
        <section className="study-panel mx-auto mt-8 max-w-2xl space-y-6">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="success">All caught up</Badge>
            <Badge variant="outline">{sessionFocus}</Badge>
          </div>
          <div className="space-y-3">
            <h1 className="section-title">No flashcards are due right now</h1>
            <p className="section-subtitle">{sessionFocus}</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <Button asChild>
              <Link href="/flashcards/blitz">
                <TimerReset className="h-4 w-4" />
                Blitz mode
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/progress">
                <RefreshCcw className="h-4 w-4" />
                Boss round
              </Link>
            </Button>
            <Button type="button" variant="secondary" onClick={() => void dueQuery.refetch()}>
              Refresh queue
            </Button>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="page-shell">
      <section className="space-y-6">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge>Recall mode</Badge>
            <Badge variant="secondary">{totalDue} due</Badge>
            <Badge variant="outline">
              {totalReviewed}/{Math.max(sessionQueueSize, 1)} cleared
            </Badge>
          </div>
          <h1 className="section-title">Study the next due card</h1>
          <p className="section-subtitle">{sessionFocus}</p>
        </div>

        {recoveryBanner}

        <Card className="overflow-hidden">
          <CardHeader className="space-y-3">
            <CardTitle>{activeCard?.topicTitle ?? "Flashcards"}</CardTitle>
            <CardDescription>
              Flip the card to reveal the answer, then choose the rating that matches your recall.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {activeCard ? (
              <>
                <FlipCard
                  front={activeCard.front}
                  back={activeCard.back}
                  hint={activeCard.hint}
                  topicTitle={activeCard.topicTitle}
                  cardType={activeCard.cardType}
                  difficulty={activeCard.difficulty}
                  flipped={flipped}
                  onFlip={handleFlip}
                />
                {flipped ? (
                  <RatingButtons
                    onRate={handleRate}
                    middleRating={activeCard.difficulty === "hard" ? "hard" : "okay"}
                    pendingRating={busyRating}
                    disabled={reviewMutation.isPending}
                  />
                ) : (
                  <div className="rounded-[1.25rem] border border-dashed border-border/90 bg-secondary/25 px-4 py-4 text-sm text-muted-foreground">
                    Flip the card first, then your rating buttons will appear here.
                  </div>
                )}
                {reviewMutation.isError ? (
                  <p className="text-sm text-danger">
                    {reviewMutation.error.message}
                  </p>
                ) : null}
                {recoverMutation.isError ? (
                  <p className="text-sm text-danger">
                    {recoverMutation.error.message}
                  </p>
                ) : null}
              </>
            ) : (
              <div className="empty-state">
                <Sparkles className="h-10 w-10 text-primary" />
                <p className="text-sm text-muted-foreground">No active flashcard is available.</p>
              </div>
            )}
          </CardContent>
        </Card>
      </section>
    </main>
  );
}

export default function FlashcardsPage() {
  return (
    <Suspense fallback={<FlashcardsLoadingState />}>
      <FlashcardsPageContent />
    </Suspense>
  );
}
