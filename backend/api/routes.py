from __future__ import annotations
import asyncio
import json
import time
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.data.maps_data import MAPS, MAP_AMBUSH_MARKERS
from backend.data.npcs_data import NPCS, STORY_ORDER
from backend.data.factions import FACTIONS
from backend.data.prompts import WORLD_NAME, FIXED_INTRO, SOCIETY_BIBLE
from backend.models.player import PlayerState
from backend.systems.pathfinding import find_path, apply_portal, path_cost, cost_to_ticks, tile_at, tile_elevation, tile_cost, check_danger_and_injure, is_dangerous
from backend.systems.time_weather import shichen_name, shichen_phase, is_night, advance_clock
from backend.data.atmosphere import scene_context
from backend.systems.economy import init_npc_inventories
from backend.systems.core import (
    npc_ids_for_player,
    move_should_fire_encounter,
    tile_forced_encounter,
    hazard_roll_death,
    tile_hazard_reason,
    enter_trap_state,
    apply_vigor_delta,
    apply_spirit_delta,
    maybe_collapse_from_attrs,
    init_npc_positions,
    npc_catalog_for_player,
    maybe_wander_npcs,
    perception_scan,
    danger_sense_narrative,
)
from backend.systems.encounter import should_trigger_encounter, generate_dynamic_encounter, apply_encounter
from backend.systems.reputation import push_event
from backend.session.store import room
from backend.game_state import get_or_init_mind
from backend.services.talk_service import build_npc_messages, apply_npc_reply, build_graceful_fallback
from backend.services.agent_service import bg_reflect, bg_plan_for_npcs
from backend import agent_brain
from backend.llm_client import chat_completion, parse_finale, parse_npc_reply_json
from backend.systems.save_system import (
    save_game, load_game, list_saves, delete_save, respawn_at_supply_point,
)

router = APIRouter()

def _player_public(p: PlayerState) -> dict[str, Any]:
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

def _maps_public() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for mid, m in MAPS.items():
        out[mid] = {"name": m["name"], "rows": m["rows"], "portals": m.get("portals", [])}
    return out

def _npc_catalog(p: PlayerState) -> list[dict[str, Any]]:
    return npc_catalog_for_player(p)

def _npcs_here(p: PlayerState) -> list[dict[str, str]]:
    return [{"id": i, "name": NPCS[i]["name"]} for i in npc_ids_for_player(p)]

def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

def _factions_public() -> dict[str, str]:
    return dict(FACTIONS)

def _story_digest(p: PlayerState) -> str:
    inv_line = "身无长物" if not p.inventory else "随身:" + "、".join(
        (f"{n}×{c}" if c > 1 else n) for n, c in sorted(p.inventory.items())
    )
    rep_line = " ".join(f"{FACTIONS[k]}{v:+d}" for k, v in p.reputation.items() if v != 0) or "声望未起"
    lines = [
        FIXED_INTRO,
        "",
        f"玩家性别:{p.gender};真实江湖(永久死亡):{'开' if p.permadeath else '关'}。",
        f"终局前最后位置:地图「{MAPS[p.map_id]['name']}」坐标 ({p.px},{p.py});约 {p.coins} 文。",
        f"江湖行迹至第 {p.world_day} 日 · {shichen_name(p.world_shichen)}(天气「{p.weather}」)。",
        f"{inv_line}。{rep_line}",
        "",
        SOCIETY_BIBLE,
        "",
        "-- 本局对话摘录(按角色)--",
        "",
    ]
    any_talk = False
    for nid in STORY_ORDER:
        hist = p.history.get(nid)
        if not hist:
            continue
        any_talk = True
        name = NPCS[nid]["name"]
        for turn in hist:
            u = turn["user"][:1400]
            a = turn["assistant"][:1400]
            stamp = ""
            if turn.get("day") and turn.get("shichen"):
                stamp = f"〔第{turn['day']}日·{turn['shichen']}〕 "
            lines.append(f"{stamp}【{name}】玩家:{u}")
            lines.append(f"{stamp}【{name}】:{a}")
            lines.append("")
    if p.events:
        lines.append("-- 本局世界事件(节选)--")
        for e in p.events[-12:]:
            lines.append(f"〔第{e.get('day','?')}日·{e.get('shichen','?')}〕 {e.get('text','')}")
        lines.append("")
    if not any_talk:
        lines.append("(尚未产生对话;请据社会总览与开场写收束。)")
    lines.append(
        f"-- 叙事参考数值(勿在正文复述数字)--\n"
        f"秩序 {p.flags['order']}  求真 {p.flags['truth']}  "
        f"希望 {p.flags['hope']}  混乱 {p.flags['chaos']}"
    )
    return "\n".join(lines)

