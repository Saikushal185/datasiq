export function isDevAuthEnabled(): boolean {
  return process.env.NEXT_PUBLIC_DEV_AUTH === "true";
}

export function getDevAuthToken(): string {
  return process.env.NEXT_PUBLIC_DEV_AUTH_TOKEN ?? "dev-demo-token";
}

export function getDevAuthIdentity() {
  return {
    id: "user_demo_local",
    email: "test.user@datasiq.local",
    name: "Test User"
  };
}
