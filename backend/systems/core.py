from typing import Any
from backend.models.player import PlayerState
from backend.data.npcs_data import NPCS, NPC_FACTION, NPC_HABITS, NPC_STATE, LONG_DISTANCE_WANDERERS
from backend.data.factions import FACTIONS
from backend.data.maps_data import MAPS, MAP_LOCATIONS, LOCATION_KEYWORDS
from backend.systems.pathfinding import tile_at, can_step_between, find_path, apply_portal
from backend.systems.time_weather import is_night, shichen_name

def clamp_delta(d: dict[str, int]) -> dict[str, int]:
    keys = ("order", "truth", "hope", "chaos")
    out: dict[str, int] = {}
    for k in keys:
        v = int(d.get(k, 0))
        if v > 3:
            v = 3
        if v < -3:
            v = -3
        out[k] = v
    return out

def clamp_favor_delta(d: int) -> int:
    if d > 3:
        return 3
    if d < -3:
        return -3
    return d

def apply_favor(p: PlayerState, npc_id: str, delta: int | None) -> None:
    if delta is None:
        return
    d = clamp_favor_delta(delta)
    cur = int(p.favor.get(npc_id, 0))
    nxt = cur + d
    if nxt > 100:
        nxt = 100
    if nxt < -100:
        nxt = -100
    p.favor[npc_id] = nxt

def push_rumor(p: PlayerState, snippet: str) -> None:
    s = snippet.strip().replace("\n", " ")
    if len(s) > 180:
        s = s[:180] + "..."
    if not s:
        return
    p.rumors.append(s)
    if len(p.rumors) > 8:
        p.rumors = p.rumors[-8:]

def npc_ids_for_player(p: PlayerState) -> list[str]:
    out: list[str] = []
    for nid, meta in NPCS.items():
        if meta.get("always"):
            out.append(nid)
            continue
        cell = p.npc_positions.get(nid) if getattr(p, "npc_positions", None) else meta.get("cell")
        if cell and cell[0] == p.map_id and cell[1] == p.px and cell[2] == p.py:
            out.append(nid)
    hidden_here = [x for x in out if NPCS.get(x, {}).get("hidden")]
    normal_here = [x for x in out if not NPCS.get(x, {}).get("hidden")]
    merged: list[str] = []
    if "jiang" in normal_here:
        merged.append("jiang")
        normal_here = [x for x in normal_here if x != "jiang"]
    merged.extend(hidden_here)
    merged.extend(normal_here)
    # 身陷险局:只许与锁定对头交谈,风闻子暂不可切
    if getattr(p, "move_locked", False):
        lid = getattr(p, "move_lock_npc_id", None)
        if lid and str(lid) in NPCS:
            return [str(lid)]
    return merged

def move_should_fire_encounter(path: list[tuple[int, int]]) -> bool:
    """至少走过一格才触发「踏入」类际遇,避免原地无移动误触。"""
    return len(path) >= 2

def _reset_trap_state(p: PlayerState) -> None:
    p.move_locked = False
    p.move_lock_npc_id = None
    p.trap_reason = None
    p.trap_attempts = 0

def enter_trap_state(p: PlayerState, reason: str, lock_npc_id: str | None = None) -> None:
    """开启「身陷险局」。具体故事走向交给 LLM;这里只置标志位与一句白话起因。"""
    p.move_locked = True
    p.move_lock_npc_id = lock_npc_id or "jiang"
    p.trap_reason = (reason or "骤入险局").strip()[:80]
    p.trap_attempts = 0

def tile_hazard_reason(p: PlayerState) -> str | None:
    """当前格是否会自动陷入险局;返回一句白话起因,**不带分类**。"""
    ch = tile_at(p.map_id, p.px, p.py) or "."
    if ch == "&":
        return "草莽暗起,骤被围在当中。"
    if ch == "I":
        return "门闩落下,烛火忽暗--进的是局,不是栈。"
    if ch == "~":
        return "脚下水势骤回,半身陷于浊流。"
    return None

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

