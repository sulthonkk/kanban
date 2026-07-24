from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module

client = TestClient(app=main_module.app)


def test_ping_returns_pong() -> None:
    response = client.get("/api/ping")
    assert response.status_code == 200
    assert response.json() == {"ping": "pong"}


def _mount_static(tmp_path: Path) -> Path:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<!doctype html><title>App</title>", encoding="utf-8")
    return static_dir


def test_root_serves_index_when_built(tmp_path, monkeypatch) -> None:
    static_dir = _mount_static(tmp_path)
    monkeypatch.setattr(main_module, "STATIC_DIR", static_dir, raising=True)
    monkeypatch.setattr(main_module, "INDEX_FILE", static_dir / "index.html", raising=True)
    response = client.get("/")
    assert response.status_code == 200
    assert "App" in response.text


def test_unknown_path_serves_index_when_built(tmp_path, monkeypatch) -> None:
    static_dir = _mount_static(tmp_path)
    monkeypatch.setattr(main_module, "STATIC_DIR", static_dir, raising=True)
    monkeypatch.setattr(main_module, "INDEX_FILE", static_dir / "index.html", raising=True)
    response = client.get("/whatever")
    assert response.status_code == 200
    assert "App" in response.text


def test_known_static_asset_is_served(tmp_path, monkeypatch) -> None:
    static_dir = _mount_static(tmp_path)
    (static_dir / "favicon.ico").write_bytes(b"ICON")
    monkeypatch.setattr(main_module, "STATIC_DIR", static_dir, raising=True)
    monkeypatch.setattr(main_module, "INDEX_FILE", static_dir / "index.html", raising=True)
    response = client.get("/favicon.ico")
    assert response.status_code == 200
    assert response.content == b"ICON"


def test_root_helps_when_not_built(tmp_path, monkeypatch) -> None:
    missing = tmp_path / "missing"
    monkeypatch.setattr(main_module, "STATIC_DIR", missing, raising=True)
    monkeypatch.setattr(main_module, "INDEX_FILE", missing / "index.html", raising=True)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "status": "frontend not built. Run `npm run build` in frontend/."
    }


def test_unknown_path_404_when_not_built(tmp_path, monkeypatch) -> None:
    missing = tmp_path / "missing"
    monkeypatch.setattr(main_module, "STATIC_DIR", missing, raising=True)
    monkeypatch.setattr(main_module, "INDEX_FILE", missing / "index.html", raising=True)
    response = client.get("/whatever")
    assert response.status_code == 404
