"use client";

import { AlertTriangle, Flame, RotateCcw, ShieldCheck } from "lucide-react";

import FreezeToken from "@/components/streak/FreezeToken";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import type { StreakResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

type StreakBarProps = {
  streak?: StreakResponse;
  isLoading?: boolean;
  isError?: boolean;
  freezePending?: boolean;
  onRetry?: () => void;
  onUseFreeze: () => void;
  className?: string;
};

function weeklyStateClassName(state: StreakResponse["weeklyBar"][number]["state"]): string {
  switch (state) {
    case "done":
      return "border-success/20 bg-success text-success-foreground";
    case "today":
      return "border-primary/20 bg-primary text-primary-foreground";
    case "warning":
      return "border-danger/20 bg-danger text-danger-foreground";
    default:
      return "border-border/80 bg-muted text-muted-foreground";
  }
}

export default function StreakBar({
  streak,
  isLoading = false,
  isError = false,
  freezePending = false,
  onRetry,
  onUseFreeze,
  className
}: StreakBarProps) {
  if (isLoading) {
    return (
      <aside className={cn("surface p-4 sm:p-5", className)}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-col gap-3">
            <Skeleton className="h-5 w-28" />
            <Skeleton className="h-10 w-52" />
            <div className="flex gap-2">
              {Array.from({ length: 5 }).map((_, index) => (
                <Skeleton key={index} className="h-12 w-12 rounded-2xl" />
              ))}
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:min-w-[26rem]">
            <Skeleton className="h-32 rounded-[1.25rem]" />
            <Skeleton className="h-32 rounded-[1.25rem]" />
          </div>
        </div>
      </aside>
    );
  }

  if (isError || !streak) {
    return (
      <aside className={cn("surface p-4 sm:p-5", className)}>
        <div className="error-state">
          <AlertTriangle className="h-10 w-10 text-danger" />
          <div className="space-y-1">
            <h2 className="text-lg font-semibold">We couldn't load your streak</h2>
            <p className="text-sm text-muted-foreground">
              The streak bar needs the latest streak state. Try again once the backend is reachable.
            </p>
          </div>
          {onRetry ? (
            <Button type="button" variant="outline" onClick={onRetry}>
              Retry
            </Button>
          ) : null}
        </div>
      </aside>
    );
  }

  const recoveryPercent =
    streak.recovery.reviewsRequired === 0
      ? 0
      : Math.min(100, (streak.recovery.reviewsCompleted / streak.recovery.reviewsRequired) * 100);

  return (
    <aside className={cn("surface p-4 sm:p-5", className)}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="flex size-14 items-center justify-center rounded-[1.25rem] bg-primary text-primary-foreground shadow-soft">
              <Flame className="h-7 w-7" />
            </div>
            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={streak.todayCompleted ? "success" : streak.graceWindow.active ? "danger" : "secondary"}>
                  {streak.todayCompleted ? "Today complete" : streak.graceWindow.active ? "Grace window active" : "Study today"}
                </Badge>
                <Badge variant="outline">Best: {streak.longestStreak} days</Badge>
              </div>
              <h2 className="text-2xl font-semibold tracking-tight text-foreground">
                {streak.currentStreak}-day streak
              </h2>
              <p className="text-sm text-muted-foreground">
                {streak.graceWindow.active
                  ? `You missed ${streak.graceWindow.missedDate ?? "a day"}. Recover or freeze before the grace window closes.`
                  : streak.todayCompleted
                    ? "You locked in today's study and kept the streak alive."
                    : "One review or one quiz attempt today keeps the streak moving."}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {streak.weeklyBar.map((day) => (
              <div
                key={day.date}
                className={cn(
                  "flex min-w-14 flex-col items-center rounded-2xl border px-3 py-2 text-center shadow-soft",
                  weeklyStateClassName(day.state)
                )}
              >
                <span className="text-[0.7rem] font-semibold uppercase tracking-[0.16em]">{day.label}</span>
                <span className="mt-1 text-xs opacity-85">{day.date.slice(5)}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="grid gap-3 lg:min-w-[28rem] lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <section className="rounded-[1.25rem] border border-border/70 bg-white/70 p-4 shadow-soft">
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1">
                <p className="text-sm font-semibold text-foreground">Recovery session</p>
                <p className="text-sm text-muted-foreground">
                  {streak.recovery.eligible
                    ? `${streak.recovery.reviewsRemaining} reviews left to save the streak.`
                    : "No recovery session is currently required."}
                </p>
              </div>
              <span className="rounded-full bg-secondary p-2 text-secondary-foreground">
                <RotateCcw className="h-4 w-4" />
              </span>
            </div>
            <div className="mt-4 space-y-2">
              <Progress value={recoveryPercent} />
              <div className="flex items-center justify-between text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
                <span>{streak.recovery.reviewsCompleted} done</span>
                <span>{streak.recovery.reviewsRequired} required</span>
              </div>
            </div>
            {streak.freezeApplied ? (
              <div className="mt-4 rounded-2xl border border-success/20 bg-success/10 px-4 py-3 text-sm text-success">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4" />
                  Freeze protection is active for the missed day.
                </div>
              </div>
            ) : null}
          </section>

          <FreezeToken
            freezeTokensRemaining={streak.freezeTokensRemaining}
            graceActive={streak.graceWindow.active}
            freezeApplied={streak.freezeApplied}
            disabled={freezePending}
            onUseFreeze={onUseFreeze}
          />
        </div>
      </div>
    </aside>
  );
}
