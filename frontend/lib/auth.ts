"use client";

import { useAuth } from "@clerk/nextjs";

import { getDevAuthToken, isDevAuthEnabled } from "@/lib/dev-auth";

export function useAppAuth() {
  const clerkAuth = useAuth();
  if (isDevAuthEnabled()) {
    return {
      ...clerkAuth,
      getToken: async () => getDevAuthToken(),
      isLoaded: true,
      isSignedIn: true,
    };
  }

  return clerkAuth;
}
