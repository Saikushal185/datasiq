"use client";

export const STREAK_RAGE_SESSION_KEY = "datasiq:streak-rage-dismissed";
export const RECOVERY_BANNER_PARAM = "recovery";
export const RECOVERY_BANNER_VALUE = "1";

function canUseSessionStorage(): boolean {
  return typeof window !== "undefined" && typeof window.sessionStorage !== "undefined";
}

export function isStreakRageDismissedForSession(modalKey: string | null): boolean {
  if (!canUseSessionStorage() || !modalKey) {
    return false;
  }

  return window.sessionStorage.getItem(STREAK_RAGE_SESSION_KEY) === modalKey;
}

export function dismissStreakRageForSession(modalKey: string | null): void {
  if (!canUseSessionStorage() || !modalKey) {
    return;
  }

  window.sessionStorage.setItem(STREAK_RAGE_SESSION_KEY, modalKey);
}

export function clearStreakRageDismissalForSession(): void {
  if (!canUseSessionStorage()) {
    return;
  }

  window.sessionStorage.removeItem(STREAK_RAGE_SESSION_KEY);
}

export function shouldShowRecoveryBanner(value: string | null): boolean {
  return value === RECOVERY_BANNER_VALUE;
}
