"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import confetti from "canvas-confetti";
import { motion } from "framer-motion";
import { RotateCcw, ShieldAlert, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useBlitzFlashcardsQuery } from "@/lib/queries";
import { cn } from "@/lib/utils";

type BlitzAnswer = {
  cardId: string;
  selectedOptionId: string;
  selectedOptionText: string;
  correct: boolean;
};

const BLITZ_CARD_COUNT = 10;
const BLITZ_DURATION_SECONDS = 60;

function BlitzMode() {
  const blitzQuery = useBlitzFlashcardsQuery();
  const cards = useMemo(() => (blitzQuery.data?.cards ?? []).slice(0, BLITZ_CARD_COUNT), [blitzQuery.data?.cards]);
  const durationSeconds = BLITZ_DURATION_SECONDS;
  const [timeLeft, setTimeLeft] = useState(durationSeconds);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<BlitzAnswer[]>([]);
  const [feedback, setFeedback] = useState<"correct" | "incorrect" | null>(null);
  const [summaryShown, setSummaryShown] = useState(false);
  const celebrateOnceRef = useRef(false);
  const feedbackTimeoutRef = useRef<number | null>(null);
  const answeringRef = useRef(false);

  const resetSession = () => {
    if (feedbackTimeoutRef.current !== null) {
      window.clearTimeout(feedbackTimeoutRef.current);
      feedbackTimeoutRef.current = null;
    }
    answeringRef.current = false;
    setTimeLeft(durationSeconds);
    setCurrentIndex(0);
    setAnswers([]);
    setFeedback(null);
    setSummaryShown(false);
    celebrateOnceRef.current = false;
  };

  useEffect(() => {
    if (currentIndex >= cards.length && cards.length > 0) {
      setSummaryShown(true);
    }
  }, [cards.length, currentIndex]);

  useEffect(() => {
    if (summaryShown) {
      return;
    }

    const interval = window.setInterval(() => {
      setTimeLeft((current) => {
        if (current <= 1) {
          window.clearInterval(interval);
          setSummaryShown(true);
          return 0;
        }
        return current - 1;
      });
    }, 1000);

    return () => window.clearInterval(interval);
  }, [summaryShown]);

  useEffect(() => {
    return () => {
      if (feedbackTimeoutRef.current !== null) {
        window.clearTimeout(feedbackTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (feedbackTimeoutRef.current === null) {
      return;
    }

    window.clearTimeout(feedbackTimeoutRef.current);
    feedbackTimeoutRef.current = null;
    answeringRef.current = false;
    setFeedback(null);
  }, [cards]);

  useEffect(() => {
    if (!summaryShown || celebrateOnceRef.current) {
      return;
    }

    const score = answers.filter((answer) => answer.correct).length;
    if (score >= 8) {
      celebrateOnceRef.current = true;
      void confetti({
        particleCount: 140,
        spread: 74,
        startVelocity: 36,
        origin: { y: 0.7 }
      });
    }
  }, [answers, summaryShown]);

  const activeCard = cards[currentIndex];
  const totalCorrect = useMemo(() => answers.filter((answer) => answer.correct).length, [answers]);
  const currentScore = cards.length === 0 ? 0 : (totalCorrect / cards.length) * 100;

  const handleAnswer = (selectedOptionId: string, selectedOptionText: string) => {
    if (!activeCard || summaryShown || answeringRef.current) {
      return;
    }

    answeringRef.current = true;
    const correct = selectedOptionText === activeCard.back;
    setAnswers((current) => [
      ...current,
      {
        cardId: activeCard.id,
        selectedOptionId,
        selectedOptionText,
        correct
      }
    ]);
    setFeedback(correct ? "correct" : "incorrect");

    if (feedbackTimeoutRef.current !== null) {
      window.clearTimeout(feedbackTimeoutRef.current);
    }

    feedbackTimeoutRef.current = window.setTimeout(() => {
      setFeedback(null);
      answeringRef.current = false;
      const nextIndex = currentIndex + 1;
      if (nextIndex >= cards.length) {
        setSummaryShown(true);
        return;
      }
      setCurrentIndex(nextIndex);
      feedbackTimeoutRef.current = null;
    }, 360);
  };

  if (blitzQuery.isLoading) {
    return (
      <Card className="overflow-hidden">
        <CardHeader>
          <div className="flex items-center gap-3">
            <Skeleton className="h-5 w-28" />
            <Skeleton className="h-5 w-16" />
          </div>
          <Skeleton className="h-8 w-64 max-w-full" />
          <Skeleton className="h-4 w-80 max-w-full" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-2.5 w-full" />
          <Skeleton className="h-[22rem] w-full rounded-[1.5rem]" />
          <div className="grid gap-3 sm:grid-cols-3">
            <Skeleton className="h-11 rounded-[1.25rem]" />
            <Skeleton className="h-11 rounded-[1.25rem]" />
            <Skeleton className="h-11 rounded-[1.25rem]" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (blitzQuery.isError) {
    return (
      <div className="error-state">
        <ShieldAlert className="h-10 w-10 text-danger" />
        <div className="space-y-1">
          <h2 className="text-lg font-semibold">Blitz mode is unavailable</h2>
          <p className="text-sm text-muted-foreground">We could not load a quick-fire set. Please try again in a moment.</p>
        </div>
        <Button type="button" variant="outline" onClick={() => void blitzQuery.refetch()}>
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
          <h2 className="text-lg font-semibold">No blitz cards yet</h2>
          <p className="text-sm text-muted-foreground">
            Once the backend serves MCQ cards from your current topic, they&apos;ll appear here for a 60-second sprint.
          </p>
        </div>
      </div>
    );
  }

  if (cards.length < BLITZ_CARD_COUNT) {
    return (
      <div className="error-state">
        <ShieldAlert className="h-10 w-10 text-danger" />
        <div className="space-y-1">
          <h2 className="text-lg font-semibold">Blitz mode needs 10 cards</h2>
          <p className="text-sm text-muted-foreground">
            The sprint only starts when a full 10-card MCQ set is ready. Reload once the backend serves the complete batch.
          </p>
        </div>
        <Button type="button" variant="outline" onClick={() => void blitzQuery.refetch()}>
          Reload set
        </Button>
      </div>
    );
  }

  if (summaryShown) {
    return (
      <Card className="overflow-hidden">
        <CardHeader className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={currentScore >= 80 ? "success" : "outline"}>
              {totalCorrect}/{cards.length} correct
            </Badge>
            <Badge variant="secondary">{Math.max(0, timeLeft)}s left</Badge>
          </div>
          <CardTitle>Blitz summary</CardTitle>
          <CardDescription>
            You answered {totalCorrect} of {cards.length} cards correctly. {currentScore >= 80 ? "Strong sprint." : "One more lap would help lock this in."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <Progress value={Math.min(100, currentScore)} />
          <div className="space-y-3">
            {answers.map((answer) => {
              const card = cards.find((item) => item.id === answer.cardId);
              if (!card) {
                return null;
              }

              return (
                <div
                  key={answer.cardId}
                  className={cn(
                    "rounded-2xl border px-4 py-3 text-sm",
                    answer.correct ? "border-success/30 bg-success/10 text-success" : "border-danger/30 bg-danger/10 text-danger"
                  )}
                >
                  <p className="font-medium">{card.front}</p>
                  <p className="mt-1 text-xs opacity-80">{answer.correct ? "Correct" : `Missed - correct answer: ${card.back}`}</p>
                </div>
              );
            })}
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Button type="button" className="w-full sm:w-auto" onClick={resetSession}>
              <RotateCcw className="h-4 w-4" />
              Restart sprint
            </Button>
            <Button
              type="button"
              variant="outline"
              className="w-full sm:w-auto"
              onClick={() => {
                resetSession();
                void blitzQuery.refetch();
              }}
            >
              Load a new set
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!activeCard) {
    return (
      <div className="error-state">
        <ShieldAlert className="h-10 w-10 text-danger" />
        <div className="space-y-1">
          <h2 className="text-lg font-semibold">The blitz set changed mid-sprint</h2>
          <p className="text-sm text-muted-foreground">
            Reload the session to get a stable 10-card sprint before continuing.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            resetSession();
            void blitzQuery.refetch();
          }}
        >
          Reload sprint
        </Button>
      </div>
    );
  }

  return (
    <Card className="overflow-hidden">
      <CardHeader className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge>Blitz mode</Badge>
          <Badge variant="secondary">{blitzQuery.data?.streakMultiplier ?? 1}x streak boost</Badge>
          <Badge variant="outline">
            {currentIndex + 1}/{cards.length}
          </Badge>
        </div>
        <div className="space-y-2">
          <CardTitle>60-second sprint</CardTitle>
          <CardDescription>
            Tap an option as fast as you can. The feedback flash is instant, and the timer keeps moving even when you hesitate.
          </CardDescription>
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
            <span>Timer</span>
            <span>{timeLeft}s</span>
          </div>
          <div className="overflow-hidden rounded-full bg-secondary/70">
            <motion.div
              className="h-2.5 rounded-full bg-primary"
              initial={false}
              animate={{ width: `${(timeLeft / durationSeconds) * 100}%` }}
              transition={{ duration: 0.35, ease: "easeOut" }}
            />
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <motion.div
          key={activeCard.id}
          className={cn(
            "rounded-[1.5rem] border border-border/70 p-4 shadow-soft",
            feedback === "correct" ? "feedback-flash-correct" : feedback === "incorrect" ? "feedback-flash-wrong" : "bg-white/80"
          )}
          initial={{ opacity: 0.96, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.18 }}
        >
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <Badge variant="outline">{activeCard.difficulty}</Badge>
              <Badge variant="secondary">{activeCard.topicTitle}</Badge>
            </div>
            <p className="text-xl font-semibold leading-tight tracking-tight text-foreground">{activeCard.front}</p>
          </div>
        </motion.div>

        <div className="grid gap-3 sm:grid-cols-2">
          {activeCard.options.map((option) => (
            <button
              key={option.id}
              type="button"
              className="flashcard-option"
              onClick={() => handleAnswer(option.id, option.text)}
              disabled={feedback !== null}
            >
              <span>{option.text}</span>
              <span className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Tap</span>
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export { BlitzMode };
