"""玩家交互 API 路由：hello, move, state, journal。"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, Field

from backend.data.maps_data import MAPS, MAP_AMBUSH_MARKERS
from backend.data.npcs_data import NPCS, STORY_ORDER
from backend.data.factions import FACTIONS
from backend.data.prompts import WORLD_NAME, FIXED_INTRO, SOCIETY_BIBLE
from backend.models.player import PlayerState
from backend.systems.pathfinding import find_path, tile_at, tile_elevation, tile_cost, check_danger_and_injure, is_dangerous
from backend.systems.time_weather import shichen_name, shichen_phase, is_night, advance_clock
from backend.data.atmosphere import scene_context
from backend.systems.economy import init_npc_inventories
from backend.systems.core import (
    npc_ids_for_player,
    move_should_fire_encounter,
    tile_forced_encounter,
    enter_trap_state,
    tile_hazard_reason,
    apply_vigor_delta,
    apply_spirit_delta,
    maybe_collapse_from_attrs,
    init_npc_positions,
    npc_catalog_for_player,
    maybe_wander_npcs,
    perception_scan,
    danger_sense_narrative,
    world_status_block,
)
from backend.systems.reputation import push_event
from backend.systems.save_system import save_game, respawn_at_supply_point
from backend.services.agent_service import bg_plan_for_npcs
from backend.views import player_public as _player_public, npcs_here as _npcs_here
from backend.views import npc_catalog as _npc_catalog, maps_public as _maps_public, factions_public as _factions_public
from backend.views import map_locations_public as _map_locations_public

router = APIRouter()


class HelloBody(BaseModel):
    player_id: str | None = None
    display_name: str | None = None
    gender: str = Field(default="未言", pattern="^(男|女|未言)$")
    permadeath: bool = False

class MoveBody(BaseModel):
    player_id: str
    to_x: int = Field(..., ge=0, le=256)
    to_y: int = Field(..., ge=0, le=256)


@router.post("/api/hello")
async def hello(body: HelloBody) -> dict[str, Any]:
    from backend.session.store import room
    from backend.systems.encounter import should_trigger_encounter
    p = room.get_or_create(body.player_id, body.display_name, body.gender, body.permadeath)
    init_npc_positions(p)
    init_npc_inventories(p)
    scan = perception_scan(p)
    danger_sense = danger_sense_narrative(p, scan) if scan else None
    return {
        "player_id": p.player_id,
        "display_name": p.display_name,
        "world_name": WORLD_NAME,
        "intro": FIXED_INTRO,
        "maps": _maps_public(),
        "npc_catalog": _npc_catalog(p),
        "player": _player_public(p),
        "npcs_here": _npcs_here(p),
        "danger_sense": {
            "alert": danger_sense or None,
            "scan": scan,
        },
        "flags": p.flags,
        "ended": p.ended,
        "ending_label": p.ending_label,
        "favor": dict(p.favor),
        "rumors": list(p.rumors),
        "npc_labels": {nid: v["name"] for nid, v in NPCS.items()},
        "ambush_markers": list(MAP_AMBUSH_MARKERS),
        "factions": _factions_public(),
        "map_locations": _map_locations_public(),
        "events": list(p.events[-10:]),
    }


@router.post("/api/move")
async def move(body: MoveBody, bg: BackgroundTasks) -> dict[str, Any]:
    from backend.session.store import room
    from backend.systems.core import update_npc_states_from_habits, update_all_npc_states_dynamic
    from backend.systems.npc_gossip import maybe_npc_gossip
    from backend.systems.encounter import should_trigger_encounter, generate_dynamic_encounter, apply_encounter

    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    if p.ended:
        raise HTTPException(400, "本局已收束")
    if p.dead:
        raise HTTPException(400, "角色已身故")
    if int(getattr(p, "unconscious_ticks", 0) or 0) > 0:
        raise HTTPException(409, "你正昏迷未醒,无法行动。")
    if getattr(p, "enslaved", False):
        raise HTTPException(400, "你已沦为囚役,难以再自行迁徙。")
    if getattr(p, "move_locked", False):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "身陷险局,须先与眼前对头周旋几句,再图挪步。",
        )

    allow_steep = bool(getattr(p, "allow_steep_next_move", False))
    from backend.systems.pathfinding import find_path as _find_path
    path = _find_path(p.map_id, p.px, p.py, body.to_x, body.to_y, allow_steep=allow_steep)
    if not path:
        raise HTTPException(400, "此处无路可达")

    from backend.systems.pathfinding import path_cost, cost_to_ticks, apply_portal
    async with p.lock:
        prev_map = p.map_id
        prev_day = int(p.world_day)
        vigor_cost_applied = 0
        spirit_cost_applied = 0
        actual_path: list[tuple[int, int]] = [path[0]]
        injuries: list[str] = []
        move_trace: list[dict[str, Any]] = [
            {
                "map_id": p.map_id,
                "px": p.px,
                "py": p.py,
                "vigor": int(getattr(p, "vigor", 0)),
                "spirit": int(getattr(p, "spirit", 0)),
            }
        ]
        forced = None
        for nx, ny in path[1:]:
            cx, cy = p.px, p.py
            ch_from = tile_at(p.map_id, cx, cy) or "."
            ch_to = tile_at(p.map_id, nx, ny) or "."
            dh = abs(tile_elevation(ch_to) - tile_elevation(ch_from))
            if dh > 2 and not allow_steep and ch_to != "!":
                pass
            p.px, p.py = nx, ny
            actual_path.append((nx, ny))
            if allow_steep and dh > 2:
                vigor_cost_applied += apply_vigor_delta(p, -12)
                spirit_cost_applied += apply_spirit_delta(p, -6)
            step_cost = max(1, tile_cost(ch_to))
            vigor_cost_applied += apply_vigor_delta(p, -max(1, step_cost // 2))
            if is_night(p.world_shichen):
                spirit_cost_applied += apply_spirit_delta(p, -1)

            if not p.dead and is_dangerous(ch_to):
                hurt, reason = check_danger_and_injure(ch_to)
                if hurt and reason:
                    vigor_cost_applied += apply_vigor_delta(p, -10)
                    spirit_cost_applied += apply_spirit_delta(p, -4)
                    injuries.append(reason)
                    if ch_to == "!" or ch_to == "~":
                        forced = {
                            "npc_id": "jiang",
                            "user_line": (
                                "<user_input>[际遇·系统指令] "
                                f"过路客一脚踏入险地:{reason} "
                                "请以「风闻子」第三方旁观的口吻描出此刻危境,"
                                "并暗示玩家可如何挣脱(硬闯、后退、求援、投石问路皆可)。"
                                "中文 4~8 句。</user_input>"
                            ),
                            "blurb": reason,
                        }
                        break

            move_trace.append({
                "map_id": p.map_id,
                "px": p.px,
                "py": p.py,
                "vigor": int(getattr(p, "vigor", 0)),
                "spirit": int(getattr(p, "spirit", 0)),
            })

            if not p.dead:
                forced = tile_forced_encounter(p)
                if forced:
                    enter_trap_state(
                        p,
                        reason=str(forced.get("blurb") or "骤入险局"),
                        lock_npc_id=str(forced["npc_id"]),
                    )
                    break
                hazard_reason = tile_hazard_reason(p)
                if hazard_reason:
                    enter_trap_state(p, reason=hazard_reason, lock_npc_id="jiang")
                    forced = {
                        "npc_id": "jiang",
                        "user_line": (
                            "<user_input>[际遇·系统指令] "
                            f"过路客骤入此局:{hazard_reason} "
                            "请以「风闻子」第三方旁观的口吻描出此刻光景,"
                            "并暗示玩家可如何挣脱(贿赂、求援、跳水、硬冲、谈判皆可)。"
                            "中文 6~10 句。</user_input>"
                        ),
                        "blurb": hazard_reason,
                    }
                    break

        cost = path_cost(prev_map, actual_path)
        ticks = cost_to_ticks(cost)
        if ticks > 0:
            advance_clock(p, ticks)
            maybe_wander_npcs(p, ticks=ticks)
            update_npc_states_from_habits(p)
            update_all_npc_states_dynamic(p)
            maybe_npc_gossip(p, ticks=ticks)
        respawn_msg: str | None = None
        from backend.systems.perception import hazard_roll_death
        if p.permadeath:
            reason = hazard_roll_death(p)
            if reason:
                p.dead = True
                p.death_reason = reason
                p.move_locked = False
                p.move_lock_npc_id = None
                push_event(p, f"{p.display_name}于{MAPS[p.map_id]['name']}遭难:{reason[:24]}", scope="near", actor="天意")
                save_game(p)
                delete_save(p.player_id)
        if not p.dead and not p.ended:
            collapsed = maybe_collapse_from_attrs(p)
            if collapsed and not p.permadeath:
                respawn_msg = respawn_at_supply_point(p)
        try:
            save_game(p)
        except Exception:
            pass
        p.last_move_map_id = p.map_id
        p.last_move_px = p.px
        p.last_move_py = p.py
        if allow_steep:
            p.allow_steep_next_move = False
        new_day = int(p.world_day)
        npc_ids_for_plan: list[str] = []
        if new_day != prev_day:
            for nid, meta in NPCS.items():
                if meta.get("hidden"):
                    continue
                cell = meta.get("cell")
                if cell and cell[0] == p.map_id:
                    npc_ids_for_plan.append(nid)

    if npc_ids_for_plan:
        bg.add_task(bg_plan_for_npcs, p.player_id, npc_ids_for_plan, new_day)

    if not p.dead and not p.ended and not getattr(p, "move_locked", False):
        if should_trigger_encounter(p):
            bg.add_task(_bg_encounter, p.player_id)

    scan = perception_scan(p)
    danger_sense = danger_sense_narrative(p, scan) if scan else None

    return {
        "player": _player_public(p),
        "npcs_here": _npcs_here(p),
        "danger_sense": {
            "alert": danger_sense or None,
            "scan": scan,
        },
        "path_map_id": prev_map,
        "path": actual_path,
        "path_cost": cost,
        "path_ticks": ticks,
        "path_algorithm": "dijkstra_min_cost",
        "forced_encounter": forced,
        "trap_state": {
            "active": bool(getattr(p, "move_locked", False)),
            "reason": getattr(p, "trap_reason", None),
            "attempts": int(getattr(p, "trap_attempts", 0) or 0),
        },
        "delta": {
            "vigor": vigor_cost_applied,
            "spirit": spirit_cost_applied,
        },
        "move_trace": move_trace,
        "injuries": injuries,
        "atmosphere": scene_context(p),
        "events": list(p.events[-10:]),
        "npc_catalog": _npc_catalog(p),
        "map_locations": _map_locations_public(),
        "respawn_msg": respawn_msg,
    }


async def _bg_encounter(player_id: str) -> None:
    try:
        from backend.session.store import room
        from backend.systems.encounter import generate_dynamic_encounter, apply_encounter
        p = room.players.get(player_id)
        if not p or p.dead or p.ended:
            return
        enc = await generate_dynamic_encounter(p)
        if enc:
            apply_encounter(p, enc)
    except Exception as e:
        import logging
        logging.getLogger("routes").warning("_bg_encounter failed for player=%s: %s", player_id, e)


@router.get("/api/state/{player_id}")
async def get_state(player_id: str) -> dict[str, Any]:
    from backend.session.store import room
    p = room.players.get(player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    scan = perception_scan(p)
    danger_sense = danger_sense_narrative(p, scan) if scan else None

    return {
        "display_name": p.display_name,
        "player": _player_public(p),
        "npcs_here": _npcs_here(p),
        "danger_sense": {
            "alert": danger_sense or None,
            "scan": scan,
        },
        "flags": p.flags,
        "ended": p.ended,
        "ending_label": p.ending_label,
        "favor": dict(p.favor),
        "rumors": list(p.rumors),
        "atmosphere": scene_context(p),
        "events": list(p.events[-10:]),
        "factions": _factions_public(),
        "npc_catalog": _npc_catalog(p),
    }


@router.get("/api/journal/{player_id}")
async def journal(player_id: str) -> dict[str, Any]:
    from backend.session.store import room
    p = room.players.get(player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    out: list[dict[str, Any]] = []
    for nid in STORY_ORDER:
        hist = p.history.get(nid) or []
        if not hist:
            continue
        out.append({
            "npc_id": nid,
            "npc_name": NPCS[nid]["name"],
            "turns": list(hist),
        })
    return {
        "history": out,
        "events": list(p.events),
        "rumors": list(p.rumors),
    }
