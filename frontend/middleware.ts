import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const isProtectedRoute = createRouteMatcher([
  "/dashboard(.*)",
  "/flashcards(.*)",
  "/learn(.*)",
  "/progress(.*)",
  "/quiz(.*)"
]);

const devAuthEnabled = process.env.NEXT_PUBLIC_DEV_AUTH === "true";

const protectedMiddleware = clerkMiddleware(async (auth, request) => {
  if (isProtectedRoute(request)) {
    await auth.protect();
  }
});

export default devAuthEnabled
  ? function middleware() {
      return NextResponse.next();
    }
  : protectedMiddleware;

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:css|gif|ico|jpg|jpeg|js(?!on)|json|png|svg|ts|tsx|woff2?)).*)",
    "/(api|trpc)(.*)"
  ]
};
