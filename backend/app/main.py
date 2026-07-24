from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Kanban API", version="0.1.0")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
INDEX_FILE = STATIC_DIR / "index.html"


@app.get("/api/ping")
def ping() -> dict[str, str]:
    return {"ping": "pong"}


if (STATIC_DIR / "_next").is_dir():
    app.mount("/_next", StaticFiles(directory=STATIC_DIR / "_next"), name="next-assets")


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
