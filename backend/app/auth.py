"""Authentication for the Kanban MVP.

A single hardcoded user (`user` / `password`) is supported. The password is
bcrypt-hashed on first use and stored in memory. Sessions are signed cookies
managed by Starlette's SessionMiddleware.
"""

from __future__ import annotations

import os
from pathlib import Path

import bcrypt

USERNAME = "user"
PASSWORD = "password"
SESSION_KEY = "user"
SESSION_SECRET = os.environ.get(
    "SESSION_SECRET", "kanban-mvp-dev-secret-change-me"
)

_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "login.html"
_LOGIN_TEMPLATE = _TEMPLATE_PATH.read_text(encoding="utf-8")

_PASSWORD_HASH: bytes | None = None


def _hash() -> bytes:
    global _PASSWORD_HASH
    if _PASSWORD_HASH is None:
        _PASSWORD_HASH = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt())
    return _PASSWORD_HASH


def verify_credentials(username: str, password: str) -> bool:
    if username != USERNAME:
        return False
    return bcrypt.checkpw(password.encode(), _hash())


def login_html(show_error: bool = False) -> str:
    error_block = (
        '<p class="error" role="alert">Invalid username or password.</p>'
        if show_error
        else ""
    )
    return _LOGIN_TEMPLATE.replace("{error_block}", error_block)
