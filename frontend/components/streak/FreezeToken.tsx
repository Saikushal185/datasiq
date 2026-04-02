"use client";

import { Shield, Snowflake } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type FreezeTokenProps = {
  freezeTokensRemaining: number;
  graceActive: boolean;
  freezeApplied: boolean;
  disabled?: boolean;
  onUseFreeze: () => void;
  className?: string;
};

export default function FreezeToken({
  freezeTokensRemaining,
  graceActive,
  freezeApplied,
  disabled = false,
  onUseFreeze,
  className
}: FreezeTokenProps) {
  const canUseFreeze = graceActive && !freezeApplied && freezeTokensRemaining > 0;

  return (
    <section className={cn("rounded-[1.25rem] border border-border/70 bg-white/70 p-4 shadow-soft", className)}>
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-secondary p-2 text-secondary-foreground">
              <Snowflake className="h-4 w-4" />
            </span>
            <p className="text-sm font-semibold text-foreground">Freeze token</p>
          </div>
          <p className="text-sm text-muted-foreground">
            Freeze tokens stop a missed day from breaking the streak when you are inside the grace window.
          </p>
        </div>
        <Badge variant={freezeTokensRemaining > 0 ? "secondary" : "outline"}>
          {freezeTokensRemaining} left
        </Badge>
      </div>

      <div className="mt-4 flex flex-col gap-3">
        {freezeApplied ? (
          <div className="rounded-2xl border border-success/20 bg-success/10 px-4 py-3 text-sm text-success">
            A freeze token is already covering the missed day.
          </div>
        ) : canUseFreeze ? (
          <Button type="button" className="w-full" disabled={disabled} onClick={onUseFreeze}>
            <Shield className="h-4 w-4" />
            Use freeze token
          </Button>
        ) : graceActive ? (
          <div className="rounded-2xl border border-danger/20 bg-danger/10 px-4 py-3 text-sm text-danger">
            No freeze tokens are available for this missed day.
          </div>
        ) : (
          <div className="rounded-2xl border border-border/70 bg-background/70 px-4 py-3 text-sm text-muted-foreground">
            Freeze tokens matter only after a missed day. Your next reset is Monday 00:00 IST.
          </div>
        )}
      </div>
    </section>
  );
}
