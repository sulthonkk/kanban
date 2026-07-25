# Backend

FastAPI service for the Kanban application. Serves the `/api/*` routes and the
statically-exported Next.js frontend (built into `frontend/out/` and copied to
`backend/static/` in the Docker image).

## Layout

- `app/main.py` — FastAPI app. Auth middleware, login/logout routes, SPA
  fallback for the frontend. A `lifespan` async context manager calls
  `app.db.init_db()` on startup so the database is created/seeded on first run,
  and includes the board API router before the SPA catch-all route.
- `app/auth.py` — Hardcoded single-user credentials (`user` / `password`),
  bcrypt password hashing, signed-cookie session helpers, login form HTML.
- `app/db.py` — SQLite persistence layer (schema, auto-create + seed, FastAPI
  `get_db` dependency). See "Database" below.
- `app/schemas.py` — Pydantic v2 models for the board API
  (`Board`/`Column`/`Card` response models + request bodies). `NonBlankStr`
  strips then enforces `min_length=1` for titles.
- `app/board_service.py` — Board service: all DB operations for the board.
  Resolves the session user's single board and raises `LookupError` for
  missing resources (routes map that to 404).
- `app/board_api.py` — Thin `APIRouter` (prefix `/api`) with the six board
  endpoints. Routes delegate to `board_service` and only handle HTTP concerns.
- `app/templates/login.html` — Login form template (styled per the project
  color scheme; Python `.replace('{error_block}', ...)` for error injection).
- `app/tests/` — pytest unit tests (`test_main.py`, `test_auth.py`,
  `test_db.py`, `test_board_api.py`).
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

## Database

`app/db.py` is a self-contained SQLite layer (stdlib `sqlite3`, no new
dependency).

- **Location:** `backend/data/kanban.db` by default; override with the
  `KANBAN_DB_PATH` env var (absolute path, used by tests). `backend/data/` is
  gitignored and mounted into the Docker image by `docker-compose.yml`.
- **Startup:** `app.main.lifespan` calls `init_db()` once per process start.
  `init_db` is idempotent — `CREATE TABLE IF NOT EXISTS` + an empty-database
  guard, so it never duplicates seed data.
- **Connection:** `get_connection()` opens with `check_same_thread=False`,
  `row_factory=Row`, and `PRAGMA foreign_keys=ON` so `ON DELETE CASCADE`
  rules fire. `get_db()` is a plain generator dependency (used via
  `Depends(get_db)`) that commits on success and rolls back on exception.

Schema (5 tables, TEXT UUIDs (`uuid4().hex`) as primary keys):

- `users (id, username UNIQUE, password_hash, created_at)`
- `boards (id, user_id FK->users CASCADE, title, created_at)`
- `columns (id, board_id FK->boards CASCADE, title, position)`
- `cards (id, column_id FK->columns CASCADE, title, details, position)`
- `chat_history (id, user_id FK->users CASCADE, role CHECK(user|assistant), content, created_at)`

Seeding (only when `users` is empty) inserts 1 user (`user`, bcrypt hash of
`auth.PASSWORD`), 1 board titled "Project board", 5 columns (Backlog, Ready,
In progress, In review, Done at positions 0–4), and 7 cards mirroring
`frontend/src/lib/board.ts` `initialColumns` (titles, details, and column
membership match exactly). `chat_history` starts empty.

This phase only delivers the persistence layer. `auth.py` and the API routes
continue to use their in-memory constants; the DB-backed user and board will
be consumed in later phases.

## Board API

`app/board_api.py` exposes six DB-backed endpoints behind the existing auth
middleware (unauthenticated requests get a 303 redirect to `/login`, same as
all other gated routes). All non-DELETE mutations return the full `Board`
snapshot so the frontend can replace its state in one round-trip.

| Method | Path | Body | Success | Not-found | Validation |
|--------|------|------|---------|-----------|------------|
| GET | `/api/board` | — | 200 `Board` | — | — |
| POST | `/api/columns/{column_id}/rename` | `RenameColumnRequest{title}` | 200 `Board` | 404 | 422 blank title |
| POST | `/api/cards` | `CreateCardRequest{column_id, title, details?}` | 201 `Board` | 404 column | 422 blank title / missing `column_id` |
| DELETE | `/api/cards/{card_id}` | — | 204 | 404 | — |
| POST | `/api/cards/{card_id}/move` | `MoveCardRequest{column_id, index?}` | 200 `Board` | 404 card/column | 422 negative `index` |
| PUT | `/api/board/meta` | `BoardMetaRequest{title}` | 200 `Board` | — | 422 blank title |

Card ordering is maintained via the `position` column. `move_card` removes
the card from its source column, renumbers the source, then inserts at the
clamped destination index and renumbers the destination. `index` is optional
(`null` / omitted appends to the end).

Scoping: each request resolves the board via `board_service._resolve_board`
from the session username (`request.session[SESSION_KEY]`), so only the
authenticated user's single board is ever touched. The frontend is not yet
wired to these endpoints (Phase 7); it still uses in-memory `board.ts`.

### Testing the board API

`conftest.py` adds two fixtures for DB-backed tests:

- `db_path` — sets `KANBAN_DB_PATH` to a `tmp_path` sqlite file and calls
  `init_db` so each test gets a fresh seeded database (full isolation).
- `db_authed_client` — a `TestClient` logged in as `user` with `db_path`
  active.

The existing `client` / `authed_client` fixtures are unchanged (they never
touch the DB), so non-DB tests remain unaffected. `test_board_api.py`
covers every endpoint plus auth-failure and invalid-input cases.