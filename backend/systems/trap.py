"""险局/脱困/生存机制。

从 systems/core.py 拆分而来，职责：
- 险局锁定与脱困 (enter_trap_state, try_clear_move_lock)
- 属性归零兜底 (maybe_collapse_from_attrs)
- 生存动作 (survival_action_delta)
- 体力/心气 (apply_vigor_delta, apply_spirit_delta, vigor_status_block)
"""
from __future__ import annotations

from typing import Any

from backend.models.player import PlayerState
from backend.systems.constants import (
    DRY_RATION_SPIRIT,
    DRY_RATION_VIGOR,
    FISH_MAX_PER_DAY,
    FISH_SPIRIT,
    FISH_VIGOR,
    FRUIT_MAX_PER_DAY,
    LIFE_BURN_TICKS,
    MAX_TRAP_ATTEMPTS,
    REST_MAX_PER_DAY,
    SAFE_REST_SLEEP_DEBT,
    SAFE_REST_SPIRIT,
    SAFE_REST_VIGOR,
    SAFE_ZONE_X_RANGE,
    SAFE_ZONE_Y_RANGE,
    WILD_FRUIT_SPIRIT,
    WILD_FRUIT_VIGOR,
    WILD_REST_SLEEP_DEBT,
    WILD_REST_SPIRIT,
    WILD_REST_VIGOR,
)
from backend.systems.pathfinding import tile_at

# ────────────────────── 体力 / 心气:带上限的可耗资源 ──────────────────────

def _clamp_int(v: int, lo: int, hi: int) -> int:
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def apply_vigor_delta(p: PlayerState, delta: int) -> int:
    if not delta:
        return 0
    cap = int(getattr(p, "vigor_max", 100) or 100)
    cur = int(getattr(p, "vigor", cap) or 0)
    nxt = _clamp_int(cur + int(delta), 0, cap)
    p.vigor = nxt
    return nxt - cur


def apply_spirit_delta(p: PlayerState, delta: int) -> int:
    if not delta:
        return 0
    cap = int(getattr(p, "spirit_max", 100) or 100)
    cur = int(getattr(p, "spirit", cap) or 0)
    nxt = _clamp_int(cur + int(delta), 0, cap)
    p.spirit = nxt
    return nxt - cur


