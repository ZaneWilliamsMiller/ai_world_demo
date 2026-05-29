"""感知扫描、危险判定、休息系统、世界状态块。

从 systems/core.py 拆分而来，职责：
- 感知扫描 (perception_scan, danger_sense_narrative)
- 危险判定 (hazard_roll_death, tile_forced_encounter)
- 休息系统 (can_rest_at, rest_at_location)
- 世界状态块 (world_status_block, recent_events_block, relevant_events_for)
"""
from __future__ import annotations

from typing import Any

from backend.models.player import PlayerState
from backend.data.npcs_data import NPCS, NPC_FACTION
from backend.data.factions import FACTIONS
from backend.data.maps_data import MAPS
from backend.systems.constants import (
    HAZARD_PROB_INN,
    HAZARD_PROB_BUSH,
    HAZARD_PROB_WATER,
    HAZARD_NIGHT_MULT,
    HAZARD_RAIN_WATER_MULT,
    HAZARD_RAIN_OTHER_MULT,
    HAZARD_FOG_MULT,
    HAZARD_LULIN_PROTECT_MULT,
    HAZARD_CAOBANG_PROTECT_MULT,
    HAZARD_POOR_COIN_MULT,
    HAZARD_RICH_COIN_MULT,
    HAZARD_MAX_DEATH_PROB,
    HAZARD_COIN_POOR_THRESHOLD,
    HAZARD_COIN_RICH_THRESHOLD,
    HAZARD_REP_PROTECT_THRESHOLD,
)
from backend.systems.pathfinding import tile_at, is_dangerous
from backend.systems.time_weather import is_night, shichen_name, shichen_phase
from backend.systems.trap import apply_vigor_delta, apply_spirit_delta


# ════════════════════════════════════════════════════════════════
# 感知扫描系统 🎮 游戏性 - 危险直觉预警
# ════════════════════════════════════════════════════════════════

DANGER_SENSE_TILES: dict[str, str] = {
    "~": "水声诡谲，似有暗流",
    "!": "地面龟裂，隙缝纵横",
    "@": "残垣断壁，已成危楼",
    "^": "悬崖壁立，下临深渊",
    "I": "门户虚掩，恐有埋伏",
    "&": "草丛蹊跷，谨防剪径",
}

FOG_WEATHERS: frozenset[str] = frozenset({"重雾", "薄雾", "湿瘴"})


def perception_scan(p: PlayerState) -> dict[str, Any] | None:
    """玩家感知扫描：检测周围危险与特殊地形。"""
    radius = 2
    if p.weather in FOG_WEATHERS:
        radius -= 1
    spirit = int(getattr(p, "spirit", 80))
    if spirit < 40:
        radius -= 1
    radius = max(1, radius)

    warnings: list[dict[str, Any]] = []
    suspicions: list[dict[str, Any]] = []

    rows = MAPS.get(p.map_id, {}).get("rows")
    if not rows:
        return None

    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = p.px + dx, p.py + dy
            if not (0 <= ny < len(rows) and 0 <= nx < len(rows[ny])):
                continue
            ch = rows[ny][nx]
            dist = abs(dx) + abs(dy)
            if dist > radius:
                continue
            if ch in DANGER_SENSE_TILES:
                if is_dangerous(ch):
                    warnings.append({
                        "x": nx, "y": ny,
                        "dist": dist,
                        "danger": DANGER_SENSE_TILES[ch],
                    })
                elif ch in ("&",):
                    if dist <= 1:
                        suspicions.append({
                            "x": nx, "y": ny,
                            "dist": dist,
                            "note": "草丛深处似有动静",
                        })
                elif ch == "I":
                    if dist <= 1:
                        suspicions.append({
                            "x": nx, "y": ny,
                            "dist": dist,
                            "note": "这户门半掩，不太对劲",
                        })

    if not warnings and not suspicions:
        return None

    return {
        "warnings": warnings,
        "suspicions": suspicions,
        "radius": radius,
        "weather_penalty": p.weather in FOG_WEATHERS,
        "spirit_penalty": spirit < 40,
    }


