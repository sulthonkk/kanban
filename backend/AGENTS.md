# Backend

FastAPI service for the Kanban application. Serves the `/api/*` routes and the
statically-exported Next.js frontend (built into `frontend/out/` and copied to
`backend/static/` in the Docker image).

## Layout

- `app/main.py` — FastAPI app. `/api/ping` health check, SPA fallback for the frontend.
- `app/tests/` — pytest unit tests (run with `pytest`).
- `requirements.txt` — Python dependencies (pinned).
- `pyproject.toml` — ruff + pytest configuration.
- `Dockerfile` — multi-stage build (Node stage builds the frontend,
  Python stage serves the app).

## Serving the frontend

In Docker, `frontend/out/` is copied into the image at `/app/static/`. The
FastAPI app serves `/_next/*` assets and returns `index.html` for unknown
paths (SPA fallback). API routes take precedence over static fallback.

If the frontend has not been built (e.g., running the backend alone), `/`
returns a JSON status object pointing you to `npm run build` in `frontend/`.