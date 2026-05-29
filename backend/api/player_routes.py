"""玩家交互 API 路由：hello, move, state, journal等"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Path, status
from pydantic import BaseModel, Field

from backend.data.maps_data import MAPS
from backend.data.npcs_data import NPCS, STORY_ORDER
from backend.systems.core import (
    tile_forced_encounter,
    enter_trap_state,
    tile_hazard_reason,
    apply_vigor_delta,
    apply_spirit_delta,
    maybe_collapse_from_attrs,
    init_npc_positions,
    maybe_wander_npcs,
    update_npc_states_from_habits,
    update_all_npc_states_dynamic,
    perception_scan,
    danger_sense_narrative,
)
from backend.systems.reputation import push_event
from backend.systems.save_system import save_game, respawn_at_supply_point, delete_save
from backend.systems.npc_gossip import maybe_npc_gossip
from backend.systems.pathfinding import find_path, tile_at, tile_elevation, tile_cost, check_danger_and_injure, is_dangerous, path_cost, cost_to_ticks
from backend.systems.perception import hazard_roll_death
from backend.systems.constants import STEEP_VIGOR_DAMAGE, STEEP_SPIRIT_DAMAGE, DANGER_VIGOR_DAMAGE, DANGER_SPIRIT_DAMAGE
from backend.systems.encounter import should_trigger_encounter, generate_dynamic_encounter, apply_encounter
from backend.systems.time_weather import shichen_name, is_night, advance_clock
from backend.data.atmosphere import scene_context
from backend.systems.economy import init_npc_inventories
from backend.services.agent_service import bg_plan_for_npcs
from backend.views import player_public as _player_public, npcs_here as _npcs_here
from backend.views import npc_catalog as _npc_catalog, maps_public as _maps_public, factions_public as _factions_public
from backend.views import map_locations_public as _map_locations_public, build_init_response

router = APIRouter()


class HelloBody(BaseModel):
    player_id: str | None = Field(None, min_length=1, max_length=64)
    display_name: str | None = Field(None, min_length=1, max_length=24)
    gender: str = Field(default="未言", pattern="^(男|女|未言)$")
    permadeath: bool = False

class MoveBody(BaseModel):
    player_id: str = Field(..., min_length=1, max_length=64)
    to_x: int = Field(..., ge=0, le=149)
    to_y: int = Field(..., ge=0, le=99)


@router.post("/api/hello")
async def hello(body: HelloBody) -> dict[str, Any]:
    from backend.session.store import room
    p = await room.get_or_create(body.player_id, body.display_name, body.gender, body.permadeath)
    init_npc_positions(p)
    init_npc_inventories(p)
    return build_init_response(p)


def _validate_move_preconditions(p, body) -> None:
    if not p:
        raise HTTPException(404, "未知 player_id")
    if p.ended:
        raise HTTPException(400, "本局已收束")
    if p.dead:
        raise HTTPException(400, "角色已身亡")
    if int(getattr(p, "unconscious_ticks", 0) or 0) > 0:
        unconscious_remaining = getattr(p, "unconscious_ticks", 0)
        raise HTTPException(
            409,
            f"⚠️ 你正处于昏迷状态，无法移动。\n"
            f"   剩余恢复时间: 约{unconscious_remaining}个时辰\n"
            f"   💡 建议: 在原地等待，或寻找医馆救治",
        )
    if getattr(p, "enslaved", False):
        raise HTTPException(400, "你已沦为囚役,难以再自行迁徙")
    if getattr(p, "move_locked", False):
        lock_reason = getattr(p, "trap_reason", "未知险情")
        lock_npc_id = getattr(p, "move_lock_npc_id", None)
        lock_npc_name = NPCS.get(lock_npc_id, {}).get("name", "眼前之人") if lock_npc_id else "对手"
        attempts = int(getattr(p, "trap_attempts", 0) or 0)
        hint = ""
        if attempts == 0:
            hint = "💡 先试着和对方交谈，了解对方意图"
        elif attempts < 3:
            hint = f"💡 已尝试{attempts}次，继续对话或考虑其他方式（贿赂/求援/硬闯）"
        else:
            hint = "💡 多次尝试未果？试试完全不同的策略，或者等待时机变化"
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"🚫 【移动被锁定】\n"
            f"   原因: {lock_reason}\n"
            f"   对手: {lock_npc_name}\n"
            f"   已尝试: {attempts}次\n"
            f"\n"
            f"   {hint}\n"
            f"   ⚔️ 解除方法: 与该NPC对话，选择合适的应对策略",
        )


def _walk_path(p, path, allow_steep):
    actual_path: list[tuple[int, int]] = [path[0]]
    vigor_cost = 0
    spirit_cost = 0
    injuries: list[str] = []
    forced = None
    for nx, ny in path[1:]:
        cx, cy = p.px, p.py
        ch_from = tile_at(p.map_id, cx, cy) or "."
        ch_to = tile_at(p.map_id, nx, ny) or "."
        dh = abs(tile_elevation(ch_to) - tile_elevation(ch_from))
        if dh > 2 and not allow_steep and ch_to != "!":
            break
        p.px, p.py = nx, ny
        actual_path.append((nx, ny))
        if allow_steep and dh > 2:
            vigor_cost += apply_vigor_delta(p, -STEEP_VIGOR_DAMAGE)
            spirit_cost += apply_spirit_delta(p, -STEEP_SPIRIT_DAMAGE)
        step_cost = max(1, tile_cost(ch_to))
        vigor_cost += apply_vigor_delta(p, -max(1, step_cost // 2))
        if is_night(p.world_shichen):
            spirit_cost += apply_spirit_delta(p, -1)

        if not p.dead and is_dangerous(ch_to):
            hurt, reason = check_danger_and_injure(ch_to)
            if hurt and reason:
                vigor_cost += apply_vigor_delta(p, -DANGER_VIGOR_DAMAGE)
                spirit_cost += apply_spirit_delta(p, -DANGER_SPIRIT_DAMAGE)
                injuries.append(reason)
                if ch_to == "!" or ch_to == "~":
                    forced = {
                        "npc_id": "jiang",
                        "user_line": (
                            "<user_input>[际遇·系统指令] "
                            f"过路客一脚踏入险地{reason} "
                            "请以「风闻子」第三方旁观的口吻描出此刻危境"
                            "并暗示玩家可如何挣脱(硬闯、后退、求援、投石问路皆可)"
                            "中文 4~8 句</user_input>"
                        ),
                        "blurb": reason,
                    }
                    break

        if not p.dead:
            forced = tile_forced_encounter(p)
            if forced:
                enter_trap_state(
                    p,
                    reason=str(forced.get("blurb") or "骤入险局"),
                    lock_npc_id=str(forced.get("npc_id", "jiang")),
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
                        "请以「风闻子」第三方旁观的口吻描出此刻光景"
                        "并暗示玩家可如何挣脱(贿赂、求援、跳水、硬冲、谈判皆可)"
                        "中文 6~10 句</user_input>"
                    ),
                    "blurb": hazard_reason,
                }
                break
    return actual_path, vigor_cost, spirit_cost, injuries, forced


async def _post_move_world_update(p, prev_map, actual_path, prev_day, bg):
    from backend.session.store import room

    cost = path_cost(prev_map, actual_path)
    ticks = cost_to_ticks(cost)
    if ticks > 0:
        advance_clock(p, ticks)
        maybe_wander_npcs(p, ticks=ticks)
        update_npc_states_from_habits(p)
        update_all_npc_states_dynamic(p)
        maybe_npc_gossip(p, ticks=ticks)
    respawn_msg: str | None = None
    if p.permadeath:
        reason = hazard_roll_death(p)
        if reason:
            p.dead = True
            p.death_reason = reason
            p.move_locked = False
            p.move_lock_npc_id = None
            push_event(p, f"{p.display_name}于{MAPS.get(p.map_id, {}).get('name', '未知之地')}遭难:{reason[:24]}", scope="near", actor="天意")
            await asyncio.to_thread(save_game, p)
            try:
                delete_save(p.player_id)
            except Exception as e:
                logging.getLogger('move').error('delete_save failed for %s: %s', p.player_id, e)
            await room.remove_player(p.player_id)
    if not p.dead and not p.ended:
        collapsed = maybe_collapse_from_attrs(p)
        if collapsed and not p.permadeath:
            respawn_msg = respawn_at_supply_point(p)
    try:
        await asyncio.to_thread(save_game, p)
    except Exception as e:
        logging.getLogger('move').error('save failed for %s: %s', p.player_id, e)
    p.last_move_map_id = p.map_id
    p.last_move_px = p.px
    p.last_move_py = p.py
    if bool(getattr(p, "allow_steep_next_move", False)):
        p.allow_steep_next_move = False
    new_day = int(p.world_day)
    npc_ids_for_plan: list[str] = []
    if new_day != prev_day:
        for nid, meta in NPCS.items():
            if meta.get("hidden"):
                continue
            cell = meta.get("cell")
            if cell and isinstance(cell, (list, tuple)) and len(cell) >= 1 and cell[0] == p.map_id:
                npc_ids_for_plan.append(nid)
    if npc_ids_for_plan:
        bg.add_task(bg_plan_for_npcs, p.player_id, npc_ids_for_plan, new_day)
    return respawn_msg, npc_ids_for_plan


def _build_move_response(p, prev_map, actual_path, forced, vigor_cost, spirit_cost, injuries, respawn_msg):
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
        "forced_encounter": forced,
        "trap_state": {
            "active": bool(getattr(p, "move_locked", False)),
            "reason": getattr(p, "trap_reason", None),
            "attempts": int(getattr(p, "trap_attempts", 0) or 0),
        },
        "delta": {
            "vigor": vigor_cost,
            "spirit": spirit_cost,
        },
        "injuries": injuries,
        "atmosphere": scene_context(p),
        "events": list(p.events[-10:]),
        "npc_catalog": _npc_catalog(p),
        "map_locations": _map_locations_public(),
        "respawn_msg": respawn_msg,
    }


@router.post("/api/move")
async def move(body: MoveBody, bg: BackgroundTasks) -> dict[str, Any]:
    from backend.session.store import room

    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")

    allow_steep = bool(getattr(p, "allow_steep_next_move", False))
    path = find_path(p.map_id, p.px, p.py, body.to_x, body.to_y, allow_steep=allow_steep)
    if not path:
        raise HTTPException(400, "此处无路可达")

    async with p.lock:
        _validate_move_preconditions(p, body)
        if (p.px, p.py) != (path[0][0], path[0][1]):
            path = find_path(p.map_id, p.px, p.py, body.to_x, body.to_y, allow_steep=allow_steep)
            if not path:
                raise HTTPException(400, "此处无路可达")
        prev_map = p.map_id
        prev_day = int(p.world_day)
        actual_path, vigor_cost, spirit_cost, injuries, forced = _walk_path(p, path, allow_steep)
        respawn_msg, _ = await _post_move_world_update(p, prev_map, actual_path, prev_day, bg)

    if not p.dead and not p.ended and not getattr(p, "move_locked", False):
        if should_trigger_encounter(p):
            bg.add_task(_bg_encounter, p.player_id)

    return _build_move_response(p, prev_map, actual_path, forced, vigor_cost, spirit_cost, injuries, respawn_msg)


async def _bg_encounter(player_id: str) -> None:
    try:
        from backend.session.store import room
        p = room.players.get(player_id)
        if not p or p.dead or p.ended:
            return
        enc = await generate_dynamic_encounter(p)
        if enc:
            async with p.lock:
                if not p.dead and not p.ended:
                    apply_encounter(p, enc)
    except Exception as e:
        import logging
        logging.getLogger("routes").warning("_bg_encounter failed for player=%s: %s", player_id, e)


@router.get("/api/state/{player_id}")
async def get_state(player_id: str = Path(..., min_length=1, max_length=64)) -> dict[str, Any]:
    from backend.session.store import room
    p = room.players.get(player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    async with p.lock:
        scan = perception_scan(p)
        danger_sense = danger_sense_narrative(p, scan) if scan else None
        result = {
            "display_name": p.display_name,
            "player": _player_public(p),
            "npcs_here": _npcs_here(p),
            "danger_sense": {
                "alert": danger_sense or None,
                "scan": scan,
            },
            "flags": dict(p.flags),
            "ended": p.ended,
            "ending_label": p.ending_label,
            "favor": dict(p.favor),
            "rumors": list(p.rumors),
            "atmosphere": scene_context(p),
            "events": list(p.events[-10:]),
            "factions": _factions_public(),
            "npc_catalog": _npc_catalog(p),
            "map_locations": _map_locations_public(),
        }
    return result


@router.get("/api/journal/{player_id}")
async def journal(player_id: str = Path(..., min_length=1, max_length=64)) -> dict[str, Any]:
    from backend.session.store import room
    p = room.players.get(player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    async with p.lock:
        out: list[dict[str, Any]] = []
        for nid in STORY_ORDER:
            hist = p.history.get(nid) or []
            if not hist:
                continue
            out.append({
                "npc_id": nid,
                "npc_name": NPCS.get(nid, {}).get("name", nid),
                "turns": list(hist),
            })
        result = {
            "history": out,
            "events": list(p.events),
            "rumors": list(p.rumors),
        }
    return result
