from typing import Any

from fastapi.testclient import TestClient


def _seed_column_ids(client: TestClient) -> dict[str, str]:
    board = client.get("/api/board").json()
    return {col["title"]: col["id"] for col in board["columns"]}


def _seed_card_ids(client: TestClient) -> dict[str, str]:
    board = client.get("/api/board").json()
    return {card["title"]: card["id"] for col in board["columns"] for card in col["cards"]}


def _card_titles_in_column(client: TestClient, column_id: str) -> list[str]:
    board = client.get("/api/board").json()
    col = next(c for c in board["columns"] if c["id"] == column_id)
    return [card["title"] for card in col["cards"]]


def _find_card(client: TestClient, card_id: str) -> dict[str, Any] | None:
    board = client.get("/api/board").json()
    for col in board["columns"]:
        for card in col["cards"]:
            if card["id"] == card_id:
                return {**card, "column_id": col["id"]}
    return None


# --------------------------------------------------------------------------- #
# GET /api/board
# --------------------------------------------------------------------------- #
def test_get_board_returns_seeded_board(db_authed_client: TestClient) -> None:
    response = db_authed_client.get("/api/board")
    assert response.status_code == 200
    board = response.json()
    assert board["title"] == "Project board"
    assert [c["title"] for c in board["columns"]] == [
        "Backlog", "Ready", "In progress", "In review", "Done"
    ]
    assert sum(len(c["cards"]) for c in board["columns"]) == 7


