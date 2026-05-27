"""共享视图工具函数——供 routes.py 和 talk_service.py 共同使用。

将 _player_public / _npcs_here / _npc_catalog 提取至此，
避免 routes.py ↔ talk_service.py 的循环导入。
"""
from __future__ import annotations

from typing import Any

from backend.data.maps_data import MAPS, MAP_LOCATIONS
from backend.data.npcs_data import NPCS
from backend.data.factions import FACTIONS
from backend.models.player import PlayerState
from backend.systems.core import npc_ids_for_player, npc_catalog_for_player
from backend.systems.time_weather import shichen_name, is_night, shichen_phase


def player_public(p: PlayerState) -> dict[str, Any]:
    """将 PlayerState 序列化为前端可用的公开字典。"""
    return {
        "map_id": p.map_id,
        "px": p.px,
        "py": p.py,
        "coins": p.coins,
        "gender": p.gender,
        "permadeath": p.permadeath,
        "dead": p.dead,
        "death_reason": p.death_reason,
        "move_locked": bool(getattr(p, "move_locked", False)),
        "move_lock_npc_id": getattr(p, "move_lock_npc_id", None),
        "trap_reason": getattr(p, "trap_reason", None),
        "trap_attempts": int(getattr(p, "trap_attempts", 0) or 0),
        "enslaved": bool(getattr(p, "enslaved", False)),
        "enslaved_reason": getattr(p, "enslaved_reason", None),
        "vigor": int(getattr(p, "vigor", 80) or 0),
        "vigor_max": int(getattr(p, "vigor_max", 100) or 100),
        "spirit": int(getattr(p, "spirit", 80) or 0),
        "spirit_max": int(getattr(p, "spirit_max", 100) or 100),
        "sleep_debt": int(getattr(p, "sleep_debt", 0) or 0),
        "unconscious_ticks": int(getattr(p, "unconscious_ticks", 0) or 0),
        "rescue_needed": bool(getattr(p, "rescue_needed", False)),
        "life_burn_ticks": int(getattr(p, "life_burn_ticks", 0) or 0),
        "life_burn_max": int(getattr(p, "life_burn_max", 0) or 0),
        "world_day": int(p.world_day),
        "world_shichen_idx": int(p.world_shichen),
        "world_shichen": shichen_name(p.world_shichen),
        "world_phase": shichen_phase(p.world_shichen),
        "world_is_night": is_night(p.world_shichen),
        "weather": p.weather,
        "inventory": dict(p.inventory),
        "reputation": dict(p.reputation),
        "npc_states": dict(getattr(p, "npc_states", {}) or {}),
        "bounties": getattr(p, "bounties", None) or [],
        "active_bounty": getattr(p, "active_bounty", None),
        "completed_bounties": getattr(p, "completed_bounties", None) or [],
    }


def npcs_here(p: PlayerState) -> list[dict[str, str]]:
    """返回当前格子上的 NPC 列表。"""
    return [{"id": i, "name": NPCS[i]["name"]} for i in npc_ids_for_player(p)]


def npc_catalog(p: PlayerState) -> list[dict[str, Any]]:
    """返回 NPC 目录。"""
    return npc_catalog_for_player(p)


def maps_public() -> dict[str, Any]:
    """返回公开地图信息。"""
    out: dict[str, Any] = {}
    for mid, m in MAPS.items():
        out[mid] = {"name": m["name"], "rows": m["rows"], "portals": m.get("portals", [])}
    return out


def map_locations_public() -> dict[str, dict[str, list[int]]]:
    """返回地点坐标映射，供前端渲染标签。"""
    out: dict[str, dict[str, list[int]]] = {}
    for mid, locs in MAP_LOCATIONS.items():
        out[mid] = {name: list(pos) for name, pos in locs.items()}
    return out


def factions_public() -> dict[str, str]:
    """返回公开势力信息。"""
    return dict(FACTIONS)
