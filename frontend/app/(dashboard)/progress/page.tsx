"use client";

import Link from "next/link";
import { AlertTriangle, ArrowRight, BarChart3, CheckCircle2, Circle, Lock, Sparkles } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { ProgressPathTopicResponse } from "@/lib/queries";
import { useProgressPathQuery, useProgressStatsQuery } from "@/lib/queries";
import { cn } from "@/lib/utils";

type ProgressChartDatum = ProgressPathTopicResponse & {
  masteryPercent: number;
};

const difficultyLabels: Record<ProgressPathTopicResponse["difficulty"], string> = {
  beginner: "Beginner",
  intermediate: "Intermediate",
  advanced: "Advanced"
};

const statusMeta: Record<
  ProgressPathTopicResponse["status"],
  {
    label: string;
    badgeVariant: "default" | "secondary" | "outline" | "success" | "danger";
    icon: typeof Lock;
    iconClassName: string;
    cardClassName: string;
    markerClassName: string;
    ctaLabel?: string;
    ctaHref?: (topicId: string) => string;
  }
> = {
  locked: {
    label: "Locked",
    badgeVariant: "outline",
    icon: Lock,
    iconClassName: "text-muted-foreground",
    cardClassName: "border-border/70 bg-white/60",
    markerClassName: "border-border/70 bg-muted/70 text-muted-foreground"
  },
  available: {
    label: "Available",
    badgeVariant: "outline",
    icon: Circle,
    iconClassName: "text-primary",
    cardClassName: "border-primary/15 bg-primary/5",
    markerClassName: "border-primary/20 bg-primary/10 text-primary",
    ctaLabel: "Start quiz",
    ctaHref: (topicId) => `/quiz/${topicId}`
  },
  in_progress: {
    label: "In progress",
    badgeVariant: "secondary",
    icon: Sparkles,
    iconClassName: "text-primary",
    cardClassName: "border-primary/25 bg-primary/5",
    markerClassName: "border-primary/25 bg-primary text-primary-foreground",
    ctaLabel: "Continue quiz",
    ctaHref: (topicId) => `/quiz/${topicId}`
  },
  completed: {
    label: "Completed",
    badgeVariant: "success",
    icon: CheckCircle2,
    iconClassName: "text-success",
    cardClassName: "border-success/20 bg-success/5",
    markerClassName: "border-success/25 bg-success text-success-foreground",
    ctaLabel: "Review",
    ctaHref: (topicId) => `/learn/${topicId}`
  }
};

function normalizeMasteryScore(score: number): number {
  const magnitude = Math.abs(score);
  return Math.min(100, magnitude <= 1 ? magnitude * 100 : magnitude);
}

function formatMasteryScore(score: number): string {
  return `${Math.round(normalizeMasteryScore(score))}%`;
}

