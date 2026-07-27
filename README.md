# Momentum

An AI-powered single-board project management application. Momentum pairs a
focused Kanban board with an assistive AI sidekick that can read and update
the board from natural conversation. The Next.js frontend (React + dnd-kit)
is statically exported and served by a FastAPI backend behind a single
origin in production.

## Features

- Single Kanban board with five renameable columns and drag-and-drop cards
- Card create / edit / delete; editable board title
- Sprint overview panel with a configurable start/deadline and progress
- Hardcoded user sign-in (`user` / `password`) with signed-cookie sessions
- Persistent state — SQLite, auto-created and seeded on first startup
- AI assistant sidebar ("Ask AI") that can:
  - create, move, or delete cards
  - rename a column or the board
  - chat naturally about the board
- Backend is the source of truth — every AI change returns the full board
  snapshot so the UI refreshes in one round-trip

## Tech stack

- **Frontend:** Next.js 16 (React 19), `@dnd-kit` for drag-and-drop,
  statically exported via `next build` with `output: 'export'`
- **Backend:** FastAPI + Pydantic v2 + Uvicorn (Python 3.11+)
- **Database:** SQLite (stdlib `sqlite3`); schema created on startup
- **AI:** OpenAI SDK pointed at OpenRouter; structured JSON responses
  validated with a pydantic schema
- **Testing:** pytest + httpx (backend), Vitest + Testing Library + Playwright
  (frontend), ruff + ESLint (lint)
- **Deployment:** Docker multi-stage build (Node stage builds the frontend,
  Python stage serves it), orchestrated with `docker-compose.yml`

## Architecture overview

- **Frontend** (`frontend/`) — Next.js client-rendered app (Kanban board +
  Sprint overview + AI chat sidebar), statically exported via `next build`
  with `output: 'export'`. Reads from and writes to the backend REST API
  (`src/lib/api.ts`). A topbar "Ask AI" button toggles a slide-in sidebar
  (`components/AIChatSidebar.tsx`) backed by `POST /api/ai/chat` — when the AI
  changes the board the returned snapshot replaces local state. A "Sign out"
  button calls `POST /api/logout`. In dev, `/api/*` and `/login` are proxied
  to the backend.
- **Backend** (`backend/`) — FastAPI app exposing the `/api/*` REST API and
  serving the static frontend build. Thin routes delegate to a board
  service that owns all database work.
- **Database** — SQLite file at `backend/data/kanban.db` (overridable via
  `KANBAN_DB_PATH`), auto-created and seeded on first startup. Single
  hardcoded user, single board, five columns, cards, and a chat history
  table reserved for the AI sidekick.
- **Authentication** — Signed-cookie sessions (Starlette
  `SessionMiddleware`); a single hardcoded user (`user` / `password`).
  Every route except `/login`, `/api/login`, `/api/logout`, and `/api/ping`
  is gated.
- **Backend REST API** — `/api/board` (read), `/api/columns/{id}/rename`,
  `/api/cards` (create), `/api/cards/{id}` (delete),
  `/api/cards/{id}/move`, and `/api/board/meta` (rename board). Mutations
  return the full board snapshot for the frontend to swap in. A connectivity
  endpoint `GET /api/ai/test` returns the OpenRouter model's answer to
  "What is 2+2?", and `POST /api/ai/chat` runs one AI board-chat turn:
  receiving a user message, returning a reply and the updated board
  snapshot (the AI can optionally apply one of the allowed board actions —
  create/delete/move card, rename column, rename board — through the board
  service).
- **AI connectivity** — OpenAI SDK pointed at OpenRouter
  (`https://openrouter.ai/api/v1`). `OPENROUTER_API_KEY` and
  `OPENROUTER_MODEL` (default `openai/gpt-oss-20b:free`) come from the
  environment; no model name is hardcoded in application code. AI board chat
  asks the model for `response_format={"type": "json_object"}` (the
  reliable path for this free reasoning model per Phase 7 notes), parses and
  validates the payload with a pydantic schema, and retries once on
  malformed JSON before returning a safe reply.
- **Deployment** — Docker multi-stage build (Node stage builds the
  frontend, Python stage serves it) orchestrated via `docker-compose.yml`.

Request flow (live end-to-end): **frontend → FastAPI API routes → board_service → SQLite**.
The frontend hydrates the board from `GET /api/board` and persists every
mutation through the API; on session expiry it redirects back to `/login`.

## Project structure

- `frontend/` — Next.js client-rendered MVP (Kanban board + Sprint overview)
- `backend/` — FastAPI backend (`/api/*` routes + serves the static frontend build)
- `docker-compose.yml` — multi-stage build (frontend build → Python image)
- `scripts/` — start/stop scripts for Windows, macOS, Linux

## Development

The frontend and backend run as separate processes in development. The
frontend's `next.config.ts` proxies `/api/*` to `http://localhost:8000` so the
browser sees one origin.

Backend (from `backend/`):

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# .venv/bin/python -m pip install -r requirements.txt         # macOS / Linux
.venv/Scripts/python.exe -m uvicorn app.main:app --reload      # Windows
# .venv/bin/python -m uvicorn app.main:app --reload            # macOS / Linux
```

> The backend starts and serves the board without an AI key, but the AI
> sidebar will return HTTP 503 until `OPENROUTER_API_KEY` is set in `.env`.
> The board itself (login, drag/drop, CRUD) works without any envconfig.

Frontend (from `frontend/`):

```bash
npm install
npm run dev
```

Open `http://localhost:3000`. API requests are proxied to the backend on port 8000.

Tests:

```bash
# frontend
npm test            # vitest unit tests
npm run test:e2e   # playwright browser tests

# backend
.venv/Scripts/python.exe -m pytest   # Windows
# .venv/bin/python -m pytest          # macOS / Linux
```

## Production (Docker)

From the repo root:

```bash
# Windows
scripts/start.ps1
scripts/stop.ps1

# macOS / Linux
bash scripts/start.sh
bash scripts/stop.sh
```

The Docker image builds the frontend (`next build` with `output: 'export'`) and
serves the resulting static files from FastAPI at `http://localhost:8000` — the
board is at `/` and the API at `/api/*`. The SQLite database is initialized and
seeded automatically on first startup.

## Environment

API keys and other secrets live in `.env` at the repo root (never committed).
Copy `.env.example` to `.env` and fill in the values before starting:

```bash
cp .env.example .env        # macOS / Linux
copy .env.example .env      # Windows
```

Required variables (see `.env.example`):

- `OPENROUTER_API_KEY` — OpenRouter API key (used by the AI connectivity layer)
- `OPENROUTER_MODEL` — model id for AI requests (defaults to `openai/gpt-oss-20b:free`)

Optional variables:

- `SESSION_SECRET` — secret used to sign session cookies. Has a dev default
  (`kanban-mvp-dev-secret-change-me`) that **must be overridden in
  production**.
- `KANBAN_DB_PATH` — absolute path to the SQLite file. Defaults to
  `backend/data/kanban.db`. Tests override this to a temp file for
  isolation.