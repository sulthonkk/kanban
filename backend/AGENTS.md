# Backend

FastAPI service for the Kanban application. Serves the `/api/*` routes and the
statically-exported Next.js frontend (built into `frontend/out/` and copied to
`backend/static/` in the Docker image).

## Layout

- `app/main.py` — FastAPI app. Auth middleware, login/logout routes, SPA
  fallback for the frontend. A `lifespan` async context manager calls
  `app.db.init_db()` on startup so the database is created/seeded on first run,
  and includes the board API router and the AI API router before the SPA
  catch-all route.
- `app/auth.py` — Hardcoded single-user credentials (`user` / `password`),
  bcrypt password hashing, signed-cookie session helpers, login form HTML.
- `app/db.py` — SQLite persistence layer (schema, auto-create + seed, FastAPI
  `get_db` dependency). See "Database" below.
- `app/schemas.py` — Pydantic v2 models for the board API
  (`Board`/`Column`/`Card` response models + request bodies). `NonBlankStr`
  strips then enforces `min_length=1` for titles. Also hosts the Phase 8
  AI structured-output models (see "AI board chat").
- `app/board_service.py` — Board service: all DB operations for the board.
  Resolves the session user's single board and raises `LookupError` for
  missing resources (routes map that to 404). All board mutations live here;
  the AI chat service calls these functions and never writes board SQL itself.
- `app/board_api.py` — Thin `APIRouter` (prefix `/api`) with the six board
  endpoints. Routes delegate to `board_service` and only handle HTTP concerns.
- `app/ai_client.py` — OpenRouter AI client. Minimal wrapper over the OpenAI
  SDK pointed at `https://openrouter.ai/api/v1`. Reads `OPENROUTER_API_KEY`
  and `OPENROUTER_MODEL` (default `openai/gpt-oss-20b:free`) from the env,
  no model name is hardcoded in app code. See "AI connectivity" below.
  Exposes single-turn `ask` (Phase 7) and multi-turn `ask_chat` (Phase 8).
- `app/ai_chat_service.py` — Phase 8 AI board-chat orchestration. Loads the
  user's board + recent `chat_history`, builds a JSON-only prompt, calls
  `ai_client.ask_chat`, validates the AI payload against the `AiResponse`
  schema, applies the optional action through `board_service`, persists both
  chat turns, and returns `(reply, board)`. See "AI board chat".
- `app/chat_history_repo.py` — Thin SQL helper for the `chat_history` table
  (Phase 8): `append(conn, user_id, role, content)` and
  `load_recent(conn, user_id, limit=10)` for chat-context loading. No schema
  change; reuses the Phase 4 table.
- `app/ai_api.py` — Thin `APIRouter` (prefix `/api/ai`) for AI features.
  Phase 7 exposes `GET /api/ai/test` ("What is 2+2?") returning
  `{"answer": "..."}`. Phase 8 adds `POST /api/ai/chat` (see "AI board chat").
  Routes delegate to `ai_client` / `ai_chat_service`; config errors map to
  503, upstream errors to 502.
- `app/templates/login.html` — Login form template (styled per the project
  color scheme; Python `.replace('{error_block}', ...)` for error injection).
- `app/tests/` — pytest unit tests (`test_main.py`, `test_auth.py`,
  `test_db.py`, `test_board_api.py`, `test_ai.py`, `test_ai_chat.py`).
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
authenticated user's single board is ever touched. The frontend is wired to
these endpoints (`frontend/src/lib/api.ts` + `KanbanBoard.tsx`) and a
"Sign out" button calls `POST /api/logout`.

### Testing the board API

`conftest.py` adds two fixtures for DB-backed tests:

- `db_path` — sets `KANBAN_DB_PATH` to a `tmp_path` sqlite file and calls
  `init_db` so each test gets a fresh seeded database (full isolation).
- `db_authed_client` — a `TestClient` logged in as `user` with `db_path`
  active.

The existing `client` / `authed_client` fixtures are unchanged (they never
touch the DB), so non-DB tests remain unaffected. `test_board_api.py`
covers every endpoint plus auth-failure and invalid-input cases.

