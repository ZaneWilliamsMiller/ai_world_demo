from __future__ import annotations
"""动态奇遇系统：基于世界状态生成上下文感知的叙事碎片

设计理念（2026 AI前沿落地）：
- 参照 ai-paracosm 的 Multi-Agent 叙事生成思路，LLM 不是随机数生成器，
  而是能根据世界上下文做出「更有逻辑的随机」
- 参照腾讯AI剧本杀的动态叙事引擎，根据玩家当前状态（位置、时辰、天气、
  声望、背包、风闻）实时生成情境碎片
- 不是硬编码的遭遇表，而是上下文驱动的叙事片段，可产生蝴蝶效应

触发机制：
- 每次移动后有一定概率触发（12%，夜间+5%，恶劣天气+5%）
- 非战斗类，不锁死玩家：是一段氛围描写 + 可选的行动提示
- 产出存入风闻或事件流，供后续对话引用

奇遇-对话桥接（SITS2026「感知代理→向量记忆」架构落地）：
- 当动态奇遇触发时，将生成的场景碎片注入同地图NPC的记忆流
- NPC在后续对话中能自然提及这些世界事件（"方才我好像听到..."）
- 实现去中心化的叙事记忆网络，让世界「活着」的证据渗透到NPC口中

关键区别于 tile_forced_encounter：
- forced_encounter 是「你被锁住了必须周旋」
- dynamic_encounter 是「你瞥见/听到/嗅到了什么」，是叙事碎片，不强制
"""
import json
import random
import logging
from typing import Any

from backend.models.player import PlayerState
from backend.data.npcs_data import NPCS, NPC_FACTION
from backend.data.maps_data import MAPS
from backend.data.factions import FACTIONS
from backend.data.atmosphere import tile_atmosphere, WORLD_REGIONS
from backend.systems.pathfinding import tile_at
from backend.systems.time_weather import shichen_name, is_night

log = logging.getLogger("encounter")

# ─── 触发概率 ───
BASE_CHANCE = 0.12          # 基础触发概率 12%
NIGHT_BONUS = 0.05          # 夜间 +5%
BAD_WEATHER_BONUS = 0.05    # 恶劣天气 +5%
WILD_BONUS = 0.06           # 荒野 +6%
LOW_SPIRIT_BONUS = 0.04     # 心气 <30 时 +4%
COOLDOWN_TICKS = 6          # 两次奇遇间至少间隔6时辰

BAD_WEATHERS = {"骤雨", "湿瘴", "重雾", "风急"}

# 非城区为野外（触发奇遇概率更高）
def _is_wild(p: PlayerState) -> bool:
    """判断玩家是否在野外（非安全城区）。"""
    # 县城区域 (x:10-50, y:25-45) 视作安全区
    if 10 <= p.px <= 50 and 25 <= p.py <= 45:
        return False
    # 寺庙区域 (x:40-65, y:10-25) 视作安全区
    if 40 <= p.px <= 65 and 10 <= p.py <= 25:
        return False
    # 关塞区域 (x:60-90, y:4-14) 视作安全区
    if 60 <= p.px <= 90 and 4 <= p.py <= 14:
        return False
    # 渡口区域 (x:70-100, y:42-62) 视作安全区
    if 70 <= p.px <= 100 and 42 <= p.py <= 62:
        return False
    return True

# ── 奇遇感知注入到对话的标记词 ──
ENCOUNTER_PERCEPTION_PREFIX = "方才在"  # 记忆流中奇遇感知记忆的识别前缀


