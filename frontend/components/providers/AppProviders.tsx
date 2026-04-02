"use client";

import * as Sentry from "@sentry/nextjs";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useUser } from "@clerk/nextjs";
import posthog from "posthog-js";
import { useEffect, useState, type ReactNode } from "react";

import { getDevAuthIdentity, isDevAuthEnabled } from "@/lib/dev-auth";

type AppProvidersProps = {
  children: ReactNode;
};

export function AppProviders({ children }: AppProvidersProps) {
  const { isLoaded, isSignedIn, user } = useUser();
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            refetchOnWindowFocus: false,
            retry: 1,
            staleTime: 30_000
          }
        }
      })
  );

  useEffect(() => {
    if (isDevAuthEnabled()) {
      const demoUser = getDevAuthIdentity();
      posthog.identify(demoUser.id, {
        email: demoUser.email,
        name: demoUser.name
      });
      Sentry.setUser({
        id: demoUser.id,
        email: demoUser.email,
        username: demoUser.name
      });
      return;
    }

    if (!isLoaded) {
      return;
    }

    if (isSignedIn && user) {
      const email = user.primaryEmailAddress?.emailAddress ?? user.emailAddresses[0]?.emailAddress ?? undefined;
      const fullName = user.fullName ?? undefined;

      posthog.identify(user.id, {
        email,
        name: fullName
      });
      Sentry.setUser({
        id: user.id,
        email,
        username: fullName ?? user.username ?? undefined
      });
      return;
    }

    posthog.reset();
    Sentry.setUser(null);
  }, [isLoaded, isSignedIn, user]);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
