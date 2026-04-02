# DatiSIQ

DatiSIQ is a full-stack adaptive learning platform for data analytics and data science topics.

The repository is organized as a small monorepo:

- `frontend/`: Next.js 15 learner experience
- `backend/`: FastAPI API for flashcards, quizzes, progress, and streaks
- `packages/contracts/`: generated API contracts used by the frontend
- `scripts/`: utility scripts for local and admin workflows
- `docs/`: product and implementation notes

## What You Can Run

The project includes a local demo mode so you can explore the app without real auth, Postgres, or external services.

- Demo user: `Test User`
- Demo email: `test.user@datasiq.local`
- Demo token: `dev-demo-token`

The backend seeds a local SQLite database automatically in demo mode, so the dashboard, flashcards, progress, and quiz screens all have believable starter content.

## Quick Start

1. Install frontend dependencies:
   `cd frontend && npm install`
2. Start the backend from the repo root:
   `npm run dev:backend`
3. Start the frontend from the `frontend/` folder or use the root script:
   `corepack pnpm run dev:frontend`

## Local URLs

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

## Demo Mode

Demo mode is enabled by the local env files checked into the workspace:

- `backend/.env`
- `frontend/.env.local`

If you want to tweak the demo identity or sample content, the main places are:

- [backend/app/core/config.py](./backend/app/core/config.py)
- [backend/app/services/local_dev.py](./backend/app/services/local_dev.py)
- [frontend/lib/dev-auth.ts](./frontend/lib/dev-auth.ts)
- [frontend/app/(dashboard)/layout.tsx](./frontend/app/(dashboard)/layout.tsx)

## Notes

- The repo is set up to work with a local test identity for fast visual checks.
- `README.md` intentionally stays focused on how to run and understand the project, not on implementation history.
- If you are cleaning the workspace, keep the real project folders and ignore generated caches like `node_modules/`, `.next/`, and local temp logs.
