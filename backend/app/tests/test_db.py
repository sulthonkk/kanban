import sqlite3
from pathlib import Path

import bcrypt

from app.auth import PASSWORD, USERNAME
from app.db import get_connection, init_db

_EXPECTED_TABLES = {"users", "boards", "columns", "cards", "chat_history"}

_SEED_COLUMN_TITLES = ["Backlog", "Ready", "In progress", "In review", "Done"]

_SEED_CARDS = [
    ("Backlog", "Refresh the onboarding", "Make the first five minutes feel effortless."),
    ("Backlog", "Customer interview notes", "Pull out the themes from this week's calls."),
    ("Ready", "Write launch page copy", "Lead with the workflow, not the feature list."),
    ("Ready", "Audit empty states", "Give each one a clear and useful next action."),
    ("In progress", "Polish the project overview", "Tighten the hierarchy and status moments."),
    ("In review", "Mobile navigation pass", "Check the compact layout at every breakpoint."),
    ("Done", "Define visual direction", "Approved: bright, calm, and editorial."),
]


def _is_hex_uuid(value: str) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 32
        and all(c in "0123456789abcdef" for c in value)
    )


def test_init_db_creates_all_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "kanban.db"
    init_db(db_path)

    conn = get_connection(db_path)
    try:
        names = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        conn.close()

    assert _EXPECTED_TABLES <= names


def test_init_db_seeds_single_user_with_verifiable_password(tmp_path: Path) -> None:
    db_path = tmp_path / "kanban.db"
    init_db(db_path)

    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT id, username, password_hash FROM users").fetchall()
    finally:
        conn.close()

    assert len(rows) == 1
    user = rows[0]
    assert user["username"] == USERNAME
    assert _is_hex_uuid(user["id"])
    assert bcrypt.checkpw(PASSWORD.encode(), user["password_hash"].encode())


def test_init_db_seeds_one_board_with_default_title(tmp_path: Path) -> None:
    db_path = tmp_path / "kanban.db"
    init_db(db_path)

    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT id, user_id, title FROM boards").fetchall()
    finally:
        conn.close()

    assert len(rows) == 1
    board = rows[0]
    assert board["title"] == "Project board"
    assert _is_hex_uuid(board["id"])
    assert _is_hex_uuid(board["user_id"])


def test_init_db_seeds_five_columns_in_order(tmp_path: Path) -> None:
    db_path = tmp_path / "kanban.db"
    init_db(db_path)

    conn = get_connection(db_path)
    try:
        columns = conn.execute(
            "SELECT id, board_id, title, position FROM columns ORDER BY position"
        ).fetchall()
    finally:
        conn.close()

    assert len(columns) == 5
    assert [c["title"] for c in columns] == _SEED_COLUMN_TITLES
    assert [c["position"] for c in columns] == [0, 1, 2, 3, 4]
    assert all(_is_hex_uuid(c["id"]) for c in columns)
    # All columns share the same (single) board.
    assert len({c["board_id"] for c in columns}) == 1


def test_init_db_seeds_seven_cards_with_correct_columns_and_positions(tmp_path: Path) -> None:
    db_path = tmp_path / "kanban.db"
    init_db(db_path)

    conn = get_connection(db_path)
    try:
        cards = conn.execute(
            """
            SELECT cards.id, cards.column_id, cards.title, cards.details, cards.position,
                   columns.title AS column_title
            FROM cards JOIN columns ON columns.id = cards.column_id
            ORDER BY columns.position, cards.position
            """
        ).fetchall()
    finally:
        conn.close()

    assert len(cards) == 7
    assert [(c["column_title"], c["title"], c["details"]) for c in cards] == _SEED_CARDS
    assert all(_is_hex_uuid(c["id"]) for c in cards)


def test_init_db_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "kanban.db"
    init_db(db_path)
    init_db(db_path)  # second call must not duplicate seed data

    conn = get_connection(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM boards").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM columns").fetchone()[0] == 5
        assert conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0] == 7
        assert conn.execute("SELECT COUNT(*) FROM chat_history").fetchone()[0] == 0
    finally:
        conn.close()


def test_chat_history_accepts_user_and_assistant_roles_round_trip(tmp_path: Path) -> None:
    db_path = tmp_path / "kanban.db"
    init_db(db_path)

    conn = get_connection(db_path)
    try:
        user_id = conn.execute("SELECT id FROM users").fetchone()[0]
        conn.execute(
            "INSERT INTO chat_history (id, user_id, role, content) VALUES (?, ?, ?, ?)",
            ("a" * 32, user_id, "user", "What should I work on?"),
        )
        conn.execute(
            "INSERT INTO chat_history (id, user_id, role, content) VALUES (?, ?, ?, ?)",
            ("b" * 32, user_id, "assistant", "Try the onboarding refresh first."),
        )
        conn.commit()
        rows = conn.execute(
            "SELECT role, content FROM chat_history ORDER BY created_at, id"
        ).fetchall()
    finally:
        conn.close()

    assert [(r["role"], r["content"]) for r in rows] == [
        ("user", "What should I work on?"),
        ("assistant", "Try the onboarding refresh first."),
    ]


def test_chat_history_rejects_invalid_role(tmp_path: Path) -> None:
    db_path = tmp_path / "kanban.db"
    init_db(db_path)

    conn = get_connection(db_path)
    try:
        user_id = conn.execute("SELECT id FROM users").fetchone()[0]
        try:
            conn.execute(
                "INSERT INTO chat_history (id, user_id, role, content) VALUES (?, ?, ?, ?)",
                ("c" * 32, user_id, "system", "disallowed role"),
            )
            raise AssertionError("CHECK constraint should have rejected 'system' role")
        except sqlite3.IntegrityError:
            pass
    finally:
        conn.close()


def test_deleting_board_cascades_to_columns_and_cards(tmp_path: Path) -> None:
    db_path = tmp_path / "kanban.db"
    init_db(db_path)

    conn = get_connection(db_path)
    try:
        conn.execute("DELETE FROM boards")
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM columns").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0] == 0
    finally:
        conn.close()


def test_deleting_column_cascades_to_its_cards(tmp_path: Path) -> None:
    db_path = tmp_path / "kanban.db"
    init_db(db_path)

    conn = get_connection(db_path)
    try:
        backlog = conn.execute(
            "SELECT id FROM columns WHERE title='Backlog'"
        ).fetchone()[0]
        conn.execute("DELETE FROM columns WHERE id=?", (backlog,))
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM columns").fetchone()[0] == 4
        assert conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0] == 5  # 7 - 2 backlog cards
    finally:
        conn.close()


def test_created_at_defaults_are_set(tmp_path: Path) -> None:
    db_path = tmp_path / "kanban.db"
    init_db(db_path)

    conn = get_connection(db_path)
    try:
        user_created = conn.execute("SELECT created_at FROM users").fetchone()[0]
        board_created = conn.execute("SELECT created_at FROM boards").fetchone()[0]
    finally:
        conn.close()

    assert user_created
    assert board_created
    # ISO-8601-ish timestamp from datetime('now'): "YYYY-MM-DD HH:MM:SS"
    assert len(user_created) == 19
    assert len(board_created) == 19
