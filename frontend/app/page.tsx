import Link from "next/link";
import { redirect } from "next/navigation";
import { auth } from "@clerk/nextjs/server";

import { isDevAuthEnabled } from "@/lib/dev-auth";

export default async function HomePage() {
  if (isDevAuthEnabled()) {
    redirect("/dashboard");
  }

  const { userId } = await auth();

  if (userId) {
    redirect("/dashboard");
  }

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        padding: "2rem"
      }}
    >
      <section
        style={{
          width: "min(32rem, 100%)",
          border: "1px solid var(--border)",
          borderRadius: "1.5rem",
          padding: "2rem",
          background: "rgba(255, 255, 255, 0.9)",
          boxShadow: "0 24px 60px rgba(15, 23, 42, 0.08)"
        }}
      >
        <p style={{ margin: 0, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
          DataSIQ
        </p>
        <h1 style={{ marginBottom: "0.75rem" }}>Sign in to continue your learning streak.</h1>
        <p style={{ marginTop: 0, marginBottom: "1.5rem", color: "var(--muted)" }}>
          Clerk authentication is now the entry point for the dashboard experience.
        </p>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <Link
            href="/sign-in"
            style={{
              padding: "0.85rem 1.1rem",
              borderRadius: "999px",
              background: "#0f172a",
              color: "#f8fafc"
            }}
          >
            Sign in
          </Link>
          <Link
            href="/sign-up"
            style={{
              padding: "0.85rem 1.1rem",
              borderRadius: "999px",
              border: "1px solid var(--border)"
            }}
          >
            Create account
          </Link>
        </div>
      </section>
    </main>
  );
}
