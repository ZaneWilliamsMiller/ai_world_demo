from __future__ import annotations

"""
运行（在 ai_world_demo 目录下）:
  python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
"""
import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.data.prompts import WORLD_NAME
from backend.api.routes import router as api_router
from backend.session.store import room
from backend.systems.save_system import save_game

_log = logging.getLogger("app")

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


# 定期自动存档（后台任务）
_auto_save_task = None

@app.on_event("startup")
async def _startup():
    """启动后台定期存档任务 + 初始化实体关键词缓存。"""
    global _auto_save_task
    _auto_save_task = asyncio.create_task(_auto_save_loop())
    # 初始化代词消解用的实体关键词缓存（从 NPCS/MAPS 数据动态构建）
    from backend.memory import init_entity_keywords
    init_entity_keywords()

async def _auto_save_loop():
    """每 5 分钟自动存档所有活跃玩家。"""
    _save_log = logging.getLogger("auto_save")
    while True:
        await asyncio.sleep(300)  # 5 分钟
        saved = 0
        for pid, p in list(room.players.items()):
            if p.dead or p.ended:
                continue
            try:
                save_game(p)
                saved += 1
            except Exception as e:
                _save_log.error("auto-save failed %s: %s", pid, e)
        if saved:
            _save_log.info("auto-saved %d player(s)", saved)

@app.on_event("shutdown")
async def _shutdown():
    """优雅关闭：取消自动存档任务 + 自动存档所有活跃玩家 + 释放 httpx 连接池。"""
    # 取消定期存档任务
    global _auto_save_task
    if _auto_save_task and not _auto_save_task.done():
        _auto_save_task.cancel()

    saved = 0
    for pid, p in list(room.players.items()):
        if p.dead or p.ended:
            continue
        try:
            save_game(p)
            saved += 1
        except Exception as e:
            _log.error("auto-save failed %s: %s", pid, e)
    if saved:
        _log.info("shutdown auto-saved %d active player(s)", saved)

    from backend.llm_client import _close_client
    await _close_client()


@app.get("/")
async def index() -> FileResponse:
    index_path = STATIC / "index.html"
    if not index_path.is_file():
        raise HTTPException(500, "缺少 static/index.html")
    return FileResponse(index_path)
