"""Tests for the AI connectivity foundation (Phase 7).

No live network calls. The OpenAI SDK client is monkeypatched with a fake
that records the request shape and returns a canned completion.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

import app.ai_client as ai_client
from app.ai_client import AIConfigError


class _FakeMessage:
    def __init__(self, content: str | None) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str | None) -> None:
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content: str | None = "4") -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self) -> None:
        self.last_kwargs: dict[str, Any] | None = None
        self.calls = 0
        self.raise_exc: Exception | None = None
        self.content: str | None = "4"

    def create(self, **kwargs: Any) -> _FakeCompletion:
        self.calls += 1
        self.last_kwargs = kwargs
        if self.raise_exc is not None:
            raise self.raise_exc
        return _FakeCompletion(self.content)


class _FakeChat:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.completions = completions


class _FakeOpenAI:
    def __init__(self) -> None:
        self.chat = _FakeChat(_FakeCompletions())


@pytest.fixture
def fake_client(monkeypatch) -> _FakeOpenAI:
    """Install a fake OpenAI client so routes do not touch the network."""
    fake = _FakeOpenAI()
    monkeypatch.setattr(ai_client, "_client", fake)
    return fake


@pytest.fixture
def ai_key(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key")


@pytest.fixture
def ai_authed(client: TestClient, ai_key, fake_client) -> TestClient:
    """Authenticated client with the fake AI client wired in."""
    response = client.post(
        "/api/login",
        data={"username": "user", "password": "password"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


# --------------------------------------------------------------------------- #
# GET /api/ai/test
# --------------------------------------------------------------------------- #
def test_ai_test_returns_answer(ai_authed: TestClient, fake_client: _FakeOpenAI) -> None:
    response = ai_authed.get("/api/ai/test")
    assert response.status_code == 200
    assert response.json() == {"answer": "4"}
    assert fake_client.chat.completions.calls == 1


def test_ai_test_sends_expected_request_shape(
    ai_authed: TestClient, fake_client: _FakeOpenAI
) -> None:
    ai_authed.get("/api/ai/test")
    kwargs = fake_client.chat.completions.last_kwargs
    assert kwargs is not None
    # The model name must come from the env, not be hardcoded in the call.
    assert kwargs["model"] == "openai/gpt-oss-20b:free"
    assert kwargs["messages"] == [
        {"role": "user", "content": "What is 2+2? Reply with just the number."}
    ]
    assert "response_format" not in kwargs
    assert kwargs["max_tokens"] == 2000


def test_ai_test_uses_openrouter_model_env_when_set(
    ai_authed: TestClient, fake_client: _FakeOpenAI, monkeypatch
) -> None:
    monkeypatch.setenv("OPENROUTER_MODEL", "some/other-model")
    ai_authed.get("/api/ai/test")
    assert fake_client.chat.completions.last_kwargs["model"] == "some/other-model"


def test_ai_test_requires_auth(client: TestClient) -> None:
    response = client.get("/api/ai/test", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


# --------------------------------------------------------------------------- #
# Missing API key -> 503
# --------------------------------------------------------------------------- #
def test_ai_test_503_when_api_key_missing(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    ai_client.reset()  # drop any cached client so _get_client re-reads env
    client.post(
        "/api/login",
        data={"username": "user", "password": "password"},
        follow_redirects=False,
    )
    response = client.get("/api/ai/test")
    assert response.status_code == 503
    assert "OPENROUTER_API_KEY" in response.json()["detail"]


def test_ai_client_ask_raises_when_key_missing(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    ai_client.reset()
    with pytest.raises(AIConfigError):
        ai_client.ask("anything")


# --------------------------------------------------------------------------- #
# Upstream failure -> 502
# --------------------------------------------------------------------------- #
def test_ai_test_502_on_upstream_error(
    client: TestClient, monkeypatch, fake_client: _FakeOpenAI
) -> None:
    fake_client.chat.completions.raise_exc = RuntimeError("boom from openrouter")
    client.post(
        "/api/login",
        data={"username": "user", "password": "password"},
        follow_redirects=False,
    )
    response = client.get("/api/ai/test")
    assert response.status_code == 502
    assert "boom from openrouter" in response.json()["detail"]


def test_ai_test_returns_empty_string_when_model_returns_none(
    ai_authed: TestClient, fake_client: _FakeOpenAI
) -> None:
    # Reasoning models occasionally return content=None; the client must
    # coerce to "" rather than propagate None to the caller.
    fake_client.chat.completions.content = None
    response = ai_authed.get("/api/ai/test")
    assert response.status_code == 200
    assert response.json() == {"answer": ""}