# ────────────────────── 险局脱困:完全交由 LLM + 属性 共同判定 ──────────────────────

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
            p.life_burn_max = 6
            p.life_burn_ticks = 6
            p.move_locked = True
            p.move_lock_npc_id = "jiang"
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
    """险境锁定的处理:只信 LLM 的 escape_outcome / enslaved 与属性兜底。

    llm_outcome ∈ {"success", "progress", "fail", None}
    llm_enslaved: LLM 写的一句被押作奴役/苦役的缘由(不致死,但失自由)。
    """
    if not getattr(p, "move_locked", False):
        return None
    if user_message.strip().startswith("[际遇"):
        return None
    lock_npc = getattr(p, "move_lock_npc_id", None)
    if lock_npc is not None and npc_id and npc_id != str(lock_npc):
        return None

    p.trap_attempts = int(getattr(p, "trap_attempts", 0)) + 1

    # 生命燃烧中:优先靠进食止损
    if int(getattr(p, "life_burn_ticks", 0)) > 0:
        if int(getattr(p, "vigor", 0)) > 0:
            p.life_burn_ticks = 0
            p.life_burn_max = 0
            _reset_trap_state(p)
            return {"outcome": "escaped", "reason": "进食回力,生命燃烧止息。"}
        return {"outcome": "struggling", "reason": "生命燃烧中,尽快进食。", "attempts": p.trap_attempts}

    # 属性兜底(致命/失自由)优先
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
        if p.trap_attempts >= 3:
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
    """
    自由文本中的生存动作:
    - 干粮/野果/打鱼:恢复
    - 睡觉:少量体力消耗、大量心气恢复,并清部分睡眠债
    """
    msg = (user_message or "").strip()
    if not msg:
        return {"vigor": 0, "spirit": 0, "items_gain": [], "items_lose": [], "note": ""}
    ch = tile_at(p.map_id, p.px, p.py) or "."

    items_gain: list[str] = []
    items_lose: list[str] = []
    vigor = 0
    spirit = 0
    note = ""

    if any(k in msg for k in ("吃干粮", "啃干粮", "干粮")) and int(p.inventory.get("干粮", 0)) > 0:
        p.inventory["干粮"] = max(0, int(p.inventory.get("干粮", 0)) - 1)
        if p.inventory["干粮"] <= 0:
            p.inventory.pop("干粮", None)
        vigor += apply_vigor_delta(p, +18)
        spirit += apply_spirit_delta(p, +6)
        items_lose.append("干粮")
        note = "你嚼了几口干粮,气力略回。"
    elif any(k in msg for k in ("打鱼", "捕鱼", "下网", "摸鱼")) and ch in ("~", "B"):
        vigor += apply_vigor_delta(p, -4)
        spirit += apply_spirit_delta(p, +2)
        p.inventory["鲜鱼"] = int(p.inventory.get("鲜鱼", 0)) + 1
        items_gain.append("鲜鱼")
        note = "你就着水势摸得一尾鲜鱼。"
    elif any(k in msg for k in ("野果", "采果", "摘果", "吃果")) and ch in ("F", "&", ","):
        vigor += apply_vigor_delta(p, +10)
        spirit += apply_spirit_delta(p, +4)
        note = "你在林地寻得野果,勉强充饥。"
    elif any(k in msg for k in ("睡", "歇息", "打盹", "合眼")):
        # 安全环境:客栈/寺廊恢复更强;荒野睡觉受罚
        safe = (ch in ("T", "Y")) or (p.map_id == "world" and p.px >= 22 and p.px <= 28 and p.py >= 5 and p.py <= 10)
        if safe:
            vigor += apply_vigor_delta(p, -2)
            spirit += apply_spirit_delta(p, +36)
            p.sleep_debt = max(0, int(getattr(p, "sleep_debt", 0)) - 14)
            note = "你在较安全处合眼调息,心气大幅回升。"
        else:
            vigor += apply_vigor_delta(p, -7)
            spirit += apply_spirit_delta(p, +12)
            p.sleep_debt = max(0, int(getattr(p, "sleep_debt", 0)) - 5)
            note = "荒野露宿,寒湿与警惕反噬了体力,只回了一点心气。"
    elif any(k in msg for k in ("攀爬", "爬坡", "翻越", "跳崖", "下崖")):
        p.allow_steep_next_move = True
        spirit += apply_spirit_delta(p, -3)
        note = "你决意冒险攀爬/跳降,下一次移动可强行越过陡差,但极易受伤。"

    # 进食后可中断生命燃烧
    if vigor > 0 and int(getattr(p, "life_burn_ticks", 0)) > 0:
        p.life_burn_ticks = 0
        p.life_burn_max = 0
        p.trap_reason = None
        p.move_locked = False
        p.move_lock_npc_id = None

    return {
        "vigor": vigor,
        "spirit": spirit,
        "items_gain": items_gain,
        "items_lose": items_lose,
        "note": note,
    }

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

