from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ping_returns_pong() -> None:
    response = client.get("/api/ping")
    assert response.status_code == 200
    assert response.json() == {"ping": "pong"}
