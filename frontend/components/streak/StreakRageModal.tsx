"use client";

import { motion } from "framer-motion";
import { AlertTriangle, Flame } from "lucide-react";

import type { StreakResponse } from "@/lib/api";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

type StreakRageModalProps = {
  open: boolean;
  streak?: StreakResponse;
  onAccept: () => void;
  onRecover: () => void;
};

function formatGraceExpiry(expiresAt: string | null): string | null {
  if (!expiresAt) {
    return null;
  }

  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Kolkata"
  }).format(new Date(expiresAt));
}

export default function StreakRageModal({ open, streak, onAccept, onRecover }: StreakRageModalProps) {
  const graceExpiry = formatGraceExpiry(streak?.graceWindow.expiresAt ?? null);
  const streakDays = streak?.currentStreak ?? 0;
  const daysMissed = streak?.graceWindow.missedDate ? 1 : 0;
  const recoveryReviewsRequired = streak?.recovery.reviewsRequired ?? 20;
  const recoveryCta = streak?.rageModal.cta || `Recover my streak (${recoveryReviewsRequired} cards)`;

  return (
    <Dialog open={open} onOpenChange={() => undefined}>
      <DialogContent
        className="border-danger/25 bg-[linear-gradient(180deg,rgba(127,29,29,0.98),rgba(69,10,10,0.98))] p-0 text-danger-foreground sm:max-w-xl [&>button]:hidden"
        onEscapeKeyDown={(event) => event.preventDefault()}
        onPointerDownOutside={(event) => event.preventDefault()}
      >
        <motion.div
          initial={{ x: 0, rotate: 0 }}
          animate={{ x: [0, -10, 8, -6, 6, 0], rotate: [0, -0.4, 0.4, -0.2, 0.2, 0] }}
          transition={{ duration: 0.55, ease: "easeInOut" }}
          className="flex flex-col gap-5 p-6 sm:p-7"
        >
          <DialogHeader className="gap-3 text-left">
            <div className="flex items-center gap-3">
              <div className="rounded-full bg-danger-foreground/10 p-3 text-danger-foreground">
                <Flame className="h-6 w-6" />
              </div>
              <div className="rounded-full border border-danger-foreground/15 bg-danger-foreground/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-danger-foreground/80">
                Streak emergency
              </div>
            </div>
            <DialogTitle className="text-2xl font-semibold tracking-tight text-danger-foreground">
              {streakDays > 0 ? `${streakDays}-day streak in danger` : "Your streak just slipped"}
            </DialogTitle>
            <DialogDescription className="text-sm leading-6 text-danger-foreground/80">
              {daysMissed > 0
                ? `You missed ${daysMissed} day. Finish ${recoveryReviewsRequired} flashcards before the grace window closes to recover the streak.`
                : "Your study streak is wobbling. A recovery session can still pull it back."}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-3 rounded-[1.5rem] border border-danger-foreground/10 bg-danger-foreground/8 p-4 sm:grid-cols-2">
            <div className="space-y-1">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-danger-foreground/65">
                Recovery target
              </p>
              <p className="text-xl font-semibold text-danger-foreground">
                {recoveryReviewsRequired} cards
              </p>
              <p className="text-sm text-danger-foreground/75">
                {streak?.recovery.reviewsRemaining ?? recoveryReviewsRequired} left in the current recovery session.
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-danger-foreground/65">
                Grace cutoff
              </p>
              <p className="text-base font-semibold text-danger-foreground">
                {graceExpiry ?? "Before tonight ends"}
              </p>
              <p className="flex items-center gap-2 text-sm text-danger-foreground/75">
                <AlertTriangle className="h-4 w-4" />
                {streak?.rageModal.reason || "Missed-day recovery is currently available."}
              </p>
            </div>
          </div>

          <DialogFooter className="gap-3 sm:justify-start">
            <Button type="button" size="lg" className="bg-danger-foreground text-danger hover:bg-danger-foreground/90" onClick={onRecover}>
              {recoveryCta}
            </Button>
            <Button
              type="button"
              size="lg"
              variant="outline"
              className="border-danger-foreground/20 bg-danger-foreground/8 text-danger-foreground hover:bg-danger-foreground/12 hover:text-danger-foreground"
              onClick={onAccept}
            >
              Accept the loss
            </Button>
          </DialogFooter>
        </motion.div>
      </DialogContent>
    </Dialog>
  );
}
