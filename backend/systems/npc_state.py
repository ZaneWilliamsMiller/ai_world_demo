"""NPC 状态管理、游走、天气感知。

从 systems/core.py 拆分而来，职责：
- NPC 状态管理（时间驱动 + 动态态度）
- NPC 游走行为
- NPC 天气感知注入
- NPC 状态感知对话注入
"""
from __future__ import annotations

from backend.data.factions import FACTIONS
from backend.data.maps_data import LOCATION_KEYWORDS, MAP_LOCATIONS, MAPS
from backend.data.npcs_data import LONG_DISTANCE_WANDERERS, NPC_FACTION, NPC_HABITS, NPC_STATE, NPCS
from backend.models.player import PlayerState
from backend.systems.constants import (
    NPC_ALERT_FAVOR_THRESHOLD,
    NPC_ALERT_REP_THRESHOLD,
    NPC_HOSTILE_FAVOR_THRESHOLD,
    NPC_HOSTILE_REP_THRESHOLD,
    NPC_WANDER_BASE_CHANCE,
)
from backend.systems.pathfinding import can_step_between
from backend.systems.time_weather import is_night, shichen_name

# ── 天气驱动 NPC 游走行为 ──
WEATHER_SHELTER = {"骤雨", "湿瘴", "重雾", "寒露", "夜霜"}
WEATHER_SLOW = {"薄雾", "风急", "闷热"}


def _weather_wander_multiplier(weather: str, night: bool) -> float:
    if weather in WEATHER_SHELTER:
        return 0.0
    if weather in WEATHER_SLOW:
        return 0.4
    if weather == "晴" and not night:
        return 1.3
    return 1.0


def _tile_is_sheltered(ch: str) -> bool:
    return ch in ("T", "Y", "M", "I")


def maybe_wander_npcs(p: PlayerState, ticks: int = 1) -> None:
    import random

    from backend.systems.core import init_npc_positions
    if ticks <= 0:
        return
    init_npc_positions(p)
    dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))
    night = is_night(p.world_shichen)
    weather_mult = _weather_wander_multiplier(p.weather, night)
    for nid, pos in list(p.npc_positions.items()):
        meta = NPCS.get(nid, {})
        if meta.get("always") or meta.get("hidden"):
            continue
        base_chance = NPC_WANDER_BASE_CHANCE * ticks
        if weather_mult <= 0.0:
            continue
        if random.random() > base_chance * weather_mult:
            continue
        if not isinstance(pos, (list, tuple)) or len(pos) < 3:
            continue
        mid, x, y = str(pos[0]), int(pos[1]), int(pos[2])
        anchor = meta.get("cell")
        unbounded = nid in LONG_DISTANCE_WANDERERS or bool(meta.get("wander_unbounded", False))
        anchor_radius = int(meta.get("wander_anchor_radius", 3) or 3)
        whitelist = meta.get("wander_maps_whitelist")
        if whitelist:
            allowed = {str(m) for m in whitelist}
            if mid not in allowed:
                if anchor and str(anchor[0]) in allowed:
                    p.npc_positions[nid] = (str(anchor[0]), int(anchor[1]), int(anchor[2]))
                continue
        rows = MAPS.get(mid, {}).get("rows", [])
        if not rows:
            continue
        if y < 0 or y >= len(rows) or x < 0 or x >= len(rows[y]):
            continue
        ch_here = rows[y][x]
        if night and ch_here in (",", "F", ";", "~", "&", "m", "/"):
            continue
        seek_shelter = p.weather in WEATHER_SHELTER and not _tile_is_sheltered(ch_here)
        cands: list[tuple[str, int, int]] = []
        shelter_cands: list[tuple[str, int, int]] = []
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if ny < 0 or ny >= len(rows) or nx < 0 or nx >= len(rows[ny]):
                continue
            a = rows[y][x]
            b = rows[ny][nx]
            if can_step_between(a, b):
                if whitelist and mid not in {str(m) for m in whitelist}:
                    continue
                if (not unbounded) and anchor:
                    am, ax, ay = str(anchor[0]), int(anchor[1]), int(anchor[2])
                    if mid != am:
                        continue
                    if abs(nx - ax) + abs(ny - ay) > anchor_radius:
                        continue
                if seek_shelter and _tile_is_sheltered(b):
                    shelter_cands.append((mid, nx, ny))
                else:
                    cands.append((mid, nx, ny))
        if seek_shelter and shelter_cands:
            p.npc_positions[nid] = random.choice(shelter_cands)
        elif cands:
            p.npc_positions[nid] = random.choice(cands)


