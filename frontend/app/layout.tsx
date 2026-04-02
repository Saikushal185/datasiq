import { ClerkProvider } from "@clerk/nextjs";
import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppProviders } from "@/components/providers/AppProviders";

import "./globals.css";

type LayoutProps = {
  children: ReactNode;
};

export const metadata: Metadata = {
  title: "DataSIQ",
  description: "Adaptive learning for the DataSIQ platform."
};

export default function RootLayout({ children }: LayoutProps) {
  return (
    <ClerkProvider>
      <html lang="en" suppressHydrationWarning>
        <body className="min-h-dvh bg-background text-foreground antialiased">
          <AppProviders>{children}</AppProviders>
        </body>
      </html>
    </ClerkProvider>
  );
}
