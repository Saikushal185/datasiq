"use client";

import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, BookOpenCheck, Flame, Trophy } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAppAuth } from "@/lib/auth";
import { getDevAuthIdentity, isDevAuthEnabled } from "@/lib/dev-auth";
import { prefetchProgressPathQuery, useProgressStatsQuery } from "@/lib/queries";

function formatMasteryScore(score: number): string {
  return `${Math.round(score * 100)}%`;
}

export default function DashboardPage() {
  const queryClient = useQueryClient();
  const { getToken, isLoaded, isSignedIn } = useAppAuth();
  const progressStatsQuery = useProgressStatsQuery();
  const demoIdentity = isDevAuthEnabled() ? getDevAuthIdentity() : null;

  const prefetchProgressPath = () => {
    void prefetchProgressPathQuery(queryClient, { getToken, isLoaded, isSignedIn });
  };

  if (progressStatsQuery.isLoading) {
    return (
      <main className="page-shell">
        <div className="grid gap-4 md:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Card key={index}>
              <CardHeader>
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-8 w-32" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-4 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
        <Card className="mt-4">
          <CardHeader>
            <Skeleton className="h-5 w-40" />
          </CardHeader>
          <CardContent className="space-y-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <Skeleton key={index} className="h-16 w-full rounded-[1.25rem]" />
            ))}
          </CardContent>
        </Card>
      </main>
    );
  }

  if (progressStatsQuery.isError) {
    return (
      <main className="page-shell">
        <div className="error-state">
          <Flame className="h-10 w-10 text-danger" />
          <div className="space-y-1">
            <h1 className="text-xl font-semibold">We couldn't load your dashboard</h1>
            <p className="text-sm text-muted-foreground">
              Progress stats are unavailable right now. Retry once the backend is reachable.
            </p>
          </div>
          <Button type="button" variant="outline" onClick={() => void progressStatsQuery.refetch()}>
            Retry dashboard
          </Button>
        </div>
      </main>
    );
  }

  const stats = progressStatsQuery.data;
  if (!stats) {
    return null;
  }
  const spotlightTopic = stats.topics.find((topic) => topic.status === "available" || topic.status === "in_progress") ?? stats.topics[0];

  return (
    <main className="page-shell">
      <section className="space-y-6">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge>Dashboard</Badge>
            {demoIdentity ? <Badge variant="outline">{demoIdentity.name}</Badge> : null}
            <Badge variant="secondary">{stats.cardsDueToday} cards due</Badge>
            <Badge variant="outline">{stats.currentStreak} day streak</Badge>
          </div>
          <h1 className="section-title">Keep the streak alive and the path moving.</h1>
          <p className="section-subtitle">
            Today's dashboard keeps the streak mechanics in view while surfacing the next topic that deserves your attention.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader>
              <CardDescription>Cards due today</CardDescription>
              <CardTitle className="text-3xl">{stats.cardsDueToday}</CardTitle>
            </CardHeader>
            <CardContent>
              <Button asChild className="w-full sm:w-auto">
                <Link href="/flashcards">
                  <BookOpenCheck className="h-4 w-4" />
                  Review now
                </Link>
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardDescription>Current streak</CardDescription>
              <CardTitle className="text-3xl">{stats.currentStreak} days</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Longest run so far: {stats.longestStreak} days. One study action today keeps this one burning.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardDescription>Spotlight topic</CardDescription>
              <CardTitle className="text-2xl">{spotlightTopic?.title ?? "No topic available yet"}</CardTitle>
            </CardHeader>
            <CardContent className="flex items-center justify-between gap-3">
              <Badge variant="outline">{spotlightTopic ? formatMasteryScore(spotlightTopic.masteryScore) : "0%"}</Badge>
              <Button asChild variant="outline">
                <Link
                  href="/progress"
                  onFocus={prefetchProgressPath}
                  onMouseEnter={prefetchProgressPath}
                  onTouchStart={prefetchProgressPath}
                >
                  View path
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <CardTitle>Topic snapshot</CardTitle>
                <CardDescription>Track which topics are completed, available, or still locked behind the path.</CardDescription>
              </div>
              <Button asChild variant="outline">
                <Link
                  href="/progress"
                  onFocus={prefetchProgressPath}
                  onMouseEnter={prefetchProgressPath}
                  onTouchStart={prefetchProgressPath}
                >
                  Open progress
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            </div>
          </CardHeader>
          <CardContent className="grid gap-3">
            {stats.topics.map((topic) => (
              <div key={topic.topicId} className="rounded-[1.25rem] border border-border/70 bg-white/70 p-4 shadow-soft">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-base font-semibold text-foreground">{topic.title}</p>
                      <Badge
                        variant={
                          topic.status === "completed"
                            ? "success"
                            : topic.status === "in_progress"
                              ? "secondary"
                              : topic.status === "available"
                                ? "outline"
                                : "outline"
                        }
                      >
                        {topic.status.replace("_", " ")}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      Mastery score: {formatMasteryScore(topic.masteryScore)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Trophy className="h-4 w-4" />
                    {topic.status === "completed" ? "Cleared" : "Keep climbing"}
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </section>
    </main>
  );
}