def should_trigger_encounter(p: PlayerState) -> bool:
    """判断本次移动是否触发动态奇遇"""
    # 冷却检查：距上次奇遇不足6时辰则不触发
    last_enc_tick = int(getattr(p, "last_dynamic_encounter_tick", 0) or 0)
    cur_tick = int(getattr(p, "world_tick", 0) or 0)
    if cur_tick - last_enc_tick < COOLDOWN_TICKS:
        return False

    chance = BASE_CHANCE
    if is_night(p.world_shichen):
        chance += NIGHT_BONUS
    if p.weather in BAD_WEATHERS:
        chance += BAD_WEATHER_BONUS
    if _is_wild(p):
        chance += WILD_BONUS
    spirit = int(getattr(p, "spirit", 80) or 0)
    if spirit < 30:
        chance += LOW_SPIRIT_BONUS

    return random.random() < chance


def _build_encounter_context(p: PlayerState) -> str:
    """构建给LLM的上下文，让LLM基于世界状态生成合理的奇遇碎片"""
    from backend.systems.time_weather import shichen_phase
    sh = shichen_name(p.world_shichen)
    phase = shichen_phase(p.world_shichen)
    night = "夜" if is_night(p.world_shichen) else "昼"
    map_name = MAPS.get(p.map_id, {}).get("name", p.map_id)

    ch = tile_at(p.map_id, p.px, p.py) or "."
    tile_desc = tile_atmosphere(ch)

    # 近期风闻（取最新2条）
    recent_rumors = list(p.rumors[-2:]) if p.rumors else []

    # 近期事件（取最新2条）
    recent_events = []
    for e in (p.events or [])[-2:]:
        recent_events.append(e.get("text", ""))

    # 此地NPC
    from backend.systems.core import npc_ids_for_player
    npcs_here = []
    for nid in npc_ids_for_player(p):
        meta = NPCS.get(nid, {})
        npcs_here.append(f"{meta.get('name', nid)}（{meta.get('short', nid)}）")

    # 声望摘要
    rep_bits = []
    for k, v in p.reputation.items():
        if v != 0:
            rep_bits.append(f"{FACTIONS.get(k, k)}{v:+d}")

    # 背包亮点
    inv_highlights = []
    for item, count in sorted((p.inventory or {}).items()):
        inv_highlights.append(f"{item}×{count}" if count > 1 else item)

    parts = [
        f"【世态】第{p.world_day}日·{sh}（{phase}·{night}）·天气「{p.weather}」·地图「{map_name}」",
        f"【所在】{tile_desc}",
    ]
    if npcs_here:
        parts.append(f"【近处有人】{'、'.join(npcs_here[:5])}")
    if recent_rumors:
        parts.append(f"【最近风闻】{'；'.join(recent_rumors)}")
    if recent_events:
        parts.append(f"【近日事】{'；'.join(recent_events)}")
    if rep_bits:
        parts.append(f"【声望】{' '.join(rep_bits)}")
    if inv_highlights:
        parts.append(f"【随身】{'、'.join(inv_highlights[:5])}")

    return "\n".join(parts)


