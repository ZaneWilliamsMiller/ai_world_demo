"""核心工具函数 + 向后兼容 re-export。

原 core.py 已拆分为：
- systems/core.py (本文件): 基础工具 + NPC定位
- systems/trap.py: 险局/脱困/生存/体力心气
- systems/npc_state.py: NPC状态管理+游走+天气感知
- systems/perception.py: 感知扫描+危险判定+休息+世界状态块
"""
from __future__ import annotations

from typing import Any

from backend.data.npcs_data import NPCS
from backend.models.player import PlayerState
from backend.systems.constants import (
    MAX_FAVOR,
    MAX_FAVOR_DELTA,
    MAX_RUMOR_LEN,
    MAX_RUMORS,
    MAX_STATE_DELTA,
)
from backend.systems.npc_state import (  # noqa: F401
    maybe_wander_npcs,
    npc_state_for_dialogue,
    npc_weather_awareness_block,
    update_all_npc_states_dynamic,
    update_npc_state_dynamic,
    update_npc_states_from_habits,
)
from backend.systems.perception import (  # noqa: F401
    can_rest_at,
    danger_sense_narrative,
    hazard_roll_death,
    perception_scan,
    recent_events_block,
    relevant_events_for,
    rest_at_location,
    tile_forced_encounter,
    val_in_range,
    world_status_block,
)

# ── 从子模块 re-export（保持向后兼容；新代码请直接从子模块导入）──
from backend.systems.trap import (  # noqa: F401
    apply_spirit_delta,
    apply_vigor_delta,
    enter_trap_state,
    maybe_collapse_from_attrs,
    survival_action_delta,
    tile_hazard_reason,
    try_clear_move_lock,
    vigor_status_block,
)

# ─── 基础工具函数 ─────────────────────

def clamp_delta(d: dict[str, int]) -> dict[str, int]:
    keys = ("order", "truth", "hope", "chaos")
    out: dict[str, int] = {}
    for k in keys:
        v = int(d.get(k, 0))
        v = min(v, MAX_STATE_DELTA)
        v = max(v, -MAX_STATE_DELTA)
        out[k] = v
    return out

def clamp_favor_delta(d: int) -> int:
    if d > MAX_FAVOR_DELTA:
        return MAX_FAVOR_DELTA
    if d < -MAX_FAVOR_DELTA:
        return -MAX_FAVOR_DELTA
    return d

def apply_favor(p: PlayerState, npc_id: str, delta: int | None) -> None:
    if delta is None:
        return
    d = clamp_favor_delta(delta)
    cur = int(p.favor.get(npc_id, 0))
    nxt = cur + d
    nxt = min(nxt, MAX_FAVOR)
    nxt = max(nxt, -MAX_FAVOR)
    p.favor[npc_id] = nxt

def push_rumor(p: PlayerState, snippet: str) -> None:
    s = snippet.strip().replace("\n", " ")
    if len(s) > MAX_RUMOR_LEN:
        s = s[:MAX_RUMOR_LEN] + "..."
    if not s:
        return
    p.rumors.append(s)
    if len(p.rumors) > MAX_RUMORS:
        p.rumors = p.rumors[-MAX_RUMORS:]

def npc_ids_for_player(p: PlayerState) -> list[str]:
    out: list[str] = []
    for nid, meta in NPCS.items():
        if meta.get("always"):
            out.append(nid)
            continue
        cell = p.npc_positions.get(nid) if getattr(p, "npc_positions", None) else meta.get("cell")
        if cell and cell[0] == p.map_id:
            # 检查NPC是否在同一格子或相邻格子
            dx = abs(cell[1] - p.px)
            dy = abs(cell[2] - p.py)
            if (dx == 0 and dy == 0) or (dx <= 1 and dy <= 1):
                out.append(nid)
    hidden_here = [x for x in out if NPCS.get(x, {}).get("hidden")]
    normal_here = [x for x in out if not NPCS.get(x, {}).get("hidden")]
    merged: list[str] = []
    if "jiang" in normal_here:
        merged.append("jiang")
        normal_here = [x for x in normal_here if x != "jiang"]
    merged.extend(hidden_here)
    merged.extend(normal_here)
    if getattr(p, "move_locked", False):
        lid = getattr(p, "move_lock_npc_id", None)
        if lid and str(lid) in NPCS:
            return [str(lid)]
    return merged

def move_should_fire_encounter(path: list[tuple[int, int]]) -> bool:
    return len(path) >= 2

def init_npc_positions(p: PlayerState) -> None:
    if getattr(p, "npc_positions", None):
        return
    p.npc_positions = {}
    for nid, meta in NPCS.items():
        cell = meta.get("cell")
        if cell:
            p.npc_positions[nid] = (str(cell[0]), int(cell[1]), int(cell[2]))

def npc_catalog_for_player(p: PlayerState) -> list[dict[str, Any]]:
    init_npc_positions(p)
    out: list[dict[str, Any]] = []
    for nid, meta in NPCS.items():
        if meta.get("hidden"):
            continue
        cell = p.npc_positions.get(nid) or meta.get("cell")
        if not cell:
            continue
        out.append({"id": nid, "name": meta["name"], "map": cell[0], "x": cell[1], "y": cell[2]})
    return out