## AI connectivity

`app/ai_client.py` is the AI connectivity foundation (Phase 7).

- **Config:** `OPENROUTER_API_KEY` (required) and `OPENROUTER_MODEL`
  (optional, defaults to `openai/gpt-oss-20b:free` per AGENTS.md) are read
  from the environment. The model name is never hardcoded in application
  code; the default lives here only for local dev convenience.
- **Client:** wraps the OpenAI SDK pointed at `https://openrouter.ai/api/v1`.
  The SDK client is lazily built and cached module-level. `reset()` clears
  the cache (used by tests to force re-reading the env).
- **Surface:** `ask(prompt, *, response_format=None, max_tokens=2000) -> str`
  sends a single-turn prompt and returns the assistant's text content
  (empty string if the model returned `None` content, e.g. a reasoning model
  that only emitted reasoning). `response_format` is accepted for later
  phases (structured outputs) but unused by Phase 7.
- **Errors:** `AIConfigError` (subclass of `RuntimeError`) is raised when
  `OPENROUTER_API_KEY` is unset. The route maps it to HTTP 503; upstream
  SDK/network failures map to HTTP 502.
- **Endpoint:** `GET /api/ai/test` sends "What is 2+2? Reply with just the
  number." and returns `{"answer": "..."}`. Auth-gated like all other
  `/api/*` routes (unauthed -> 303 to `/login`).

### Model capability notes

`openai/gpt-oss-20b:free` is a reasoning model. Verified live against
OpenRouter:

- Plain text completion: works (e.g. "2+2" -> "4").
- `response_format: json_schema` (strict structured outputs): supported by
  the parameter but intermittent for this model — some calls return
  `content: null` because the model spends the token budget on reasoning.
  Workaround for Phase 8 (which uses structured outputs): use a generous
  `max_tokens` (>= 2000), retry on `content is None`, or fall back to
  `response_format: {type: "json_object"}` (100% reliable in testing).

Phase 7 only uses the plain text path, which is reliable.

### Testing the AI client

`test_ai.py` monkeypatches `ai_client._client` with a fake SDK client that
records the request kwargs and returns a canned completion. No live network
calls run in the suite. Coverage: successful response, request-shape
assertion (model from env, no hardcoded model in the call, no
`response_format` for the test prompt), `OPENROUTER_MODEL` override,
auth-gating (303 to `/login`), 503 on missing key, 502 on upstream error,
and `None`-content coercion.

## AI board chat (Phase 8)

Phase 8 adds the backend foundation for AI-driven board updates. No frontend
chat UI yet (Phase 9). All board mutations continue to live in
`board_service.py`; the AI chat service only validates and dispatches.

### Layering

```
POST /api/ai/chat        (app/ai_api.py — thin, auth-gated)
        |
        v
ai_chat_service.handle_chat(conn, username, message)
        |
        |-- board_service.get_board(...)                # current snapshot
        |-- chat_history_repo.load_recent(..., limit=10) # context window
        |-- ai_client.ask_chat(messages, response_format={"type": "json_object"})
        |-- json.loads + AiResponse pydantic validation (single retry on failure)
        |-- _validate_references(board, action)         # reject hallucinated ids
        |-- board_service.<mutator>(...)                # no new SQL here
        |-- chat_history_repo.append(user_turn) + append(assistant_turn)
        '-- return ChatResult(reply, board)
```

### Structured-output strategy

Per the Phase 7 model-capability notes, strict `response_format: json_schema`
is intermittent for `openai/gpt-oss-20b:free` (occasionally returns
`content: null`). Phase 8 therefore uses the documented reliable fallback:

1. `response_format={"type": "json_object"}` (100% reliable per Phase 7 notes)
   + a JSON-only system prompt that declares the exact action schema.
2. `json.loads` the model output; on `JSONDecodeError`, retry once with a
   corrective prompt ("Output ONLY a JSON object...").
