"""存档 API 路由：save, load, delete_save, saves_list。"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.systems.core import init_npc_positions
from backend.systems.economy import init_npc_inventories
from backend.systems.save_system import save_game, load_game, list_saves, delete_save
from backend.views import build_init_response

router = APIRouter()


class SaveBody(BaseModel):
    player_id: str

class LoadBody(BaseModel):
    player_id: str
    display_name: str | None = None
    gender: str = Field(default="未言", pattern="^(男|女|未言)$")
    permadeath: bool = False

class DeleteSaveBody(BaseModel):
    player_id: str


@router.get("/api/saves")
async def saves_list() -> dict[str, Any]:
    """列出全部存档角色。"""
    return {"saves": list_saves()}


@router.post("/api/save")
async def save_player(body: SaveBody) -> dict[str, Any]:
    """手动保存当前角色进度。"""
    from backend.session.store import room
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    path = await asyncio.to_thread(save_game, p)
    return {"ok": True, "path": path}


@router.post("/api/load")
async def load_player(body: LoadBody) -> dict[str, Any]:
    from backend.session.store import room
    loaded = load_game(body.player_id)
    if not loaded:
        raise HTTPException(404, f"存档不存在: {body.player_id}")
    if loaded.dead and loaded.permadeath:
        raise HTTPException(400, "此角色已在真实江湖中身故，存档已废")
    if loaded.ended:
        raise HTTPException(400, "此角色的故事已收束，不可再入")
    room.players[body.player_id] = loaded
    init_npc_positions(loaded)
    init_npc_inventories(loaded)
    return build_init_response(loaded)


@router.post("/api/delete-save")
async def remove_save(body: DeleteSaveBody) -> dict[str, Any]:
    """删除角色存档（手动弃档）。"""
    from backend.session.store import room
    ok = delete_save(body.player_id)
    room.players.pop(body.player_id, None)
    return {"ok": ok}