def danger_sense_narrative(p: PlayerState, scan: dict[str, Any] | None) -> str:
    """将感知扫描结果转化为叙事性文字。"""
    if not scan:
        return ""

    parts: list[str] = []
    warnings = sorted(scan.get("warnings", []), key=lambda x: x.get("dist", 99))
    suspicions = sorted(scan.get("suspicions", []), key=lambda x: x.get("dist", 99))

    for w in warnings[:3]:
        d = w.get("dist", 99)
        txt = w.get("danger", "")
        if d == 1:
            parts.append(f"{txt}就在近旁")
        elif d == 2:
            parts.append(f"{txt}在左近")
        else:
            parts.append(f"{txt}在远处")

    for s in suspicions[:2]:
        dist = s.get("dist", 99)
        note = s.get("note", "")
        if dist <= 1:
            parts.append(note)

    if not parts:
        return ""

    prefixes = ["【感知】", "【直觉】", "【警惕】"]
    prefix = prefixes[len(parts) % 3] if parts else "【感知】"
    return f"{prefix}{'，'.join(parts)}。"


def tile_forced_encounter(p: PlayerState) -> dict[str, Any] | None:
    """当前格有隐藏 NPC 且地格符号匹配时,供移动接口返回强制剧情引信。"""
    ch = tile_at(p.map_id, p.px, p.py) or "."
    for nid, meta in NPCS.items():
        if not meta.get("hidden"):
            continue
        cell = meta.get("cell")
        if not cell or not isinstance(cell, (list, tuple)) or len(cell) < 3:
            continue
        if cell[0] != p.map_id or cell[1] != p.px or cell[2] != p.py:
            continue
        need = meta.get("triggers_on_tile")
        if need and ch != need:
            continue
        return {
            "npc_id": nid,
            "user_line": meta.get(
                "encounter_user",
                "[际遇] 狭路有变,请直接写对峙开场。",
            ),
            "blurb": meta.get("encounter_blurb", "险遇"),
        }
    return None


def hazard_roll_death(p: PlayerState) -> str | None:
    """非 LLM 的随机横死(真实江湖模式)。"""
    import random

    ch = tile_at(p.map_id, p.px, p.py) or "."
    base = {"I": HAZARD_PROB_INN, "&": HAZARD_PROB_BUSH, "~": HAZARD_PROB_WATER}.get(ch, 0.0)
    if base <= 0:
        return None

    night_mult = HAZARD_NIGHT_MULT if is_night(p.world_shichen) else 1.0
    weather_mult = 1.0
    if p.weather in ("骤雨", "湿瘴"):
        weather_mult = HAZARD_RAIN_WATER_MULT if ch == "~" else HAZARD_RAIN_OTHER_MULT
    elif p.weather in ("重雾", "薄雾"):
        weather_mult = HAZARD_FOG_MULT
    rep_mult = 1.0
    lulin = int(p.reputation.get("lulin", 0))
    caobang = int(p.reputation.get("caobang", 0))
    if ch in ("&", "I") and lulin >= HAZARD_REP_PROTECT_THRESHOLD:
        rep_mult *= HAZARD_LULIN_PROTECT_MULT
    if ch == "~" and caobang >= HAZARD_REP_PROTECT_THRESHOLD:
        rep_mult *= HAZARD_CAOBANG_PROTECT_MULT
    if ch == "I":
        if p.coins <= HAZARD_COIN_POOR_THRESHOLD:
            rep_mult *= HAZARD_POOR_COIN_MULT
        elif p.coins >= HAZARD_COIN_RICH_THRESHOLD:
            rep_mult *= HAZARD_RICH_COIN_MULT

    p_die = max(0.0, min(HAZARD_MAX_DEATH_PROB, base * night_mult * weather_mult * rep_mult))
    if random.random() >= p_die:
        return None

    if ch == "I":
        return "蒙汗药翻肠,黑店不留客。"
    if ch == "&":
        return "剪径贼从芦荡里起,刀光比话快。"
    if ch == "~":
        return "水鬼与暗流同来,尸骨不必上岸。"
    return None


