from fastapi.testclient import TestClient

from app.auth import PASSWORD, USERNAME, verify_credentials


def test_ping_is_public(client: TestClient) -> None:
    response = client.get("/api/ping")
    assert response.status_code == 200
    assert response.json() == {"ping": "pong"}


def test_verify_credentials_accepts_known_user() -> None:
    assert verify_credentials(USERNAME, PASSWORD) is True


def test_verify_credentials_rejects_wrong_password() -> None:
    assert verify_credentials(USERNAME, "wrong") is False


def test_verify_credentials_rejects_unknown_user() -> None:
    assert verify_credentials("nobody", PASSWORD) is False


def test_login_form_renders_without_session(client: TestClient) -> None:
    response = client.get("/login")
    assert response.status_code == 200
    assert "Sign in" in response.text
    assert 'action="/api/login"' in response.text
    assert "Demo credentials:" in response.text


def test_login_form_shows_error_when_query_set(client: TestClient) -> None:
    response = client.get("/login?error=1")
    assert response.status_code == 200
    assert "Invalid username or password." in response.text


def test_unauthenticated_root_redirects_to_login(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_unauthenticated_api_is_gated(client: TestClient) -> None:
    # /api/ping is public; every other /api path under test is gated.
    # Use a placeholder gated path that we know will 303 rather than 404 once authed.
    response = client.get("/api/anything-else", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_static_asset_path_is_gated_without_session(client: TestClient) -> None:
    response = client.get("/_next/static/chunks/x.js", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_login_with_valid_credentials_sets_session_and_redirects(client: TestClient) -> None:
    response = client.post(
        "/api/login",
        data={"username": USERNAME, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    set_cookie = response.headers.get("set-cookie", "")
    assert "kanban_session=" in set_cookie


def test_login_with_invalid_password_redirects_to_login_with_error(client: TestClient) -> None:
    response = client.post(
        "/api/login",
        data={"username": USERNAME, "password": "wrong"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=1"
    assert "kanban_session=" not in response.headers.get("set-cookie", "")


def test_login_with_unknown_user_redirects_to_login_with_error(client: TestClient) -> None:
    response = client.post(
        "/api/login",
        data={"username": "nobody", "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=1"


def test_authenticated_can_reach_root(client: TestClient) -> None:
    client.post("/api/login", data={"username": USERNAME, "password": PASSWORD})
    response = client.get("/", follow_redirects=False)
    # Authed response is either the SPA (200) or the "not built" JSON (200) -
    # what matters for this auth test is that it is NOT a 303 to /login.
    assert response.status_code == 200


def test_logout_clears_session_and_redirects_to_login(client: TestClient) -> None:
    client.post("/api/login", data={"username": USERNAME, "password": PASSWORD})
    response = client.post("/api/logout", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    # After logout, / is gated again.
    gated = client.get("/", follow_redirects=False)
    assert gated.status_code == 303
    assert gated.headers["location"] == "/login"


def test_full_login_flow(client: TestClient) -> None:
    # 1. Anonymous visit redirects to login.
    step1 = client.get("/", follow_redirects=False)
    assert step1.status_code == 303
    assert step1.headers["location"] == "/login"

    # 2. Login form is reachable.
    step2 = client.get("/login")
    assert step2.status_code == 200
    assert "Sign in" in step2.text

    # 3. Submit bad credentials -> back to login with error.
    step3 = client.post(
        "/api/login",
        data={"username": "user", "password": "nope"},
        follow_redirects=False,
    )
    assert step3.status_code == 303
    assert step3.headers["location"] == "/login?error=1"

    # 4. Submit correct credentials -> redirect to /.
    step4 = client.post(
        "/api/login",
        data={"username": USERNAME, "password": PASSWORD},
        follow_redirects=False,
    )
    assert step4.status_code == 303
    assert step4.headers["location"] == "/"

    # 5. Authenticated visit to / is allowed (not redirected).
    step5 = client.get("/", follow_redirects=False)
    assert step5.status_code != 303

    # 6. Logout -> redirect to /login.
    step6 = client.post("/api/logout", follow_redirects=False)
    assert step6.status_code == 303
    assert step6.headers["location"] == "/login"

    # 7. After logout, anonymous visit redirects to login again.
    step7 = client.get("/", follow_redirects=False)
    assert step7.status_code == 303
    assert step7.headers["location"] == "/login"
