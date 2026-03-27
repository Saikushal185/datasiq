# DatiSIQ Design Spec

**Date:** 2026-03-27
**Project:** DatiSIQ
**Status:** Approved for planning

## Goal

Build DatiSIQ as a full-stack adaptive learning platform for data analytics and data science topics, with multi-user authentication from day one, rule-based adaptive progression, flashcards with simplified FSRS scheduling, quizzes, streak mechanics tied to IST day boundaries, and an offline AI-assisted curriculum generation pipeline.

## Product Scope

DatiSIQ is a personal project that will be used by multiple friends, so the first version needs to behave like a real multi-user product rather than a local prototype. The product must support:

- Clerk-based authentication and route protection
- Topic-based learning paths with unlock logic
- Recall, blitz, and boss-round flashcard flows
- Quiz-based evaluation and mastery updates
- IST-based streak tracking with grace and freeze rules
- Admin-only curriculum generation using batch Claude calls
- Frontend and backend monitoring from the first release

The implementation must follow the exact stack and file structure in the project brief.

## Repository and Tooling Strategy

This repository will be a polyglot monorepo with explicit orchestration rather than two unrelated folders.

- `frontend/` will contain the Next.js 15 application.
- `backend/` will contain the FastAPI application and Alembic migrations.
- `scripts/` will contain manual admin utilities, including curriculum generation.
- `packages/contracts/` will contain generated frontend-consumable API contract types derived from the backend OpenAPI schema.
- The repo root will own lightweight coordination files such as `package.json`, `pnpm-workspace.yaml`, and deployment config.

This keeps the Python backend isolated while still giving the frontend a reliable generated contract package for API-facing types. The backend remains the source of truth for network contracts, while the frontend gets generated TypeScript types rather than hand-maintained duplicates.

## Runtime Boundaries

### Frontend runtime

The frontend will run as a Next.js 15 App Router application on Vercel in production and on `http://localhost:3000` in local development.

### Backend runtime

The backend will run as a FastAPI service on Railway in production and on `http://localhost:8000` in local development.

### Script runtime

`scripts/generate_cards.py` will be a manual Python CLI tool run by an admin from the repository root. It will use the same backend environment variables as the FastAPI app, including `DATABASE_URL`, `ANTHROPIC_API_KEY`, and `ADMIN_SECRET` when needed. It may import backend modules through package-safe imports such as `backend.app.services.ai_service`, but it must not depend on brittle relative-import execution from inside the `scripts/` folder.

This script is not part of the live user request path and is not triggered automatically by page loads.

## Local Development Contract

Local development must be predictable for future contributors and future-you.

- Frontend runs on port `3000`
- Backend runs on port `8000`
- Frontend reads `NEXT_PUBLIC_API_URL=http://localhost:8000`
- Backend connects to Neon and Upstash through environment variables
- Starter curriculum and sample data will be seeded through backend-safe scripts or documented admin flows

The repo should expose clear root-level commands for starting the frontend and backend independently. Shared startup assumptions must be documented so the workspace does not depend on tribal knowledge.

## Production Connectivity

The frontend and backend communicate over an env-driven HTTP boundary.

- Vercel will receive `NEXT_PUBLIC_API_URL` for the deployed Railway backend base URL.
- FastAPI will allow CORS only for approved origins: local frontend and the production Vercel domain.
- The frontend must treat backend cold starts as recoverable loading states, not as silent failures.
- No production secret may be embedded in frontend code.

All API routes exposed to the frontend will be versioned under `/api/v1/...` from day one to preserve room for future breaking changes without forcing a full synchronized redeploy.

## Architecture Overview

The project is a two-app product with one frontend and one backend, but the backend owns all business rules and persistence concerns.

### Frontend responsibilities

- Authentication UI through Clerk
- Protected route rendering
- Query orchestration through TanStack Query
- Form handling with React Hook Form and Zod
- Learning interactions and visual feedback
- Progress visualization using Recharts
- PostHog event tracking
- Sentry browser error capture

### Backend responsibilities

- Clerk token verification and user resolution
- Database persistence through SQLAlchemy 2.0 async
- Alembic migrations
- Flashcard due-card selection and review writes
- Quiz grading and result breakdown
- Streak calculations in IST
- Adaptive topic unlocking and mastery updates
- Admin-only curriculum generation triggers
- Sentry backend instrumentation

### Infrastructure responsibilities

- Neon stores relational learning data
- Upstash REST stores ephemeral session and cache state only
- Supabase Storage stores static assets only
- Anthropic + LangChain are used only in admin/offline curriculum generation flows

## Required File Structure

The implementation must scaffold the exact structure from the brief, including empty placeholder files where required. Additional support files may be added only when needed to make the prescribed structure operational.

## Data Model Strategy

