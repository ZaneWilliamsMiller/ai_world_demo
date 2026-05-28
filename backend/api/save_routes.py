"""存档 API 路由：save, load, delete_save, saves_list。"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.data.maps_data import MAP_AMBUSH_MARKERS
from backend.data.npcs_data import NPCS
from backend.data.prompts import WORLD_NAME, FIXED_INTRO
from backend.models.player import PlayerState
from backend.systems.core import init_npc_positions, perception_scan, danger_sense_narrative
from backend.systems.economy import init_npc_inventories
from backend.systems.save_system import save_game, load_game, list_saves, delete_save
from backend.views import player_public as _player_public, npcs_here as _npcs_here
from backend.views import npc_catalog as _npc_catalog, maps_public as _maps_public, factions_public as _factions_public
from backend.views import map_locations_public as _map_locations_public

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
    """加载已有角色（覆盖内存中的当前玩家）。"""
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
    scan = perception_scan(loaded)
    danger_sense = danger_sense_narrative(loaded, scan) if scan else None
    return {
        "player_id": loaded.player_id,
        "display_name": loaded.display_name,
        "world_name": WORLD_NAME,
        "intro": FIXED_INTRO,
        "maps": _maps_public(),
        "npc_catalog": _npc_catalog(loaded),
        "player": _player_public(loaded),
        "npcs_here": _npcs_here(loaded),
        "danger_sense": {
            "alert": danger_sense or None,
            "scan": scan,
        },
        "flags": loaded.flags,
        "ended": loaded.ended,
        "ending_label": loaded.ending_label,
        "favor": dict(loaded.favor),
        "rumors": list(loaded.rumors),
        "npc_labels": {nid: v["name"] for nid, v in NPCS.items()},
        "ambush_markers": list(MAP_AMBUSH_MARKERS),
        "factions": _factions_public(),
        "map_locations": _map_locations_public(),
        "events": list(loaded.events[-10:]),
    }


@router.post("/api/delete-save")
async def remove_save(body: DeleteSaveBody) -> dict[str, Any]:
    """删除角色存档（手动弃档）。"""
    from backend.session.store import room
    ok = delete_save(body.player_id)
    room.players.pop(body.player_id, None)
    return {"ok": ok}
