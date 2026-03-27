# DatiSIQ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement DatiSIQ end-to-end in the exact user-mandated Step 1 through Step 13 order, without skipping or combining steps, while preserving strict typing, API contracts, and mobile-first behavior.

**Architecture:** DatiSIQ is a polyglot monorepo with a Next.js 15 frontend in `frontend/`, a FastAPI backend in `backend/`, generated API-facing TypeScript contract types in `packages/contracts/`, and an admin-only offline curriculum generation script in `scripts/`. Postgres is the source of truth, Upstash REST stores only ephemeral state, and all frontend server state flows through `frontend/lib/api.ts` plus TanStack Query hooks.

**Tech Stack:** pnpm workspace orchestration, Next.js 15 App Router, TypeScript strict mode, Tailwind CSS v4, shadcn/ui, TanStack Query v5, Framer Motion v11, Recharts, React Hook Form, Zod, canvas-confetti, Clerk, FastAPI, Pydantic v2, SQLAlchemy 2.0 async, Alembic, asyncpg, httpx, python-jose, Neon/Postgres, Upstash REST, Supabase Storage, Anthropic Python SDK, LangChain v0.3, Sentry SDK, PostHog, pytest, pytest-asyncio, openapi-typescript for generated frontend contracts.

---

## File Map

### Root workspace

- `package.json`: root scripts for frontend, contracts, and shared developer commands
- `pnpm-workspace.yaml`: workspace registration for `frontend` and `packages/*`
- `.gitignore`: node, Python, Next.js, and env ignores
- `vercel.json`: Vercel deployment config, placeholder in Step 1 and final content in Step 13
- `docs/superpowers/specs/2026-03-27-datisiq-design.md`: approved design spec
- `docs/superpowers/plans/2026-03-27-datisiq-implementation.md`: this implementation plan

### Contracts package

- `packages/contracts/package.json`: generated-contract package metadata
- `packages/contracts/src/index.ts`: re-export generated API types
- `packages/contracts/src/generated.ts`: generated OpenAPI types

### Frontend

- `frontend/package.json`: Next.js app dependencies and scripts
- `frontend/tsconfig.json`: strict TypeScript configuration
- `frontend/next.config.ts`: Next.js config
- `frontend/postcss.config.mjs`: Tailwind v4 PostCSS hook
- `frontend/components.json`: shadcn/ui registry config
- `frontend/app/globals.css`: Tailwind imports and global tokens
- `frontend/app/layout.tsx`: root providers and global shell wiring
- `frontend/app/page.tsx`: landing or auth-aware redirect
- `frontend/app/(auth)/sign-in/[[...sign-in]]/page.tsx`: Clerk sign-in page
- `frontend/app/(auth)/sign-up/[[...sign-up]]/page.tsx`: Clerk sign-up page
- `frontend/app/(dashboard)/layout.tsx`: protected shell, sidebar, streak integration
- `frontend/app/(dashboard)/dashboard/page.tsx`: dashboard overview
- `frontend/app/(dashboard)/learn/[topicId]/page.tsx`: topic learning surface
- `frontend/app/(dashboard)/flashcards/page.tsx`: due-card recall flow
- `frontend/app/(dashboard)/flashcards/blitz/page.tsx`: blitz mode page
- `frontend/app/(dashboard)/quiz/[topicId]/page.tsx`: quiz page
- `frontend/app/(dashboard)/progress/page.tsx`: path and mastery page
- `frontend/components/flashcards/FlipCard.tsx`: 3D flashcard component
- `frontend/components/flashcards/BlitzMode.tsx`: timed 10-card experience
- `frontend/components/flashcards/RatingButtons.tsx`: review actions and celebration trigger
- `frontend/components/flashcards/BossRound.tsx`: 15-card boss round flow
- `frontend/components/streak/StreakBar.tsx`: top streak banner
- `frontend/components/streak/StreakRageModal.tsx`: missed-streak modal
- `frontend/components/streak/FreezeToken.tsx`: freeze-token action block
- `frontend/components/quiz/MCQQuestion.tsx`: multiple-choice question renderer
- `frontend/components/quiz/CodeQuestion.tsx`: code-output question renderer
- `frontend/components/ui/*`: individually installed shadcn/ui primitives
- `frontend/lib/api.ts`: typed fetch wrapper and auth-aware request helper
- `frontend/lib/queries.ts`: TanStack Query hooks and query keys
- `frontend/lib/streak-utils.ts`: session dismissal and client streak helpers
- `frontend/middleware.ts`: Clerk route protection

