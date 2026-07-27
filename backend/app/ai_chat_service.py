"""AI board-chat service (Phase 8).

Orchestrates the structured AI board-chat flow:

1. Resolve the session user's id and current ``Board`` snapshot.
2. Load the last N chat turns from ``chat_history``.
3. Build a JSON-only prompt containing the board snapshot and the supported
   action schema, plus history + the new user message.
4. Call the AI via :func:`ai_client.ask_chat` with
   ``response_format={"type": "json_object"}`` (the documented reliable path
   for ``gpt-oss-20b:free``; per AGENTS.md Phase 7 notes strict ``json_schema``
   mode is intermittent for this free model).
5. Parse + validate the AI payload with the pydantic :class:`AiResponse`
   schema. On parse failure, retry once with a corrective prompt; if the
   retry still fails, return a safe apologetic reply with no mutation.
6. Apply a validated action through the existing :mod:`board_service`
   mutators only. No SQL is written here.
7. Persist the user turn and the assistant turn to ``chat_history``.
8. Return ``(reply, board)`` where ``board`` is always the current snapshot
   (mirrors the board-API convention that mutations return the full Board).

All board mutations stay in :mod:`board_service`. This service never touches
board/card/column SQL directly.

Raises :class:`ai_client.AIConfigError` when the key is missing; callers map
that to HTTP 503. Upstream SDK exceptions propagate (callers map to 502).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

import pydantic

from app import ai_client, board_service, chat_history_repo
from app.schemas import (
    AiResponse,
    Board,
    CreateCardAction,
    DeleteCardAction,
    MoveCardAction,
    RenameColumnAction,
    UpdateBoardMetaAction,
)

_HISTORY_LIMIT = 10
_MAX_TOKENS = 2000
_RESPONSE_FORMAT = {"type": "json_object"}

_SAFE_REPLY = (
    "Sorry, I could not produce a valid response. Please rephrase your request."
)

_SYSTEM_PROMPT = (
    "You are a Kanban board assistant. You can talk to the user and optionally "
    "perform ONE board action per reply.\n\n"
    "You MUST respond with a single JSON object and nothing else. The JSON "
    'object has this shape:\n\n'
    '{\n  "reply": "<short human-readable reply to the user>",\n  "action": null\n}\n\n'
    "`action` is either null or exactly one object with a `type` field. Allowed "
    "action types and their fields:\n\n"
    '- create_card:       {"type": "create_card", "column_id": "<id>", '
    '"title": "<non-empty>", "details": "<optional, default empty>"}\n'
    '- delete_card:       {"type": "delete_card", "card_id": "<id>"}\n'
    '- move_card:         {"type": "move_card", "card_id": "<id>", '
    '"column_id": "<id>", "index": <optional non-negative int, omit to append>}\n'
    '- rename_column:     {"type": "rename_column", "column_id": "<id>", '
    '"title": "<non-empty>"}\n'
    '- update_board_meta: {"type": "update_board_meta", "title": "<non-empty>"}\n\n'
    "Rules:\n"
    "- Use the ids provided in the current board snapshot below. Never invent ids.\n"
    '- If the user\'s request does not map to one of the allowed actions, set '
    '"action" to null and answer in "reply".\n'
    '- "reply" is always present and non-empty.\n'
    "- Output ONLY the JSON object. No markdown, no commentary, no code fences."
)

_RETRY_PROMPT = (
    "Your previous output was not valid JSON matching the agreed schema. "
    "Output ONLY a JSON object with keys \"reply\" (string) and \"action\" "
    "(null or one allowed action object). No other text."
)


@dataclass
class ChatResult:
    reply: str
    board: Board


def _resolve_user_id(conn: sqlite3.Connection, username: str) -> str:
    row = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    if row is None:
        # The auth middleware guarantees the session user exists; this only
        # triggers if the DB was wiped mid-session. Treat as missing board.
        raise LookupError("user not found")
    return row[0]


def _board_to_text(board: Board) -> str:
    """Compact textual snapshot for the AI prompt (in addition to JSON)."""
    lines = [f'Board "{board.title}" (id={board.id}):']
    for col in board.columns:
        lines.append(f'- Column {col.title!r} (id={col.id}):')
        if not col.cards:
            lines.append("    (empty)")
        for card in col.cards:
            details = f" -- {card.details!r}" if card.details else ""
            lines.append(f"    * {card.title!r} (id={card.id}){details}")
    return "\n".join(lines)


def _build_messages(
    board: Board, history: list[dict[str, str]], user_message: str
) -> list[dict[str, str]]:
    user_content = (
        f"Current board:\n```json\n{board.model_dump_json()}\n```\n\n"
        f"{_board_to_text(board)}\n\n"
        f"User message:\n{user_message}\n\n"
        "Respond with the JSON object only."
    )
    return (
        [{"role": "system", "content": _SYSTEM_PROMPT}]
        + history
        + [{"role": "user", "content": user_content}]
    )


def _parse_ai_output(raw: str) -> AiResponse | None:
    """Parse + validate the model output. Returns None on any failure."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    try:
        return AiResponse.model_validate(data)
    except pydantic.ValidationError:
        return None


