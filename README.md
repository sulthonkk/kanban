# Kanban

A single-board Kanban application. Next.js frontend (React + dnd-kit) statically
exported and served by a FastAPI backend. Single origin in production.

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
board is at `/` and the API at `/api/*`.

## Environment

API keys and other secrets live in `.env` at the repo root (never committed).
See `.env.example` for required variables.