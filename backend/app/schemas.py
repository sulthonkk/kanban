"""Pydantic models for the Kanban API request bodies and responses."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field


def _strip(value: str) -> str:
    return value.strip() if isinstance(value, str) else value


# A non-blank string: whitespace is stripped, then a minimum length of 1 is
# enforced. Empty/whitespace-only titles fail validation with a 422.
NonBlankStr = Annotated[str, BeforeValidator(_strip), Field(min_length=1)]


class Card(BaseModel):
    id: str
    title: str
    details: str


class Column(BaseModel):
    id: str
    title: str
    cards: list[Card]


class Board(BaseModel):
    id: str
    title: str
    columns: list[Column]


class CreateCardRequest(BaseModel):
    column_id: str
    title: NonBlankStr
    details: str = ""


class RenameColumnRequest(BaseModel):
    title: NonBlankStr


class MoveCardRequest(BaseModel):
    column_id: str
    index: int | None = Field(default=None, ge=0)


class BoardMetaRequest(BaseModel):
    title: NonBlankStr


class ChatRequest(BaseModel):
    message: NonBlankStr


# --- AI structured action schemas (Phase 8) ------------------------------- #
# The AI returns at most one action per turn. Each action is discriminated by
# its ``type`` field so malformed/unknown types are rejected at parse time.
# All board mutations stay in ``board_service``; these models only describe
# the validated payload passed through to the service mutators.

IdStr = Annotated[str, Field(min_length=1)]


class CreateCardAction(BaseModel):
    type: Literal["create_card"]
    column_id: IdStr
    title: NonBlankStr
    details: str = ""


class DeleteCardAction(BaseModel):
    type: Literal["delete_card"]
    card_id: IdStr


class MoveCardAction(BaseModel):
    type: Literal["move_card"]
    card_id: IdStr
    column_id: IdStr
    index: int | None = Field(default=None, ge=0)


class RenameColumnAction(BaseModel):
    type: Literal["rename_column"]
    column_id: IdStr
    title: NonBlankStr


class UpdateBoardMetaAction(BaseModel):
    type: Literal["update_board_meta"]
    title: NonBlankStr


AiAction = (
    CreateCardAction
    | DeleteCardAction
    | MoveCardAction
    | RenameColumnAction
    | UpdateBoardMetaAction
)


class AiResponse(BaseModel):
    """Validated payload returned by the AI for the board chat flow.

    ``reply`` is always present; ``action`` is optional so the model can
    answer without touching the board.
    """

    reply: NonBlankStr
    action: AiAction | None = None
