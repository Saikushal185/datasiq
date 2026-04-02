import Link from "next/link";
import { ArrowLeft, BookOpenCheck } from "lucide-react";

import { BossRound } from "@/components/flashcards/BossRound";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

type LearnTopicPageProps = {
  params: Promise<{
    topicId: string;
  }>;
};

export default async function LearnTopicPage({ params }: LearnTopicPageProps) {
  const { topicId } = await params;

  return (
    <main className="page-shell">
      <section className="space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge>Boss access</Badge>
              <Badge variant="secondary">Topic {topicId}</Badge>
            </div>
            <h1 className="section-title">Topic review</h1>
            <p className="section-subtitle">
              Finish the boss round to validate mastery for this topic. The backend will eventually persist the completion and unlock the next step in the path.
            </p>
          </div>
          <Button asChild variant="outline">
            <Link href="/flashcards">
              <ArrowLeft className="h-4 w-4" />
              Back to flashcards
            </Link>
          </Button>
        </div>

        <Card className="overflow-hidden">
          <CardContent className="pt-6">
            <div className="mb-6 flex items-center gap-3 rounded-2xl border border-border/70 bg-primary/5 px-4 py-3 text-sm text-primary">
              <BookOpenCheck className="h-4 w-4" />
              Boss round cards are randomized from the selected topic.
            </div>
            <BossRound topicId={topicId} />
          </CardContent>
        </Card>
      </section>
    </main>
  );
}
