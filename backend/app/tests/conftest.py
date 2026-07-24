from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main_module


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