def _validate_references(board: Board, action: object) -> str | None:
    """Return an error string if the action references missing ids, else None.

    The board_service functions also raise LookupError on bad ids, but we
    check first so we can produce a friendly reply rather than aborting the
    transaction (which would roll back the persisted chat history).
    """
    column_ids = {c.id for c in board.columns}
    card_ids = {card.id for col in board.columns for card in col.cards}

    if isinstance(action, (CreateCardAction, RenameColumnAction)):
        if action.column_id not in column_ids:
            return "That column does not exist on your board."
    elif isinstance(action, DeleteCardAction):
        if action.card_id not in card_ids:
            return "That card does not exist on your board."
    elif isinstance(action, MoveCardAction):
        if action.card_id not in card_ids:
            return "That card does not exist on your board."
        if action.column_id not in column_ids:
            return "That column does not exist on your board."
    elif isinstance(action, UpdateBoardMetaAction):
        pass
    return None


def _apply_action(
    conn: sqlite3.Connection, username: str, action: object
) -> Board:
    """Dispatch one validated action to the existing board_service mutator."""
    if isinstance(action, CreateCardAction):
        return board_service.create_card(
            conn, username, action.column_id, action.title, action.details
        )
    if isinstance(action, DeleteCardAction):
        board_service.delete_card(conn, username, action.card_id)
        return board_service.get_board(conn, username)
    if isinstance(action, MoveCardAction):
        return board_service.move_card(
            conn, username, action.card_id, action.column_id, action.index
        )
    if isinstance(action, RenameColumnAction):
        return board_service.rename_column(
            conn, username, action.column_id, action.title
        )
    if isinstance(action, UpdateBoardMetaAction):
        return board_service.update_board_meta(conn, username, action.title)
    # Unreachable: AiResponse validation restricts action to the union.
    raise AssertionError(f"unhandled action {action!r}")  # pragma: no cover


def handle_chat(
    conn: sqlite3.Connection, username: str, user_message: str
) -> ChatResult:
    """Run one AI board-chat turn. See module docstring for the contract.

    The caller owns the connection commit/rollback (via ``get_db``). On the
    safe-failure path (malformed/invalid AI output) this function still
    appends both chat turns to ``chat_history`` so the conversation history
    is preserved and visible to future turns; the transaction commits
    normally because no exception is raised.
    """
    user_id = _resolve_user_id(conn, username)
    board_before = board_service.get_board(conn, username)

    history = chat_history_repo.load_recent(conn, user_id, limit=_HISTORY_LIMIT)
    # Persist the user turn AFTER loading history so the prompt isn't built
    # with the just-appended turn duplicated.
    chat_history_repo.append(conn, user_id, "user", user_message)

    messages = _build_messages(board_before, history, user_message)

    raw = ai_client.ask_chat(
        messages,
        response_format=_RESPONSE_FORMAT,
        max_tokens=_MAX_TOKENS,
    )
    ai_response = _parse_ai_output(raw)

    if ai_response is None:
        # Retry once with a corrective user turn appended.
        retry_messages = messages + [{"role": "user", "content": _RETRY_PROMPT}]
        raw = ai_client.ask_chat(
            retry_messages,
            response_format=_RESPONSE_FORMAT,
            max_tokens=_MAX_TOKENS,
        )
        ai_response = _parse_ai_output(raw)

    if ai_response is None:
        chat_history_repo.append(conn, user_id, "assistant", _SAFE_REPLY)
        return ChatResult(
            reply=_SAFE_REPLY, board=board_service.get_board(conn, username)
        )

    reply = ai_response.reply
    action = ai_response.action

    if action is not None:
        ref_error = _validate_references(board_before, action)
        if ref_error is not None:
            reply = f"{reply} (Note: {ref_error})"
            action = None

    if action is not None:
        board_after = _apply_action(conn, username, action)
    else:
        board_after = board_service.get_board(conn, username)

    chat_history_repo.append(conn, user_id, "assistant", reply)
    return ChatResult(reply=reply, board=board_after)
