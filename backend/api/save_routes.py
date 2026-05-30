"""存档 API 路由：save, load, delete_save, saves_list"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.api.schema import SavesListResponse, SaveResponse, InitResponse, DeleteSaveResponse
from backend.api.views import build_init_response
from backend.systems.core import init_npc_positions
from backend.systems.economy import init_npc_inventories
from backend.systems.save_system import delete_save, list_saves, load_game, save_game

router = APIRouter()

_PID = Field(..., min_length=1, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')

class SaveBody(BaseModel):
    player_id: str = _PID

class LoadBody(BaseModel):
    player_id: str = _PID
    display_name: str | None = Field(None, min_length=1, max_length=24)
    gender: str = Field(default="未言", pattern="^(男|女|未言)$")
    permadeath: bool = False

class DeleteSaveBody(BaseModel):
    player_id: str = _PID


@router.get("/api/saves", response_model=SavesListResponse)
async def saves_list():
    return {"saves": list_saves()}


@router.post("/api/save", response_model=SaveResponse)
async def save_player(body: SaveBody):
    from backend.session.store import room
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    async with p.lock:
        await asyncio.to_thread(save_game, p)
    return {"ok": True}


@router.post("/api/load", response_model=InitResponse)
async def load_player(body: LoadBody):
    from backend.session.store import room
    loaded = await asyncio.to_thread(load_game, body.player_id)
    if not loaded:
        raise HTTPException(404, f"存档不存在: {body.player_id}")
    if loaded.dead and loaded.permadeath:
        raise HTTPException(400, "此角色已在真实江湖中身故，存档已封")
    if loaded.ended:
        raise HTTPException(400, "此角色的故事已收束，不可再入")
    async with loaded.lock:
        for attr in ("bounties", "completed_bounties", "rumors", "events"):
            val = getattr(loaded, attr, None)
            if val is None:
                setattr(loaded, attr, [])
        for attr in ("favor", "inventory", "minds", "npc_positions", "npc_inventories", "npc_inventory_restock_day", "npc_states", "item_use_tracker"):
            val = getattr(loaded, attr, None)
            if val is None:
                setattr(loaded, attr, {})
        init_npc_positions(loaded)
        init_npc_inventories(loaded)
    await room.set_player(body.player_id, loaded)
    return build_init_response(loaded)


@router.post("/api/delete-save", response_model=DeleteSaveResponse)
async def remove_save(body: DeleteSaveBody):
    from backend.session.store import room
    ok = await asyncio.to_thread(delete_save, body.player_id)
    await room.remove_player(body.player_id)
    return {"ok": ok}