### Backend

- `backend/requirements.txt`: Python dependencies
- `backend/Dockerfile`: Railway container image, placeholder in Step 1 and final content in Step 13
- `backend/alembic.ini`: Alembic config
- `backend/alembic/env.py`: Alembic environment
- `backend/alembic/script.py.mako`: Alembic template
- `backend/alembic/versions/0001_initial_schema.py`: initial migration
- `backend/app/main.py`: FastAPI app assembly
- `backend/app/core/config.py`: env-backed settings
- `backend/app/core/database.py`: async SQLAlchemy engine, session, base imports
- `backend/app/core/auth.py`: Clerk verification and current-user resolution
- `backend/app/core/redis.py`: Upstash REST client helpers
- `backend/app/routers/flashcards.py`: flashcard endpoints
- `backend/app/routers/quiz.py`: quiz endpoints
- `backend/app/routers/progress.py`: progress endpoints
- `backend/app/routers/streak.py`: streak endpoints
- `backend/app/routers/curriculum.py`: admin curriculum endpoints
- `backend/app/services/fsrs_service.py`: simplified SM-2 scheduling logic
- `backend/app/services/streak_service.py`: IST streak and grace rules
- `backend/app/services/adaptive_service.py`: quiz-driven mastery and unlock logic
- `backend/app/services/ai_service.py`: Claude batch generation orchestration
- `backend/app/models/db.py`: SQLAlchemy enums and models
- `backend/app/schemas/flashcards.py`: flashcard request and response models
- `backend/app/schemas/quiz.py`: quiz request and response models
- `backend/app/schemas/progress.py`: progress response models
- `backend/app/schemas/streak.py`: streak response models
- `backend/app/schemas/curriculum.py`: curriculum request and response models

### Tests and support files

- `backend/tests/models/test_db_metadata.py`: schema and enum metadata tests
- `backend/tests/auth/test_auth_dependency.py`: Clerk verification tests
- `backend/tests/routers/test_stub_routes.py`: stub response contract tests
- `backend/tests/services/test_fsrs_service.py`: FSRS unit tests
- `backend/tests/services/test_streak_service.py`: streak edge-case tests
- `backend/tests/routers/test_flashcards_router.py`: DB-backed flashcard route tests
- `backend/tests/routers/test_quiz_router.py`: DB-backed quiz route tests
- `backend/tests/routers/test_progress_router.py`: DB-backed progress route tests
- `backend/tests/routers/test_streak_router.py`: DB-backed streak route tests
- `scripts/generate_cards.py`: manual curriculum generation CLI

## Assumptions

- Use `pnpm` for all JavaScript package management.
- Use a local Python virtual environment under `.venv` for backend work.
- Use `pytest` and `pytest-asyncio` for backend verification.
- Generate frontend API types from FastAPI OpenAPI with `openapi-typescript`.
- Keep frontend validation schemas local to the frontend for UX, while backend Pydantic remains the network source of truth.
- Do not execute live Anthropic generation until Step 11.

## Task Sequence

### Task 1: Step 1 Workspace Scaffold