def _parse_plan_target(plan_text: str) -> tuple[str, int, int] | None:
    """从计划文本中解析目标地点坐标（长关键词优先匹配）。"""
    sorted_kw = sorted(LOCATION_KEYWORDS.keys(), key=len, reverse=True)
    for kw in sorted_kw:
        if kw in plan_text:
            map_id, loc_name = LOCATION_KEYWORDS[kw]
            coords = MAP_LOCATIONS.get(map_id, {}).get(loc_name)
            if coords:
                return (map_id, coords[0], coords[1])
    return None


def plan_driven_step(p: PlayerState, npc_id: str, mind: object) -> tuple[str, int, int] | None:
    """基于计划的定向移动一步。"""
    pos = p.npc_positions.get(npc_id)
    if not pos or not isinstance(pos, (list, tuple)) or len(pos) < 3:
        return None

    mid, x, y = str(pos[0]), int(pos[1]), int(pos[2])
    sh_name = shichen_name(p.world_shichen)
    plan = mind.plan_by_shichen.get(sh_name, "")
    if not plan:
        return None

    target = _parse_plan_target(plan)
    if target is None:
        return None

    target_mid, tx, ty = target
    if target_mid != mid:
        return None

    if x == tx and y == ty:
        return None

    rows = MAPS.get(mid, {}).get("rows", [])
    if not rows:
        return None

    if y < 0 or y >= len(rows) or x < 0 or x >= len(rows[y]):
        return None

    dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))
    best: tuple[str, int, int] | None = None
    best_dist = abs(x - tx) + abs(y - ty)

    for dx, dy in dirs:
        nx, ny = x + dx, y + dy
        if ny < 0 or ny >= len(rows) or nx < 0 or nx >= len(rows[ny]):
            continue
        a = rows[y][x]
        b = rows[ny][nx]
        if not can_step_between(a, b):
            continue
        dist = abs(nx - tx) + abs(ny - ty)
        if dist < best_dist:
            best = (mid, nx, ny)
            best_dist = dist

    return best


def is_active_at(active_val: tuple | list, sh: int, *, nocturnal: bool = False) -> bool:
    """判断 NPC 在时辰 sh 是否处于活跃时段。

    active_val: (start, end) 24小时制，如 (18, 29) 表示 18:00 到次日 05:00。
    sh: 当前时辰 0-11（子时=0, 丑时=1, ..., 亥时=11）。
    nocturnal: 是否为夜行 NPC（影响子时/丑时/寅时的判定）。
    """
    if not isinstance(active_val, (list, tuple)) or len(active_val) < 2:
        return True
    a0, a1 = int(active_val[0]), int(active_val[1])
    hour = (sh * 2 + 23) % 24
    in_active = (a0 <= hour <= a1) or (a0 <= hour + 24 <= a1)
    if sh in (0, 1, 2) and not nocturnal:
        in_active = False
    return in_active