Postgres is the source of truth for users, topics, progress, reviews, quizzes, and streak history.

### User identity model

- Clerk is the identity provider
- `users.clerk_id` is the stable external identity key
- All user-owned tables reference `users.id` as the internal foreign key target
- `users.clerk_id` remains unique and required

On first authenticated backend access, the backend must resolve or create the local user row using a race-safe database upsert strategy on `clerk_id`, followed by a fetch. This avoids duplicate-key failures when multiple initial requests arrive in parallel.

### Enum strategy

Python `Enum` classes will define the canonical domain values for:

- Topic difficulty
- Topic progress status
- Flashcard type
- Flashcard difficulty
- Flashcard review rating
- Quiz question type
- Streak event type

These enums will be reused in SQLAlchemy models and Pydantic schemas. Frontend API-facing string unions and data transfer types will be generated from the backend OpenAPI schema into `packages/contracts/` to avoid drift.

### Migration rules

Alembic is the only schema migration mechanism. After initial launch:

- Any new non-null column must ship with a server default or a backfill in the same migration
- Enum changes must be deliberate and migration-safe
- Migrations must preserve existing user data

Raw SQL is allowed only inside Alembic revisions, per the project rules.

## Database Schema

The initial database schema must include all tables from the project brief:

- `users`
- `topics`
- `user_topic_progress`
- `flashcards`
- `flashcard_options`
- `flashcard_reviews`
- `quizzes`
- `quiz_questions`
- `quiz_attempts`
- `streak_events`

All timestamps are stored in UTC. IST conversion happens only at the display or business-rule boundary, never by storing localized timestamps in the database.

## Backend Boundaries

Routers stay thin. Business rules live in services. Schemas define all request and response contracts.

### Routers

- `flashcards.py`
- `quiz.py`
- `progress.py`
- `streak.py`
- `curriculum.py`

All frontend-facing routes will be mounted under `/api/v1`.

### Services

- `fsrs_service.py`: simplified SM-2 review scheduling exactly as specified
- `streak_service.py`: day-boundary logic, grace windows, freeze replenishment, rage-modal eligibility
- `adaptive_service.py`: mastery and topic unlock rules
- `ai_service.py`: curriculum generation orchestration only

`ai_service.py` remains in the required services folder, but structural enforcement happens at the router boundary: only admin-only curriculum routes and the offline generation script may call it. The curriculum router must require an admin secret check backed by `ADMIN_SECRET`.

## Redis Strategy

Redis through Upstash REST is only for ephemeral state.

Examples:

- `session:{userId}:blitz`
- `session:{userId}:recovery`
- `streak:{userId}:state`

Every Redis key must have a TTL. Redis is not the source of truth for streak history, quiz attempts, or review history. If a Redis key expires, the backend must still be able to recover correct long-term state from Postgres.

## Authentication Strategy

### Frontend

- Clerk middleware protects dashboard routes
- `(auth)` routes host Clerk sign-in and sign-up pages
- `(dashboard)` routes are protected from unauthenticated access

### Backend

- Backend verifies Clerk-issued identity on every authenticated request
- Backend resolves the local user record from the verified Clerk subject
- Backend never trusts a user identifier sent from the client body

The auth boundary must support multiple users from day one.

## API Contract Strategy

Every endpoint must have a corresponding Pydantic request and response model. The backend OpenAPI schema is the source of truth for API contracts. Generated frontend contract types will be used by `frontend/lib/api.ts` and query hooks.

All API calls from the frontend go through `frontend/lib/api.ts`. Components must not call `fetch` directly.

## Feature Design

### Flashcard system

#### Recall mode

- Due cards are fetched from `GET /api/v1/flashcards/due`
- `FlipCard.tsx` uses a CSS 3D transform for the flip interaction
- After reveal, the user rates the card
- `POST /api/v1/flashcards/review` writes the review and returns the next review timestamp
- Easy ratings trigger `canvas-confetti`

#### Blitz mode

- `GET /api/v1/flashcards/blitz` returns 10 random MCQ cards from the user's current topic
- The flow runs as a 60-second session
- Timer progress is animated with Framer Motion
- Answers show immediate correct/incorrect feedback
- The result screen shows score and confetti at `8/10` or better

#### Boss round

- `GET /api/v1/flashcards/boss/{topicId}` returns 15 randomized cards for a completed topic
- A score of at least `80%` marks the topic completed
- A failing result returns concepts to revisit
- Boss-round results update `user_topic_progress`

### Quiz system

- `GET /api/v1/quiz/{topicId}` returns one quiz and its questions
- MCQ questions return shuffled options
- Code-output questions expose a code snippet and answer options
- `POST /api/v1/quiz/{quizId}/submit` grades answers automatically
- The response includes score, pass/fail, and per-question explanations