**Files:**
- Create: `package.json`
- Create: `pnpm-workspace.yaml`
- Create: `.gitignore`
- Create: `packages/contracts/package.json`
- Create: `packages/contracts/src/index.ts`
- Create: `packages/contracts/src/generated.ts`
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/next.config.ts`
- Create: `frontend/postcss.config.mjs`
- Create: `frontend/components.json`
- Create: `frontend/app/globals.css`
- Create: `frontend/app/layout.tsx`
- Create: `frontend/app/page.tsx`
- Create: `frontend/app/(auth)/sign-in/[[...sign-in]]/page.tsx`
- Create: `frontend/app/(auth)/sign-up/[[...sign-up]]/page.tsx`
- Create: `frontend/app/(dashboard)/layout.tsx`
- Create: `frontend/app/(dashboard)/dashboard/page.tsx`
- Create: `frontend/app/(dashboard)/learn/[topicId]/page.tsx`
- Create: `frontend/app/(dashboard)/flashcards/page.tsx`
- Create: `frontend/app/(dashboard)/flashcards/blitz/page.tsx`
- Create: `frontend/app/(dashboard)/quiz/[topicId]/page.tsx`
- Create: `frontend/app/(dashboard)/progress/page.tsx`
- Create: `frontend/components/flashcards/FlipCard.tsx`
- Create: `frontend/components/flashcards/BlitzMode.tsx`
- Create: `frontend/components/flashcards/RatingButtons.tsx`
- Create: `frontend/components/flashcards/BossRound.tsx`
- Create: `frontend/components/streak/StreakBar.tsx`
- Create: `frontend/components/streak/StreakRageModal.tsx`
- Create: `frontend/components/streak/FreezeToken.tsx`
- Create: `frontend/components/quiz/MCQQuestion.tsx`
- Create: `frontend/components/quiz/CodeQuestion.tsx`
- Create: `frontend/lib/api.ts`
- Create: `frontend/lib/queries.ts`
- Create: `frontend/lib/streak-utils.ts`
- Create: `frontend/middleware.ts`
- Create: `backend/requirements.txt`
- Create: `backend/Dockerfile`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/app/main.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/database.py`
- Create: `backend/app/core/auth.py`
- Create: `backend/app/core/redis.py`
- Create: `backend/app/routers/flashcards.py`
- Create: `backend/app/routers/quiz.py`
- Create: `backend/app/routers/progress.py`
- Create: `backend/app/routers/streak.py`
- Create: `backend/app/routers/curriculum.py`
- Create: `backend/app/services/fsrs_service.py`
- Create: `backend/app/services/streak_service.py`
- Create: `backend/app/services/adaptive_service.py`
- Create: `backend/app/services/ai_service.py`
- Create: `backend/app/models/db.py`
- Create: `backend/app/schemas/flashcards.py`
- Create: `backend/app/schemas/quiz.py`
- Create: `backend/app/schemas/progress.py`
- Create: `backend/app/schemas/streak.py`
- Create: `backend/app/schemas/curriculum.py`
- Create: `backend/tests/models/test_db_metadata.py`
- Create: `backend/tests/auth/test_auth_dependency.py`
- Create: `backend/tests/routers/test_stub_routes.py`
- Create: `backend/tests/services/test_fsrs_service.py`
- Create: `backend/tests/services/test_streak_service.py`
- Create: `backend/tests/routers/test_flashcards_router.py`
- Create: `backend/tests/routers/test_quiz_router.py`
- Create: `backend/tests/routers/test_progress_router.py`
- Create: `backend/tests/routers/test_streak_router.py`
- Create: `scripts/generate_cards.py`
- Create: `vercel.json`

- [ ] **Step 1: Create root workspace files and scripts**

```json
{
  "name": "datasiq",
  "private": true,
  "packageManager": "pnpm@10",
  "scripts": {
    "dev:frontend": "pnpm --dir frontend dev",
    "build:frontend": "pnpm --dir frontend build",
    "typecheck:frontend": "pnpm --dir frontend exec tsc --noEmit",
    "contracts:generate": "openapi-typescript http://localhost:8000/openapi.json -o packages/contracts/src/generated.ts"
  }
}
```

- [ ] **Step 2: Create every required frontend and backend file with TODO-safe placeholder content**

```ts
export default function PlaceholderPage() {
  return <main>TODO: implement page</main>;
}
```

```python
"""TODO: implement this module in its assigned step."""
```

- [ ] **Step 3: Add minimal package manifests and config placeholders without implementing business logic**

```yaml
packages:
  - "frontend"
  - "packages/*"
```

- [ ] **Step 4: Verify the scaffold matches the expected tree**

Run: `rg --files`
Expected: all requested frontend, backend, scripts, and root files appear in the output

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "chore: scaffold datasiq workspace"
```

### Task 2: Step 2 Models and Initial Migration

**Files:**
- Modify: `backend/app/models/db.py`
- Modify: `backend/app/core/database.py`
- Modify: `backend/alembic.ini`
- Modify: `backend/alembic/env.py`
- Modify: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/0001_initial_schema.py`
- Modify: `backend/tests/models/test_db_metadata.py`

- [ ] **Step 1: Write the failing metadata test for table names, enum coverage, and key constraints**

```python
def test_expected_tables_exist() -> None:
    table_names = set(Base.metadata.tables.keys())
    assert "users" in table_names
    assert "flashcard_reviews" in table_names
    assert "streak_events" in table_names
```

- [ ] **Step 2: Run the test to verify it fails before models exist**

