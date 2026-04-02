"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { BarChart3, BookOpenCheck, Flame, LayoutDashboard, Menu, Zap } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";

import FreezeToken from "@/components/streak/FreezeToken";
import StreakBar from "@/components/streak/StreakBar";
import StreakRageModal from "@/components/streak/StreakRageModal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger
} from "@/components/ui/sheet";
import { getDevAuthIdentity, isDevAuthEnabled } from "@/lib/dev-auth";
import { useFreezeStreakMutation, useStreakQuery } from "@/lib/queries";
import { dismissStreakRageForSession, isStreakRageDismissedForSession } from "@/lib/streak-utils";
import { cn } from "@/lib/utils";

type DashboardLayoutProps = {
  children: ReactNode;
};

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/flashcards", label: "Flashcards", icon: BookOpenCheck },
  { href: "/flashcards/blitz", label: "Blitz", icon: Zap },
  { href: "/progress", label: "Progress", icon: BarChart3 }
];

type SidebarNavProps = {
  pathname: string;
  onNavigate?: () => void;
};

function SidebarNav({ pathname, onNavigate }: SidebarNavProps) {
  return (
    <nav className="flex flex-col gap-2">
      {navItems.map((item) => {
        const isActive =
          item.href === "/flashcards"
            ? pathname === "/flashcards"
            : pathname === item.href || pathname.startsWith(`${item.href}/`);
        const Icon = item.icon;

        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex items-center gap-3 rounded-[1.25rem] px-4 py-3 text-sm font-medium transition-colors",
              isActive
                ? "bg-primary text-primary-foreground shadow-soft"
                : "text-muted-foreground hover:bg-secondary hover:text-foreground"
            )}
            onClick={onNavigate}
          >
            <Icon className="h-4 w-4" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const pathname = usePathname();
  const router = useRouter();
  const streakQuery = useStreakQuery();
  const freezeMutation = useFreezeStreakMutation();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [rageModalOpen, setRageModalOpen] = useState(false);
  const seenModalKeyRef = useRef<string | null>(null);
  const demoIdentity = isDevAuthEnabled() ? getDevAuthIdentity() : null;
  const rageModalKey = streakQuery.data
    ? `${streakQuery.data.graceWindow.missedDate ?? "none"}:${streakQuery.data.currentStreak}:${streakQuery.data.protectedStreakDate ?? "none"}`
    : null;

  useEffect(() => {
    if (!streakQuery.data || !rageModalKey) {
      return;
    }

    if (!streakQuery.data.rageModal.show) {
      if (seenModalKeyRef.current === rageModalKey) {
        seenModalKeyRef.current = null;
      }
      return;
    }

    if (seenModalKeyRef.current === rageModalKey || isStreakRageDismissedForSession(rageModalKey)) {
      return;
    }

    seenModalKeyRef.current = rageModalKey;
    setRageModalOpen(true);
  }, [rageModalKey, streakQuery.data]);

  const handleUseFreeze = () => {
    freezeMutation.mutate();
  };

  const handleDismissRageModal = () => {
    dismissStreakRageForSession(rageModalKey);
    setRageModalOpen(false);
  };

  const handleRecoverStreak = () => {
    dismissStreakRageForSession(rageModalKey);
    setRageModalOpen(false);
    router.push("/flashcards?recovery=1");
  };

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-[96rem] flex-col px-4 py-4 sm:px-6 lg:px-8">
      <StreakBar
        className="sticky top-4 z-30 w-full"
        streak={streakQuery.data}
        isLoading={streakQuery.isLoading}
        isError={streakQuery.isError}
        freezePending={freezeMutation.isPending}
        onRetry={() => void streakQuery.refetch()}
        onUseFreeze={handleUseFreeze}
      />

      {freezeMutation.isError ? (
        <div className="mt-3 rounded-[1.25rem] border border-danger/20 bg-danger/10 px-4 py-3 text-sm text-danger">
          {freezeMutation.error.message}
        </div>
      ) : null}

      <div className="mt-4 flex flex-1 gap-4">
        <aside className="surface hidden w-72 shrink-0 p-5 lg:flex lg:flex-col lg:gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <div className="rounded-[1rem] bg-primary p-3 text-primary-foreground shadow-soft">
                <Flame className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">DatiSIQ</p>
                <h2 className="text-lg font-semibold tracking-tight text-foreground">Adaptive dashboard</h2>
              </div>
            </div>
            <p className="text-sm text-muted-foreground">
              Protect the streak, review due cards, and keep the learning path moving.
            </p>
          </div>

          {demoIdentity ? (
            <div className="rounded-[1.25rem] border border-border/70 bg-white/70 p-4 shadow-soft">
              <div className="flex items-center gap-2">
                <Badge variant="secondary">Test account</Badge>
                <Badge variant="outline">Local demo</Badge>
              </div>
              <p className="mt-3 text-base font-semibold text-foreground">{demoIdentity.name}</p>
              <p className="text-sm text-muted-foreground">{demoIdentity.email}</p>
            </div>
          ) : null}

          <SidebarNav pathname={pathname} />

          <div className="rounded-[1.25rem] border border-border/70 bg-white/70 p-4 shadow-soft">
            <div className="flex items-center gap-2">
              <Badge variant="secondary">Recovery route</Badge>
              <Badge variant="outline">20 cards</Badge>
            </div>
            <p className="mt-3 text-sm text-muted-foreground">
              If the rage modal appears, the fastest path back is the flashcard queue.
            </p>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col gap-4">
          <header className="surface flex items-center justify-between p-4 lg:hidden">
            <div className="space-y-1">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">DatiSIQ</p>
              <h1 className="text-lg font-semibold tracking-tight text-foreground">Dashboard shell</h1>
              {demoIdentity ? <p className="text-sm text-muted-foreground">{demoIdentity.name}</p> : null}
            </div>
            <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
              <SheetTrigger asChild>
                <Button type="button" variant="outline" size="icon">
                  <Menu className="h-4 w-4" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-[min(24rem,calc(100vw-2rem))]">
                <SheetHeader>
                  <SheetTitle>Navigation</SheetTitle>
                  <SheetDescription>Move between your dashboard surfaces.</SheetDescription>
                </SheetHeader>
                <div className="mt-6 flex flex-col gap-6">
                  <SidebarNav pathname={pathname} onNavigate={() => setMobileNavOpen(false)} />
                  {streakQuery.data ? (
                    <FreezeToken
                      freezeTokensRemaining={streakQuery.data.freezeTokensRemaining}
                      graceActive={streakQuery.data.graceWindow.active}
                      freezeApplied={streakQuery.data.freezeApplied}
                      disabled={freezeMutation.isPending}
                      onUseFreeze={handleUseFreeze}
                    />
                  ) : null}
                </div>
              </SheetContent>
            </Sheet>
          </header>

          <div className="min-w-0 flex-1">{children}</div>
        </div>
      </div>

      <StreakRageModal
        open={rageModalOpen}
        streak={streakQuery.data}
        onAccept={handleDismissRageModal}
        onRecover={handleRecoverStreak}
      />
    </div>
  );
}