# ────────────────────────────────────────────────────────────────────
# 自然休息系统
# ────────────────────────────────────────────────────────────────────

REST_TILES = {"T", "Y", "M", "B", "@"}
REST_VIGOR_FRAC = 0.25
REST_SPIRIT_FRAC = 0.20
REST_SLEEP_DEBT_DELTA = -3
REST_TIME_TICKS = 2

TILE_REST_MOOD: dict[str, str] = {
    "T": "客栈",
    "Y": "驿站",
    "M": "市集",
    "B": "兵站",
    "@": "佛寺",
}


def can_rest_at(p: PlayerState) -> tuple[bool, str]:
    ch = tile_at(p.map_id, p.px, p.py) or "."
    if ch not in REST_TILES:
        if ch == "I":
            return (False, "黑店虎狼之地，不敢闭眼——换个安生处再说。")
        nearby_hint = _nearby_rest_hint(p)
        if nearby_hint:
            return (False, f"此处无歇脚之所。{nearby_hint}")
        return (False, "此处无歇脚之所，寻客栈(T)、佛寺(@)或驿站(Y)再歇不迟。")
    mood = TILE_REST_MOOD.get(ch, "歇脚处")
    return (True, mood)


def _nearby_rest_hint(p: PlayerState) -> str:
    m = MAPS.get(p.map_id)
    if not m:
        return ""
    best_dist = 999
    best_tile = ""
    for y, row in enumerate(m["rows"]):
        for x, tile in enumerate(row):
            if tile in REST_TILES:
                d = abs(x - p.px) + abs(y - p.py)
                if d < best_dist:
                    best_dist = d
                    best_tile = tile
    if best_dist < 6 and best_tile:
        mood = TILE_REST_MOOD.get(best_tile, "补给点")
        return f"最近的{mood}距此约{best_dist}格，往那个方向走走看。"
    return ""


def rest_at_location(p: PlayerState) -> dict[str, object]:
    """在当前位置休息，恢复体力/心气，降低睡眠债。"""
    can, mood = can_rest_at(p)
    if not can:
        return {
            "ok": False,
            "reason": mood,
            "delta": {"vigor": 0, "spirit": 0, "sleep_debt": 0},
            "ticks_passed": 0,
            "note": "",
        }

    vmax = int(getattr(p, "vigor_max", 100) or 100)
    smax = int(getattr(p, "spirit_max", 100) or 100)
    cur_v = int(getattr(p, "vigor", 80) or 0)
    cur_s = int(getattr(p, "spirit", 80) or 0)
    cur_sd = int(getattr(p, "sleep_debt", 0) or 0)

    v_restore = max(1, int(vmax * REST_VIGOR_FRAC))
    s_restore = max(1, int(smax * REST_SPIRIT_FRAC))
    actual_v = min(v_restore, vmax - cur_v)
    actual_s = min(s_restore, smax - cur_s)
    actual_sd = max(REST_SLEEP_DEBT_DELTA, -cur_sd)

    if actual_v <= 0 and actual_s <= 0 and actual_sd >= 0:
        from backend.systems.time_weather import advance_clock
        advance_clock(p, REST_TIME_TICKS)
        return {
            "ok": True,
            "reason": f"你在{mood}略坐了坐，身上已经松快了，再歇也是白坐。",
            "delta": {"vigor": 0, "spirit": 0, "sleep_debt": 0},
            "ticks_passed": REST_TIME_TICKS,
            "note": f"你在{mood}略坐了坐——时辰不声不响地溜了过去。",
        }

    from backend.systems.time_weather import advance_clock, shichen_name
    actual_vigor = apply_vigor_delta(p, actual_v) if actual_v > 0 else 0
    actual_spirit = apply_spirit_delta(p, actual_s) if actual_s > 0 else 0
    if actual_sd < 0:
        p.sleep_debt = max(0, cur_sd + actual_sd)
        actual_sleep_d = cur_sd - p.sleep_debt
    else:
        actual_sleep_d = 0

    advance_clock(p, REST_TIME_TICKS)

    parts: list[str] = []
    if actual_vigor > 0:
        parts.append(f"体力恢复了些（+{actual_vigor}）")
    if actual_spirit > 0:
        parts.append(f"心头松快了（+{actual_spirit}）")
    if actual_sleep_d > 0:
        parts.append("倦意减了几分")

    detail = "、".join(parts) if parts else "略坐了坐"
    note = f"你在{mood}歇了一阵——{detail}。"

    from backend.systems.reputation import push_event
    push_event(p, f"{p.display_name}在{mood}歇脚，{detail}", scope="self", actor=p.display_name)

    return {
        "ok": True,
        "reason": detail,
        "delta": {
            "vigor": actual_vigor,
            "spirit": actual_spirit,
            "sleep_debt": -(actual_sleep_d) if actual_sleep_d > 0 else 0,
        },
        "ticks_passed": REST_TIME_TICKS,
        "note": note,
        "location": mood,
    }