def vigor_status_block(p: PlayerState) -> str:
    v = int(getattr(p, "vigor", 80))
    s = int(getattr(p, "spirit", 80))
    vmax = int(getattr(p, "vigor_max", 100))
    smax = int(getattr(p, "spirit_max", 100))

    def _phase(x: int, cap: int) -> str:
        if x <= max(1, cap // 8):
            return "近枯竭"
        if x <= cap // 3:
            return "极弱"
        if x <= cap // 2:
            return "见底"
        if x <= cap * 3 // 4:
            return "尚可"
        return "尚足"

    return (
        f"【身心此刻】体力 {v}/{vmax}({_phase(v, vmax)}),"
        f"心气 {s}/{smax}({_phase(s, smax)})。\n"
        "请据这两项的高低,自然写出玩家的喘息、神色、判断力起伏。"
        "做事(奔走、力斗、熬夜、纵酒、忍痛、被吓)请给 vigor_delta/spirit_delta 写实变化;"
        "歇脚、温食、温言、安寝时也照实回血。**不可超过上限**。"
    )


# ────────────────────── 险局脱困 ──────────────────────

def _reset_trap_state(p: PlayerState) -> None:
    p.move_locked = False
    p.move_lock_npc_id = None
    p.trap_reason = None
    p.trap_attempts = 0
    p.trap_type = None


def enter_trap_state(p: PlayerState, reason: str, lock_npc_id: str | None = None, trap_type: str = "npc") -> None:
    """开启「身陷险局」。"""
    p.move_locked = True
    p.move_lock_npc_id = lock_npc_id or "jiang"
    p.trap_type = trap_type
    p.trap_reason = (reason or "骤入险局").strip()[:80]
    p.trap_attempts = 0


def tile_hazard_reason(p: PlayerState) -> str | None:
    """当前格是否会自动陷入险局。"""
    ch = tile_at(p.map_id, p.px, p.py) or "."
    if ch == "&":
        return "草莽暗起,骤被围在当中。"
    if ch == "I":
        return "门闩落下,烛火忽暗--进的是局,不是栈。"
    if ch == "~":
        return "脚下水势骤回,半身陷于浊流。"
    return None


def maybe_collapse_from_attrs(p: PlayerState) -> dict[str, Any] | None:
    """属性归零的硬兜底:保证不会出现长锁不死的循环。"""
    v = int(getattr(p, "vigor", 100))
    s = int(getattr(p, "spirit", 100))
    if v <= 0 and s <= 0:
        p.dead = True
        p.death_reason = "气力心神俱断,倒于此地。"
        _reset_trap_state(p)
        return {"outcome": "dead", "reason": p.death_reason}
    if v <= 0:
        if int(getattr(p, "life_burn_ticks", 0)) <= 0:
            p.life_burn_max = LIFE_BURN_TICKS
            p.life_burn_ticks = LIFE_BURN_TICKS
            p.move_locked = True
            p.move_lock_npc_id = "jiang"
            p.trap_type = "environment"
            p.trap_reason = "体力枯竭,生命在燃烧;尽快进食。"
            return {"outcome": "burning", "reason": p.trap_reason}
        return {"outcome": "burning", "reason": "生命燃烧中,若不进食将饿死。"}
    if s <= 0:
        p.dead = True
        p.death_reason = "心气失守,魂不归窍。"
        _reset_trap_state(p)
        return {"outcome": "dead", "reason": p.death_reason}
    return None


def try_clear_move_lock(
    p: PlayerState,
    user_message: str,
    npc_id: str,
    *,
    llm_outcome: str | None = None,
    llm_enslaved: str | None = None,
) -> dict[str, Any] | None:
    """险境锁定的处理。"""
    if not getattr(p, "move_locked", False):
        return None
    if user_message.strip().startswith("[际遇"):
        return None
    lock_npc = getattr(p, "move_lock_npc_id", None)
    if lock_npc is not None and npc_id and npc_id != str(lock_npc):
        return None

    p.trap_attempts = int(getattr(p, "trap_attempts", 0)) + 1

    if int(getattr(p, "life_burn_ticks", 0)) > 0:
        if int(getattr(p, "vigor", 0)) > 0:
            p.life_burn_ticks = 0
            p.life_burn_max = 0
            _reset_trap_state(p)
            return {"outcome": "escaped", "reason": "进食回力,生命燃烧止息。"}
        return {"outcome": "struggling", "reason": "生命燃烧中,尽快进食。", "attempts": p.trap_attempts}

    collapsed = maybe_collapse_from_attrs(p)
    if collapsed:
        return collapsed

    if llm_enslaved:
        p.enslaved = True
        p.enslaved_reason = llm_enslaved.strip()[:80] or "失了自由身。"
        p.ended = True
        p.ending_label = "囚徒残年"
        _reset_trap_state(p)
        return {"outcome": "enslaved", "reason": p.enslaved_reason}

    if llm_outcome == "success":
        _reset_trap_state(p)
        return {"outcome": "escaped", "reason": "终得脱身,可再行旅。"}

    if llm_outcome == "fail":
        if p.trap_attempts >= MAX_TRAP_ATTEMPTS:
            p.enslaved = True
            p.enslaved_reason = "周旋已尽,被人押作苦役。"
            p.ended = True
            p.ending_label = "囚徒残年"
            _reset_trap_state(p)
            return {"outcome": "enslaved", "reason": p.enslaved_reason}
        return {
            "outcome": "struggling",
            "reason": "险局未解,仍需周旋。",
            "attempts": p.trap_attempts,
        }

    if llm_outcome == "progress":
        return {
            "outcome": "struggling",
            "reason": "暂占上风,但仍未脱身。",
            "attempts": p.trap_attempts,
        }

    return {
        "outcome": "struggling",
        "reason": "险局未解,仍需周旋。",
        "attempts": p.trap_attempts,
    }


def survival_action_delta(p: PlayerState, user_message: str) -> dict[str, Any]:
    """自由文本中的生存动作。"""
    msg = (user_message or "").strip()
    if not msg:
        return {"vigor": 0, "spirit": 0, "items_gain": [], "items_lose": [], "note": ""}
    ch = tile_at(p.map_id, p.px, p.py) or "."

    items_gain: list[str] = []
    items_lose: list[str] = []
    vigor = 0
    spirit = 0
    note = ""

    if not p.item_use_tracker:
        p.item_use_tracker = {}
    tracker = p.item_use_tracker
    day_key = str(p.world_day)

    if any(k in msg for k in ("吃干粮", "啃干粮")) and int(p.inventory.get("干粮", 0)) > 0:
        ration_key = "干粮"
        if tracker.get(ration_key, 0) >= 3:
            note = "干粮已在本轮消耗过，不可重复使用。"
        else:
            tracker[ration_key] = tracker.get(ration_key, 0) + 1
            p.inventory["干粮"] = max(0, int(p.inventory.get("干粮", 0)) - 1)
            if p.inventory["干粮"] <= 0:
                p.inventory.pop("干粮", None)
            vigor += apply_vigor_delta(p, DRY_RATION_VIGOR)
            spirit += apply_spirit_delta(p, DRY_RATION_SPIRIT)
            items_lose.append("干粮")
            note = "你嚼了几口干粮,气力略回。"
    elif any(k in msg for k in ("打鱼", "捕鱼", "下网", "摸鱼")) and ch in ("~", "B"):
        fish_key = "鲜鱼"
        if tracker.get(fish_key, 0) >= FISH_MAX_PER_DAY:
            note = "今日已多次打鱼,水边再无收获。"
        else:
            tracker[fish_key] = tracker.get(fish_key, 0) + 1
            vigor += apply_vigor_delta(p, FISH_VIGOR)
            spirit += apply_spirit_delta(p, FISH_SPIRIT)
            p.inventory["鲜鱼"] = int(p.inventory.get("鲜鱼", 0)) + 1
            items_gain.append("鲜鱼")
            note = "你就着水势摸得一尾鲜鱼。"
    elif any(k in msg for k in ("野果", "采果", "摘果", "吃果")) and ch in ("F", "&", ","):
        fruit_key = "野果"
        if tracker.get(fruit_key, 0) >= FRUIT_MAX_PER_DAY:
            note = "附近野果已被采尽,明日再来。"
        else:
            tracker[fruit_key] = tracker.get(fruit_key, 0) + 1
            vigor += apply_vigor_delta(p, WILD_FRUIT_VIGOR)
            spirit += apply_spirit_delta(p, WILD_FRUIT_SPIRIT)
            note = "你在林地寻得野果,勉强充饥。"
    elif any(k in msg for k in ("睡", "歇息", "打盹", "合眼")):
        if getattr(p, "move_locked", False):
            note = "身处险局，无法安歇。"
        else:
            rest_key = "_rest"
            if tracker.get(rest_key, 0) >= REST_MAX_PER_DAY:
                note = "今日已多次歇息,难以再入睡。"
            else:
                tracker[rest_key] = tracker.get(rest_key, 0) + 1
                safe = (ch in ("T", "Y")) or (p.map_id == "world" and SAFE_ZONE_X_RANGE[0] <= p.px <= SAFE_ZONE_X_RANGE[1] and SAFE_ZONE_Y_RANGE[0] <= p.py <= SAFE_ZONE_Y_RANGE[1])
                if safe:
                    vigor += apply_vigor_delta(p, SAFE_REST_VIGOR)
                    spirit += apply_spirit_delta(p, SAFE_REST_SPIRIT)
                    p.sleep_debt = max(0, int(getattr(p, "sleep_debt", 0)) - SAFE_REST_SLEEP_DEBT)
                    note = "你在较安全处合眼调息,心气大幅回升。"
                else:
                    vigor += apply_vigor_delta(p, WILD_REST_VIGOR)
                    spirit += apply_spirit_delta(p, WILD_REST_SPIRIT)
                    p.sleep_debt = max(0, int(getattr(p, "sleep_debt", 0)) - WILD_REST_SLEEP_DEBT)
                    note = "荒野露宿,寒湿与警惕反噬了体力,只回了一点心气。"
    elif any(k in msg for k in ("攀爬", "爬坡", "翻越", "跳崖", "下崖")):
        p.allow_steep_next_move = True
        spirit += apply_spirit_delta(p, -3)
        note = "你决意冒险攀爬/跳降,下一次移动可强行越过陡差,但极易受伤。"

    if vigor > 0 and int(getattr(p, "life_burn_ticks", 0)) > 0:
        p.life_burn_ticks = 0
        p.life_burn_max = 0
        p.trap_reason = None
        p.move_locked = False
        p.move_lock_npc_id = None
        p.trap_type = None

    return {
        "vigor": vigor,
        "spirit": spirit,
        "items_gain": items_gain,
        "items_lose": items_lose,
        "note": note,
    }
