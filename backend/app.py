from __future__ import annotations

"""
运行（在 ai_world_demo 目录下）:
  python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.data.prompts import WORLD_NAME
from backend.api.routes import router as api_router

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"

def _cors_allow_origins() -> tuple[list[str], bool]:
    """返回 (origins, allow_credentials)。origins 为 * 时凭证必须为 False（浏览器规范）。"""
    raw = (settings.cors_allow_origins or "").strip()
    if not raw or raw == "*":
        return ["*"], False
    origins = [x.strip() for x in raw.split(",") if x.strip()]
    if not origins:
        return ["*"], False
    return origins, True

_origins, _creds = _cors_allow_origins()

app = FastAPI(title=f"{WORLD_NAME} · 江湖行纪")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

@app.get("/")
async def index() -> FileResponse:
    index_path = STATIC / "index.html"
    if not index_path.is_file():
        raise HTTPException(500, "缺少 static/index.html")
    return FileResponse(index_path)