class HelloBody(BaseModel):
    player_id: str | None = None
    display_name: str | None = None
    gender: str = Field(default="未言", pattern="^(男|女|未言)$")
    permadeath: bool = False

class MoveBody(BaseModel):
    player_id: str
    to_x: int = Field(..., ge=0, le=256)
    to_y: int = Field(..., ge=0, le=256)

class TalkBody(BaseModel):
    player_id: str
    npc_id: str = Field(..., min_length=1, max_length=32)
    message: str = Field(..., min_length=1, max_length=2000)

class FinaleBody(BaseModel):
    player_id: str
    closing_note: str | None = Field(None, max_length=600)

class AgentActBody(BaseModel):
    player_id: str
    npc_id: str = Field(..., min_length=1, max_length=32)

class SaveBody(BaseModel):
    player_id: str

class LoadBody(BaseModel):
    player_id: str
    display_name: str | None = None
    gender: str = Field(default="未言", pattern="^(男|女|未言)$")
    permadeath: bool = False

class DeleteSaveBody(BaseModel):
    player_id: str

@router.get("/api/health")
async def health() -> dict[str, str]:
    from backend.config import settings
    return {"status": "ok", "model": settings.llm_model, "world": WORLD_NAME}


# ═══════════════════════════════════════════════════════
#  存档 API
# ═══════════════════════════════════════════════════════

@router.get("/api/saves")
async def saves_list() -> dict[str, Any]:
    """列出全部存档角色。"""
    return {"saves": list_saves()}


@router.post("/api/save")
async def save_player(body: SaveBody) -> dict[str, Any]:
    """手动保存当前角色进度。"""
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    path = save_game(p)
    return {"ok": True, "path": path}


@router.post("/api/load")
async def load_player(body: LoadBody) -> dict[str, Any]:
    """加载已有角色（覆盖内存中的当前玩家）。"""
    loaded = load_game(body.player_id)
    if not loaded:
        raise HTTPException(404, f"存档不存在: {body.player_id}")
    # 如果已死亡的真实江湖角色，不允许再玩
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
        "events": list(loaded.events[-10:]),
    }


@router.post("/api/delete-save")
async def remove_save(body: DeleteSaveBody) -> dict[str, Any]:
    """删除角色存档（手动弃档）。"""
    ok = delete_save(body.player_id)
    room.players.pop(body.player_id, None)
    return {"ok": ok}


# ═══════════════════════════════════════════════════════
#  物品使用 API（🎮 游戏性）
# ═══════════════════════════════════════════════════════

class UseItemBody(BaseModel):
    player_id: str
    item: str = Field(..., min_length=1, max_length=20, description="物品名，如干粮/金创药/安神散")


