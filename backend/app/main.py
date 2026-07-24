from fastapi import FastAPI

app = FastAPI(title="Kanban API", version="0.1.0")


@app.get("/api/ping")
def ping() -> dict[str, str]:
    return {"ping": "pong"}