Run: `pytest backend/tests/models/test_db_metadata.py -q`
Expected: FAIL because the metadata is still empty or placeholder-only

- [ ] **Step 3: Implement SQLAlchemy enums, UUID keys, relationships, and timestamp defaults**

```python
class TopicDifficulty(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
```

```python
id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
```

- [ ] **Step 4: Write the initial Alembic migration with all tables and enum types from the spec**

Run: `cd backend; alembic upgrade head`
Expected: migration applies cleanly against the configured development database

- [ ] **Step 5: Re-run the metadata test and commit**

Run: `pytest backend/tests/models/test_db_metadata.py -q`
Expected: PASS

```bash
git add backend/app/models/db.py backend/app/core/database.py backend/alembic.ini backend/alembic/env.py backend/alembic/script.py.mako backend/alembic/versions/0001_initial_schema.py backend/tests/models/test_db_metadata.py
git commit -m "feat: add initial database schema"
```

### Task 3: Step 3 Clerk Auth Foundation

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/app/layout.tsx`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/app/(auth)/sign-in/[[...sign-in]]/page.tsx`
- Modify: `frontend/app/(auth)/sign-up/[[...sign-up]]/page.tsx`
- Modify: `frontend/middleware.ts`
- Modify: `backend/requirements.txt`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/core/auth.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/auth/test_auth_dependency.py`

- [ ] **Step 1: Write the failing backend auth test for verified Clerk subject extraction and race-safe user resolution**

```python
async def test_get_current_user_rejects_missing_bearer_token() -> None:
    with pytest.raises(HTTPException):
        await get_current_user(session=mock_session, authorization=None)
```

- [ ] **Step 2: Run the auth test to verify it fails**

Run: `pytest backend/tests/auth/test_auth_dependency.py -q`
Expected: FAIL because the auth dependency is still a placeholder

- [ ] **Step 3: Implement Clerk frontend providers and route protection**

```ts
export default clerkMiddleware(async (auth, req) => {
  if (isProtectedRoute(req)) {
    await auth.protect();
  }
});
```

- [ ] **Step 4: Implement backend token verification and local user upsert**

```python
stmt = insert(User).values(...).on_conflict_do_nothing(index_elements=[User.clerk_id])
```

- [ ] **Step 5: Re-run auth tests and frontend typecheck**

Run: `pytest backend/tests/auth/test_auth_dependency.py -q`
Expected: PASS

Run: `pnpm --dir frontend exec tsc --noEmit`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/app/layout.tsx frontend/app/page.tsx frontend/app/(auth)/sign-in/[[...sign-in]]/page.tsx frontend/app/(auth)/sign-up/[[...sign-up]]/page.tsx frontend/middleware.ts backend/requirements.txt backend/app/core/config.py backend/app/core/auth.py backend/app/main.py backend/tests/auth/test_auth_dependency.py
git commit -m "feat: add clerk auth foundation"
```

### Task 4: Step 4 Pydantic Schemas and Stub Routers

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/routers/flashcards.py`
- Modify: `backend/app/routers/quiz.py`
- Modify: `backend/app/routers/progress.py`
- Modify: `backend/app/routers/streak.py`
- Modify: `backend/app/routers/curriculum.py`
- Modify: `backend/app/schemas/flashcards.py`
- Modify: `backend/app/schemas/quiz.py`
- Modify: `backend/app/schemas/progress.py`
- Modify: `backend/app/schemas/streak.py`
- Modify: `backend/app/schemas/curriculum.py`
- Modify: `packages/contracts/src/index.ts`
- Modify: `backend/tests/routers/test_stub_routes.py`

- [ ] **Step 1: Write failing API contract tests for stub endpoints**

```python
def test_progress_path_returns_ordered_topics(client: TestClient) -> None:
    response = client.get("/api/v1/progress/path")
    assert response.status_code == 200
    assert "topics" in response.json()
```

- [ ] **Step 2: Run the stub route tests to verify they fail**

Run: `pytest backend/tests/routers/test_stub_routes.py -q`
Expected: FAIL because routers and schemas are placeholders

- [ ] **Step 3: Implement Pydantic request and response models for every endpoint**

```python
class FlashcardReviewRequest(BaseModel):
    card_id: UUID
    rating: ReviewRating
