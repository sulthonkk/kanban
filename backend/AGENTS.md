# Backend

FastAPI service for the Kanban application. Serves the `/api/*` routes and the
statically-exported Next.js frontend (built into `frontend/out/` and copied to
`backend/static/` in the Docker image).

## Layout

- `app/main.py` — FastAPI app. Auth middleware, login/logout routes, SPA
  fallback for the frontend.
- `app/auth.py` — Hardcoded single-user credentials (`user` / `password`),
  bcrypt password hashing, signed-cookie session helpers, login form HTML.
- `app/templates/login.html` — Login form template (styled per the project
  color scheme; Python `.replace('{error_block}', ...)` for error injection).
- `app/tests/` — pytest unit tests (`test_main.py`, `test_auth.py`).
- `requirements.txt` — Python dependencies (pinned).
- `pyproject.toml` — ruff + pytest configuration.
- `Dockerfile` — multi-stage build (Node stage builds the frontend,
  Python stage serves the app).

## Authentication

- Single hardcoded user with bcrypt-hashed password.
- Session stored in a signed cookie via Starlette `SessionMiddleware`
  (cookie name `kanban_session`).
- `SESSION_SECRET` is read from the env var `SESSION_SECRET`; falls back to a
  development default that **must** be overridden in production.
- Auth middleware (`require_auth`) gates every path except `/login`,
  `/api/login`, `/api/logout`, and `/api/ping`. Unauthenticated requests are
  redirected to `/login` (303).
- `GET /login` returns the styled login HTML form; `POST /api/login` validates
  the credentials (redirects to `/` on success, `/login?error=1` on failure);
  `POST /api/logout` clears the session and redirects to `/login`.

## Serving the frontend

In Docker, `frontend/out/` is copied into the image at `/app/static/`. The
FastAPI app serves `/_next/*` assets and returns `index.html` for unknown
paths (SPA fallback). API routes take precedence over static fallback.

If the frontend has not been built (e.g., running the backend alone), `/`
returns a JSON status object pointing you to `npm run build` in `frontend/`.