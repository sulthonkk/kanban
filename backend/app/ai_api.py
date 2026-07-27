"""Thin API routes for AI features.

Business logic / SDK wiring lives in :mod:`app.ai_client`; orchestration for
the board chat flow lives in :mod:`app.ai_chat_service`. Routes stay thin:
they resolve the session user, delegate to the service, and map
configuration errors to HTTP 503 and upstream request failures to 502.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.ai_chat_service import ChatResult, handle_chat
from app.ai_client import AIConfigError, ask
from app.auth import SESSION_KEY
from app.db import get_db
from app.schemas import ChatRequest

router = APIRouter(prefix="/api/ai", tags=["ai"])

_TEST_PROMPT = "What is 2+2? Reply with just the number."


def _username(request: Request) -> str:
    username = request.session.get(SESSION_KEY)
    if username is None:
        # The auth middleware already gates these routes; this is a guard.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return username


@router.get("/test")
def test(request: Request) -> dict[str, str]:
    _username(request)  # auth guard (middleware also gates)
    try:
        answer = ask(_TEST_PROMPT)
    except AIConfigError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI not configured (OPENROUTER_API_KEY missing)",
        )
    except Exception as exc:  # upstream SDK / network errors
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI request failed: {exc}",
        )
    return {"answer": answer}


@router.post("/chat")
def chat(
    body: ChatRequest,
    request: Request,
    conn=Depends(get_db),
) -> dict:
    _username(request)  # auth guard (middleware also gates)
    try:
        result: ChatResult = handle_chat(conn, _username(request), body.message)
    except AIConfigError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI not configured (OPENROUTER_API_KEY missing)",
        )
    except Exception as exc:  # upstream SDK / network errors
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI request failed: {exc}",
        )
    return {"reply": result.reply, "board": result.board.model_dump()}
