"""Thin API routes for the Kanban board.

Business logic lives in :mod:`app.board_service`. Routes map service
``LookupError`` to HTTP 404 and otherwise return Pydantic models so the
OpenAPI schema reflects the real contract.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth import SESSION_KEY
from app.board_service import (
    create_card as _create_card,
)
from app.board_service import (
    delete_card as _delete_card,
)
from app.board_service import (
    get_board as _get_board,
)
from app.board_service import (
    move_card as _move_card,
)
from app.board_service import (
    rename_column as _rename_column,
)
from app.board_service import (
    update_board_meta as _update_board_meta,
)
from app.db import get_db
from app.schemas import (
    Board,
    BoardMetaRequest,
    CreateCardRequest,
    MoveCardRequest,
    RenameColumnRequest,
)

router = APIRouter(prefix="/api", tags=["board"])


def _username(request: Request) -> str:
    username = request.session.get(SESSION_KEY)
    if username is None:
        # The auth middleware already gates these routes; this is a guard.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return username


@router.get("/board", response_model=Board)
def get_board(request: Request, conn=Depends(get_db)) -> Board:
    return _get_board(conn, _username(request))


@router.post("/columns/{column_id}/rename", response_model=Board)
def rename_column(
    column_id: str,
    body: RenameColumnRequest,
    request: Request,
    conn=Depends(get_db),
) -> Board:
    try:
        return _rename_column(conn, _username(request), column_id, body.title)
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="column not found"
        )


@router.post("/cards", response_model=Board, status_code=status.HTTP_201_CREATED)
def create_card(
    body: CreateCardRequest,
    request: Request,
    conn=Depends(get_db),
) -> Board:
    try:
        return _create_card(conn, _username(request), body.column_id, body.title, body.details)
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="column not found"
        )


@router.delete(
    "/cards/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def delete_card(card_id: str, request: Request, conn=Depends(get_db)) -> None:
    try:
        _delete_card(conn, _username(request), card_id)
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="card not found"
        )


@router.post("/cards/{card_id}/move", response_model=Board)
def move_card(
    card_id: str,
    body: MoveCardRequest,
    request: Request,
    conn=Depends(get_db),
) -> Board:
    try:
        return _move_card(conn, _username(request), card_id, body.column_id, body.index)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/board/meta", response_model=Board)
def update_board_meta(
    body: BoardMetaRequest,
    request: Request,
    conn=Depends(get_db),
) -> Board:
    return _update_board_meta(conn, _username(request), body.title)