### Adaptive learning path

`adaptive_service.py` applies pure rule-based logic after quiz attempts:

- If score `< 0.6`, current topic becomes `in_progress`
- If score `>= 0.8`, unlock the next topic by `order_index`
- `mastery_score` is a weighted average of the last three quiz scores

`GET /api/v1/progress/path` returns the ordered topic path and statuses.

### Streak system

A streak day is defined as at least one flashcard review or one quiz attempt on that IST calendar day.

Rules:

- Streak increments at midnight IST
- Missing a day opens a grace period until `11:59 PM` IST on the next day
- Recovery requires 20 flashcard reviews in one session
- One freeze token replenishes every Monday at `00:00` IST
- Using a freeze token prevents a streak break for the missed day

`GET /api/v1/streak` must return enough metadata for the frontend to render both the persistent streak UI and the rage modal trigger state.

## Frontend Structure

The frontend will use the exact requested App Router structure.

### Root layout

`frontend/app/layout.tsx` provides:

- Clerk provider
- TanStack Query provider
- PostHog provider
- Sentry browser initialization hooks as needed

### Dashboard layout

The dashboard layout should remain structural, not business-heavy. It composes:

- Navigation shell
- `StreakBar`
- A lightweight streak-modal trigger hook

`StreakRageModal` itself should be a focused component rendered through a portal or equivalent overlay pattern, rather than embedding all of its state logic directly inside the layout file.

## Query and State Strategy

TanStack Query v5 is the server-state layer for all backend data.

Each query-backed page must define:

- loading state
- empty state where applicable
- error state with retry affordance where useful

This prevents blank or unstable UI when the backend is slow, unavailable, or cold-starting.

### Prefetching

Navigation should prefetch both route code and high-probability data where it improves perceived speed:

- Dashboard navigation can prefetch flashcards, progress, and quiz surfaces
- Learning flows can prefetch the next likely request

## Mobile-First UI Requirements

The minimum supported width is `375px`.

Component expectations:

- Sidebar collapses into a compact mobile navigation pattern below desktop breakpoints
- Streak bar compresses to a low-height banner
- Flashcard buttons use large touch targets
- Quiz and blitz layouts stay single-column on narrow screens
- Flip interactions remain tap-friendly

Desktop enhancements may layer on top, but the base layout must work on mobile first.

## Observability Contract

Observability is required from the start, not as a later add-on.

### Frontend Sentry

Capture:

- query failures
- rendering errors
- unexpected interaction failures

Where safe, enrich events with identifiers such as topic ID and user Clerk ID.

### Backend Sentry

Capture:

- unhandled route exceptions
- service-level failures
- curriculum generation failures
- auth verification failures where appropriate

### PostHog

Track product events such as:

- flashcard review submitted
- blitz completed
- boss round passed or failed
- quiz submitted
- freeze token used
- streak recovered

This makes it possible to debug both system errors and product behavior.

## Testing Strategy

The implementation plan must include tests for the most failure-prone logic, especially:

- FSRS scheduling transitions
- IST midnight boundary handling
- grace period cutoff at `11:59 PM` IST on the next day
- Monday freeze-token replenishment
- first-user creation under parallel requests
- quiz grading and adaptive unlock rules

Component-level UI work should also verify critical interaction states such as loading, empty, and error rendering.

## Step Order

Implementation must follow the user-mandated sequence exactly:

1. Scaffold full folder structure
2. Write SQLAlchemy models and initial Alembic migration
3. Implement Clerk auth middleware and backend Clerk verification
4. Implement FastAPI routers and Pydantic schemas with stub logic
5. Implement `fsrs_service.py` and `streak_service.py`
6. Wire real DB queries into routers
7. Build flashcard components
8. Build streak UI
9. Build quiz UI
10. Build progress path page
11. Write `generate_cards.py`
12. Add Sentry and PostHog
13. Write `vercel.json` and Railway Dockerfile

These steps must not be skipped or combined.

## Non-Negotiable Rules

- TypeScript strict mode only
- No `any`
- No raw `fetch` in components
- No raw SQL outside Alembic migrations
- Every FastAPI endpoint has a Pydantic response model
- Secrets come only from environment variables
- Redis keys are namespaced
- Dates are stored as UTC
- IST conversion happens at the logic or display boundary
- UI must work at `375px` minimum width

## Open Decisions Already Resolved

The following decisions are locked for planning:

- Use a polyglot monorepo with root orchestration
- Use backend OpenAPI as the API contract source of truth
- Generate frontend API types rather than hand-maintaining them
- Keep AI generation off the live user request path
- Treat observability as part of the initial architecture
- Define error, loading, and empty states explicitly in the UI design

## Next Step

The next step after this spec is an implementation plan that breaks the work into small, sequential tasks aligned to the required build order.
