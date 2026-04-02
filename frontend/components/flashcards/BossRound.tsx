"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import confetti from "canvas-confetti";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, RotateCcw, Sparkles } from "lucide-react";

import { FlipCard } from "@/components/flashcards/FlipCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useBossRoundFlashcardsQuery } from "@/lib/queries";
import type { FlashcardCardResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

type BossRoundProps = {
  topicId: string;
};

type BossResult = {
  cardId: string;
  correct: boolean;
};

function BossRound({ topicId }: BossRoundProps) {
  const bossQuery = useBossRoundFlashcardsQuery(topicId);
  const cards = bossQuery.data?.cards ?? [];
  const passThreshold = bossQuery.data?.passThreshold ?? 0.8;
  const [currentIndex, setCurrentIndex] = useState(0);
  const [results, setResults] = useState<BossResult[]>([]);
  const [flipped, setFlipped] = useState(false);
  const [selectedOptionId, setSelectedOptionId] = useState<string | null>(null);
  const [summaryVisible, setSummaryVisible] = useState(false);
  const [isAdvancing, setIsAdvancing] = useState(false);
  const celebrateRef = useRef(false);
  const advanceTimeoutRef = useRef<number | null>(null);
  const advancingRef = useRef(false);

  const setAdvancing = (value: boolean) => {
    advancingRef.current = value;
    setIsAdvancing(value);
  };

  useEffect(() => {
    if (advanceTimeoutRef.current !== null) {
      window.clearTimeout(advanceTimeoutRef.current);
      advanceTimeoutRef.current = null;
    }
    setCurrentIndex(0);
    setResults([]);
    setFlipped(false);
    setSelectedOptionId(null);
    setSummaryVisible(false);
    setAdvancing(false);
    celebrateRef.current = false;
  }, [topicId]);

  useEffect(() => {
    return () => {
      if (advanceTimeoutRef.current !== null) {
        window.clearTimeout(advanceTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (summaryVisible || results.length !== cards.length || cards.length === 0) {
      return;
    }

    setSummaryVisible(true);
  }, [cards.length, results.length, summaryVisible]);

  const activeCard = cards[currentIndex];
  const scoredCount = results.filter((result) => result.correct).length;
  const score = cards.length === 0 ? 0 : scoredCount / cards.length;
  const passed = cards.length > 0 && score >= passThreshold;

  useEffect(() => {
    if (!summaryVisible || celebrateRef.current || !passed) {
      return;
    }

    celebrateRef.current = true;
    void confetti({
      particleCount: 180,
      spread: 82,
      startVelocity: 42,
      origin: { y: 0.68 }
    });
  }, [passed, summaryVisible]);

  const revisitConcepts = useMemo(() => {
    const missedCards = results.filter((result) => !result.correct).map((result) => result.cardId);
    return cards
      .filter((card) => missedCards.includes(card.id))
      .map((card) => card.front)
      .slice(0, 5);
  }, [cards, results]);

  const resetRound = () => {
    if (advanceTimeoutRef.current !== null) {
      window.clearTimeout(advanceTimeoutRef.current);
      advanceTimeoutRef.current = null;
    }
    setCurrentIndex(0);
    setResults([]);
    setFlipped(false);
    setSelectedOptionId(null);
    setSummaryVisible(false);
    setAdvancing(false);
    celebrateRef.current = false;
  };

  const advance = (cardId: string, correct: boolean) => {
    setResults((current) => [...current, { cardId, correct }]);
    const nextIndex = currentIndex + 1;
    setSelectedOptionId(null);
    setFlipped(false);
    setAdvancing(false);

    if (nextIndex < cards.length) {
      setCurrentIndex(nextIndex);
      return;
    }

    setSummaryVisible(true);
  };

  const handleAnswer = (card: FlashcardCardResponse, optionId: string) => {
    if (advancingRef.current) {
      return;
    }

    const selectedOption = card.options.find((option) => option.id === optionId);
    if (!selectedOption) {
      return;
    }

    setSelectedOptionId(optionId);
    setAdvancing(true);
    const correct = selectedOption.text === card.back;
    if (advanceTimeoutRef.current !== null) {
      window.clearTimeout(advanceTimeoutRef.current);
    }
    advanceTimeoutRef.current = window.setTimeout(() => {
      advance(card.id, correct);
      advanceTimeoutRef.current = null;
    }, 280);
  };

  const handleSelfCheck = (card: FlashcardCardResponse, correct: boolean) => {
    if (advancingRef.current) {
      return;
    }

    setAdvancing(true);
    if (advanceTimeoutRef.current !== null) {
      window.clearTimeout(advanceTimeoutRef.current);
    }
    advanceTimeoutRef.current = window.setTimeout(() => {
      advance(card.id, correct);
      advanceTimeoutRef.current = null;
    }, 0);
  };

  if (bossQuery.isLoading) {
    return (
      <Card className="overflow-hidden">
        <CardHeader>
          <Skeleton className="h-5 w-36" />
          <Skeleton className="h-8 w-72 max-w-full" />
          <Skeleton className="h-4 w-80 max-w-full" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-2.5 w-full" />
          <Skeleton className="h-[22rem] w-full rounded-[1.5rem]" />
        </CardContent>
      </Card>
    );
  }

  if (bossQuery.isError) {
    return (
      <div className="error-state">
        <AlertTriangle className="h-10 w-10 text-danger" />
        <div className="space-y-1">
          <h2 className="text-lg font-semibold">Boss round unavailable</h2>
          <p className="text-sm text-muted-foreground">
            We could not load the boss set for this topic. Try again once the study data is ready.
          </p>
        </div>
        <Button type="button" variant="outline" onClick={() => void bossQuery.refetch()}>
          Try again
        </Button>
      </div>
    );
  }

  if (cards.length === 0) {
    return (
      <div className="empty-state">
        <Sparkles className="h-10 w-10 text-primary" />
        <div className="space-y-1">
          <h2 className="text-lg font-semibold">No boss-round cards yet</h2>
          <p className="text-sm text-muted-foreground">
            The backend will return a 15-card boss set here once the topic has completed material.
          </p>
        </div>
      </div>
    );
  }

  if (summaryVisible) {
    return (
      <Card className="overflow-hidden">
        <CardHeader className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={passed ? "success" : "danger"}>{passed ? "Boss round passed" : "Needs another pass"}</Badge>
            <Badge variant="secondary">
              {scoredCount}/{cards.length} correct
            </Badge>
            <Badge variant="outline">{Math.round(score * 100)}%</Badge>
          </div>
          <CardTitle>{bossQuery.data?.topic.title ?? "Boss round"}</CardTitle>
          <CardDescription>
            {passed
              ? "You cleared the 80% threshold. The next backend step will be able to mark the topic completed."
              : "You were close. Review the concepts below before trying again."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <Progress value={Math.min(100, score * 100)} />
          <div className="space-y-3">
            {revisitConcepts.length > 0 ? (
              revisitConcepts.map((concept) => (
                <div key={concept} className="rounded-2xl border border-danger/20 bg-danger/10 px-4 py-3 text-sm text-danger">
                  {concept}
                </div>
              ))
            ) : (
              <div className="rounded-2xl border border-success/20 bg-success/10 px-4 py-3 text-sm text-success">
                No revisit concepts were recorded. Great work.
              </div>
            )}
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Button type="button" className="w-full sm:w-auto" onClick={resetRound}>
              <RotateCcw className="h-4 w-4" />
              Retry boss round
            </Button>
            <Button type="button" variant="outline" className="w-full sm:w-auto" onClick={() => void bossQuery.refetch()}>
              Reload cards
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden">
      <CardHeader className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge>Boss round</Badge>
          <Badge variant={bossQuery.data?.topic.completed ? "success" : "secondary"}>
            {bossQuery.data?.topic.completed ? "Already completed" : "Unlocking"}
          </Badge>
          <Badge variant="outline">
            {currentIndex + 1}/{cards.length}
          </Badge>
        </div>
        <div className="space-y-2">
          <CardTitle>{bossQuery.data?.topic.title ?? "Boss round"}</CardTitle>
          <CardDescription>
            Score at least 80% to clear the topic. Mixed card types are handled by either MCQ scoring or a quick self-check.
          </CardDescription>
        </div>
        <Progress value={Math.min(100, (currentIndex / cards.length) * 100)} />
      </CardHeader>
      <CardContent className="space-y-5">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeCard.id}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.2 }}
          >
            <FlipCard
              front={activeCard.front}
              back={activeCard.back}
              hint={activeCard.hint}
              topicTitle={activeCard.topicTitle}
              cardType={activeCard.cardType}
              difficulty={activeCard.difficulty}
              flipped={flipped}
              onFlip={() => setFlipped((current) => !current)}
            />
          </motion.div>
        </AnimatePresence>

        {activeCard.cardType === "mcq" && activeCard.options.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {activeCard.options.map((option) => {
              const isSelected = selectedOptionId === option.id;
              const isCorrect = option.text === activeCard.back;
              return (
                <button
                  key={option.id}
                  type="button"
                  className={cn("flashcard-option", isSelected ? "flashcard-option-selected" : "")}
                  disabled={selectedOptionId !== null || isAdvancing}
                  onClick={() => handleAnswer(activeCard, option.id)}
                >
                  <span>{option.text}</span>
                  <span className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                    {selectedOptionId !== null ? (isCorrect ? "Correct" : "Try again") : "Choose"}
                  </span>
                </button>
              );
            })}
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            <Button
              type="button"
              variant="secondary"
              size="lg"
              className="w-full rounded-[1.25rem]"
              disabled={isAdvancing}
              onClick={() => handleSelfCheck(activeCard, true)}
            >
              <CheckCircle2 className="h-4 w-4" />
              I knew it
            </Button>
            <Button
              type="button"
              variant="danger"
              size="lg"
              className="w-full rounded-[1.25rem]"
              disabled={isAdvancing}
              onClick={() => handleSelfCheck(activeCard, false)}
            >
              <AlertTriangle className="h-4 w-4" />
              I missed it
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export { BossRound };