@router.post("/api/item/use")
async def use_item(body: UseItemBody) -> dict[str, Any]:
    """消耗背包中的一个物品，应用身心效果。

    可消耗的物品：干粮/鲜鱼/野果/粗酒/熟牛肉/茶饼（食）、
    金创药/解毒丸/安神散（药）、火折（物）。

    文书、兵器、信物等不可直接消耗——需通过NPC交互使用。

    返回 "success": true/false + 叙事描述 + 效用变化。
    """
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, f"未知 player_id: {body.player_id}")
    if getattr(p, "dead", False):
        raise HTTPException(400, "角色已故，物无所用。")

    from backend.systems.economy import use_player_item

    result = use_player_item(p, body.item)

    # 若成功消耗，写入事件流供后续NPC对话引用
    if result.get("success"):
        from backend.systems.reputation import push_event
        item_name = str(result.get("item_consumed", body.item))
        note = str(result.get("note", ""))
        if note:
            push_event(p, f"{p.display_name}用掉了{note}", scope="self", actor=p.display_name)

    return {
        **result,
        "player": _player_public(p),
    }


# ═══════════════════════════════════════════════════════
#  自然休息 API（🎮 游戏性）
# ═══════════════════════════════════════════════════════

class RestBody(BaseModel):
    player_id: str


@router.post("/api/rest")
async def player_rest(body: RestBody) -> dict[str, Any]:
    """在补给点歇脚恢复体力/心气/睡眠债。

    可休息的地形：客栈(T)、驿站(Y)、市集(M)、兵站(B)、佛寺(@)。
    每次休息消耗 2 时辰；若属性已满则略坐一坐（仍过时辰但不回）。

    返回：ok、delta（变化量）、ticks_passed、note（叙事）。
    """
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, f"未知 player_id: {body.player_id}")
    if getattr(p, "dead", False):
        raise HTTPException(400, "魂已归西，无足歇矣。")
    if p.ended:
        raise HTTPException(400, "本局已收束")
    if int(getattr(p, "unconscious_ticks", 0) or 0) > 0:
        raise HTTPException(400, "昏迷之中，身不由己。")
    if getattr(p, "move_locked", False):
        raise HTTPException(409, "身陷险局，须先周旋脱身方可歇息。")

    from backend.systems.core import rest_at_location

    async with p.lock:
        result = rest_at_location(p)
        # 自动存档
        try:
            from backend.systems.save_system import save_game
            save_game(p)
        except Exception:
            pass

    scan = perception_scan(p)
    danger_sense = danger_sense_narrative(p, scan) if scan else None
    return {
        **result,
        "player": _player_public(p),
        "danger_sense": {
            "alert": danger_sense or None,
            "scan": scan,
        },
        "atmosphere": scene_context(p),
        "events": list(p.events[-5:]),
    }


@router.post("/api/hello")
async def hello(body: HelloBody) -> dict[str, Any]:
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
        "events": list(p.events[-10:]),
    }