# ── 天气驱动 NPC 游走行为 ──
# 恶劣天气下 NPC 会缩回室内/遮挡处，不随意走动
WEATHER_SHELTER = {"骤雨", "湿瘴", "重雾", "寒露", "夜霜"}
WEATHER_SLOW = {"薄雾", "风急", "闷热"}


def _weather_wander_multiplier(weather: str, night: bool) -> float:
    """天气对 NPC 游走概率的乘数：越恶劣越不愿走动。"""
    if weather in WEATHER_SHELTER:
        return 0.0  # 恶劣天气：NPC 不游走，缩在室内
    if weather in WEATHER_SLOW:
        return 0.4  # 不佳天气：游走概率减为 40%
    if weather == "晴" and not night:
        return 1.3  # 晴好白日：游走更活跃
    return 1.0


def _tile_is_sheltered(ch: str) -> bool:
    """判断地格是否为室内/有遮蔽的地点（NPC 躲雨的去处）。"""
    return ch in ("T", "Y", "M", "I")


def maybe_wander_npcs(p: PlayerState, ticks: int = 1) -> None:
    import random
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
        # 每 tick 小概率移动，保持"有限游走"；天气影响概率
        base_chance = 0.18 * ticks
        if weather_mult <= 0.0:
            continue  # 恶劣天气完全不走动
        if random.random() > base_chance * weather_mult:
            continue
        mid, x, y = pos
        anchor = meta.get("cell")
        unbounded = nid in LONG_DISTANCE_WANDERERS or bool(meta.get("wander_unbounded", False))
        anchor_radius = int(meta.get("wander_anchor_radius", 3) or 3)
        whitelist = meta.get("wander_maps_whitelist")
        if whitelist:
            allowed = {str(m) for m in whitelist}
            if mid not in allowed:
                # 若脏状态落在白名单外，拉回锚点
                if anchor and str(anchor[0]) in allowed:
                    p.npc_positions[nid] = (str(anchor[0]), int(anchor[1]), int(anchor[2]))
                continue
        rows = MAPS.get(mid, {}).get("rows", [])
        if not rows:
            continue
        # 夜晚荒郊野外：NPC 倾向就地休息，不再游走
        ch_here = rows[y][x]
        if night and ch_here in (",", "F", ";", "~", "&", "m", "/"):
            continue
        # 恶劣天气中未遮蔽的 NPC：优先向遮蔽处移动
        seek_shelter = p.weather in WEATHER_SHELTER and not _tile_is_sheltered(ch_here)
        cands: list[tuple[str, int, int]] = []
        shelter_cands: list[tuple[str, int, int]] = []
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if ny < 0 or ny >= len(rows) or nx < 0 or nx >= len(rows[0]):
                continue
            a = rows[y][x]
            b = rows[ny][nx]
            if can_step_between(a, b):
                if whitelist and mid not in {str(m) for m in whitelist}:
                    continue
                if (not unbounded) and anchor:
                    am, ax, ay = str(anchor[0]), int(anchor[1]), int(anchor[2])
                    # 固定 NPC：限制在锚点附近游走，防止长期漂移
                    if mid != am:
                        continue
                    if abs(nx - ax) + abs(ny - ay) > anchor_radius:
                        continue
                if seek_shelter and _tile_is_sheltered(b):
                    shelter_cands.append((mid, nx, ny))
                else:
                    cands.append((mid, nx, ny))
        # 风雨中 NPC 优先躲进室内
        if seek_shelter and shelter_cands:
            p.npc_positions[nid] = random.choice(shelter_cands)
        elif cands:
            p.npc_positions[nid] = random.choice(cands)