```

- [ ] **Step 4: Implement `/api/v1` routers with mock data only, no real DB queries yet**

```python
router = APIRouter(prefix="/flashcards", tags=["flashcards"])
```

- [ ] **Step 5: Generate frontend contract types from OpenAPI**

Run: `pnpm contracts:generate`
Expected: `packages/contracts/src/generated.ts` is created or updated successfully

- [ ] **Step 6: Re-run route tests and commit**

Run: `pytest backend/tests/routers/test_stub_routes.py -q`
Expected: PASS

```bash
git add backend/app/main.py backend/app/routers backend/app/schemas packages/contracts/src/index.ts backend/tests/routers/test_stub_routes.py packages/contracts/src/generated.ts
git commit -m "feat: add stub api contracts"
```

### Task 5: Step 5 FSRS Service

**Files:**
- Modify: `backend/app/services/fsrs_service.py`
- Modify: `backend/tests/services/test_fsrs_service.py`

- [ ] **Step 1: Write failing unit tests for the simplified SM-2 transitions**

```python
def test_easy_rating_scales_interval_and_stability() -> None:
    result = compute_next_review("easy", stability=2.0, difficulty=2.5, interval=3)
    assert result["interval_days"] == 8
```

- [ ] **Step 2: Run the FSRS tests to verify they fail**

Run: `pytest backend/tests/services/test_fsrs_service.py -q`
Expected: FAIL because the service is still a placeholder

- [ ] **Step 3: Implement `compute_next_review` exactly from the approved spec**

```python
ease_map = {"forgot": 1.2, "hard": 1.5, "okay": 2.0, "easy": 2.8}
```

- [ ] **Step 4: Re-run the FSRS tests**

Run: `pytest backend/tests/services/test_fsrs_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/fsrs_service.py backend/tests/services/test_fsrs_service.py
git commit -m "feat: implement fsrs scheduling service"
```

### Task 6: Step 5 Streak Service

**Files:**
- Modify: `backend/app/services/streak_service.py`
- Modify: `backend/tests/services/test_streak_service.py`

- [ ] **Step 1: Write failing unit tests for IST midnight, grace cutoff, and Monday replenishment**

```python
def test_replenishes_freeze_token_on_monday_midnight_ist() -> None:
    state = evaluate_streak_state(...)
    assert state.freeze_tokens_remaining == 1
```

- [ ] **Step 2: Run the streak tests to verify they fail**

Run: `pytest backend/tests/services/test_streak_service.py -q`
Expected: FAIL because the streak service is still a placeholder

- [ ] **Step 3: Implement `streak_service.py` with `pytz`-based IST helpers and pure functions**

```python
IST = pytz.timezone("Asia/Kolkata")
```

- [ ] **Step 4: Re-run the streak tests**

Run: `pytest backend/tests/services/test_streak_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/streak_service.py backend/tests/services/test_streak_service.py
git commit -m "feat: implement streak rules service"
```

### Task 7: Step 6 Core DB, Redis, and Adaptive Wiring

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/core/database.py`
- Modify: `backend/app/core/auth.py`
- Modify: `backend/app/core/redis.py`
- Modify: `backend/app/services/adaptive_service.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Implement shared async session, settings, Upstash REST client, and adaptive helpers**

```python
async with httpx.AsyncClient(base_url=settings.upstash_redis_rest_url) as client:
    ...
```

- [ ] **Step 2: Ensure Redis helpers always set TTLs for ephemeral keys**

```python
await set_json(f"session:{user_id}:blitz", payload, ttl_seconds=3600)
```

- [ ] **Step 3: Add adaptive learning helper functions**

```python
def compute_weighted_mastery(scores: list[float]) -> float:
    ...
```

- [ ] **Step 4: Run service tests**

Run: `pytest backend/tests/services -q`
Expected: PASS for FSRS, streak, and any new adaptive tests

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/config.py backend/app/core/database.py backend/app/core/auth.py backend/app/core/redis.py backend/app/services/adaptive_service.py backend/requirements.txt backend/tests/services
git commit -m "feat: add shared backend runtime services"
```

### Task 8: Step 6 Flashcards and Streak Router DB Integration

**Files:**
- Modify: `backend/app/routers/flashcards.py`
- Modify: `backend/app/routers/streak.py`
- Modify: `backend/app/schemas/flashcards.py`
- Modify: `backend/app/schemas/streak.py`
- Modify: `backend/tests/routers/test_flashcards_router.py`
- Modify: `backend/tests/routers/test_streak_router.py`

- [ ] **Step 1: Write failing route tests for due cards, review writes, freeze use, and recovery validation**

