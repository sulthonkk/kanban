"""Board service: all database operations for the Kanban board.

Routes are thin and delegate here. The service owns the SQL and the
"current user's single board" resolution. Missing resources raise
``LookupError`` which routes translate into HTTP 404.

The service takes an open ``sqlite3.Connection`` (provided by the ``get_db``
dependency) and the authenticated username, and returns Pydantic models from
:mod:`app.schemas`.
"""

from __future__ import annotations

import sqlite3
import uuid

from app.schemas import Board, Card, Column


def _resolve_board(conn: sqlite3.Connection, username: str) -> str:
    """Return the id of the single board owned by ``username``.

    Raises ``LookupError`` if the user (or their board) does not exist.
    """
    row = conn.execute(
        "SELECT boards.id FROM boards "
        "JOIN users ON users.id = boards.user_id "
        "WHERE users.username = ?",
        (username,),
    ).fetchone()
    if row is None:
        raise LookupError("board not found")
    return row[0]


def _load_board(conn: sqlite3.Connection, board_id: str) -> Board:
    columns = conn.execute(
        "SELECT id, title, position FROM columns WHERE board_id = ? ORDER BY position",
        (board_id,),
    ).fetchall()

    columns_model: list[Column] = []
    for col in columns:
        cards = conn.execute(
            "SELECT id, title, details FROM cards WHERE column_id = ? ORDER BY position",
            (col["id"],),
        ).fetchall()
        columns_model.append(
            Column(
                id=col["id"],
                title=col["title"],
                cards=[Card(id=c["id"], title=c["title"], details=c["details"]) for c in cards],
            )
        )

    board = conn.execute(
        "SELECT id, title FROM boards WHERE id = ?", (board_id,)
    ).fetchone()
    return Board(id=board["id"], title=board["title"], columns=columns_model)


def get_board(conn: sqlite3.Connection, username: str) -> Board:
    board_id = _resolve_board(conn, username)
    return _load_board(conn, board_id)


def rename_column(
    conn: sqlite3.Connection, username: str, column_id: str, title: str
) -> Board:
    board_id = _resolve_board(conn, username)
    result = conn.execute(
        "UPDATE columns SET title = ? WHERE id = ? AND board_id = ?",
        (title, column_id, board_id),
    )
    if result.rowcount == 0:
        raise LookupError("column not found")
    return _load_board(conn, board_id)


def create_card(
    conn: sqlite3.Connection,
    username: str,
    column_id: str,
    title: str,
    details: str,
) -> Board:
    board_id = _resolve_board(conn, username)
    column = conn.execute(
        "SELECT id FROM columns WHERE id = ? AND board_id = ?",
        (column_id, board_id),
    ).fetchone()
    if column is None:
        raise LookupError("column not found")

    next_position = conn.execute(
        "SELECT COALESCE(MAX(position), -1) + 1 FROM cards WHERE column_id = ?",
        (column_id,),
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO cards (id, column_id, title, details, position) VALUES (?, ?, ?, ?, ?)",
        (uuid.uuid4().hex, column_id, title, details, next_position),
    )
    return _load_board(conn, board_id)


def delete_card(conn: sqlite3.Connection, username: str, card_id: str) -> None:
    board_id = _resolve_board(conn, username)
    result = conn.execute(
        "DELETE FROM cards WHERE id = ? AND column_id IN ("
        "SELECT id FROM columns WHERE board_id = ?)",
        (card_id, board_id),
    )
    if result.rowcount == 0:
        raise LookupError("card not found")


def move_card(
    conn: sqlite3.Connection,
    username: str,
    card_id: str,
    destination_column_id: str,
    destination_index: int | None,
) -> Board:
    board_id = _resolve_board(conn, username)

    card = conn.execute(
        "SELECT cards.id, cards.column_id FROM cards "
        "JOIN columns ON columns.id = cards.column_id "
        "WHERE cards.id = ? AND columns.board_id = ?",
        (card_id, board_id),
    ).fetchone()
    if card is None:
        raise LookupError("card not found")

    dest = conn.execute(
        "SELECT id FROM columns WHERE id = ? AND board_id = ?",
        (destination_column_id, board_id),
    ).fetchone()
    if dest is None:
        raise LookupError("column not found")

    source_column_id = card["column_id"]

    # Cards remaining in the source column after removing the moved card.
    remaining = [
        r["id"]
        for r in conn.execute(
            "SELECT id FROM cards WHERE column_id = ? AND id != ? ORDER BY position",
            (source_column_id, card_id),
        )
    ]

    if source_column_id == destination_column_id:
        ordered = remaining
    else:
        # Renumber the source column sequentially after the removal.
        for position, cid in enumerate(remaining):
            conn.execute(
                "UPDATE cards SET position = ? WHERE id = ?", (position, cid)
            )
        ordered = [
            r["id"]
            for r in conn.execute(
                "SELECT id FROM cards WHERE column_id = ? ORDER BY position",
                (destination_column_id,),
            )
        ]

    index = len(ordered) if destination_index is None else min(destination_index, len(ordered))
    ordered.insert(index, card_id)

    for position, cid in enumerate(ordered):
        conn.execute(
            "UPDATE cards SET column_id = ?, position = ? WHERE id = ?",
            (destination_column_id, position, cid),
        )

    return _load_board(conn, board_id)


def update_board_meta(
    conn: sqlite3.Connection, username: str, title: str
) -> Board:
    board_id = _resolve_board(conn, username)
    conn.execute("UPDATE boards SET title = ? WHERE id = ?", (title, board_id))
    return _load_board(conn, board_id)