@router.post("/api/move")
async def move(body: MoveBody, bg: BackgroundTasks) -> dict[str, Any]:
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
    path = find_path(p.map_id, p.px, p.py, body.to_x, body.to_y, allow_steep=allow_steep)
    if not path:
        raise HTTPException(400, "此处无路可达")

    async with p.lock:
        prev_map = p.map_id
        prev_day = int(p.world_day)
        vigor_cost_applied = 0
        spirit_cost_applied = 0
        actual_path: list[tuple[int, int]] = [path[0]]
        injuries: list[str] = []  # 记录路途受伤信息
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
        # 逐格移动:沿路结算,支持险地穿越(不弹错误,靠受伤概率)
        for nx, ny in path[1:]:
            cx, cy = p.px, p.py
            ch_from = tile_at(p.map_id, cx, cy) or "."
            ch_to = tile_at(p.map_id, nx, ny) or "."
            dh = abs(tile_elevation(ch_to) - tile_elevation(ch_from))
            # 裂隙 (!) 超高差视作不可越;其它地形放宽限制
            if dh > 2 and not allow_steep and ch_to != "!":
                pass  # 容许通行（非裂隙险地）
            p.px, p.py = nx, ny
            actual_path.append((nx, ny))
            if allow_steep and dh > 2:
                vigor_cost_applied += apply_vigor_delta(p, -12)
                spirit_cost_applied += apply_spirit_delta(p, -6)
            # 逐格扣体力/心气
            step_cost = max(1, tile_cost(ch_to))
            vigor_cost_applied += apply_vigor_delta(p, -max(1, step_cost // 2))
            if is_night(p.world_shichen):
                spirit_cost_applied += apply_spirit_delta(p, -1)

            # 险地受伤概率（不弹错误，只受伤/减属性）
            if not p.dead and is_dangerous(ch_to):
                hurt, reason = check_danger_and_injure(ch_to)
                if hurt and reason:
                    vigor_cost_applied += apply_vigor_delta(p, -10)
                    spirit_cost_applied += apply_spirit_delta(p, -4)
                    injuries.append(reason)
                    # 致命险地可能触发锁定际遇
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

            # 路途遭遇:一旦触发立即停下
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

            # 大地图无界门,连续前行
        cost = path_cost(prev_map, actual_path)
        ticks = cost_to_ticks(cost)
        if ticks > 0:
            advance_clock(p, ticks)
            maybe_wander_npcs(p, ticks=ticks)
            # CMA式NPC状态感知:基于时辰与习惯自动更新NPC状态
            from backend.systems.core import update_npc_states_from_habits, update_all_npc_states_dynamic
            update_npc_states_from_habits(p)
            # 叠加上下文状态:声望/好感驱动的动态态度（alert/hostile）
            update_all_npc_states_dynamic(p)
            # MAS涌现:同格子NPC社交闲聊(Multi-Agent Social Gossip)
            from backend.systems.npc_gossip import maybe_npc_gossip
            maybe_npc_gossip(p, ticks=ticks)
        respawn_msg: str | None = None
        if p.permadeath:
            reason = hazard_roll_death(p)
            if reason:
                p.dead = True
                p.death_reason = reason
                p.move_locked = False
                p.move_lock_npc_id = None
                push_event(p, f"{p.display_name}于{MAPS[p.map_id]['name']}遭难:{reason[:24]}", scope="near", actor="天意")
                # 真实江湖：死亡即删档
                save_game(p)  # 先存档留档（存档时间戳记录最后状态）
                delete_save(p.player_id)
        # 已在逐格循环中完成沿途遭遇与消耗

        # 体力/心气归零的兜底(移动也可能直接走死)
        if not p.dead and not p.ended:
            collapsed = maybe_collapse_from_attrs(p)
            if collapsed and not p.permadeath:
                # 非真实江湖：属性归零 → 复活到最近补给点
                respawn_msg = respawn_at_supply_point(p)

        # ── 自动存档 ──
        try:
            save_game(p)
        except Exception:
            pass
        # 一次性陡差通行许可,用后即焚
        if allow_steep:
            p.allow_steep_next_move = False
        # 大地图无界门,无需推送过界门事件
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

    # 动态奇遇系统(2026 AI前沿:上下文驱动的叙事碎片生成)
    # 改为后台异步：不阻塞移动响应，奇遇结果存到 player 状态，下次刷新时生效
    if not p.dead and not p.ended and not getattr(p, "move_locked", False):
        if should_trigger_encounter(p):
            bg.add_task(_bg_encounter, p.player_id)

    # 感知扫描：当前位置周围危险预警
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
        "respawn_msg": respawn_msg,
    }

@router.get("/api/state/{player_id}")
async def get_state(player_id: str) -> dict[str, Any]:
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

@router.get("/api/agent/{player_id}/{npc_id}/mind")
async def agent_mind(player_id: str, npc_id: str) -> dict[str, Any]:
    p = room.players.get(player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    if npc_id not in NPCS:
        raise HTTPException(404, "未知 npc_id")
    mind = p.minds.get(npc_id)
    if mind is None:
        return {
            "npc_id": npc_id,
            "npc_name": NPCS[npc_id]["name"],
            "items": [],
            "plan_day": None,
            "plan_summary": "",
            "plan_by_shichen": {},
            "affect_valence": 0.0,
            "affect_arousal": 5.0,
            "affect_mood": "平静",
            "affect_cause": "",
        }
    return {
        "npc_id": npc_id,
        "npc_name": NPCS[npc_id]["name"],
        "items": [m.to_dict() for m in mind.items],
        "importance_since_reflect": float(mind.importance_since_reflect),
        "plan_day": mind.plan_day,
        "plan_summary": mind.plan_summary,
        "plan_by_shichen": dict(mind.plan_by_shichen),
        "affect_valence": float(mind.affect_valence),
        "affect_arousal": float(mind.affect_arousal),
        "affect_mood": mind.affect_mood,
        "affect_cause": mind.affect_cause,
    }

@router.post("/api/agent/reflect")
async def agent_reflect(body: AgentActBody) -> dict[str, Any]:
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    npc = NPCS.get(body.npc_id)
    if not npc:
        raise HTTPException(404, "未知 npc_id")
    mind = get_or_init_mind(p, body.npc_id)
    new_refls = await agent_brain.reflect(
        npc_id=body.npc_id,
        npc_name=npc["name"],
        npc_blurb=str(npc.get("short", "")),
        mind=mind,
        world_day=int(p.world_day),
        world_shichen=shichen_name(p.world_shichen),
    )
    return {
        "added": [m.to_dict() for m in new_refls],
        "count": len(new_refls),
    }

@router.post("/api/agent/plan")
async def agent_plan(body: AgentActBody) -> dict[str, Any]:
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    npc = NPCS.get(body.npc_id)
    if not npc:
        raise HTTPException(404, "未知 npc_id")
    mind = get_or_init_mind(p, body.npc_id)
    ok = await agent_brain.plan_day(
        npc_id=body.npc_id,
        npc_name=npc["name"],
        npc_blurb=str(npc.get("short", "")),
        mind=mind,
        world_day=int(p.world_day),
    )
    return {
        "ok": ok,
        "plan_day": mind.plan_day,
        "plan_summary": mind.plan_summary,
        "plan_by_shichen": dict(mind.plan_by_shichen),
    }

@router.get("/api/journal/{player_id}")
async def journal(player_id: str) -> dict[str, Any]:
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

@router.post("/api/npc/talk")
async def npc_talk(body: TalkBody, bg: BackgroundTasks) -> dict[str, Any]:
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    if p.ended:
        raise HTTPException(400, "本局已收束")
    if p.dead:
        raise HTTPException(400, "角色已身故,无法交谈")

    npc = NPCS.get(body.npc_id)
    if not npc:
        raise HTTPException(400, "未知 npc")

    allowed = set(npc_ids_for_player(p))
    if body.npc_id not in allowed:
        raise HTTPException(400, "此人不在你当前这一格(或不可交谈)。请先移动贴近。")

    async with p.lock:
        hist = p.history.setdefault(body.npc_id, [])
        hist_slice = list(hist[-14:])

    # ── Prompt 压缩：历史超过 14 轮时压缩早期对话 ──
    import backend.systems.prompt_compress as _pc
    if len(hist_slice) >= _pc.COMPRESS_THRESHOLD:
        hist_slice = await _pc.compress_conversation_history(
            hist_slice, npc_name=NPCS.get(body.npc_id, {}).get("name", ""))

    messages = build_npc_messages(p, body.npc_id, body.message, hist_slice)
    t0 = time.perf_counter()

    # 使用 JSON Mode
    is_light_inquiry = body.message.startswith("[系统指令·问路")
    is_fallback = False
    try:
        raw = await chat_completion(
            messages,
            temperature=0.85,
            max_tokens=450 if is_light_inquiry else 800,
            response_format={"type": "json_object"}
        )
        parsed = parse_npc_reply_json(raw)
    except Exception as e:
        is_fallback = True
        fallback = build_graceful_fallback(body.npc_id, f"{type(e).__name__}: {e}")
        parsed = fallback["parsed"]
        import logging
        logging.getLogger("api.routes").warning(
            "LLM fallback for npc=%s player=%s: %s",
            body.npc_id, body.player_id, str(e)[:120]
        )

    async with p.lock:
        out, needs_reflect = apply_npc_reply(p, body.npc_id, body.message, parsed)

    # 降级响应不触发反思（无实质内容可反思）
    if needs_reflect and not is_light_inquiry and not is_fallback:
        bg.add_task(bg_reflect, p.player_id, body.npc_id)

    out["server_ms"] = int((time.perf_counter() - t0) * 1000)
    if is_fallback:
        out["llm_fallback"] = True
    return out

@router.post("/api/npc/talk_stream")
async def npc_talk_stream(body: TalkBody, bg: BackgroundTasks) -> StreamingResponse:
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    if p.ended:
        raise HTTPException(400, "本局已收束")
    if p.dead:
        raise HTTPException(400, "角色已身故,无法交谈")
    npc = NPCS.get(body.npc_id)
    if not npc:
        raise HTTPException(400, "未知 npc")
    allowed = set(npc_ids_for_player(p))
    if body.npc_id not in allowed:
        raise HTTPException(400, "此人不在你当前这一格(或不可交谈)。请先移动贴近。")

    async with p.lock:
        hist = p.history.setdefault(body.npc_id, [])
        hist_slice = list(hist[-14:])

    # ── Prompt 压缩：历史超过 14 轮时压缩早期对话 ──
    import backend.systems.prompt_compress as _pc
    if len(hist_slice) >= _pc.COMPRESS_THRESHOLD:
        hist_slice = await _pc.compress_conversation_history(
            hist_slice, npc_name=NPCS.get(body.npc_id, {}).get("name", ""))

    messages = build_npc_messages(p, body.npc_id, body.message, hist_slice)

    async def event_gen():
        t0 = time.perf_counter()
        try:
            # 先强制 JSON Mode，保证状态字段与正文解耦，避免把"状态变更说明"直接吐给前端
            is_light = body.message.startswith("[系统指令·问路")
            raw = await chat_completion(
                messages,
                temperature=0.85,
                max_tokens=450 if is_light else 800,
                response_format={"type": "json_object"},
            )
            parsed = parse_npc_reply_json(raw)
        except Exception as e:
            fb = build_graceful_fallback(body.npc_id, str(e))
            parsed = fb["parsed"]
            import logging
            logging.getLogger("api.routes").warning(
                "LLM fallback (stream) for npc=%s player=%s: %s",
                body.npc_id, body.player_id, str(e)[:120]
            )
            # 降级态也逐段推给前端，维持流式观感
            vis = (parsed.visible_text or "").strip()
            if vis:
                for i in range(0, len(vis), 16):
                    yield _sse({"chunk": vis[i : i + 16]})
                    await asyncio.sleep(0.01)
            try:
                async with p.lock:
                    out, _ = apply_npc_reply(p, body.npc_id, body.message, parsed)
            except Exception:
                out = {}
            out["server_ms"] = int((time.perf_counter() - t0) * 1000)
            out["llm_fallback"] = True
            yield _sse({"done": True, **out})
            return

        # 仅把 visible_text 逐段推给前端,维持"流式出字"观感
        vis = (parsed.visible_text or "").strip()
        if vis:
            chunk_size = 16
            for i in range(0, len(vis), chunk_size):
                yield _sse({"chunk": vis[i : i + chunk_size]})
                await asyncio.sleep(0.01)

        try:
            async with p.lock:
                out, needs_reflect = apply_npc_reply(p, body.npc_id, body.message, parsed)
        except Exception as e:
            yield _sse({"error": f"状态写入失败:{e}", "fatal": True})
            return

        if needs_reflect:
            bg.add_task(bg_reflect, p.player_id, body.npc_id)
        out["server_ms"] = int((time.perf_counter() - t0) * 1000)
        yield _sse({"done": True, **out})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )

@router.post("/api/finale")
async def finale(body: FinaleBody) -> dict[str, Any]:
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    if p.dead:
        raise HTTPException(400, "已身故,无法收束成文。请新开周目。")
    if p.ended:
        return {
            "ending_label": p.ending_label,
            "epilogue": None,
            "already": True,
            "server_ms": 0,
        }

    digest = _story_digest(p)
    extra = (body.closing_note or "").strip()
    user_block = digest
    if extra:
        user_block += f"\n\n-- 玩家对收束的额外说明 --\n{extra}"

    messages = [
        {
            "role": "system",
            "content": (
                f"你是「{WORLD_NAME}」江湖的终局叙事者。\n"
                "尊重社会总览、世界事件流与对话摘录;收束时世界仍可继续运转。\n"
                "正文 220~420 字,第二人称「你」;不要列出数值;不要出现 STATE_UPDATE / PERMADEATH / EVENT 等机读行。\n"
                "落笔时把【世态此刻】(时辰、天气)与玩家身上钱物落到环境笔触里,让结局有此地此夜的呼吸。\n"
                "正文结束后**另起一行**:ENDING_TITLE: 六字到十四字标题(无书名号)"
            ),
        },
        {"role": "user", "content": user_block},
    ]
    t0 = time.perf_counter()
    raw = await chat_completion(messages, temperature=0.95, max_tokens=900)
    epilogue, title = parse_finale(raw)
    if not title:
        title = "无名之夜"

    async with p.lock:
        p.ended = True
        p.ending_label = title

    server_ms = int((time.perf_counter() - t0) * 1000)
    return {
        "ending_label": title,
        "epilogue": epilogue.strip(),
        "flags": p.flags,
        "server_ms": server_ms,
    }


# ══════════════════════════════════════════════════════════════
# 悬赏榜 API（2026-05-26 新增）
# ══════════════════════════════════════════════════════════════
from backend.systems.bounty_board import (
    generate_bounties,
    can_accept_bounty,
    accept_bounty,
    check_bounty_progress,
    complete_bounty,
    abandon_bounty,
    format_bounty_board,
    refresh_bounties,
)


class RefreshBountyBody(BaseModel):
    player_id: str


class AcceptBountyBody(BaseModel):
    player_id: str
    bounty_id: str


class CompleteBountyBody(BaseModel):
    player_id: str


class AbandonBountyBody(BaseModel):
    player_id: str


@router.post("/api/bounty/refresh")
async def bounty_refresh(body: RefreshBountyBody) -> dict[str, Any]:
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    refresh_bounties(p)
    # 首次生成
    if not p.bounties:
        p.bounties = generate_bounties(p, count=3)
    board_text = format_bounty_board(p)
    return {"bounties": p.bounties, "board_text": board_text}


@router.post("/api/bounty/accept")
async def bounty_accept(body: AcceptBountyBody) -> dict[str, Any]:
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    ok, msg = accept_bounty(p, body.bounty_id)
    return {"ok": ok, "message": msg}


@router.post("/api/bounty/check")
async def bounty_check(body: CompleteBountyBody) -> dict[str, Any]:
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    progress = check_bounty_progress(p)
    if progress is None:
        return {"has_active": False}
    return {"has_active": True, **progress}


@router.post("/api/bounty/complete")
async def bounty_complete(body: CompleteBountyBody) -> dict[str, Any]:
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    ok, msg, reward = complete_bounty(p)
    return {"ok": ok, "message": msg, "reward": reward}


@router.post("/api/bounty/abandon")
async def bounty_abandon(body: AbandonBountyBody) -> dict[str, Any]:
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    ok, msg = abandon_bounty(p)
    return {"ok": ok, "message": msg}


async def _bg_encounter(player_id: str) -> None:
    """后台异步生成动态奇遇，结果写入玩家状态"""
    try:
        p = room.players.get(player_id)
        if not p or p.dead or p.ended:
            return
        enc = await generate_dynamic_encounter(p)
        if enc:
            apply_encounter(p, enc)
    except Exception as e:
        import logging
        logging.getLogger("routes").warning("_bg_encounter failed for player=%s: %s", player_id, e)