```python
async def test_review_endpoint_persists_next_review(client) -> None:
    response = await client.post("/api/v1/flashcards/review", json={"card_id": str(card_id), "rating": "easy"})
    assert response.status_code == 200
```

- [ ] **Step 2: Run the flashcard and streak route tests to verify they fail**

Run: `pytest backend/tests/routers/test_flashcards_router.py backend/tests/routers/test_streak_router.py -q`
Expected: FAIL because the routes still return mocks

- [ ] **Step 3: Replace mock flashcard and streak responses with SQLAlchemy-backed queries**

- [ ] **Step 4: Use Upstash REST only for ephemeral session state**

- [ ] **Step 5: Re-run the route tests**

Run: `pytest backend/tests/routers/test_flashcards_router.py backend/tests/routers/test_streak_router.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/flashcards.py backend/app/routers/streak.py backend/app/schemas/flashcards.py backend/app/schemas/streak.py backend/tests/routers/test_flashcards_router.py backend/tests/routers/test_streak_router.py
git commit -m "feat: wire flashcard and streak routes"
```

### Task 9: Step 6 Quiz and Progress Router DB Integration

**Files:**
- Modify: `backend/app/routers/quiz.py`
- Modify: `backend/app/routers/progress.py`
- Modify: `backend/app/schemas/quiz.py`
- Modify: `backend/app/schemas/progress.py`
- Modify: `backend/app/services/adaptive_service.py`
- Modify: `backend/tests/routers/test_quiz_router.py`
- Modify: `backend/tests/routers/test_progress_router.py`

- [ ] **Step 1: Write failing route tests for quiz grading, pass/fail, mastery updates, and ordered learning path**

```python
async def test_submit_quiz_unlocks_next_topic_on_high_score(client) -> None:
    response = await client.post(f"/api/v1/quiz/{quiz_id}/submit", json=payload)
    assert response.json()["passed"] is True
```

- [ ] **Step 2: Run the quiz and progress tests to verify they fail**

Run: `pytest backend/tests/routers/test_quiz_router.py backend/tests/routers/test_progress_router.py -q`
Expected: FAIL because the routes still return mocks

- [ ] **Step 3: Replace mock quiz and progress logic with real SQLAlchemy queries and adaptive updates**

- [ ] **Step 4: Re-run the tests and regenerate contract types**

Run: `pytest backend/tests/routers/test_quiz_router.py backend/tests/routers/test_progress_router.py -q`
Expected: PASS

Run: `pnpm contracts:generate`
Expected: generated frontend contracts reflect the final route payloads

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/quiz.py backend/app/routers/progress.py backend/app/schemas/quiz.py backend/app/schemas/progress.py backend/app/services/adaptive_service.py backend/tests/routers/test_quiz_router.py backend/tests/routers/test_progress_router.py packages/contracts/src/generated.ts
git commit -m "feat: wire quiz and progress routes"
```

### Task 10: Step 6 Curriculum Admin Wiring

**Files:**
- Modify: `backend/app/routers/curriculum.py`
- Modify: `backend/app/schemas/curriculum.py`
- Modify: `backend/app/core/auth.py`
- Modify: `packages/contracts/src/generated.ts`

- [ ] **Step 1: Implement the admin-gated curriculum route without live generation yet**

- [ ] **Step 2: Mount the route under `/api/v1/curriculum` and verify OpenAPI output**

Run: `pnpm contracts:generate`
Expected: curriculum types are present in generated contracts

- [ ] **Step 3: Smoke-test the backend app**

Run: `cd backend; uvicorn app.main:app --reload`
Expected: FastAPI starts and `/docs` shows all `/api/v1` endpoints

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/curriculum.py backend/app/schemas/curriculum.py backend/app/core/auth.py packages/contracts/src/generated.ts
git commit -m "feat: add curriculum admin route wiring"
```

