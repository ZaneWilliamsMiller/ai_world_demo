"""
故事事件系统 —— LLM 驱动的江湖叙事引擎

玩家进入游戏或悬赏刷新时，先由 LLM 根据世界背景、NPC 状态、玩家历史
生成若干故事事件（如：逃犯潜逃、货物失窃、帮派纷争），
再由官方机构（衙门/镖局/漕帮）据此发布悬赏。

设计要点：
  - 故事事件是悬赏的叙事前提，悬赏是故事事件的制度性回应
  - 故事事件写入相关 NPC 的记忆，NPC 会据此调整行为和对话
  - 故事事件注入对话 prompt，NPC 可主动提及
"""
from __future__ import annotations

import json
import logging
import random
from typing import Any

from backend.agents.game_state import get_or_init_mind
from backend.data.factions import FACTIONS
from backend.data.maps_data import MAP_LOCATIONS
from backend.data.npcs_data import NPCS, NPC_FACTION
from backend.models.player import PlayerState
from backend.systems.constants import BOUNTY_REFRESH_INTERVAL_DAYS
from backend.systems.time_weather import shichen_name

import backend.memory as mem

log = logging.getLogger("story_events")

from backend.llm.params import STORY_EVENT_TEMPERATURE, STORY_EVENT_MAX_TOKENS

_FACTION_BOUNTY_AUTHORITY = {
    "yamen": "衙门",
    "biaoju": "镖局",
    "caobang": "漕帮",
}


def _build_story_context(p: PlayerState) -> str:
    parts = []

    parts.append(f"【时辰】第{p.world_day}日 · {shichen_name(p.world_shichen)}")
    parts.append(f"【天气】{p.weather or '晴'}")

    locs = MAP_LOCATIONS.get(p.map_id, {})
    loc_names = list(locs.keys())[:15]
    parts.append(f"【主要地点】{'、'.join(loc_names)}")

    visible_npcs = [
        (nid, m) for nid, m in NPCS.items()
        if not m.get("hidden") and nid != "jiang"
    ]
    npc_lines = []
    for nid, m in visible_npcs[:20]:
        name = m.get("name", nid)
        short = m.get("short", "")
        fac = NPC_FACTION.get(nid)
        fac_name = FACTIONS.get(fac, "") if fac else ""
        blurb = m.get("character", {})
        desc_parts = [short] if short else []
        if fac_name:
            desc_parts.append(fac_name)
        if blurb:
            for k, v in list(blurb.items())[:2]:
                desc_parts.append(f"{k}:{v}")
        npc_lines.append(f"· {name}（{nid}）{' '.join(desc_parts)}")
    if npc_lines:
        parts.append("【江湖人物】\n" + "\n".join(npc_lines))

    rep_bits = []
    for fac, val in (p.reputation or {}).items():
        if val != 0:
            rep_bits.append(f"{FACTIONS.get(fac, fac)}{val:+d}")
    if rep_bits:
        parts.append(f"【玩家声望】{' '.join(rep_bits)}")

    if p.rumors:
        parts.append(f"【近日风闻】{'；'.join(p.rumors[-5:])}")

    if p.events:
        recent = [e.get("text", "") for e in p.events[-6:] if e.get("text")]
        if recent:
            parts.append(f"【近日事件】{'；'.join(recent)}")

    completed = getattr(p, "completed_bounties", []) or []
    if completed:
        parts.append(f"【已结悬赏】{len(completed)}件")

    active = getattr(p, "active_bounty", None)
    if active:
        parts.append(f"【当前悬赏】{active.get('title', '')}")

    return "\n\n".join(parts)


