from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module

CLIENT = TestClient(app=main_module.app)


def test_ping_is_public_and_open() -> None:
    response = CLIENT.get("/api/ping")
    assert response.status_code == 200
    assert response.json() == {"ping": "pong"}


def test_root_requires_auth(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_root_serves_index_when_built(
    authed_client: TestClient, static_dir: Path, monkeypatch
) -> None:
    monkeypatch.setattr(main_module, "STATIC_DIR", static_dir, raising=True)
    monkeypatch.setattr(main_module, "INDEX_FILE", static_dir / "index.html", raising=True)
    response = authed_client.get("/")
    assert response.status_code == 200
    assert "App" in response.text


def test_unknown_path_serves_index_when_built(
    authed_client: TestClient, static_dir: Path, monkeypatch
) -> None:
    monkeypatch.setattr(main_module, "STATIC_DIR", static_dir, raising=True)
    monkeypatch.setattr(main_module, "INDEX_FILE", static_dir / "index.html", raising=True)
    response = authed_client.get("/whatever")
    assert response.status_code == 200
    assert "App" in response.text


def test_known_static_asset_is_served(
    authed_client: TestClient, static_dir: Path, monkeypatch
) -> None:
    (static_dir / "favicon.ico").write_bytes(b"ICON")
    monkeypatch.setattr(main_module, "STATIC_DIR", static_dir, raising=True)
    monkeypatch.setattr(main_module, "INDEX_FILE", static_dir / "index.html", raising=True)
    response = authed_client.get("/favicon.ico")
    assert response.status_code == 200
    assert response.content == b"ICON"


def test_root_helps_when_not_built(authed_client: TestClient, tmp_path, monkeypatch) -> None:
    missing = tmp_path / "missing"
    monkeypatch.setattr(main_module, "STATIC_DIR", missing, raising=True)
    monkeypatch.setattr(main_module, "INDEX_FILE", missing / "index.html", raising=True)
    response = authed_client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "status": "frontend not built. Run `npm run build` in frontend/."
    }


def test_unknown_path_404_when_not_built(authed_client: TestClient, tmp_path, monkeypatch) -> None:
    missing = tmp_path / "missing"
    monkeypatch.setattr(main_module, "STATIC_DIR", missing, raising=True)
    monkeypatch.setattr(main_module, "INDEX_FILE", missing / "index.html", raising=True)
    response = authed_client.get("/whatever")
    assert response.status_code == 404