### Task 11: Step 7 Flashcard UI and Data Hooks

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/app/layout.tsx`
- Modify: `frontend/app/(dashboard)/flashcards/page.tsx`
- Modify: `frontend/app/(dashboard)/flashcards/blitz/page.tsx`
- Modify: `frontend/app/(dashboard)/learn/[topicId]/page.tsx`
- Modify: `frontend/components/flashcards/FlipCard.tsx`
- Modify: `frontend/components/flashcards/RatingButtons.tsx`
- Modify: `frontend/components/flashcards/BlitzMode.tsx`
- Modify: `frontend/components/flashcards/BossRound.tsx`
- Modify: `frontend/components/ui/*`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/lib/queries.ts`

- [ ] **Step 1: Install required frontend libraries and individual shadcn components**

Run: `pnpm --dir frontend add @tanstack/react-query framer-motion recharts react-hook-form zod @hookform/resolvers canvas-confetti`
Expected: dependencies are added without introducing `any`-based code

Run: `pnpm --dir frontend dlx shadcn@latest add button card dialog progress sheet badge skeleton`
Expected: only the listed UI primitives are installed

- [ ] **Step 2: Build the typed fetch wrapper and flashcard query hooks**

```ts
export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}${path}`, init);
  if (!response.ok) throw new Error(`API request failed: ${response.status}`);
  return (await response.json()) as T;
}
```

- [ ] **Step 3: Build `FlipCard`, `RatingButtons`, `BlitzMode`, and `BossRound` with mobile-first states**

- [ ] **Step 4: Wire flashcard pages to real queries**

- [ ] **Step 5: Typecheck and build the frontend flashcard surfaces**

Run: `pnpm --dir frontend exec tsc --noEmit`
Expected: PASS

Run: `pnpm --dir frontend build`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/app/layout.tsx frontend/app/(dashboard)/flashcards/page.tsx frontend/app/(dashboard)/flashcards/blitz/page.tsx frontend/app/(dashboard)/learn/[topicId]/page.tsx frontend/components/flashcards frontend/components/ui frontend/lib/api.ts frontend/lib/queries.ts
git commit -m "feat: build flashcard experiences"
```

### Task 12: Step 8 Streak UI and Dashboard Integration

**Files:**
- Modify: `frontend/app/(dashboard)/layout.tsx`
- Modify: `frontend/app/(dashboard)/dashboard/page.tsx`
- Modify: `frontend/components/streak/StreakBar.tsx`
- Modify: `frontend/components/streak/StreakRageModal.tsx`
- Modify: `frontend/components/streak/FreezeToken.tsx`
- Modify: `frontend/lib/queries.ts`
- Modify: `frontend/lib/streak-utils.ts`

- [ ] **Step 1: Build query hooks and client helpers for session-limited modal display**

```ts
const STREAK_MODAL_SESSION_KEY = "datasiq:streak-rage-dismissed";
```

- [ ] **Step 2: Implement `StreakBar`, `FreezeToken`, and `StreakRageModal`**

- [ ] **Step 3: Integrate the streak components into the protected dashboard shell**

- [ ] **Step 4: Typecheck and manually verify the streak surfaces**

Run: `pnpm --dir frontend exec tsc --noEmit`
Expected: PASS

Run: `pnpm --dir frontend build`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/app/(dashboard)/layout.tsx frontend/app/(dashboard)/dashboard/page.tsx frontend/components/streak frontend/lib/queries.ts frontend/lib/streak-utils.ts
git commit -m "feat: add streak dashboard ui"
```

### Task 13: Step 9 Quiz UI and Submission Flow

**Files:**
- Modify: `frontend/app/(dashboard)/quiz/[topicId]/page.tsx`
- Modify: `frontend/components/quiz/MCQQuestion.tsx`
- Modify: `frontend/components/quiz/CodeQuestion.tsx`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/lib/queries.ts`

- [ ] **Step 1: Build typed quiz query and mutation hooks**

- [ ] **Step 2: Implement `MCQQuestion` and `CodeQuestion`**

- [ ] **Step 3: Build the quiz page with React Hook Form and Zod**

```ts
const quizSchema = z.object({
  answers: z.record(z.string(), z.string().min(1))
});
```

- [ ] **Step 4: Typecheck and build the quiz route**

Run: `pnpm --dir frontend exec tsc --noEmit`
Expected: PASS

Run: `pnpm --dir frontend build`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/app/(dashboard)/quiz/[topicId]/page.tsx frontend/components/quiz frontend/lib/api.ts frontend/lib/queries.ts
git commit -m "feat: build quiz interface"
```

### Task 14: Step 10 Progress Path Visualization

**Files:**
- Modify: `frontend/app/(dashboard)/progress/page.tsx`
- Modify: `frontend/app/(dashboard)/dashboard/page.tsx`
- Modify: `frontend/lib/queries.ts`

- [ ] **Step 1: Build typed progress query hooks**

- [ ] **Step 2: Implement the progress page using Recharts and clear topic state visuals**

- [ ] **Step 3: Add prefetching from the dashboard and nav**

- [ ] **Step 4: Typecheck and build the progress route**

Run: `pnpm --dir frontend exec tsc --noEmit`
Expected: PASS

Run: `pnpm --dir frontend build`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/app/(dashboard)/progress/page.tsx frontend/app/(dashboard)/dashboard/page.tsx frontend/lib/queries.ts
git commit -m "feat: add progress visualization"
```

### Task 15: Step 11 AI Generation Script and Live Curriculum Trigger

**Files:**
- Modify: `backend/app/services/ai_service.py`
- Modify: `backend/app/routers/curriculum.py`
- Modify: `backend/app/schemas/curriculum.py`
- Modify: `scripts/generate_cards.py`
- Modify: `backend/tests/routers/test_stub_routes.py`

- [ ] **Step 1: Write the failing generation test or isolated contract check**

- [ ] **Step 2: Implement `ai_service.py` with Anthropic + LangChain batch orchestration**

- [ ] **Step 3: Implement `scripts/generate_cards.py` as a manual admin CLI**

```python
async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic-id", required=True)
```

- [ ] **Step 4: Replace the curriculum route placeholder with the live admin-triggered generation flow**

Run: `pytest backend/tests/routers/test_stub_routes.py -q`
Expected: PASS with updated curriculum behavior

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai_service.py backend/app/routers/curriculum.py backend/app/schemas/curriculum.py scripts/generate_cards.py backend/tests/routers/test_stub_routes.py
git commit -m "feat: add curriculum generation pipeline"
```

### Task 16: Step 12 Monitoring and Analytics

**Files:**
- Modify: `frontend/app/layout.tsx`
- Modify: `frontend/package.json`
- Modify: `frontend/lib/api.ts`
- Modify: `backend/app/main.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Install Sentry and PostHog SDKs**

Run: `pnpm --dir frontend add @sentry/nextjs posthog-js`
Expected: packages installed successfully

Run: `python -m pip install -r backend/requirements.txt`
Expected: backend deps include Sentry SDK

- [ ] **Step 2: Add frontend PostHog and Sentry initialization**

- [ ] **Step 3: Add backend Sentry initialization and error tagging**

- [ ] **Step 4: Verify build and startup**

Run: `pnpm --dir frontend build`
Expected: PASS

Run: `cd backend; uvicorn app.main:app --reload`
Expected: backend starts with Sentry enabled when DSN is present

- [ ] **Step 5: Commit**

```bash
git add frontend/app/layout.tsx frontend/package.json frontend/lib/api.ts backend/app/main.py backend/app/core/config.py backend/requirements.txt
git commit -m "feat: add monitoring and analytics"
```

### Task 17: Step 13 Deployment Configuration

**Files:**
- Modify: `vercel.json`
- Modify: `backend/Dockerfile`
- Modify: `frontend/package.json`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Replace deployment placeholders with final production config**

- [ ] **Step 2: Verify production build commands locally**

Run: `pnpm --dir frontend build`
Expected: PASS

Run: `docker build -f backend/Dockerfile backend`
Expected: image builds successfully

- [ ] **Step 3: Commit**

```bash
git add vercel.json backend/Dockerfile frontend/package.json backend/requirements.txt
git commit -m "chore: add deployment configuration"
```

## Verification Checklist Before Claiming Completion

- [ ] `rg --files` shows every required file from the project brief
- [ ] `pytest backend/tests -q` passes
- [ ] `pnpm --dir frontend exec tsc --noEmit` passes
- [ ] `pnpm --dir frontend build` passes
- [ ] `pnpm contracts:generate` runs cleanly
- [ ] `cd backend; alembic upgrade head` succeeds against the configured dev database
- [ ] `cd backend; uvicorn app.main:app --reload` serves `/docs`
- [ ] Manual QA covers sign-in, due cards, blitz, boss round, quiz submit, streak modal, freeze, recovery, and progress path

## Notes for Execution

- Do not collapse steps together even if implementation overlap is tempting.
- Keep placeholder-only files in Step 1, then replace them in their assigned step.
- Any unavoidable type assertion in TypeScript must be documented inline with a brief comment.
- Do not put live AI calls anywhere in normal user request handling.
- Preserve API versioning under `/api/v1` throughout the build.
