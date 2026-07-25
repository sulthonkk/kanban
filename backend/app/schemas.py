"""Pydantic models for the Kanban API request bodies and responses."""

from __future__ import annotations

from typing import Annotated

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
