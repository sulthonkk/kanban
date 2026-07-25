"""OpenRouter AI client.

A minimal wrapper over the OpenAI SDK pointed at the OpenRouter base URL.
Reads ``OPENROUTER_API_KEY`` and ``OPENROUTER_MODEL`` from the environment;
no model name is hardcoded in application code (``OPENROUTER_MODEL`` defaults
to the dev model ``openai/gpt-oss-20b:free`` per AGENTS.md).

Architecture role: the "external dependency" the AI service exposes to
routes. Routes stay thin (``app/ai_api.py``); this module owns SDK wiring.

For Phase 7 only the plain ``ask`` call is exercised by ``GET /api/ai/test``.
The optional ``response_format`` parameter is accepted so Phase 8 can reuse
the same client for structured outputs.
"""

from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-oss-20b:free"


class AIConfigError(RuntimeError):
    """Raised when the AI client cannot be built (e.g. missing API key)."""


def _read_key() -> str | None:
    return os.environ.get("OPENROUTER_API_KEY")


def _read_model() -> str:
    return os.environ.get("OPENROUTER_MODEL") or DEFAULT_MODEL


_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        key = _read_key()
        if not key:
            raise AIConfigError("OPENROUTER_API_KEY is not set")
        _client = OpenAI(base_url=BASE_URL, api_key=key)
    return _client


def reset() -> None:
    """Clear the cached client. Used by tests to force re-reading the env."""
    global _client
    _client = None


def ask(
    prompt: str,
    *,
    response_format: dict[str, Any] | None = None,
    max_tokens: int = 2000,
) -> str:
    """Send a single-turn prompt to the configured OpenRouter model.

    Returns the assistant's text content (empty string if the model returned
    ``None`` content, e.g. a reasoning model that only emitted reasoning).
    Raises :class:`AIConfigError` if the key is missing; otherwise
    propagates SDK exceptions to the caller.
    """
    client = _get_client()
    kwargs: dict[str, Any] = {
        "model": _read_model(),
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format
    completion = client.chat.completions.create(**kwargs)
    return completion.choices[0].message.content or ""
