"""共享视图工具函数——供 routes.py 和 talk_service.py 共同使用。

将 _player_public / _npcs_here / _npc_catalog 提取至此，
避免 routes.py ↔ talk_service.py 的循环导入。
"""
from __future__ import annotations

from typing import Any

from backend.data.factions import FACTIONS
from backend.data.maps_data import MAP_AMBUSH_MARKERS, MAP_LOCATIONS, MAPS
from backend.data.npcs_data import NPCS
from backend.data.prompts import FIXED_INTRO, WORLD_NAME
from backend.models.player import PlayerState
from backend.systems.core import danger_sense_narrative, npc_catalog_for_player, npc_ids_for_player, perception_scan
from backend.systems.time_weather import is_night, shichen_name, shichen_phase

_maps_cache: dict | None = None
_factions_cache: dict | None = None
_map_locations_cache: dict | None = None
_npc_labels_cache: dict | None = None
_ambush_markers_cache: list | None = None


def _strip_private(d: Any) -> Any:
    if isinstance(d, dict):
        return {k: _strip_private(v) for k, v in d.items() if not k.startswith("_")}
    if isinstance(d, list):
        return [_strip_private(i) for i in d]
    return d


def player_public(p: PlayerState) -> dict[str, Any]:
    return {
        "map_id": p.map_id,
        "px": p.px,
        "py": p.py,
        "coins": p.coins,
        "gender": p.gender,
        "permadeath": p.permadeath,
        "dead": p.dead,
        "death_reason": p.death_reason,
        "ended": bool(getattr(p, "ended", False)),
        "ending_label": getattr(p, "ending_label", None),
        "move_locked": bool(getattr(p, "move_locked", False)),
        "move_lock_npc_id": getattr(p, "move_lock_npc_id", None),
        "trap_reason": getattr(p, "trap_reason", None),
        "trap_attempts": int(getattr(p, "trap_attempts", 0) or 0),
        "trap_type": getattr(p, "trap_type", None),
        "enslaved": bool(getattr(p, "enslaved", False)),
        "enslaved_reason": getattr(p, "enslaved_reason", None),
        "vigor": max(0, int(getattr(p, "vigor", 0) or 0)),
        "vigor_max": max(1, int(getattr(p, "vigor_max", 100) or 100)),
        "spirit": max(0, int(getattr(p, "spirit", 0) or 0)),
        "spirit_max": max(1, int(getattr(p, "spirit_max", 100) or 100)),
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
        "bounties": _strip_private(getattr(p, "bounties", None) or []),
        "active_bounty": _strip_private(getattr(p, "active_bounty", None)),
        "completed_bounties": getattr(p, "completed_bounties", None) or [],
        "flags": dict(getattr(p, "flags", {}) or {}),
        "favor": dict(getattr(p, "favor", {}) or {}),
    }


def npcs_here(p: PlayerState) -> list[dict[str, str]]:
    result = []
    for i in npc_ids_for_player(p):
        meta = NPCS.get(i, {})
        name = meta.get("name", i)
        result.append({"id": i, "name": name})
    return result


def npc_catalog(p: PlayerState) -> list[dict[str, Any]]:
    return npc_catalog_for_player(p)


def maps_public() -> dict[str, Any]:
    global _maps_cache
    if _maps_cache is not None:
        return _maps_cache
    out: dict[str, Any] = {}
    for mid, m in MAPS.items():
        out[mid] = {"name": m.get("name", mid), "rows": m.get("rows", []), "portals": m.get("portals", [])}
    _maps_cache = out
    return _maps_cache


def map_locations_public() -> dict[str, dict[str, list[int]]]:
    global _map_locations_cache
    if _map_locations_cache is not None:
        return _map_locations_cache
    out: dict[str, dict[str, list[int]]] = {}
    for mid, locs in MAP_LOCATIONS.items():
        out[mid] = {name: list(pos) for name, pos in locs.items()}
    _map_locations_cache = out
    return _map_locations_cache


def factions_public() -> dict[str, str]:
    global _factions_cache
    if _factions_cache is not None:
        return _factions_cache
    _factions_cache = dict(FACTIONS)
    return _factions_cache


def npc_labels_public() -> dict[str, str]:
    global _npc_labels_cache
    if _npc_labels_cache is not None:
        return _npc_labels_cache
    _npc_labels_cache = {nid: v.get("name", nid) for nid, v in NPCS.items()}
    return _npc_labels_cache


def ambush_markers_public() -> list:
    global _ambush_markers_cache
    if _ambush_markers_cache is not None:
        return _ambush_markers_cache
    _ambush_markers_cache = list(MAP_AMBUSH_MARKERS)
    return _ambush_markers_cache


def build_init_response(p: PlayerState) -> dict[str, Any]:
    scan = perception_scan(p)
    danger_sense = danger_sense_narrative(p, scan) if scan else None
    return {
        "player_id": p.player_id,
        "display_name": p.display_name,
        "world_name": WORLD_NAME,
        "intro": FIXED_INTRO,
        "maps": maps_public(),
        "npc_catalog": npc_catalog(p),
        "player": player_public(p),
        "npcs_here": npcs_here(p),
        "danger_sense": {
            "alert": danger_sense or None,
            "scan": scan,
        },
        "flags": p.flags,
        "ended": p.ended,
        "ending_label": p.ending_label,
        "favor": dict(p.favor),
        "rumors": list(p.rumors),
        "npc_labels": npc_labels_public(),
        "ambush_markers": ambush_markers_public(),
        "factions": factions_public(),
        "map_locations": map_locations_public(),
        "events": list(p.events[-10:]),
    }
