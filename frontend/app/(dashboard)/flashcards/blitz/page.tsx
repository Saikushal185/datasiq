"use client";

import { BlitzMode } from "@/components/flashcards/BlitzMode";
import { Badge } from "@/components/ui/badge";

export default function BlitzPage() {
  return (
    <main className="page-shell">
      <section className="space-y-6">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge>Quick-fire</Badge>
            <Badge variant="secondary">10 cards</Badge>
            <Badge variant="outline">60 seconds</Badge>
          </div>
          <h1 className="section-title">Blitz mode</h1>
          <p className="section-subtitle">
            Tap fast, think faster. Every answer is graded instantly and the sprint ends on the timer or after the tenth card.
          </p>
        </div>

        <BlitzMode />
      </section>
    </main>
  );
}
