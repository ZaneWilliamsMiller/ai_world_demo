"""主路由：挂载子路由 + health 端点。

原 routes.py 已拆分为：
- api/routes.py (本文件): health + 子路由挂载
- api/player_routes.py: hello, move, state, journal
- api/npc_routes.py: talk, talk_stream, agent, finale, bounty, item, rest
- api/save_routes.py: save, load, delete_save, saves_list
"""
from __future__ import annotations

from fastapi import APIRouter

from backend.data.prompts import WORLD_NAME

router = APIRouter()

from backend.api.npc_routes import router as npc_router
from backend.api.player_routes import router as player_router
from backend.api.save_routes import router as save_router
from backend.api.admin_routes import router as admin_router
from backend.config import settings

router.include_router(player_router)
router.include_router(npc_router)
router.include_router(save_router)
router.include_router(admin_router)

if settings.enable_test_routes:
    from backend.api.dev import router as test_router

    router.include_router(test_router)


@router.get("/api/health")
async def health() -> dict[str, str]:
    try:
        from backend.config import settings

        llm_ok = bool(settings.llm_api_key and settings.llm_base_url)
        shutdown_ok = bool(settings.shutdown_secret)
    except Exception:
        llm_ok = False
        shutdown_ok = False
    return {
        "status": "ok",
        "llm_configured": str(llm_ok).lower(),
        "shutdown_configured": str(shutdown_ok).lower(),
        "world": WORLD_NAME,
    }
