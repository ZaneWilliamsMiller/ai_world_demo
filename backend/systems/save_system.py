"""
save_system.py — 局外存档：每个角色独立 JSON 存档文件
========================================================

功能：
  - save_game(p)      → 序列化 PlayerState → saves/<player_id>.json
  - load_game(pid)    → 从 saves/<player_id>.json 还原 PlayerState
  - list_saves()      → 列出全部存档的摘要
  - delete_save(pid)  → 删除存档文件（真实江湖死亡/手动弃档）

存档文件路径：<项目根>/saves/
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import fields
from pathlib import Path
from typing import Any

from backend.models.player import PlayerState
from backend.data.factions import FACTIONS

log = logging.getLogger("save_system")

SAVE_DIR = Path(__file__).resolve().parents[2] / "saves"


def _ensure_dir() -> None:
    SAVE_DIR.mkdir(parents=True, exist_ok=True)


def _serialize_player(p: PlayerState) -> dict[str, Any]:
    """将 PlayerState 转为纯 JSON 可序列化的 dict。

    跳过 lock（asyncio.Lock 不可序列化）；
    minds 中的 AgentMind 转为 dict；
    npc_positions 中的 tuple 转为 list。"""
    data: dict[str, Any] = {}
    for fld in fields(p):
        key = fld.name
        if key == "lock":
            continue
        val = getattr(p, key, None)
        if key == "minds" and val:
            val = {nid: _mind_to_dict(m) for nid, m in val.items()}
        elif key == "npc_positions" and val:
            val = {nid: list(v) for nid, v in val.items()}
        data[key] = val
    return data


def _mind_to_dict(mind: Any) -> dict[str, Any]:
    """AgentMind → dict。"""
    return {
        "items": [item.to_dict() for item in getattr(mind, "items", [])],
        "importance_since_reflect": float(getattr(mind, "importance_since_reflect", 0)),
        "last_reflect_at": float(getattr(mind, "last_reflect_at", 0)),
        "plan_day": getattr(mind, "plan_day", None),
        "plan_by_shichen": dict(getattr(mind, "plan_by_shichen", {})),
        "plan_summary": str(getattr(mind, "plan_summary", "")),
        "affect_valence": float(getattr(mind, "affect_valence", 0)),
        "affect_arousal": float(getattr(mind, "affect_arousal", 5)),
        "affect_mood": str(getattr(mind, "affect_mood", "平静")),
        "affect_cause": str(getattr(mind, "affect_cause", "")),
        "affect_updated_at": float(getattr(mind, "affect_updated_at", 0)),
        "last_insight_at": float(getattr(mind, "last_insight_at", 0)),
    }


def _deserialize_player(data: dict[str, Any]) -> PlayerState:
    """从 dict 还原 PlayerState。"""
    # 特殊字段：minds 需要重建 AgentMind
    minds_raw = data.pop("minds", {}) or {}
    # npc_positions 的 list → tuple
    npc_pos_raw = data.pop("npc_positions", {}) or {}

    # 确保 reputation 完整（老存档兼容）
    rep = data.get("reputation", {})
    if not isinstance(rep, dict):
        rep = {}
    for k in FACTIONS.keys():
        rep.setdefault(k, 0)
    data["reputation"] = rep

    p = PlayerState(**data)

    # 还原 minds
    from backend.memory import Memory, AgentMind
    for nid, md in minds_raw.items():
        mind = AgentMind()
        mind.importance_since_reflect = float(md.get("importance_since_reflect", 0))
        mind.last_reflect_at = float(md.get("last_reflect_at", 0))
        mind.plan_day = md.get("plan_day")
        mind.plan_by_shichen = dict(md.get("plan_by_shichen", {}))
        mind.plan_summary = str(md.get("plan_summary", ""))
        mind.affect_valence = float(md.get("affect_valence", 0))
        mind.affect_arousal = float(md.get("affect_arousal", 5))
        mind.affect_mood = str(md.get("affect_mood", "平静"))
        mind.affect_cause = str(md.get("affect_cause", ""))
        mind.affect_updated_at = float(md.get("affect_updated_at", 0))
        mind.last_insight_at = float(md.get("last_insight_at", 0))
        for item_raw in md.get("items", []):
            mem = Memory(
                kind=str(item_raw.get("kind", "observation")),
                text=str(item_raw.get("text", "")),
                importance=float(item_raw.get("importance", 0)),
                anchor=bool(item_raw.get("is_anchor", False)),
            )
            mem.created_day = int(item_raw.get("created_day", 0))
            mem.created_shichen = str(item_raw.get("created_shichen", ""))
            mem.refs = list(item_raw.get("refs", []))
            mind.items.append(mem)
        p.minds[nid] = mind

    # 还原 npc_positions：list → tuple
    p.npc_positions = {
        nid: (str(v[0]), int(v[1]), int(v[2]))
        for nid, v in npc_pos_raw.items()
    }

    # 兼容：没有这些字段的老存档
    if not hasattr(p, "vigor_max") or not p.vigor_max:
        p.vigor_max = 100
    if not hasattr(p, "spirit_max") or not p.spirit_max:
        p.spirit_max = 100
    # 体力永远不应从 0 开始（新角色保底 80）
    if int(getattr(p, "vigor", 0)) <= 0:
        p.vigor = 80
    if int(getattr(p, "spirit", 0)) <= 0:
        p.spirit = 80

    return p


# ═══════════════════════════════════════════════════════
#  公开 API
# ═══════════════════════════════════════════════════════

def save_game(p: PlayerState) -> str:
    """保存角色到 JSON 文件。返回保存路径字符串。"""
    _ensure_dir()
    data = _serialize_player(p)
    fp = SAVE_DIR / f"{p.player_id}.json"
    try:
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log.info("存档成功: %s (%s, 第%d日, 制钱%d)", p.display_name, p.player_id,
                  p.world_day, p.coins)
        return str(fp)
    except Exception as e:
        log.error("存档失败 %s: %s", p.player_id, e)
        raise


def load_game(player_id: str) -> PlayerState | None:
    """从 JSON 文件加载角色。文件不存在返回 None。"""
    fp = SAVE_DIR / f"{player_id}.json"
    if not fp.is_file():
        return None
    try:
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        p = _deserialize_player(data)
        log.info("存档加载: %s (%s, 第%d日)", p.display_name, p.player_id, p.world_day)
        return p
    except Exception as e:
        log.error("存档加载失败 %s: %s", player_id, e)
        return None


def list_saves() -> list[dict[str, Any]]:
    """列出全部存档摘要（用于展示可选角色列表）。"""
    _ensure_dir()
    result: list[dict[str, Any]] = []
    for fp in sorted(SAVE_DIR.glob("*.json")):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            result.append({
                "player_id": data.get("player_id", fp.stem),
                "display_name": data.get("display_name", ""),
                "gender": data.get("gender", ""),
                "permadeath": data.get("permadeath", False),
                "dead": data.get("dead", False),
                "map_id": data.get("map_id", ""),
                "world_day": data.get("world_day", 0),
                "coins": data.get("coins", 0),
                "vigor": data.get("vigor", 0),
                "spirit": data.get("spirit", 0),
                "ended": data.get("ended", False),
            })
        except Exception:
            continue
    return result


def delete_save(player_id: str) -> bool:
    """删除存档文件（真实江湖死亡/手动弃档）。返回是否成功删除。"""
    fp = SAVE_DIR / f"{player_id}.json"
    if not fp.is_file():
        return False
    try:
        fp.unlink()
        log.info("存档已删除: %s", player_id)
        return True
    except Exception as e:
        log.error("删除存档失败 %s: %s", player_id, e)
        return False


def respawn_at_supply_point(p: PlayerState) -> str:
    """非真实江湖模式下，重伤后返回最近补给点。

    补给点 = {T: 客栈, Y: 驿站, I: 黑店, M: 市集, B: 兵站}

    在当前地图找最近的补给点格子；找不到则回 county 客栈 (4,2)。
    恢复 50% 体力/心气，清除 debuff。
    返回一句文本描述。"""
    from backend.data.maps_data import MAPS
    from backend.systems.pathfinding import walkable

    supply_tiles = {"T", "Y", "I", "M", "B"}
    candidates: list[tuple[int, int, str]] = []  # (manhattan_dist, x, y)

    # 先在当前地图找
    m = MAPS.get(p.map_id)
    if m:
        rows = m["rows"]
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch in supply_tiles:
                    d = abs(x - p.px) + abs(y - p.py)
                    candidates.append((d, x, y))

    if candidates:
        candidates.sort()
        _, nx, ny = candidates[0]
    else:
        # 回同福栈
        p.map_id = "world"
        nx, ny = 8, 13

    old_map, old_x, old_y = p.map_id, p.px, p.py
    p.px, p.py = nx, ny
    p.dead = False
    p.death_reason = None
    p.vigor = max(40, p.vigor_max // 2)
    p.spirit = max(40, p.spirit_max // 2)
    p.move_locked = False
    p.move_lock_npc_id = None
    p.trap_reason = None
    p.trap_attempts = 0
    p.life_burn_ticks = 0
    p.life_burn_max = 0
    p.unconscious_ticks = 0

    map_name = MAPS.get(p.map_id, {}).get("name", p.map_id)
    msg = f"重伤苏醒，被江湖路人拖至{map_name}补给处。气力心神恢复一半。"
    log.info("respawn: %s (%s,%s)→(%s,%s)", p.display_name, old_x, old_y, nx, ny)

    # 触发事件
    from backend.systems.reputation import push_event
    push_event(p, msg[:48], scope="near", actor="江湖路人")

    return msg