function formatLastStudiedAt(value: string | null): string {
  if (!value) {
    return "Not studied yet";
  }

  const studiedAt = new Date(value);
  if (Number.isNaN(studiedAt.getTime())) {
    return "Recently studied";
  }

  const diffDays = Math.floor((Date.now() - studiedAt.getTime()) / 86_400_000);

  if (diffDays <= 0) {
    return "Studied today";
  }

  if (diffDays === 1) {
    return "Studied yesterday";
  }

  if (diffDays < 7) {
    return `Studied ${diffDays} days ago`;
  }

  return `Studied ${studiedAt.toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;
}

function formatStudyCount(value: number): string {
  return value.toLocaleString();
}

function ProgressTooltip({
  active,
  payload
}: {
  active?: boolean;
  payload?: Array<{
    payload?: ProgressChartDatum;
  }>;
}) {
  if (!active || !payload?.length || !payload[0]?.payload) {
    return null;
  }

  const topic = payload[0].payload;
  const meta = statusMeta[topic.status];
  const Icon = meta.icon;

  return (
    <div className="rounded-[1.25rem] border border-border/70 bg-card/95 px-3 py-3 shadow-soft backdrop-blur">
      <div className="flex items-center gap-2">
        <Icon className={cn("h-4 w-4", meta.iconClassName)} />
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Topic {topic.orderIndex}</p>
      </div>
      <p className="mt-2 text-sm font-semibold text-foreground">{topic.title}</p>
      <p className="mt-1 text-sm text-muted-foreground">
        {meta.label} - {formatMasteryScore(topic.masteryScore)} mastery
      </p>
      <p className="mt-1 text-xs text-muted-foreground">{formatLastStudiedAt(topic.lastStudiedAt)}</p>
    </div>
  );
}

function ProgressLoadingState() {
  return (
    <main className="page-shell">
      <section className="space-y-4">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-10 w-80 max-w-full" />
        <Skeleton className="h-4 w-[28rem] max-w-full" />
      </section>

      <div className="mt-6 grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <CardHeader>
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-4 w-72 max-w-full" />
          </CardHeader>
          <CardContent className="space-y-3">
            <Skeleton className="h-[16rem] w-full rounded-[1.25rem]" />
            <div className="flex flex-wrap gap-2">
              <Skeleton className="h-7 w-24 rounded-full" />
              <Skeleton className="h-7 w-24 rounded-full" />
              <Skeleton className="h-7 w-24 rounded-full" />
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
          {Array.from({ length: 4 }).map((_, index) => (
            <Card key={index}>
              <CardHeader>
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-8 w-28" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-4 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      <Card className="mt-4">
        <CardHeader>
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-4 w-72 max-w-full" />
        </CardHeader>
        <CardContent className="space-y-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-28 w-full rounded-[1.5rem]" />
          ))}
        </CardContent>
      </Card>
    </main>
  );
}

function ProgressErrorState({
  message,
  onRetry
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <main className="page-shell">
      <div className="error-state mx-auto mt-8 max-w-xl">
        <AlertTriangle className="h-10 w-10 text-danger" />
        <div className="space-y-1">
          <h1 className="text-xl font-semibold">We couldn't load the progress path</h1>
          <p className="text-sm text-muted-foreground">{message}</p>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row">
          <Button type="button" variant="outline" onClick={onRetry}>
            Retry progress
          </Button>
          <Button asChild variant="secondary">
            <Link href="/dashboard">
              <ArrowRight className="h-4 w-4" />
              Back to dashboard
            </Link>
          </Button>
        </div>
      </div>
    </main>
  );
}

export default function ProgressPage() {
  const pathQuery = useProgressPathQuery();
  const statsQuery = useProgressStatsQuery();

  if (pathQuery.isLoading || statsQuery.isLoading) {
    return <ProgressLoadingState />;
  }

  if (pathQuery.isError || statsQuery.isError) {
    const message = pathQuery.error?.message ?? statsQuery.error?.message ?? "Progress data is unavailable right now.";
    return <ProgressErrorState message={message} onRetry={() => void Promise.all([pathQuery.refetch(), statsQuery.refetch()])} />;
  }

  const path = pathQuery.data;
  const stats = statsQuery.data;
  if (!path || !stats) {
    return (
      <main className="page-shell">
        <div className="error-state mx-auto mt-8 max-w-xl">
          <BarChart3 className="h-10 w-10 text-primary" />
          <div className="space-y-1">
            <h1 className="text-xl font-semibold">No progress data yet</h1>
            <p className="text-sm text-muted-foreground">
              We couldn't find an ordered topic path for this account yet. Try again after the backend returns progress data.
            </p>
          </div>
          <Button asChild variant="outline">
            <Link href="/dashboard">
              <ArrowRight className="h-4 w-4" />
              Return to dashboard
            </Link>
          </Button>
        </div>
      </main>
    );
  }

  const orderedTopics = [...path.topics].sort((left, right) => left.orderIndex - right.orderIndex);
  const chartData = orderedTopics.map((topic) => ({
    ...topic,
    masteryPercent: normalizeMasteryScore(topic.masteryScore)
  }));
  const totalTopics = orderedTopics.length;
  const completedTopics = orderedTopics.filter((topic) => topic.status === "completed").length;
  const currentTopic =
    orderedTopics.find((topic) => topic.id === path.currentTopicId) ??
    orderedTopics.find((topic) => topic.status === "in_progress") ??
    orderedTopics.find((topic) => topic.status === "available") ??
    null;
  const completedRate = totalTopics > 0 ? Math.round((completedTopics / totalTopics) * 100) : 0;
  const unlockedTopics = orderedTopics.filter((topic) => topic.status !== "locked").length;
  const pathComplete = totalTopics > 0 && completedTopics === totalTopics;
  const nextActionTopic =
    currentTopic ??
    orderedTopics.find((topic) => topic.status === "available" || topic.status === "in_progress" || topic.status === "completed") ??
    null;
  const nextActionMeta = nextActionTopic ? statusMeta[nextActionTopic.status] : null;

  return (
    <main className="page-shell">
      <section className="space-y-6">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge>Progress path</Badge>
            <Badge variant="secondary">
              {formatStudyCount(completedTopics)}/{formatStudyCount(totalTopics)} completed
            </Badge>
            <Badge variant="outline">{stats.cardsDueToday} cards due</Badge>
          </div>
          <h1 className="section-title">Follow the unlock path from left to right.</h1>
          <p className="section-subtitle">
            See which topics are locked, available, in progress, or completed, and use the mastery chart to spot where the next study push will matter most.
          </p>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
          <Card className="overflow-hidden">
            <CardHeader>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="space-y-1">
                  <CardTitle>Mastery overview</CardTitle>
                  <CardDescription>Backend mastery scores plotted across the ordered topic path.</CardDescription>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline">{completedRate}% completed</Badge>
                  <Badge variant="secondary">{unlockedTopics} unlocked</Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="h-[18rem] rounded-[1.25rem] border border-border/70 bg-white/70 p-3 shadow-soft">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 8, right: 4, bottom: 8, left: -8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.25)" vertical={false} />
                    <XAxis
                      dataKey="orderIndex"
                      tickLine={false}
                      axisLine={false}
                      tickMargin={8}
                      tickFormatter={(value) => `#${value}`}
                      style={{ fontSize: 12 }}
                    />
                    <YAxis
                      tickLine={false}
                      axisLine={false}
                      width={42}
                      tickMargin={8}
                      tickFormatter={(value) => `${value}%`}
                      domain={[0, 100]}
                      style={{ fontSize: 12 }}
                    />
                    <Tooltip content={<ProgressTooltip />} cursor={{ fill: "rgba(2, 6, 23, 0.04)" }} />
                    <Bar dataKey="masteryPercent" radius={[10, 10, 0, 0]}>
                      {chartData.map((topic) => (
                        <Cell
                          key={topic.id}
                          fill={
                            topic.status === "completed"
                              ? "hsl(var(--success))"
                              : topic.status === "in_progress"
                                ? "hsl(var(--primary))"
                                : topic.status === "available"
                                  ? "hsl(var(--secondary))"
                                  : "hsl(var(--muted))"
                          }
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">Locked</Badge>
                <Badge variant="secondary">Available</Badge>
                <Badge>In progress</Badge>
                <Badge variant="success">Completed</Badge>
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
            <Card>
              <CardHeader>
                <CardDescription>Current streak</CardDescription>
                <CardTitle className="text-3xl">{stats.currentStreak} days</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">Longest run so far: {stats.longestStreak} days.</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardDescription>Cards due today</CardDescription>
                <CardTitle className="text-3xl">{stats.cardsDueToday}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">Use due cards to keep the path moving and preserve the streak.</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardDescription>Next topic</CardDescription>
                <CardTitle className="text-2xl">{pathComplete ? "Path complete" : currentTopic?.title ?? "Nothing unlocked yet"}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  {currentTopic ? <Badge variant={statusMeta[currentTopic.status].badgeVariant}>{statusMeta[currentTopic.status].label}</Badge> : null}
                  {currentTopic ? <Badge variant="outline">{difficultyLabels[currentTopic.difficulty]}</Badge> : null}
                </div>
                <p className="text-sm text-muted-foreground">
                  {pathComplete
                    ? "Every topic is complete. Review any node to keep mastery fresh."
                    : currentTopic
                      ? formatLastStudiedAt(currentTopic.lastStudiedAt)
                      : "Complete earlier topics to unlock the first step."}
                </p>
                {nextActionTopic && nextActionMeta?.ctaHref ? (
                  <Button asChild variant="outline" className="w-full">
                    <Link href={nextActionMeta.ctaHref(nextActionTopic.id)}>
                      {nextActionMeta.ctaLabel}
                      <ArrowRight className="h-4 w-4" />
                    </Link>
                  </Button>
                ) : null}
              </CardContent>
            </Card>
          </div>
        </div>

        <Card>
          <CardHeader>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="space-y-1">
                <CardTitle>Topic unlock path</CardTitle>
                <CardDescription>Each node shows the current state, difficulty, and the last time it was studied.</CardDescription>
              </div>
              <Badge variant="outline">{path.currentTopicId ? `Current topic: ${path.currentTopicId}` : "No active topic"}</Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="relative space-y-4">
              {orderedTopics.length > 0 ? (
                <>
                  <div className="absolute bottom-0 left-5 top-5 w-px bg-border/70" />
                  {orderedTopics.map((topic, index) => {
                    const meta = statusMeta[topic.status];
                    const Icon = meta.icon;
                    const isCurrent = topic.id === path.currentTopicId;
                    const isFinal = index === orderedTopics.length - 1;

                    return (
                      <article key={topic.id} className={cn("relative flex gap-4", !isFinal && "pb-4")}>
                        <div className={cn("relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full border", meta.markerClassName)}>
                          <Icon className={cn("h-4 w-4", meta.iconClassName)} />
                        </div>
                        <div
                          className={cn(
                            "min-w-0 flex-1 rounded-[1.5rem] border p-4 shadow-soft sm:p-5",
                            meta.cardClassName,
                            isCurrent && "ring-2 ring-primary/15"
                          )}
                        >
                          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                            <div className="min-w-0 space-y-3">
                              <div className="flex flex-wrap items-center gap-2">
                                <Badge variant="outline">#{topic.orderIndex}</Badge>
                                <Badge variant={meta.badgeVariant}>{meta.label}</Badge>
                                <Badge variant="secondary">{difficultyLabels[topic.difficulty]}</Badge>
                                {isCurrent ? <Badge>Current topic</Badge> : null}
                              </div>
                              <div className="space-y-1">
                                <h3 className="text-lg font-semibold tracking-tight text-foreground">{topic.title}</h3>
                                <p className="text-sm text-muted-foreground">
                                  Mastery {formatMasteryScore(topic.masteryScore)} - {formatLastStudiedAt(topic.lastStudiedAt)}
                                </p>
                              </div>
                            </div>

                            <div className="flex shrink-0 flex-col items-start gap-2 sm:items-end">
                              {meta.ctaHref ? (
                                <Button asChild variant={topic.status === "completed" ? "secondary" : "outline"}>
                                  <Link href={meta.ctaHref(topic.id)}>
                                    {meta.ctaLabel}
                                    <ArrowRight className="h-4 w-4" />
                                  </Link>
                                </Button>
                              ) : (
                                <Button type="button" variant="outline" disabled>
                                  Locked
                                </Button>
                              )}
                              <p className="text-xs text-muted-foreground">
                                {topic.status === "locked"
                                  ? "Complete earlier topics to unlock this node."
                                  : topic.status === "completed"
                                    ? "Ready for a review loop."
                                    : "Continue studying to improve the next unlock."}
                              </p>
                            </div>
                          </div>
                        </div>
                      </article>
                    );
                  })}
                </>
              ) : (
                <div className="rounded-[1.5rem] border border-dashed border-border/80 bg-white/65 px-5 py-8 text-center shadow-soft">
                  <BarChart3 className="mx-auto h-10 w-10 text-primary" />
                  <div className="mt-3 space-y-1">
                    <h3 className="text-base font-semibold">No topics are available yet</h3>
                    <p className="text-sm text-muted-foreground">Once the backend exposes ordered topics, the unlock path will appear here.</p>
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Topic snapshot</CardTitle>
            <CardDescription>Backend stats mirrored from the dashboard so the progress route stays in sync.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {stats.topics.map((topic) => {
              const meta = statusMeta[topic.status];
              const Icon = meta.icon;

              return (
                <div key={topic.topicId} className="rounded-[1.25rem] border border-border/70 bg-white/70 p-4 shadow-soft">
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <p className="text-sm font-semibold text-foreground">{topic.title}</p>
                      <Badge variant={meta.badgeVariant}>{meta.label}</Badge>
                    </div>
                    <Icon className={cn("h-5 w-5", meta.iconClassName)} />
                  </div>
                  <p className="mt-3 text-2xl font-semibold tracking-tight">{formatMasteryScore(topic.masteryScore)}</p>
                  <p className="mt-1 text-sm text-muted-foreground">Unlock state: {meta.label.toLowerCase()}</p>
                </div>
              );
            })}
          </CardContent>
        </Card>
      </section>
    </main>
  );
}