def relevant_events_for(p: PlayerState, npc_id: str, k: int = 4) -> list[dict[str, Any]]:
    """挑选与该 NPC 最相关的近期事件。"""
    if not p.events:
        return []
    fac = NPC_FACTION.get(npc_id)
    npc_meta = NPCS.get(npc_id) or {}
    npc_map = (npc_meta.get("cell") or (None,))[0]
    out: list[dict[str, Any]] = []
    for e in reversed(p.events):
        out.append(e)
        if len(out) >= k:
            break
    out.reverse()
    if npc_id == "jiang":
        return out
    pri: list[dict[str, Any]] = []
    rest: list[dict[str, Any]] = []
    for e in out:
        a = e.get("actor") or ""
        if fac and (fac in a or FACTIONS.get(fac, "") in a):
            pri.append(e)
        elif npc_map and npc_map in a:
            pri.append(e)
        else:
            rest.append(e)
    return (pri + rest)[:k]


def world_status_block(p: PlayerState) -> str:
    """生成给 NPC 的「世态此刻」上下文。"""
    sh = shichen_name(p.world_shichen)
    phase = shichen_phase(p.world_shichen)
    night = "(夜)" if is_night(p.world_shichen) else ""
    coins_line = f"随身制钱 {p.coins} 文"
    inv = sorted(p.inventory.items()) if p.inventory else []
    inv_line = "身无长物" if not inv else "身上有:" + "、".join(
        (f"{n}×{c}" if c > 1 else n) for n, c in inv
    )
    rep_line = ""
    if p.reputation:
        bits = []
        for k, name in FACTIONS.items():
            v = int(p.reputation.get(k, 0))
            if v != 0:
                bits.append(f"{name}{v:+d}")
        if bits:
            rep_line = "声望:" + " ".join(bits)
    parts = [
        f"【世态此刻】第 {p.world_day} 日 · {sh}{night}({phase}) · 天气「{p.weather}」",
        f"· {coins_line};{inv_line}",
    ]
    if rep_line:
        parts.append(f"· {rep_line}")
    return "\n".join(parts)


def recent_events_block(p: PlayerState, npc_id: str) -> str:
    evs = relevant_events_for(p, npc_id, k=4)
    if not evs:
        return ""
    lines = ["【近日江湖事(可作闲笔印证或反驳,不必逐字复述)】"]
    for e in evs:
        tag = f"[{e.get('shichen', '?')}]"
        lines.append(f"· {tag} {e.get('text', '')}")
    return "\n".join(lines)


def val_in_range(v: int, lo: int, hi: int) -> bool:
    return lo <= v <= hi