def update_npc_states_from_habits(p: PlayerState) -> dict[str, str]:
    """基于 NPC_HABITS 的活跃时段自动更新 NPC 状态(CMA式状态感知)。

    每个 NPC 根据当前时辰与自身的活跃区间、昼行/夜行偏好,
    自动切换 idle/resting/busy 状态,让世界自然呼吸。

    返回变更字典 {npc_id: old_state → new_state}。"""
    if not getattr(p, "npc_states", None):
        p.npc_states = {}

    changes: dict[str, str] = {}
    sh = int(getattr(p, "world_shichen", 6) or 6)  # 0-11 (mod 12)


    for nid, habits in NPC_HABITS.items():
        meta = NPCS.get(nid, {})
        if meta.get("always") or meta.get("hidden"):
            continue  # 风闻子与隐藏NPC不受此规则

        a0, a1 = habits.get("active", (4, 21))
        a0_mod, a1_mod = a0 % 12, a1 % 12

        # 活跃时段判定:支持跨午夜区间(如 18-29 → 6-5)
        if a0 <= a1:
            in_active = (a0_mod <= sh <= a1_mod)
        else:
            # 跨午夜区间 wrap around
            in_active = (sh >= a0_mod or sh <= a1_mod)

        # 强制深夜休憩:子时丑时寅时非夜行NPC resting
        # 夜行 NPC（nocturnal=True）不受此限制，它们在夜间反而更活跃
        if sh in (0, 1, 2):  # 子、丑、寅
            if not habits.get("nocturnal", False):
                in_active = False

        old_state = p.npc_states.get(nid, "idle")
        new_state = "idle" if in_active else "resting"

        if new_state != old_state:
            p.npc_states[nid] = new_state
            changes[nid] = f"{old_state}→{new_state}"

    # ── NPC 情绪自然衰减:随时间回归中性(情感计算闭环)──
    sh_name = shichen_name(p.world_shichen)
    for nid, mind in list(getattr(p, "minds", {}).items()):
        if mind is not None and hasattr(mind, "affect_valence"):
            mind.mood_decay_tick(sh_name)

    return changes


def update_npc_state_dynamic(p: PlayerState, npc_id: str) -> str | None:
    """基于玩家声望、好感、当前处境动态调整单个 NPC 的行为状态。

    与 update_npc_states_from_habits（纯时间驱动）互补：
    - 时间决定 NPC 的基础作息（idle/resting）
    - 此函数叠加玩家因素（alert/hostile），让 NPC 对「你」的态度有记忆

    在对话前调用，确保 NPC 的状态反映了其对玩家的真实态度。
    返回新状态字符串，若无变更返回 None。
    """
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

    # 判定优先级：hostile > alert > 恢复中性
    if rep_v <= -25 or fav <= -30:
        new_state = "hostile"
    elif rep_v <= -8 or fav <= -8 or is_trap_target:
        new_state = "alert"
    else:
        # 关系已恢复 → 回退到中立状态，由时间驱动接管
        if current in ("hostile", "alert"):
            new_state = "idle"
        else:
            return None

    if new_state != current:
        p.npc_states[npc_id] = new_state
        return new_state
    return None


def update_all_npc_states_dynamic(p: PlayerState) -> dict[str, str]:
    """对所有已存在的 NPC 状态进行动态评估。

    在移动后调用，确保前端显示的 NPC 状态图标反映玩家声望。

    Returns:
        {npc_id: old→new} 变更字典。
    """
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
    """NPC 状态感知:将 NPC 当前状态注入对话提示。

    让 NPC 的回应与其作息状态一致--深夜休憩的 NPC 说话更短、更不耐烦。
    状态决定语气、语速、耐心程度。

    2026-05-24 改进：alert/hostile 状态附加声望/好感原因，让 NPC 态度有据可循。"""
    from backend.data.npcs_data import NPC_STATE
    from backend.systems.time_weather import is_night

    state = getattr(p, "npc_states", {}).get(npc_id, "idle")
    night = is_night(p.world_shichen)

    # 状态 → 行为指引
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
        return ""  # idle 状态不需要特别提示

    # ── 动态态度溯源：让 NPC 知道为什么提防/敌视这个玩家 ──
    attitude_context = ""
    if state in ("alert", "hostile"):
        fac = NPC_FACTION.get(npc_id)
        rep_v = int(p.reputation.get(fac, 0)) if fac else 0
        fav = int(p.favor.get(npc_id, 0))
        reasons: list[str] = []
        if fac and rep_v <= -25:
            reasons.append(f"此人在{FACTIONS.get(fac, fac)}里声名狼藉（{rep_v:+d}），早就不是一路人")
        elif fac and rep_v <= -8:
            reasons.append(f"此人在{FACTIONS.get(fac, fac)}名声不佳（{rep_v:+d}），你对他没好感")
        if fav <= -30:
            reasons.append(f"你与此人旧怨极深（好感{fav:+d}），见他就烦")
        elif fav <= -8:
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
    """天气感知注入：让 NPC 的言行与天气一致——雨天会抖蓑衣、雾天会警觉、
    晴天会更放松。NPC 不应在滂沱大雨中说「今天天气不错」。

    返回空字符串表示天气无需额外提示（晴好天气 NPC 表现如常）。"""
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