3. Validate the parsed dict against the pydantic `AiResponse` schema
   (discriminated union on `action.type`). Malformed/unknown actions are
   rejected at parse time — no mutation, no exception, just a safe reply.
4. Validate referenced `card_id` / `column_id` values against the current
   board snapshot (the AI may hallucinate stale ids from history); an
   annotated apology is appended and the action is dropped.

No new dependencies: pydantic v2 (already pinned) handles validation.

### Action schema

The AI returns exactly one `reply` (always present) and at most one `action`
per turn (MVP — simplest correct behavior). Models live in `app/schemas.py`:

- `CreateCardAction`     — `{type, column_id, title, details?}`
- `DeleteCardAction`     — `{type, card_id}`
- `MoveCardAction`       — `{type, card_id, column_id, index?}`
- `RenameColumnAction`   — `{type, column_id, title}`
- `UpdateBoardMetaAction`— `{type, title}`
- `AiAction` — discriminated union of the above (rejected at parse time if
  the `type` is unknown or any required field is missing/blank).
- `AiResponse` — `{reply: NonBlankStr, action: AiAction | None}`.

`NonBlankStr` (strip + `min_length=1`) and `IdStr` (`min_length=1`) are
reused for all required string fields, matching the board-API validators.

### API endpoint

`POST /api/ai/chat`, auth-gated by the existing middleware (unauthed -> 303
to `/login`, like all `/api/*` routes). Body: `{"message": "..."}` (pydantic
`ChatRequest`, `NonBlankStr`). Response: `{"reply": "...", "board": {...}}`
— `board` is always the current snapshot (mirrors the board-API convention
that callers can replace state in one round-trip).

### chat_history integration

- The user turn is appended **after** loading history (so it isn't duplicated
  in the prompt) and **before** calling the AI.
- The assistant turn is appended **after** validation (so we never store an
  invalid AI reply as if it were successful). On the safe-failure path the
  canonical apology text is persisted instead.
- `chat_history_repo.load_recent` orders by SQLite `rowid` (insertion order)
  rather than `created_at`, because rows written in the same second would
  otherwise lack a stable tiebreaker.
- No schema change; `role` values `'user'` / `'assistant'` match the existing
  CHECK constraint from Phase 4.

### Error handling

| Failure                                      | HTTP | Persisted         |
|----------------------------------------------|------|-------------------|
| `AIConfigError` (`OPENROUTER_API_KEY` unset) | 503  | neither turn      |
| Upstream SDK / network error                 | 502  | neither turn (the |
|                                              |      | `get_db` dep rolls|
|                                              |      | back the user turn|
|                                              |      | on the exception) |
| Malformed AI JSON (even after retry)         | 200  | both turns (safe  |
|                                              |      | apology persisted)|
| Invalid action (unknown type / blank field)  | 200  | both turns (safe |
|                                              |      | reply persisted)  |
| Action references missing card/column        | 200  | both turns        |
| `LookupError` raised by `board_service`      | 500  | neither survives  |
|                                              |      | the rollback       |

All 200 responses on AI-failure paths include the unchanged board snapshot.

### Testing the AI chat service

`test_ai_chat.py` reuses the Phase 7 fake-OpenAI pattern: a fake
`completions.create` records every call and returns canned content from a
FIFO queue, so the suite can stage both primary and retry outputs. No live
network calls. Coverage: reply-only success, AI creating/deleting/moving/
renaming cards/columns, malformed-JSON safe reply (with and without retry
recovery), unknown action-type rejection, blank-title rejection, hallucinated
`card_id` rejection, `chat_history` persistence (both turns in correct
order, even on AI failure), history loaded as multi-turn context,
auth-gating (303 to `/login`), blank-message 422, 503 on missing key, 502 on
upstream error, and direct `handle_chat` service tests for each action.
The fake-SDK assert confirms every call uses `response_format={"type":
"json_object"}` and the model name from the env.

The full suite is `test_main.py`, `test_auth.py`, `test_db.py`,
`test_board_api.py`, `test_ai.py`, `test_ai_chat.py` (91 tests total).