def update_npc_states_from_habits(p: PlayerState) -> dict[str, str]:
    """基于 NPC_HABITS 的活跃时段自动更新 NPC 状态。"""
    if not getattr(p, "npc_states", None):
        p.npc_states = {}

    changes: dict[str, str] = {}
    raw_sh = getattr(p, "world_shichen", None)
    sh = int(raw_sh) if raw_sh is not None else 6

    for nid, habits in NPC_HABITS.items():
        meta = NPCS.get(nid, {})
        if meta.get("always") or meta.get("hidden"):
            continue

        active_val = habits.get("active", (4, 21))
        nocturnal = habits.get("nocturnal", False)
        in_active = is_active_at(active_val, sh, nocturnal=nocturnal)

        old_state = p.npc_states.get(nid, "idle")
        new_state = "idle" if in_active else "resting"

        if new_state != old_state:
            p.npc_states[nid] = new_state
            changes[nid] = f"{old_state}→{new_state}"

    # NPC 情绪自然衰减
    sh_name = shichen_name(p.world_shichen)
    for nid, mind in list(getattr(p, "minds", {}).items()):
        if mind is not None and hasattr(mind, "affect_valence"):
            mind.mood_decay_tick(sh_name)

    return changes


def update_npc_state_dynamic(p: PlayerState, npc_id: str) -> str | None:
    """基于玩家声望、好感、当前处境动态调整单个 NPC 的行为状态。"""
    if not getattr(p, "npc_states", None):
        p.npc_states = {}

    meta = NPCS.get(npc_id, {})
    if meta.get("always") or meta.get("hidden"):
        return None

    current = p.npc_states.get(npc_id, "idle")
    fac = NPC_FACTION.get(npc_id)
    rep_v = int(p.reputation.get(fac, 0)) if fac else 0
    fav = int(p.favor.get(npc_id, 0))

    is_trap_target = (
        getattr(p, "move_locked", False)
        and getattr(p, "move_lock_npc_id", None) == npc_id
    )

    if rep_v <= NPC_HOSTILE_REP_THRESHOLD or fav <= NPC_HOSTILE_FAVOR_THRESHOLD:
        new_state = "hostile"
    elif rep_v <= NPC_ALERT_REP_THRESHOLD or fav <= NPC_ALERT_FAVOR_THRESHOLD or is_trap_target:
        new_state = "alert"
    elif current in ("hostile", "alert"):
        new_state = "idle"
    else:
        return None

    if new_state != current:
        p.npc_states[npc_id] = new_state
        return new_state
    return None


def update_all_npc_states_dynamic(p: PlayerState) -> dict[str, str]:
    """对所有已存在的 NPC 状态进行动态评估。"""
    changes: dict[str, str] = {}
    for nid in NPCS:
        meta = NPCS.get(nid, {})
        if meta.get("always") or meta.get("hidden"):
            continue
        old = p.npc_states.get(nid, "idle") if hasattr(p, "npc_states") else "idle"
        result = update_npc_state_dynamic(p, nid)
        if result:
            changes[nid] = f"{old}→{result}"
    return changes


