# Kanban

A single-board Kanban application. Frontend MVP (Next.js + React + dnd-kit) and a FastAPI backend.

## Project structure

- `frontend/` — Next.js client-rendered MVP (Kanban board + Sprint overview)
- `backend/` — FastAPI backend (currently a `/api/ping` health check)
- `docker-compose.yml` — runs the backend in Docker
- `scripts/` — start/stop scripts for Windows, macOS, Linux

## Frontend

From `frontend/`:

```bash
npm install
npm run dev
```

Tests:

```bash
npm test            # vitest unit tests
npm run test:e2e    # playwright browser tests
```

## Backend (Docker)

From the repo root:

```bash
# Windows
scripts/start.ps1
scripts/stop.ps1

# macOS / Linux
bash scripts/start.sh
bash scripts/stop.sh
```

The backend is served at `http://localhost:8000` with the health endpoint at `/api/ping`.

## Backend (local, without Docker)

From `backend/`:

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# .venv/bin/python -m pip install -r requirements.txt         # macOS / Linux
.venv/Scripts/python.exe -m uvicorn app.main:app --reload      # Windows
# .venv/bin/python -m uvicorn app.main:app --reload            # macOS / Linux
```

Tests:

```bash
.venv/Scripts/python.exe -m pytest           # Windows
# .venv/bin/python -m pytest                  # macOS / Linux
```

## Environment

API keys and other secrets live in `.env` at the repo root (never committed). See `.env.example` for required variables.