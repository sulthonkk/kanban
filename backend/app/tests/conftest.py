from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.db import init_db


@pytest.fixture
def client() -> TestClient:
    return TestClient(app=main_module.app)


@pytest.fixture
def authed_client(client: TestClient) -> TestClient:
    response = client.post(
        "/api/login",
        data={"username": "user", "password": "password"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<!doctype html><title>App</title>", encoding="utf-8")
    return static_dir


@pytest.fixture
def db_path(tmp_path: Path, monkeypatch) -> Path:
    """A fresh, seeded SQLite database isolated to this test.

    Sets ``KANBAN_DB_PATH`` so ``get_db`` (used by the board API) opens this
    file, then creates + seeds the schema. Existing ``client`` /
    ``authed_client`` fixtures are unaffected (they never touch the DB).
    """
    path = tmp_path / "kanban.db"
    monkeypatch.setenv("KANBAN_DB_PATH", str(path))
    init_db(path)
    return path


@pytest.fixture
def db_authed_client(client: TestClient, db_path: Path) -> TestClient:
    """An authenticated client backed by a fresh seeded DB."""
    response = client.post(
        "/api/login",
        data={"username": "user", "password": "password"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client