async def generate_story_events(p: PlayerState, count: int = 3) -> list[dict[str, Any]]:
    """由 LLM 生成故事事件，作为悬赏的叙事前提。

    返回结构：
    [
        {
            "id": "evt_xxxx",
            "title": "事件标题",
            "desc": "事件描述（2~4句）",
            "severity": "minor" | "moderate" | "major",
            "involved_npcs": ["npc_id_1", "npc_id_2"],
            "location": "地点名",
            "faction": "yamen" | "biaoju" | "caobang",
            "bounty_hint": {
                "type": "缉拿|押送|打探|寻回",
                "target_npc": "npc_id",
                "target_item": "物品名或空",
                "location": "地点名",
            },
        },
        ...
    ]
    """
    ctx = _build_story_context(p)

    resolved_titles = []
    for evt in (getattr(p, "story_events", []) or []):
        if evt.get("resolved") and evt.get("title"):
            resolved_titles.append(evt["title"])
    avoid_clause = ""
    if resolved_titles:
        avoid_clause = "\n\n注意：以下事件已发生并已结案，请勿重复或延续：\n" + "、".join(resolved_titles[:6])

    messages = [
        {
            "role": "system",
            "content": (
                "你是「青笺录」江湖的故事事件生成器。根据当前世界状态，生成"
                f"{count}个**同时发生的江湖事件**，作为悬赏榜的叙事前提。\n\n"
                "规则：\n"
                "· 事件必须符合世界观（架空晚明江湖），与当前时辰、天气、地点、人物呼应\n"
                "· 事件之间可以有因果关联（如：A事件导致B事件），也可以独立\n"
                "· 事件涉及的人物必须是【江湖人物】列表中的NPC，用NPC的id引用\n"
                "· 事件要有叙事深度——不是简单的「某人犯罪」，而是有前因后果的江湖事\n"
                "· severity: minor=小纠纷/小偷小摸, moderate=逃犯/失窃/纠纷, major=命案/帮派火拼/官府密令\n"
                "· faction: 此事件最可能由哪个官方机构出面发布悬赏（yamen=衙门, biaoju=镖局, caobang=漕帮）\n"
                "· bounty_hint.type: 缉拿(找人)、押送(护送)、打探(情报)、寻回(找物)\n"
                "· bounty_hint.target_npc: 悬赏目标NPC的id\n"
                "· bounty_hint.target_item: 寻回类需要的物品名，其他类型留空字符串\n"
                "· bounty_hint.location: 事件发生或目标所在的地点名\n\n"
                "输出JSON：\n"
                '{"events": [{"title": "事件标题", "desc": "2~4句描述", '
                '"severity": "minor|moderate|major", "involved_npcs": ["id1","id2"], '
                '"location": "地点名", "faction": "yamen|biaoju|caobang", '
                '"bounty_hint": {"type": "缉拿|押送|打探|寻回", '
                '"target_npc": "npc_id", "target_item": "", "location": "地点名"}}]}'
            ),
        },
        {"role": "user", "content": ctx + avoid_clause},
    ]

    try:
        from backend.llm.client import chat_completion
        raw = await chat_completion(
            messages,
            temperature=STORY_EVENT_TEMPERATURE,
            max_tokens=STORY_EVENT_MAX_TOKENS,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(raw)
        events_raw = parsed.get("events", [])
        if not events_raw:
            return _fallback_story_events(p, count)

        result = []
        valid_npc_ids = set(NPCS.keys())
        valid_locations = set()
        for locs in MAP_LOCATIONS.values():
            valid_locations.update(locs.keys())

        for i, evt in enumerate(events_raw[:count]):
            involved = [
                nid for nid in evt.get("involved_npcs", [])
                if nid in valid_npc_ids and nid != "jiang"
            ]
            if not involved:
                visible = [nid for nid in NPCS if not NPCS[nid].get("hidden") and nid != "jiang"]
                if visible:
                    involved = [random.choice(visible)]

            target_npc = evt.get("bounty_hint", {}).get("target_npc", "")
            if target_npc not in valid_npc_ids or target_npc == "jiang":
                target_npc = involved[0] if involved else ""

            loc = evt.get("location", "")
            if loc not in valid_locations:
                loc_names = list(MAP_LOCATIONS.get(p.map_id, {}).keys())
                loc = random.choice(loc_names) if loc_names else "市口"

            bounty_loc = evt.get("bounty_hint", {}).get("location", loc)
            if bounty_loc not in valid_locations:
                bounty_loc = loc

            faction = evt.get("faction", "yamen")
            if faction not in _FACTION_BOUNTY_AUTHORITY:
                faction = "yamen"

            btype = evt.get("bounty_hint", {}).get("type", "打探")
            if btype not in ("缉拿", "押送", "打探", "寻回"):
                btype = "打探"

            result.append({
                "id": f"evt_{random.randint(1000, 9999)}_{i}",
                "title": evt.get("title", f"江湖事{i+1}")[:30],
                "desc": evt.get("desc", "")[:200],
                "severity": evt.get("severity", "moderate") if evt.get("severity") in ("minor", "moderate", "major") else "moderate",
                "involved_npcs": involved,
                "location": loc,
                "faction": faction,
                "bounty_hint": {
                    "type": btype,
                    "target_npc": target_npc,
                    "target_item": evt.get("bounty_hint", {}).get("target_item", ""),
                    "location": bounty_loc,
                },
                "issued_at_day": int(p.world_day),
                "issued_at_shichen": shichen_name(p.world_shichen),
            })

        return result

    except Exception as e:
        log.warning("LLM story event generation failed: %s, using fallback", e)
        return _fallback_story_events(p, count)


def _fallback_story_events(p: PlayerState, count: int) -> list[dict[str, Any]]:
    """LLM 失败时的规则化回退生成。"""
    result = []
    visible = [nid for nid, m in NPCS.items() if not m.get("hidden") and nid != "jiang"]
    loc_names = list(MAP_LOCATIONS.get(p.map_id, {}).keys())
    if not loc_names:
        loc_names = ["市口"]

    templates = [
        {
            "title": "有人夜入{loc}行窃",
            "desc": "昨夜{loc}一带有贼人出没，据称偷走了若干银钱与一封密信，事主已报官。",
            "severity": "minor",
            "faction": "yamen",
            "bounty_type": "寻回",
            "bounty_item": "密信",
        },
        {
            "title": "{npc}被指通匪潜逃",
            "desc": "{npc}被衙门指通匪，已于数日前潜逃，据传藏匿于{loc}附近。",
            "severity": "major",
            "faction": "yamen",
            "bounty_type": "缉拿",
            "bounty_item": "",
        },
        {
            "title": "{loc}货物遭劫",
            "desc": "镖局一批货物在{loc}附近遭不明人士劫持，镖师受伤，货物下落不明。",
            "severity": "moderate",
            "faction": "biaoju",
            "bounty_type": "打探",
            "bounty_item": "",
        },
        {
            "title": "漕帮内斗风声",
            "desc": "漕帮内部近日纷争不断，有人想拉拢外力，在{loc}放出风声招揽江湖客。",
            "severity": "moderate",
            "faction": "caobang",
            "bounty_type": "打探",
            "bounty_item": "",
        },
        {
            "title": "{npc}需人护送至{loc}",
            "desc": "{npc}身携要物，需从{loc}护送至安全之处，途中恐有截杀。",
            "severity": "moderate",
            "faction": "biaoju",
            "bounty_type": "押送",
            "bounty_item": "",
        },
    ]

    used = set()
    for i in range(count):
        tmpl = random.choice(templates)
        while id(tmpl) in used and len(used) < len(templates):
            tmpl = random.choice(templates)
        used.add(id(tmpl))

        npc_id = random.choice(visible) if visible else ""
        npc_name = NPCS.get(npc_id, {}).get("name", npc_id)
        loc = random.choice(loc_names)

        title = tmpl["title"].format(npc=npc_name, loc=loc)
        desc = tmpl["desc"].format(npc=npc_name, loc=loc)

        result.append({
            "id": f"evt_{random.randint(1000, 9999)}_{i}",
            "title": title,
            "desc": desc,
            "severity": tmpl["severity"],
            "involved_npcs": [npc_id] if npc_id else [],
            "location": loc,
            "faction": tmpl["faction"],
            "bounty_hint": {
                "type": tmpl["bounty_type"],
                "target_npc": npc_id,
                "target_item": tmpl["bounty_item"],
                "location": loc,
            },
            "issued_at_day": int(p.world_day),
            "issued_at_shichen": shichen_name(p.world_shichen),
        })

    return result


def write_story_events_to_memory(p: PlayerState, events: list[dict[str, Any]]) -> None:
    """将故事事件写入相关 NPC 的记忆流。"""
    for evt in events:
        desc = evt.get("desc", "")
        if not desc:
            continue
        day = int(p.world_day)
        shichen = shichen_name(p.world_shichen)

        for npc_id in evt.get("involved_npcs", []):
            try:
                mind = get_or_init_mind(p, npc_id)
                mem.record_observation(
                    mind,
                    f"[江湖事] {desc}",
                    world_day=day,
                    world_shichen=shichen,
                    importance=4.0 if evt.get("severity") == "major" else 3.0,
                )
            except Exception as e:
                log.debug("Failed to write story event to %s memory: %s", npc_id, e)

        mind_jiang = get_or_init_mind(p, "jiang")
        try:
            mem.record_observation(
                mind_jiang,
                f"[江湖事] {evt.get('title', '')}：{desc}",
                world_day=day,
                world_shichen=shichen,
                importance=5.0 if evt.get("severity") == "major" else 3.5,
            )
        except Exception as e:
            log.debug("Failed to write story event to jiang memory: %s", e)


def format_story_events_for_prompt(p: PlayerState, npc_id: str = "") -> str:
    events = getattr(p, "story_events", []) or []
    if not events:
        return ""

    lines = ["【近日江湖事（悬赏由来）】"]
    for evt in events:
        fac_name = _FACTION_BOUNTY_AUTHORITY.get(evt.get("faction", ""), "衙门")
        is_involved = npc_id and npc_id in evt.get("involved_npcs", [])
        is_target = npc_id and evt.get("bounty_hint", {}).get("target_npc") == npc_id
        if is_target:
            lines.append(
                f"· [{fac_name}]{evt.get('title', '')}——**你正是此事的当事人！**{evt.get('desc', '')[:80]}"
            )
        elif is_involved:
            lines.append(
                f"· [{fac_name}]{evt.get('title', '')}——你与此事有关。{evt.get('desc', '')[:80]}"
            )
        else:
            lines.append(
                f"· [{fac_name}]{evt.get('title', '')}——{evt.get('desc', '')[:80]}"
            )
    return "\n".join(lines)


def format_bounty_context_for_prompt(p: PlayerState, npc_id: str = "") -> str:
    active = getattr(p, "active_bounty", None)
    if not active:
        return ""

    title = active.get("title", "")
    desc = active.get("desc", "")
    requires = active.get("requires", {})
    btype = active.get("type", "")

    is_target = npc_id and requires.get("talk_to_npc") == npc_id and btype == "缉拿"
    if is_target:
        parts = [f"【你正在被通缉！】衙门正在悬赏缉拿你（「{title}」），此客可能就是来抓你的。你应当警惕、回避、否认，或试图蒙混过关。"]
    else:
        parts = [f"【你知晓的悬赏】此客正在办理「{title}」（{btype}）"]
    if desc:
        parts.append(f"  事由：{desc[:60]}")

    req_parts = []
    if "talk_to_npc" in requires:
        npc_name = NPCS.get(requires["talk_to_npc"], {}).get("name", requires["talk_to_npc"])
        req_parts.append(f"需与{npc_name}交谈")
    if "ask_about" in requires:
        req_parts.append(f"打听「{requires['ask_about']}」")
    if "move_to" in requires:
        req_parts.append(f"前往{requires['move_to']}")
    if "have_item" in requires:
        req_parts.append(f"持有{requires['have_item']}")
    if req_parts:
        parts.append("  条件：" + "、".join(req_parts))

    return "\n".join(parts)
