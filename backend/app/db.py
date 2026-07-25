"""SQLite persistence for the Kanban MVP.

A single small database lives in ``backend/data/kanban.db`` (or
``$KANBAN_DB_PATH`` when overridden, e.g. for tests). The schema is created
on app startup via :func:`init_db`, which is idempotent: it builds the tables
and seeds the single hardcoded user + default board only when the database
is empty.

The layer is deliberately self-contained in this phase and not yet wired into
authentication or API routes; downstream phases consume :func:`get_db`.
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import bcrypt

from app.auth import PASSWORD, USERNAME

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS boards (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS columns (
    id       TEXT PRIMARY KEY,
    board_id TEXT NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    title    TEXT NOT NULL,
    position INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS cards (
    id       TEXT PRIMARY KEY,
    column_id TEXT NOT NULL REFERENCES columns(id) ON DELETE CASCADE,
    title    TEXT NOT NULL,
    details  TEXT NOT NULL,
    position INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_history (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# Seed board mirrors frontend/src/lib/board.ts initialColumns.
_SEED_COLUMNS: list[tuple[str, str, int]] = [
    ("Backlog", "Backlog", 0),
    ("Ready", "Ready", 1),
    ("In progress", "In progress", 2),
    ("In review", "In review", 3),
    ("Done", "Done", 4),
]

_SEED_CARDS: list[tuple[str, str, str]] = [
    # (column title, card title, card details)
    ("Backlog", "Refresh the onboarding", "Make the first five minutes feel effortless."),
    ("Backlog", "Customer interview notes", "Pull out the themes from this week's calls."),
    ("Ready", "Write launch page copy", "Lead with the workflow, not the feature list."),
    ("Ready", "Audit empty states", "Give each one a clear and useful next action."),
    ("In progress", "Polish the project overview", "Tighten the hierarchy and status moments."),
    ("In review", "Mobile navigation pass", "Check the compact layout at every breakpoint."),
    ("Done", "Define visual direction", "Approved: bright, calm, and editorial."),
]


def resolve_db_path() -> Path:
    """Return the database file path.

    Honors the ``KANBAN_DB_PATH`` env var (absolute path), otherwise falls
    back to ``backend/data/kanban.db`` relative to this module. The parent
    directory is created on demand.
    """
    override = os.environ.get("KANBAN_DB_PATH")
    if override:
        path = Path(override)
    else:
        path = Path(__file__).resolve().parent.parent / "data" / "kanban.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_connection(path: Path | str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with sensible defaults.

    - ``check_same_thread=False`` so the connection is usable from FastAPI
      request handlers (the app is single-process; SQLite handles its own
      locking).
    - ``row_factory=Row`` for dict-style access.
    - ``PRAGMA foreign_keys=ON`` so the declared ON DELETE CASCADE rules fire.
    """
    if path is None:
        path = resolve_db_path()
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def seed_if_empty(conn: sqlite3.Connection) -> None:
    """Seed the single user + default board when the database is empty.

    Idempotent: if a user already exists, this is a no-op.
    """
    existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing:
        return

    user_id = uuid.uuid4().hex
    password_hash = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()
    conn.execute(
        "INSERT INTO users (id, username, password_hash) VALUES (?, ?, ?)",
        (user_id, USERNAME, password_hash),
    )

    board_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO boards (id, user_id, title) VALUES (?, ?, ?)",
        (board_id, user_id, "Project board"),
    )

    column_ids: dict[str, str] = {}
    for title, _label, position in _SEED_COLUMNS:
        column_id = uuid.uuid4().hex
        column_ids[title] = column_id
        conn.execute(
            "INSERT INTO columns (id, board_id, title, position) VALUES (?, ?, ?, ?)",
            (column_id, board_id, title, position),
        )

    position = 0
    for column_title, card_title, card_details in _SEED_CARDS:
        column_id = column_ids[column_title]
        conn.execute(
            "INSERT INTO cards (id, column_id, title, details, position) VALUES (?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, column_id, card_title, card_details, position),
        )
        position += 1


def init_db(path: Path | str | None = None) -> None:
    """Create the schema and seed defaults if needed. Idempotent.

    Safe to call on every startup: ``CREATE TABLE IF NOT EXISTS`` plus the
    empty-database guard in :func:`seed_if_empty`.
    """
    conn = get_connection(path)
    try:
        conn.executescript(_SCHEMA)
        seed_if_empty(conn)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency yielding a connection for request handlers.

    Not wired into any route in this phase; provided for downstream phases.
    The connection is closed on exit and rolled back if the handler raised.
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
