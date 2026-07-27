"""chat_history persistence helper.

Thin SQL layer for the ``chat_history`` table created in Phase 4. Mirrors the
convention that DB access lives in dedicated modules rather than in routes or
services. No schema change: rows are still ``(id, user_id, role, content,
created_at)`` with ``role`` constrained to ``'user'`` / ``'assistant'``.

Both functions take an open ``sqlite3.Connection``; callers (the service +
``get_db`` dependency) own the transaction commit/rollback.
"""

from __future__ import annotations

import sqlite3
import uuid
from typing import Any


def append(
    conn: sqlite3.Connection, user_id: str, role: str, content: str
) -> None:
    """Insert one chat_history row.

    ``role`` is validated by the table CHECK constraint; passing anything other
    than ``'user'`` / ``'assistant'`` raises sqlite3.IntegrityError (caller's
    transaction rolls back, which is the desired safety behavior).
    """
    conn.execute(
        "INSERT INTO chat_history (id, user_id, role, content) "
        "VALUES (?, ?, ?, ?)",
        (uuid.uuid4().hex, user_id, role, content),
    )


def load_recent(
    conn: sqlite3.Connection, user_id: str, limit: int = 10
) -> list[dict[str, Any]]:
    """Return the most recent ``limit`` chat_history rows for ``user_id``.

    Ordered oldest-first so callers can append directly to the messages list
    they build for the AI. Returns plain dicts ``{"role": ..., "content": ...}``
    to match the OpenAI chat-completions message shape.
    """
    rows = conn.execute(
        "SELECT role, content FROM chat_history "
        "WHERE user_id = ? ORDER BY rowid DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    # rowid is monotonically increasing by insertion order, so DESC + reversed
    # yields oldest-first. This avoids relying on created_at ties (which would
    # otherwise leave equal-timestamp rows in undefined order).
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