def test_get_board_requires_auth(client: TestClient) -> None:
    response = client.get("/api/board", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


# --------------------------------------------------------------------------- #
# POST /api/columns/{id}/rename
# --------------------------------------------------------------------------- #
def test_rename_column_updates_title(db_authed_client: TestClient) -> None:
    column_ids = _seed_column_ids(db_authed_client)
    response = db_authed_client.post(
        f"/api/columns/{column_ids['Backlog']}/rename",
        json={"title": "  Inbox  "},
    )
    assert response.status_code == 200
    titles = [c["title"] for c in response.json()["columns"]]
    assert titles == ["Inbox", "Ready", "In progress", "In review", "Done"]


def test_rename_column_404_for_unknown(db_authed_client: TestClient) -> None:
    response = db_authed_client.post(
        "/api/columns/does-not-exist/rename",
        json={"title": "X"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "column not found"


def test_rename_column_rejects_blank_title(db_authed_client: TestClient) -> None:
    column_ids = _seed_column_ids(db_authed_client)
    response = db_authed_client.post(
        f"/api/columns/{column_ids['Backlog']}/rename",
        json={"title": "   "},
    )
    assert response.status_code == 422


def test_rename_column_rejects_missing_field(db_authed_client: TestClient) -> None:
    column_ids = _seed_column_ids(db_authed_client)
    response = db_authed_client.post(
        f"/api/columns/{column_ids['Backlog']}/rename", json={}
    )
    assert response.status_code == 422


def test_rename_column_requires_auth(client: TestClient) -> None:
    response = client.post(
        "/api/columns/whatever/rename", json={"title": "X"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


# --------------------------------------------------------------------------- #
# POST /api/cards
# --------------------------------------------------------------------------- #
def test_create_card_appends_to_column(db_authed_client: TestClient) -> None:
    column_ids = _seed_column_ids(db_authed_client)
    response = db_authed_client.post(
        "/api/cards",
        json={
            "column_id": column_ids["Backlog"],
            "title": "New task",
            "details": "Some details",
        },
    )
    assert response.status_code == 201
    backlog = next(c for c in response.json()["columns"] if c["id"] == column_ids["Backlog"])
    assert backlog["cards"][-1]["title"] == "New task"
    assert backlog["cards"][-1]["details"] == "Some details"
    assert len(backlog["cards"]) == 3  # two seed cards + new


def test_create_card_defaults_empty_details(db_authed_client: TestClient) -> None:
    column_ids = _seed_column_ids(db_authed_client)
    response = db_authed_client.post(
        "/api/cards",
        json={"column_id": column_ids["Ready"], "title": "No details"},
    )
    assert response.status_code == 201
    card = response.json()["columns"][1]["cards"][-1]
    assert card["details"] == ""


def test_create_card_404_for_unknown_column(db_authed_client: TestClient) -> None:
    response = db_authed_client.post(
        "/api/cards", json={"column_id": "nope", "title": "X"}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "column not found"


def test_create_card_rejects_blank_title(db_authed_client: TestClient) -> None:
    column_ids = _seed_column_ids(db_authed_client)
    response = db_authed_client.post(
        "/api/cards", json={"column_id": column_ids["Backlog"], "title": "  "}
    )
    assert response.status_code == 422


def test_create_card_rejects_missing_column_id(db_authed_client: TestClient) -> None:
    response = db_authed_client.post(
        "/api/cards", json={"title": "X"}
    )
    assert response.status_code == 422


def test_create_card_requires_auth(client: TestClient) -> None:
    response = client.post(
        "/api/cards", json={"column_id": "x", "title": "y"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


# --------------------------------------------------------------------------- #
# DELETE /api/cards/{id}
# --------------------------------------------------------------------------- #
def test_delete_card_removes_it(db_authed_client: TestClient) -> None:
    card_ids = _seed_card_ids(db_authed_client)
    target = card_ids["Refresh the onboarding"]
    response = db_authed_client.delete(f"/api/cards/{target}")
    assert response.status_code == 204
    board = db_authed_client.get("/api/board").json()
    flat = [card["id"] for col in board["columns"] for card in col["cards"]]
    assert target not in flat
    assert sum(len(c["cards"]) for c in board["columns"]) == 6


def test_delete_card_404_for_unknown(db_authed_client: TestClient) -> None:
    response = db_authed_client.delete("/api/cards/does-not-exist")
    assert response.status_code == 404
    assert response.json()["detail"] == "card not found"


def test_delete_card_requires_auth(client: TestClient) -> None:
    response = client.delete("/api/cards/whatever", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


# --------------------------------------------------------------------------- #
# POST /api/cards/{id}/move
# --------------------------------------------------------------------------- #
def test_move_card_to_different_column_appends(db_authed_client: TestClient) -> None:
    column_ids = _seed_column_ids(db_authed_client)
    card_ids = _seed_card_ids(db_authed_client)
    card_id = card_ids["Refresh the onboarding"]  # in Backlog (pos 0)

    response = db_authed_client.post(
        f"/api/cards/{card_id}/move",
        json={"column_id": column_ids["Done"]},
    )
    assert response.status_code == 200
    backlog_titles = _card_titles_in_column(db_authed_client, column_ids["Backlog"])
    done_titles = _card_titles_in_column(db_authed_client, column_ids["Done"])
    assert backlog_titles == ["Customer interview notes"]
    assert done_titles == ["Define visual direction", "Refresh the onboarding"]


def test_move_card_to_specific_index(db_authed_client: TestClient) -> None:
    column_ids = _seed_column_ids(db_authed_client)
    card_ids = _seed_card_ids(db_authed_client)
    card_id = card_ids["Define visual direction"]  # in Done (pos 0)

    response = db_authed_client.post(
        f"/api/cards/{card_id}/move",
        json={"column_id": column_ids["Backlog"], "index": 0},
    )
    assert response.status_code == 200
    backlog_titles = _card_titles_in_column(db_authed_client, column_ids["Backlog"])
    assert backlog_titles == [
        "Define visual direction", "Refresh the onboarding", "Customer interview notes"
    ]


def test_move_card_within_same_column_reorders(db_authed_client: TestClient) -> None:
    column_ids = _seed_column_ids(db_authed_client)
    card_ids = _seed_card_ids(db_authed_client)
    card_id = card_ids["Customer interview notes"]  # Backlog pos 1 -> pos 0

    response = db_authed_client.post(
        f"/api/cards/{card_id}/move",
        json={"column_id": column_ids["Backlog"], "index": 0},
    )
    assert response.status_code == 200
    backlog_titles = _card_titles_in_column(db_authed_client, column_ids["Backlog"])
    assert backlog_titles == ["Customer interview notes", "Refresh the onboarding"]


def test_move_card_index_clamped_to_end(db_authed_client: TestClient) -> None:
    column_ids = _seed_column_ids(db_authed_client)
    card_ids = _seed_card_ids(db_authed_client)
    card_id = card_ids["Refresh the onboarding"]

    response = db_authed_client.post(
        f"/api/cards/{card_id}/move",
        json={"column_id": column_ids["Done"], "index": 999},
    )
    assert response.status_code == 200
    done_titles = _card_titles_in_column(db_authed_client, column_ids["Done"])
    assert done_titles == ["Define visual direction", "Refresh the onboarding"]


def test_move_card_404_for_unknown_card(db_authed_client: TestClient) -> None:
    column_ids = _seed_column_ids(db_authed_client)
    response = db_authed_client.post(
        "/api/cards/nope/move",
        json={"column_id": column_ids["Backlog"]},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "card not found"


def test_move_card_404_for_unknown_destination_column(db_authed_client: TestClient) -> None:
    card_ids = _seed_card_ids(db_authed_client)
    response = db_authed_client.post(
        f"/api/cards/{card_ids['Refresh the onboarding']}/move",
        json={"column_id": "nope"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "column not found"


def test_move_card_rejects_negative_index(db_authed_client: TestClient) -> None:
    column_ids = _seed_column_ids(db_authed_client)
    card_ids = _seed_card_ids(db_authed_client)
    response = db_authed_client.post(
        f"/api/cards/{card_ids['Refresh the onboarding']}/move",
        json={"column_id": column_ids["Done"], "index": -1},
    )
    assert response.status_code == 422


def test_move_card_requires_auth(client: TestClient) -> None:
    response = client.post(
        "/api/cards/whatever/move", json={"column_id": "x"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


# --------------------------------------------------------------------------- #
# PUT /api/board/meta
# --------------------------------------------------------------------------- #
def test_update_board_meta_renames_title(db_authed_client: TestClient) -> None:
    response = db_authed_client.put("/api/board/meta", json={"title": "  Sprint 42  "})
    assert response.status_code == 200
    assert response.json()["title"] == "Sprint 42"
    # Persisted.
    assert db_authed_client.get("/api/board").json()["title"] == "Sprint 42"


def test_update_board_meta_rejects_blank(db_authed_client: TestClient) -> None:
    response = db_authed_client.put("/api/board/meta", json={"title": ""})
    assert response.status_code == 422


def test_update_board_meta_rejects_whitespace_only(db_authed_client: TestClient) -> None:
    response = db_authed_client.put("/api/board/meta", json={"title": "    "})
    assert response.status_code == 422


def test_update_board_meta_requires_auth(client: TestClient) -> None:
    response = client.put(
        "/api/board/meta", json={"title": "X"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


# --------------------------------------------------------------------------- #
# Persistence + isolation
# --------------------------------------------------------------------------- #
def test_mutations_persist_across_requests(db_authed_client: TestClient) -> None:
    column_ids = _seed_column_ids(db_authed_client)
    db_authed_client.post(
        "/api/cards",
        json={"column_id": column_ids["Ready"], "title": "Persisted", "details": "y"},
    )
    board = db_authed_client.get("/api/board").json()
    ready = next(c for c in board["columns"] if c["id"] == column_ids["Ready"])
    assert ready["cards"][-1]["title"] == "Persisted"


def test_each_test_gets_fresh_seeded_database(db_authed_client: TestClient) -> None:
    # If the DB were shared with other tests, earlier mutations would leak.
    # Here we should see the pristine 7 seed cards.
    board = db_authed_client.get("/api/board").json()
    assert sum(len(c["cards"]) for c in board["columns"]) == 7
    assert board["title"] == "Project board"
