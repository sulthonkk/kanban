"""Tests for the AI board-chat flow (Phase 8).

No live network calls. The OpenAI SDK client is monkeypatched with a fake
that records each request and returns a canned completion. The DB-backed
fixtures from ``conftest.py`` provide a fresh seeded database per test.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

import app.ai_client as ai_client
from app.ai_chat_service import handle_chat
from app.db import get_connection


class _FakeMessage:
    def __init__(self, content: str | None) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str | None) -> None:
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content: str | None) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    """Records every call; returns canned content in FIFO order."""

    def __init__(self, contents: list[str | None] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._contents = list(contents) if contents is not None else []
        self.raise_exc: Exception | None = None

    def create(self, **kwargs: Any) -> _FakeCompletion:
        self.calls.append(kwargs)
        if self.raise_exc is not None:
            raise self.raise_exc
        if self._contents:
            content = self._contents.pop(0)
        else:
            content = None
        return _FakeCompletion(content)


class _FakeChat:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.completions = completions


class _FakeOpenAI:
    def __init__(self, completions: _FakeCompletions | None = None) -> None:
        self.chat = _FakeChat(completions or _FakeCompletions())


def _ai(message: str) -> dict[str, Any]:
    """Helper: a single-turn fake completion output."""
    return message


@pytest.fixture
def ai_key(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key")


@pytest.fixture
def db_chat_client(
    client: TestClient, db_path, ai_key, monkeypatch
) -> tuple[TestClient, _FakeCompletions]:
    """Authed client + fake AI + fresh DB. Returns (client, fake_completions)."""
    fake_completions = _FakeCompletions()
    fake = _FakeOpenAI(fake_completions)
    monkeypatch.setattr(ai_client, "_client", fake)
    response = client.post(
        "/api/login",
        data={"username": "user", "password": "password"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client, fake_completions


def _first_column_id() -> str:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM columns ORDER BY position LIMIT 1"
        ).fetchone()
        return row["id"]
    finally:
        conn.close()


def _first_card_id() -> str:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT cards.id FROM cards JOIN columns ON columns.id = cards.column_id "
            "ORDER BY columns.position, cards.position LIMIT 1"
        ).fetchone()
        return row["id"]
    finally:
        conn.close()


def _count_cards() -> int:
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    finally:
        conn.close()


def _chat_history_rows() -> list[dict[str, str]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT role, content FROM chat_history ORDER BY rowid"
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# 1. Successful reply-only response (no mutation)
# --------------------------------------------------------------------------- #
def test_chat_success_reply_only(db_chat_client) -> None:
    client, fake = db_chat_client
    fake._contents = [
        json.dumps({"reply": "Got it, here is the board state.", "action": None})
    ]
    cards_before = _count_cards()

    response = client.post("/api/ai/chat", json={"message": "show me the board"})

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Got it, here is the board state."
    assert "board" in body
    assert _count_cards() == cards_before  # no mutation
    assert len(fake.calls) == 1


def test_chat_returns_board_snapshot_shape(db_chat_client) -> None:
    client, fake = db_chat_client
    fake._contents = [json.dumps({"reply": "ok", "action": None})]

    response = client.post("/api/ai/chat", json={"message": "hello"})

    board = response.json()["board"]
    assert "id" in board
    assert "title" in board
    assert isinstance(board["columns"], list)
    assert len(board["columns"]) == 5


# --------------------------------------------------------------------------- #
# 2. AI creates a card
# --------------------------------------------------------------------------- #
def test_chat_ai_creates_card(db_chat_client) -> None:
    client, fake = db_chat_client
    column_id = _first_column_id()
    cards_before = _count_cards()
    fake._contents = [
        json.dumps(
            {
                "reply": "I created the deployment task.",
                "action": {
                    "type": "create_card",
                    "column_id": column_id,
                    "title": "Deploy the application",
                    "details": "tomorrow morning",
                },
            }
        )
    ]

    response = client.post(
        "/api/ai/chat", json={"message": "create a deploy task for tomorrow"}
    )

    assert response.status_code == 200
    body = response.json()
    assert "deploy" in body["reply"].lower()
    assert _count_cards() == cards_before + 1
    # The returned board snapshot reflects the new card.
    first_col = body["board"]["columns"][0]
    titles = [c["title"] for c in first_col["cards"]]
    assert "Deploy the application" in titles


# --------------------------------------------------------------------------- #
# 3. Malformed AI JSON response (retry -> safe reply)
# --------------------------------------------------------------------------- #
def test_chat_malformed_json_safe_reply(db_chat_client) -> None:
    client, fake = db_chat_client
    cards_before = _count_cards()
    fake._contents = ["not json at all", "still not json"]  # primary + retry

    response = client.post("/api/ai/chat", json={"message": "do something"})

    assert response.status_code == 200
    body = response.json()
    assert "could not" in body["reply"].lower()
    assert _count_cards() == cards_before  # no mutation
    assert len(fake.calls) == 2  # primary + one retry


def test_chat_malformed_json_then_valid_after_retry(db_chat_client) -> None:
    client, fake = db_chat_client
    fake._contents = [
        "garbage",
        json.dumps({"reply": "Recovered on retry.", "action": None}),
    ]

    response = client.post("/api/ai/chat", json={"message": "hi"})

    assert response.status_code == 200
    assert response.json()["reply"] == "Recovered on retry."
    assert len(fake.calls) == 2


# --------------------------------------------------------------------------- #
# 4. Invalid action rejection
# --------------------------------------------------------------------------- #
def test_chat_unknown_action_type_rejected(db_chat_client) -> None:
    client, fake = db_chat_client
    cards_before = _count_cards()
    fake._contents = [
        json.dumps(
            {
                "reply": "I will hack it.",
                "action": {"type": "DROP_TABLE", "table": "cards"},
            }
        )
    ]

    response = client.post("/api/ai/chat", json={"message": "delete everything"})

    assert response.status_code == 200
    body = response.json()
    # Validation rejects the action; the service returns a safe reply.
    assert "could not" in body["reply"].lower()
    assert _count_cards() == cards_before


def test_chat_blank_title_rejected(db_chat_client) -> None:
    client, fake = db_chat_client
    column_id = _first_column_id()
    cards_before = _count_cards()
    fake._contents = [
        "   ",  # invalid JSON
        json.dumps(
            {
                "reply": "doing it",
                "action": {
                    "type": "create_card",
                    "column_id": column_id,
                    "title": "   ",  # NonBlankStr rejects
                },
            }
        ),
    ]

    response = client.post("/api/ai/chat", json={"message": "make a blank card"})

    assert response.status_code == 200
    assert _count_cards() == cards_before


def test_chat_hallucinated_card_id_no_mutation(db_chat_client) -> None:
    client, fake = db_chat_client
    cards_before = _count_cards()
    column_id = _first_column_id()
    fake._contents = [
        json.dumps(
            {
                "reply": "moved it",
                "action": {
                    "type": "move_card",
                    "card_id": "nonexistent-card-id",
                    "column_id": column_id,
                },
            }
        )
    ]

    response = client.post("/api/ai/chat", json={"message": "move first card"})

    assert response.status_code == 200
    body = response.json()
    # Validation flagged the missing card; reply annotated, no mutation.
    assert "does not exist" in body["reply"].lower()
    assert _count_cards() == cards_before


# --------------------------------------------------------------------------- #
# 5. chat_history persistence
# --------------------------------------------------------------------------- #
def test_chat_persists_both_turns_to_history(db_chat_client) -> None:
    client, fake = db_chat_client
    fake._contents = [json.dumps({"reply": "Hello back.", "action": None})]

    client.post("/api/ai/chat", json={"message": "hi there"})

    rows = _chat_history_rows()
    assert len(rows) == 2
    assert rows[0] == {"role": "user", "content": "hi there"}
    assert rows[1] == {"role": "assistant", "content": "Hello back."}


def test_chat_history_persisted_even_on_malformed_response(db_chat_client) -> None:
    client, fake = db_chat_client
    fake._contents = ["not json", "still not"]

    client.post("/api/ai/chat", json={"message": "hello"})

    rows = _chat_history_rows()
    assert len(rows) == 2
    assert rows[0]["role"] == "user"
    assert rows[0]["content"] == "hello"
    assert rows[1]["role"] == "assistant"
    assert "could not" in rows[1]["content"].lower()


def test_chat_history_loaded_as_context(db_chat_client) -> None:
    client, fake = db_chat_client
    fake._contents = [
        json.dumps({"reply": "first", "action": None}),
        json.dumps({"reply": "second", "action": None}),
    ]

    client.post("/api/ai/chat", json={"message": "turn one"})
    client.post("/api/ai/chat", json={"message": "turn two"})

    # Second request's messages list should include the prior user+assistant turn.
    second_messages = fake.calls[1]["messages"]
    roles = [m["role"] for m in second_messages]
    # system + prior user + prior assistant + current user
    assert roles == ["system", "user", "assistant", "user"]
    assert second_messages[1]["content"] == "turn one"
    assert second_messages[2]["content"] == "first"


# --------------------------------------------------------------------------- #
# 6. Authentication protection
# --------------------------------------------------------------------------- #
def test_chat_requires_auth(client: TestClient) -> None:
    response = client.post(
        "/api/ai/chat", json={"message": "hi"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_chat_blank_message_rejected(db_chat_client) -> None:
    client, fake = db_chat_client
    response = client.post("/api/ai/chat", json={"message": "   "})
    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# 7. Mocked AI calls (no real OpenRouter calls in CI)
# --------------------------------------------------------------------------- #
def test_chat_never_hits_network(db_chat_client) -> None:
    client, fake = db_chat_client
    fake._contents = [json.dumps({"reply": "ok", "action": None})]
    client.post("/api/ai/chat", json={"message": "anything"})
    # All completions.create calls used the fake SDK client.
    assert all(call["model"] == "openai/gpt-oss-20b:free" for call in fake.calls)


def test_chat_uses_json_object_response_format(db_chat_client) -> None:
    client, fake = db_chat_client
    fake._contents = [json.dumps({"reply": "ok", "action": None})]
    client.post("/api/ai/chat", json={"message": "anything"})
    assert fake.calls[0]["response_format"] == {"type": "json_object"}


# --------------------------------------------------------------------------- #
# 8. Error mapping (503 / 502)
# --------------------------------------------------------------------------- #
def test_chat_503_when_api_key_missing(
    client: TestClient, db_path, monkeypatch
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    ai_client.reset()
    client.post(
        "/api/login",
        data={"username": "user", "password": "password"},
        follow_redirects=False,
    )
    response = client.post("/api/ai/chat", json={"message": "hi"})
    assert response.status_code == 503
    assert "OPENROUTER_API_KEY" in response.json()["detail"]


def test_chat_502_on_upstream_error(
    client: TestClient, db_path, ai_key, monkeypatch
) -> None:
    fake = _FakeOpenAI(_FakeCompletions())
    fake.chat.completions.raise_exc = RuntimeError("boom from openrouter")
    monkeypatch.setattr(ai_client, "_client", fake)
    client.post(
        "/api/login",
        data={"username": "user", "password": "password"},
        follow_redirects=False,
    )
    response = client.post("/api/ai/chat", json={"message": "hi"})
    assert response.status_code == 502
    assert "boom from openrouter" in response.json()["detail"]


# --------------------------------------------------------------------------- #
# 9. Direct service tests for action application
# --------------------------------------------------------------------------- #
def test_service_handle_chat_applies_delete_card(
    db_path, ai_key, monkeypatch
) -> None:
    fake_completions = _FakeCompletions()
    fake = _FakeOpenAI(fake_completions)
    monkeypatch.setattr(ai_client, "_client", fake)

    conn = get_connection()
    try:
        card_id = _first_card_id()
        cards_before = _count_cards()
        fake_completions._contents = [
            json.dumps(
                {
                    "reply": "Deleted.",
                    "action": {"type": "delete_card", "card_id": card_id},
                }
            )
        ]

        result = handle_chat(conn, "user", "delete the first card")
        conn.commit()

        assert result.reply == "Deleted."
        assert _count_cards() == cards_before - 1
    finally:
        conn.close()


def test_service_handle_chat_applies_rename_column(
    db_path, ai_key, monkeypatch
) -> None:
    fake_completions = _FakeCompletions()
    fake = _FakeOpenAI(fake_completions)
    monkeypatch.setattr(ai_client, "_client", fake)

    conn = get_connection()
    try:
        column_id = _first_column_id()
        fake_completions._contents = [
            json.dumps(
                {
                    "reply": "Renamed.",
                    "action": {
                        "type": "rename_column",
                        "column_id": column_id,
                        "title": "New Stage",
                    },
                }
            )
        ]

        result = handle_chat(conn, "user", "rename the first column to New Stage")
        conn.commit()

        assert result.reply == "Renamed."
        first_col = result.board.columns[0]
        assert first_col.title == "New Stage"
    finally:
        conn.close()


def test_service_handle_chat_applies_update_board_meta(
    db_path, ai_key, monkeypatch
) -> None:
    fake_completions = _FakeCompletions()
    fake = _FakeOpenAI(fake_completions)
    monkeypatch.setattr(ai_client, "_client", fake)

    conn = get_connection()
    try:
        fake_completions._contents = [
            json.dumps(
                {
                    "reply": "Renamed board.",
                    "action": {
                        "type": "update_board_meta",
                        "title": "Momentum Board",
                    },
                }
            )
        ]

        result = handle_chat(conn, "user", "rename the board to Momentum Board")
        conn.commit()

        assert result.board.title == "Momentum Board"
    finally:
        conn.close()