def val_in_range(v: int, lo: int, hi: int) -> bool:
    return lo <= v <= hi

def tile_forced_encounter(p: PlayerState) -> dict[str, Any] | None:
    """当前格有隐藏 NPC 且地格符号匹配时,供移动接口返回强制剧情引信。"""
    ch = tile_at(p.map_id, p.px, p.py) or "."
    for nid, meta in NPCS.items():
        if not meta.get("hidden"):
            continue
        cell = meta.get("cell")
        if not cell or cell[0] != p.map_id or cell[1] != p.px or cell[2] != p.py:
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
    """非 LLM 的随机横死(真实江湖模式);结合时辰、天气、声望与气运。"""
    import random

    ch = tile_at(p.map_id, p.px, p.py) or "."
    base = {"I": 0.10, "&": 0.08, "~": 0.04}.get(ch, 0.0)
    if base <= 0:
        return None

    # 夜里更危险
    night_mult = 1.6 if is_night(p.world_shichen) else 1.0
    # 雨雾减损视野,水路加重
    weather_mult = 1.0
    if p.weather in ("骤雨", "湿瘴"):
        weather_mult = 1.4 if ch == "~" else 1.15
    elif p.weather in ("重雾", "薄雾"):
        weather_mult = 1.25
    # 绿林声望高,剪径与黑店少为难;漕帮高,水路稍宽
    rep_mult = 1.0
    lulin = int(p.reputation.get("lulin", 0))
    caobang = int(p.reputation.get("caobang", 0))
    if ch in ("&", "I") and lulin >= 20:
        rep_mult *= 0.5
    if ch == "~" and caobang >= 20:
        rep_mult *= 0.6
    # 怀里没钱,黑店反而懒得动手;钱多了招贼
    if ch == "I":
        if p.coins <= 20:
            rep_mult *= 0.4
        elif p.coins >= 300:
            rep_mult *= 1.4

    p_die = max(0.0, min(0.5, base * night_mult * weather_mult * rep_mult))
    if random.random() >= p_die:
        return None

    if ch == "I":
        return "蒙汗药翻肠,黑店不留客。"
    if ch == "&":
        return "剪径贼从芦荡里起,刀光比话快。"
    if ch == "~":
        return "水鬼与暗流同来,尸骨不必上岸。"
    return None

def relevant_events_for(p: PlayerState, npc_id: str, k: int = 4) -> list[dict[str, Any]]:
    """挑选与该 NPC 最相关的近期事件(同势力/同图/通用风闻),最多 k 条。"""
    if not p.events:
        return []
    fac = NPC_FACTION.get(npc_id)
    npc_meta = NPCS.get(npc_id) or {}
    npc_map = (npc_meta.get("cell") or (None,))[0]
    out: list[dict[str, Any]] = []
    for e in reversed(p.events):
        # 后向取近,最多 k;不严格过滤,仅打分
        out.append(e)
        if len(out) >= k:
            break
    out.reverse()
    # 风闻子吃所有事件;其他人偏向相关
    if npc_id == "jiang":
        return out
    # 简易相关:actor 与 npc 同势力/同图
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
    from backend.systems.time_weather import shichen_name, shichen_phase
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
        tag = f"[{e['shichen']}]"
        lines.append(f"· {tag} {e['text']}")
    return "\n".join(lines)