async def generate_dynamic_encounter(p: PlayerState) -> dict[str, Any] | None:
    """生成一次动态奇遇叙事碎片

    返回：
    {
        "scene": str,          # 叙事碎片（2~4句氛围+事件描写）
        "hint": str | None,    # 可选的行动暗示
        "scope": str,          # "near" | "world"
    }
    或 None（LLM调用失败时回退到纯文本模板）
    """
    ctx = _build_encounter_context(p)

    messages = [
        {
            "role": "system",
            "content": (
                "你是「青笺录」江湖的动态叙事引擎。根据当前世界状态，生成一段2~4句的"
                "情境碎片——玩家瞥见、听到、嗅到、或直觉感到的事。\n\n"
                "规则：\n"
                "· 不是战斗遭遇，不锁住玩家，只是世界在「活着」的证据\n"
                "· 可以是：远处的异动、路人的闲语、一道不寻常的影子、一封被遗弃的信、"
                "一阵不该出现在此地的气味、一条隐约可闻的暗号……\n"
                "· 要与当前时辰、天气、地点、风闻呼应——夜里荒野不宜出现集市叫卖\n"
                "· 偶尔（约30%概率）暗示一条后续可追的线索，但不要每次都给线索\n"
                "· 文风：武侠白话，短句为主，善用通感与留白，不用现代词\n\n"
                "输出JSON：\n"
                '{"scene": "叙事碎片正文", "hint": "行动暗示或null", "scope": "near或world"}'
            ),
        },
        {"role": "user", "content": ctx},
    ]

    try:
        from backend.llm_client import chat_completion
        raw = await chat_completion(
            messages,
            temperature=0.92,
            max_tokens=200,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(raw)
        scene = parsed.get("scene", "").strip()
        if not scene:
            return None
        return {
            "scene": scene,
            "hint": parsed.get("hint") or None,
            "scope": parsed.get("scope", "near"),
        }
    except Exception as e:
        log.warning("动态奇遇LLM生成失败: %s", e)
        return _fallback_encounter(p)


def _fallback_encounter(p: PlayerState) -> dict[str, Any]:
    """LLM不可用时的纯文本奇遇模板"""
    map_name = MAPS.get(p.map_id, {}).get("name", p.map_id)
    ch = tile_at(p.map_id, p.px, p.py) or "."
    tile_desc = tile_atmosphere(ch)
    night = is_night(p.world_shichen)

    templates = [
        {"scene": f"{tile_desc}你隐约觉得此处比来时更静了些。", "hint": None, "scope": "near"},
        {"scene": f"风从{map_name}的方向送来一丝不属于此地的烟味。", "hint": "或许可以找人问问来路。", "scope": "near"},
        {"scene": "远处有人影一闪，等你定睛去看，只剩暮色。", "hint": None, "scope": "near"},
        {"scene": "脚下的泥里踩到一片碎瓷——不是碗，像是官窑的残片。", "hint": "或许附近有人丢过什么。", "scope": "near"},
    ]
    if night:
        templates.append({"scene": "夜风里混着一声不像是猫叫的啼声，从墙那头过来又消失了。", "hint": "可向风闻子打听此间夜事。", "scope": "near"})

    return random.choice(templates)


def apply_encounter(p: PlayerState, encounter: dict[str, Any]) -> None:
    """将奇遇写入世界状态，并注入同地图NPC记忆流（奇遇-对话桥接）

    SITS2026「感知代理→向量记忆」架构落地：
    世界事件不应只存在于事件流中，而应渗透到NPC的感知记忆里。
    当动态奇遇触发时，同地图的NPC会获得一条「感知记忆」，
    使他们在后续对话中能自然提及这些世界事件。

    记忆注入策略（NPC性格差异化）：
    - 风闻子：所有奇遇必入记忆（职业敏感性，importance+2）
    - 夜行NPC（hei/jianfei/shuizu）：夜间奇遇记忆更深（importance+1）
    - 同势力NPC：与势力相关的事件记忆更深
    - 其他NPC：基础重要性，但可能「没留意到」
    """
    from backend.systems.reputation import push_event
    from backend.systems.core import push_rumor, npc_ids_for_player
    from backend.game_state import get_or_init_mind
    from backend import agent_brain, memory as mem

    scene = encounter.get("scene", "")
    hint = encounter.get("hint")
    scope = encounter.get("scope", "near")

    if not scene:
        return

    # 写入事件流
    push_event(p, f"际遇：{scene}", scope=scope, actor="天意")

    # 如果有暗示，写入风闻
    if hint:
        push_rumor(p, f"际遇余响——{hint}")

    # ── 奇遇-对话桥接：将叙事碎片注入同地图NPC的记忆流 ──
    sh_now = shichen_name(p.world_shichen)
    night = is_night(p.world_shichen)
    map_name = MAPS.get(p.map_id, {}).get("name", p.map_id)

    # 遍历同地图的所有可见NPC
    for nid, meta in NPCS.items():
        if meta.get("hidden"):
            continue
        # 只注入同地图的NPC（包括玩家当前格和附近的）
        cell = meta.get("cell")
        if not cell or cell[0] != p.map_id:
            # 也检查游走中的NPC
            npc_pos = p.npc_positions.get(nid)
            if not npc_pos or npc_pos[0] != p.map_id:
                continue

        npc_short = meta.get("short", nid)
        npc_name = meta.get("name", nid)

        # 记忆重要性差异化：基于NPC身份
        base_importance = 4.0  # 默认：中等，像是"似乎有点什么动静"

        # 风闻子：职业敏感，所有奇遇都记
        if nid == "jiang":
            base_importance = 7.0  # 高——"这等事哪能逃过我的耳目"
        # 夜行NPC：夜间奇遇更敏锐
        elif nid in ("hei", "jianfei", "shuizu") and night:
            base_importance = 5.5  # 中高——"夜里的事我门儿清"
        # 同势力NPC：势力相关事件更重要
        else:
            npc_fac = NPC_FACTION.get(nid)
            if npc_fac:
                # 检查奇遇场景是否含有势力关键词
                fac_name = FACTIONS.get(npc_fac, "")
                if fac_name and fac_name in scene:
                    base_importance += 1.5

        # 构建NPC视角的感知记忆（不是"玩家看到了"，而是"我好像察觉到"）
        perception_text = f"方才在{map_name}，我隐约察觉到一些动静：{scene[:80]}"
        if hint:
            perception_text += f"（或许{hint[:30]}）"
        perception_text = perception_text[:240]

        # 情感记忆加权
        mind = get_or_init_mind(p, nid)
        affective_imp = mem.affective_memory_importance(base_importance, mind)

        # 写入记忆流
        agent_brain.record_observation(
            mind,
            perception_text,
            world_day=int(p.world_day),
            world_shichen=sh_now,
            importance=affective_imp,
        )

    # 更新冷却时间戳
    p.last_dynamic_encounter_tick = int(getattr(p, "world_tick", 0) or 0)


def format_encounter_perception_block(mind: "mem.AgentMind", world_shichen: str) -> str:
    """从NPC记忆流中抽取最近的奇遇感知记忆，生成可注入对话的提示块。

    SITS2026「感知代理→向量记忆」架构落地：
    当 NPC 在近几个时辰内感知到了动态奇遇（通过 apply_encounter 注入），
    此函数会将其整理为一段简短的对话提示，让 NPC 可以自然地在闲聊中提及。

    设计要点：
    - 不是每次都提及——只在记忆较新且较重要时才注入
    - 语气是「隐约察觉」，不是「全知全能」
    - 给NPC一个自然的引入口，不是生硬地复述
    """
    import time as _time
    now = _time.time()
    # 只取最近2小时内的感知记忆（6时辰 ≈ 12小时，2小时约为1-2个时辰）
    RECENT_THRESHOLD_S = 7200.0

    encounter_perceptions = []
    for m in mind.items:
        if m.kind != "observation":
            continue
        # 识别奇遇感知记忆：以「方才在」开头
        if not m.text.startswith(ENCOUNTER_PERCEPTION_PREFIX):
            continue
        # 只取近期的
        if (now - m.created_at) > RECENT_THRESHOLD_S:
            continue
        encounter_perceptions.append(m)

    if not encounter_perceptions:
        return ""

    # 最多取2条最相关的
    recent = sorted(encounter_perceptions, key=lambda m: m.created_at, reverse=True)[:2]

    lines = ["【你隐约察觉到的事（若话题合适，可自然提及——像想起方才的一丝异样）】"]
    for m in recent:
        # 提取核心内容（去掉「方才在XXX，我隐约察觉到一些动静：」前缀）
        text = m.text
        colon_idx = text.find("：")
        core = text[colon_idx + 1:] if colon_idx >= 0 else text
        lines.append(f"· {core}")
    lines.append("· 提及时不必详述，一笔带过即可——像不经意想起方才的动静。")

    return "\n".join(lines)
