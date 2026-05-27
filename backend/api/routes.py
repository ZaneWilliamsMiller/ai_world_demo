"""主路由：挂载子路由 + health 端点。

原 routes.py 已拆分为：
- api/routes.py (本文件): health + 子路由挂载
- api/player_routes.py: hello, move, state, journal
- api/npc_routes.py: talk, talk_stream, agent, finale, bounty, item, rest
- api/save_routes.py: save, load, delete_save, saves_list
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from backend.data.prompts import WORLD_NAME

router = APIRouter()

# ── 挂载子路由 ──
from backend.api.player_routes import router as player_router
from backend.api.npc_routes import router as npc_router
from backend.api.save_routes import router as save_router
from backend.api.test_routes import router as test_router

router.include_router(player_router)
router.include_router(npc_router)
router.include_router(save_router)
router.include_router(test_router)


@router.get("/api/health")
async def health() -> dict[str, str]:
    from backend.config import settings
    return {"status": "ok", "model": settings.llm_model, "world": WORLD_NAME}
