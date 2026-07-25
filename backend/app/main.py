from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.auth import SESSION_KEY, SESSION_SECRET, login_html, verify_credentials
from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Kanban API", version="0.1.0", lifespan=lifespan)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
INDEX_FILE = STATIC_DIR / "index.html"

PUBLIC_PATHS = {"/login", "/api/login", "/api/logout", "/api/ping"}


@app.middleware("http")
async def require_auth(request: Request, call_next):
    path = request.url.path
    if path in PUBLIC_PATHS:
        return await call_next(request)
    if request.session.get(SESSION_KEY) is None:
        return RedirectResponse("/login", status_code=303)
    return await call_next(request)


if (STATIC_DIR / "_next").is_dir():
    app.mount("/_next", StaticFiles(directory=STATIC_DIR / "_next"), name="next-assets")


@app.get("/login")
def login(request: Request):
    show_error = request.url.query == "error=1"
    return HTMLResponse(login_html(show_error))


@app.post("/api/login")
def api_login(request: Request, username: str = Form(), password: str = Form()):
    if not verify_credentials(username, password):
        return RedirectResponse("/login?error=1", status_code=303)
    request.session[SESSION_KEY] = username
    return RedirectResponse("/", status_code=303)


@app.post("/api/logout")
def api_logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/api/ping")
def ping() -> dict[str, str]:
    return {"ping": "pong"}


@app.get("/", response_model=None)
def root() -> FileResponse | dict[str, str]:
    if INDEX_FILE.is_file():
        return FileResponse(INDEX_FILE)
    return {"status": "frontend not built. Run `npm run build` in frontend/."}


@app.get("/{full_path:path}")
def spa_fallback(full_path: str) -> FileResponse:
    candidate = STATIC_DIR / full_path
    if full_path and candidate.is_file():
        return FileResponse(candidate)
    if INDEX_FILE.is_file():
        return FileResponse(INDEX_FILE)
    raise HTTPException(status_code=404, detail="Frontend build not found")


app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, session_cookie="kanban_session")