def npc_state_for_dialogue(p: PlayerState, npc_id: str) -> str:
    """NPC 状态感知:将 NPC 当前状态注入对话提示。"""
    state = getattr(p, "npc_states", {}).get(npc_id, "idle")
    night = is_night(p.world_shichen)

    STATE_BEHAVIOR = {
        "resting": (
            "你正倚着、半寐着。有人来扰你清静。"
            + ("深夜被人搅醒,心里窝着火。语气倦怠、带三分火气,回话尽量短(2~5句),可直接下逐客令。"
               if night else "困倦不爱挪动,言语简短,能推便推。回话尽量短(3~6句)。")
        ),
        "busy": "你正忙着料理事务,手上停个不停。说话急促简短,少有空隙胡扯。若非必要,可请对方自便。",
        "alert": "你隐隐觉得不对劲。话里有话,暗中留意对方举动。言语谨慎、不露声色地试探。",
        "hostile": "来者不善。你摆出不好惹的派头,准备撕破脸。语气带刺、寸步不让。",
        "traveling": "你正赶路,脚下匆匆,未必愿意停下细聊。可点个头继续走,或停下简短回一句。",
        "idle": "",
    }

    behavior = STATE_BEHAVIOR.get(state, "")
    if not behavior:
        return ""

    attitude_context = ""
    if state in ("alert", "hostile"):
        fac = NPC_FACTION.get(npc_id)
        rep_v = int(p.reputation.get(fac, 0)) if fac else 0
        fav = int(p.favor.get(npc_id, 0))
        reasons: list[str] = []
        if fac and rep_v <= NPC_HOSTILE_REP_THRESHOLD:
            reasons.append(f"此人在{FACTIONS.get(fac, fac)}里声名狼藉（{rep_v:+d}），早就不是一路人")
        elif fac and rep_v <= NPC_ALERT_REP_THRESHOLD:
            reasons.append(f"此人在{FACTIONS.get(fac, fac)}名声不佳（{rep_v:+d}），你对他没好感")
        if fav <= NPC_HOSTILE_FAVOR_THRESHOLD:
            reasons.append(f"你与此人旧怨极深（好感{fav:+d}），见他就烦")
        elif fav <= NPC_ALERT_FAVOR_THRESHOLD:
            reasons.append(f"你与此人有些过节（好感{fav:+d}）")
        if reasons:
            attitude_context = "\n".join(f"· {r}" for r in reasons)

    state_meta = NPC_STATE.get(state, {})
    label = state_meta.get("label", state)
    icon = state_meta.get("icon", "")

    lines = [
        f"【你现在状态】{icon} {label}",
        f"· {behavior}",
    ]
    if attitude_context:
        lines.append(attitude_context)
    lines.append("· 不要复述此提示块--把状态写进语气、语速、回话长短里。")
    return "\n".join(lines)


def npc_weather_awareness_block(p: PlayerState) -> str:
    """天气感知注入。"""
    weather = p.weather
    night = is_night(p.world_shichen)

    WEATHER_BEHAVIOR: dict[str, str] = {
        "骤雨": (
            "外面正下着瓢泼大雨。你身上可能淋湿了，若是在室内则能听见瓦上雨声像擂鼓。"
            + "说话比平时急三分，动作也快——谁都不想在大雨里多待。"
            + (" 夜雨更添寒意，语气里会不自觉地带上几分对这场雨的抱怨。" if night else "")
        ),
        "湿瘴": (
            "空气又湿又闷，水汽像贴在皮肤上。呼吸比平时沉，说话时偶尔清一清嗓子。"
            + "你隐约觉得有些不安——这种天气什么都容易霉，包括人心。"
        ),
        "重雾": (
            "浓雾锁住视线，三尺之外人鬼莫辨。你的警觉比平时高——"
            + "雾里什么都可能藏着。说话声量会下意识压低一些，偶尔侧耳去听雾里的动静。"
        ),
        "薄雾": (
            "薄雾像纱帐罩着四周，视线有些模糊但不妨碍走路。"
            + "你比平时更留意身后的脚步——雾天水汽传声，时远时近。"
        ),
        "风急": (
            "风刮得紧，吹得幌子、衣角都猎猎作响。你说话得稍大声些才听得清，"
            + "时不时要按住被风掀起的物什。语气里带着对这场风的不耐。"
        ),
        "寒露": (
            "露水很重，空气凉得像刚从井里提上来的。你下意识拢了拢衣襟，"
            + "说话时偶尔搓一搓手——不是因为怕，是因为冷。"
        ),
        "夜霜": (
            "霜花结在瓦上、草尖上，月光一照像碎银。你呼出的气都成了白雾。"
            + "夜越深越冷，你说话简短、动作利索——多说一字就多漏一口热气。"
        ),
        "闷热": (
            "天气闷热无风，汗黏在背上。你有些烦躁，话也比平时少——"
            + "不是不愿意说，是天太闷了懒得开口。扇子若有若无地摇。"
        ),
    }

    behavior = WEATHER_BEHAVIOR.get(weather, "")
    if not behavior:
        return ""

    lines = [
        "【此时天气影响你的举止】",
        f"· {behavior}",
        "· 把天气写进你的小动作、语气和用词里——但不要原句宣告天气。",
    ]
    return "\n".join(lines)
