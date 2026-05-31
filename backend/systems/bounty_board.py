"""
悬赏榜系统（2026-05-26 新增，2026-05-31 重构）

悬赏由故事事件驱动：
  1. LLM 根据世界状态生成故事事件（逃犯潜逃、货物失窃、帮派纷争等）
  2. 官方机构（衙门/镖局/漕帮）据此发布悬赏
  3. 故事事件写入相关 NPC 记忆，NPC 会据此调整行为和对话

完成悬赏可获得：
  - 制钱（coin_delta）
  - 声望（rep_delta）
  - 信物（items_gain）
  - NPC 好感（favor_delta）

设计要点：
  - 悬赏必须有叙事前提（故事事件），不再随机生成
  - 拒绝「空气完成任务」：必须有真实的行动/对话/移动才能判定完成
  - 与记忆系统集成：故事事件和完成悬赏均写入记忆流
"""
from __future__ import annotations

import logging
import random
from typing import Any

import backend.memory as mem
from backend.agents.game_state import get_or_init_mind
from backend.data.factions import FACTIONS
from backend.data.maps_data import MAP_LOCATIONS
from backend.data.npcs_data import NPCS, NPC_FACTION
from backend.models.player import PlayerState
from backend.systems.constants import BOUNTY_COUNT_RANGE, BOUNTY_REFRESH_INTERVAL_DAYS
from backend.systems.core import apply_favor
from backend.systems.task_fsm import TaskFSM, TaskState
from backend.systems.time_weather import shichen_name

log = logging.getLogger("bounty")

_SEVERITY_REWARD_MAP = {
    "minor": {"coins": 100, "rep_delta": 1},
    "moderate": {"coins": 200, "rep_delta": 2},
    "major": {"coins": 350, "rep_delta": 3},
}

_FACTION_BOUNTY_AUTHORITY = {
    "yamen": "衙门",
    "biaoju": "镖局",
    "caobang": "漕帮",
}


def _requires_to_sub_steps(requires: dict[str, str]) -> list[dict]:
    label_map = {
        "talk_to_npc": "与{v}交谈",
        "ask_about": "打听{v}的消息",
        "move_to": "前往{v}",
        "with_npc": "护送{v}",
        "have_item": "获得{v}",
    }
    steps = []
    for k, v in requires.items():
        label = label_map.get(k, "{v}").format(v=v)
        steps.append({"key": f"{k}_{v}", "label": label, "completed": False})
    return steps


def _get_location_coords(map_id: str, loc_name: str) -> tuple[int, int]:
    locs = MAP_LOCATIONS.get(map_id, {})
    coords = locs.get(loc_name)
    if coords:
        return (coords[0], coords[1])
    return (25, 28)


def _find_npc_at_location(p: PlayerState, map_id: str, loc_name: str) -> str | None:
    npc_pos_data = getattr(p, "npc_positions", {})
    loc_coords = _get_location_coords(map_id, loc_name)
    best_npc = None
    best_dist = 999
    for nid, m in NPCS.items():
        if m.get("hidden") or nid == "jiang":
            continue
        pos = npc_pos_data.get(nid)
        if pos and len(pos) >= 3 and pos[0] == map_id:
            dist = abs(int(pos[1]) - loc_coords[0]) + abs(int(pos[2]) - loc_coords[1])
            if dist < best_dist:
                best_dist = dist
                best_npc = nid
    if best_npc and best_dist <= 8:
        return best_npc
    visible = [nid for nid, m in NPCS.items() if not m.get("hidden") and nid != "jiang"]
    return random.choice(visible) if visible else None


def generate_bounties_from_events(
    p: PlayerState,
    story_events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """从故事事件派生悬赏——每个事件生成一个悬赏。"""
    result = []

    for evt in story_events:
        hint = evt.get("bounty_hint", {})
        btype = hint.get("type", "打探")
        target_npc = hint.get("target_npc", "")
        target_item = hint.get("target_item", "")
        loc_name = hint.get("location", evt.get("location", ""))
        faction = evt.get("faction", "yamen")
        severity = evt.get("severity", "moderate")

        if not target_npc:
            visible = [nid for nid, m in NPCS.items() if not m.get("hidden") and nid != "jiang"]
            target_npc = random.choice(visible) if visible else ""
        if not loc_name:
            loc_names = list(MAP_LOCATIONS.get(p.map_id, {}).keys())
            loc_name = random.choice(loc_names) if loc_names else "市口"

        target_meta = NPCS.get(target_npc, {})
        target_name = target_meta.get("name", target_npc)
        target_short = target_meta.get("short", target_npc)
        fac_name = _FACTION_BOUNTY_AUTHORITY.get(faction, "衙门")

        requires: dict[str, str] = {}
        title = ""
        desc = evt.get("desc", "")

        if btype == "缉拿":
            requires = {
                "talk_to_npc": target_npc,
                "ask_about": f"{target_name}下落",
            }
            title = f"缉拿{target_name}"
            if not desc:
                desc = f"{fac_name}通缉{target_name}（{target_short}），有人见其在{loc_name}一带出没。"

        elif btype == "押送":
            dest_npc = _find_npc_at_location(p, p.map_id, loc_name) or target_npc
            dest_name = NPCS.get(dest_npc, {}).get("name", dest_npc)
            requires = {
                "move_to": loc_name,
                "with_npc": target_npc,
            }
            title = f"护送{target_name}至{dest_name}"
            if not desc:
                desc = f"{target_name}需从{loc_name}被护送至{dest_name}，途中可能遇袭。"

        elif btype == "寻回":
            if not target_item:
                target_item = "旧信物"
            requires = {
                "move_to": loc_name,
                "have_item": target_item,
            }
            title = f"寻回{target_item}"
            if not desc:
                desc = f"有人在{loc_name}遗失了{target_item}，捡到者请送至{target_name}处。"

        else:  # 打探
            location_npc = _find_npc_at_location(p, p.map_id, loc_name) or target_npc
            requires = {
                "talk_to_npc": location_npc,
                "ask_about": target_name,
            }
            title = f"打探{target_name}之虚实"
            if not desc:
                desc = f"有人想了解{target_name}（{target_short}）最近在干什么，去向{loc_name}的人打听。"

        sev = _SEVERITY_REWARD_MAP.get(severity, _SEVERITY_REWARD_MAP["moderate"])
        reward: dict[str, Any] = {"coins": sev["coins"]}

        rep_fac = faction if faction in FACTIONS else "yamen"
        reward["rep"] = {rep_fac: sev["rep_delta"]}
        if btype == "押送":
            reward["rep"].setdefault("biaoju", 0)
            reward["rep"]["biaoju"] = reward["rep"].get("biaoju", 0) + 1
        elif btype == "打探":
            reward["rep"].setdefault("caobang", 0)
            reward["rep"]["caobang"] = reward["rep"].get("caobang", 0) + 1
            reward["items_gain"] = ["密信"]
        elif btype == "寻回":
            reward["favor"] = {target_npc: 3}
            reward["items_gain"] = ["谢礼"]
        elif btype == "缉拿":
            reward["favor"] = {target_npc: -2}

        min_rep: dict[str, int] = {}
        if btype == "缉拿" and faction == "yamen":
            min_rep = {"yamen": 1}
        elif btype == "押送" and faction == "biaoju":
            min_rep = {"biaoju": 1}

        loc_px, loc_py = _get_location_coords(p.map_id, loc_name)

        bounty: dict[str, Any] = {
            "id": f"bounty_{btype}_{random.randint(1000, 9999)}",
            "type": btype,
            "title": title,
            "desc": desc,
            "reward": reward,
            "requires": requires,
            "min_rep": min_rep,
            "issued_at_day": int(p.world_day),
            "issued_at_shichen": shichen_name(p.world_shichen),
            "_target_coords": (p.map_id, loc_px, loc_py),
            "story_event_id": evt.get("id", ""),
        }

        fsm = TaskFSM(initial_state=TaskState.AVAILABLE)
        fsm.sub_steps = _requires_to_sub_steps(requires)
        bounty["task_fsm"] = fsm.to_dict()

        result.append(bounty)

    return result


def generate_bounties(p: PlayerState, count: int = 3) -> list[dict[str, Any]]:
    """兼容旧接口：无故事事件时用规则化回退生成。"""
    from backend.systems.story_events import _fallback_story_events
    events = _fallback_story_events(p, count)
    return generate_bounties_from_events(p, events)


def can_accept_bounty(p: PlayerState, bounty: dict[str, Any]) -> tuple[bool, str]:
    if bounty["id"] in (p.completed_bounties or []):
        return False, "此悬赏已完成，不可重复接取。"
    if p.active_bounty is not None:
        return False, "请先完成或放弃当前悬赏。"
    min_rep = bounty.get("min_rep", {})
    for fac, threshold in min_rep.items():
        cur = int((p.reputation or {}).get(fac, 0))
        if cur < threshold:
            fac_name = FACTIONS.get(fac, fac)
            return False, f"需要{fac_name}声望达到{threshold}才能接此悬赏（当前{cur}）。"
    return True, ""


def accept_bounty(p: PlayerState, bounty_id: str) -> tuple[bool, str]:
    bounties = p.bounties or []
    bounty = next((b for b in bounties if b["id"] == bounty_id), None)
    if not bounty:
        return False, "悬赏不存在。"

    ok, reason = can_accept_bounty(p, bounty)
    if not ok:
        return False, reason

    fsm = TaskFSM.from_dict(bounty["task_fsm"])
    if not fsm.transition(TaskState.IN_PROGRESS):
        return False, "无法接取此悬赏。"
    bounty["task_fsm"] = fsm.to_dict()

    requires = bounty.get("requires", {})
    if "move_to" in requires:
        coords = bounty.get("_target_coords")
        if coords:
            bounty["_target_pos"] = coords
        else:
            bounty["_target_pos"] = (p.map_id, p.px, p.py)

    p.active_bounty = bounty
    return True, f"已接取悬赏：「{bounty['title']}」。"


def check_bounty_progress(p: PlayerState) -> dict[str, Any] | None:
    bounty = p.active_bounty
    if not bounty:
        return None

    requires = bounty.get("requires", {})
    progress: dict[str, Any] = {"done": False, "reason": ""}

    fsm = TaskFSM.from_dict(bounty.get("task_fsm", {}))

    if "talk_to_npc" in requires:
        target_npc = requires["talk_to_npc"]
        ask_about = requires.get("ask_about", "")
        last_npc = getattr(p, "last_talk_npc_id", None)
        last_msg = getattr(p, "last_talk_message", None) or ""

        if last_npc == target_npc:
            npc_name = NPCS.get(target_npc, {}).get("name", target_npc)
            ask_matched = False
            if ask_about:
                ask_lower = ask_about.lower()
                msg_lower = last_msg.lower()
                if ask_lower in msg_lower:
                    ask_matched = True
                else:
                    ask_keywords = [ask_lower[i:i+2] for i in range(len(ask_lower) - 1)] if len(ask_lower) >= 2 else [ask_lower]
                    if ask_keywords:
                        hits = sum(1 for kw in ask_keywords if kw in msg_lower)
                        ask_matched = hits >= max(1, len(ask_keywords) // 2)
                if ask_matched:
                    progress["done"] = True
                    progress["reason"] = f"已向{npc_name}打探「{ask_about}」。"
                    fsm.complete_step(f"talk_to_npc_{target_npc}")
                    fsm.complete_step(f"ask_about_{ask_about}")
                else:
                    hist_with = p.history.get(target_npc, [])
                    recent_count = sum(
                        1 for h in hist_with[-6:]
                        if h.get("day") == int(p.world_day)
                    )
                    if recent_count >= 2:
                        ask_matched = True
                        progress["done"] = True
                        progress["reason"] = f"已与{npc_name}深入交谈。"
                        fsm.complete_step(f"talk_to_npc_{target_npc}")
                        fsm.complete_step(f"ask_about_{ask_about}")
                    else:
                        progress["reason"] = f"已找到{npc_name}，但尚未问及「{ask_about}」。"
                        fsm.complete_step(f"talk_to_npc_{target_npc}")
            else:
                progress["done"] = True
                progress["reason"] = f"已与{npc_name}交谈。"
                fsm.complete_step(f"talk_to_npc_{target_npc}")
        else:
            npc_name = NPCS.get(target_npc, {}).get("name", target_npc)
            progress["reason"] = f"尚未找到{npc_name}（目标：{target_npc}）。"

    elif "move_to" in requires:
        dest_map_id = requires.get("move_to", "")
        target_pos = bounty.get("_target_pos")
        if target_pos:
            t_map, t_px, t_py = target_pos
            if p.map_id == t_map and p.px == t_px and p.py == t_py:
                progress["done"] = True
                progress["reason"] = f"已抵达目的地坐标 ({t_px},{t_py})。"
                fsm.complete_step(f"move_to_{dest_map_id}")
            else:
                progress["reason"] = "尚在途中，未到目的地。"
        else:
            last_map = getattr(p, "last_move_map_id", None)
            if last_map and last_map == dest_map_id:
                progress["done"] = True
                progress["reason"] = f"已抵达{dest_map_id}。"
                fsm.complete_step(f"move_to_{dest_map_id}")
            else:
                progress["reason"] = "尚未到达目的地。"

        if "with_npc" in requires:
            with_npc_id = requires["with_npc"]
            if progress["done"]:
                fsm.complete_step(f"with_npc_{with_npc_id}")

    elif "have_item" in requires:
        item = requires["have_item"]
        if (p.inventory or {}).get(item, 0) > 0:
            progress["done"] = True
            progress["reason"] = f"已找到{item}。"
            fsm.complete_step(f"have_item_{item}")
        else:
            progress["reason"] = f"尚未获得{item}。"

    if fsm.all_steps_completed() and fsm.can_transition(TaskState.COMPLETABLE):
        fsm.transition(TaskState.COMPLETABLE)

    bounty["task_fsm"] = fsm.to_dict()
    return progress


def complete_bounty(p: PlayerState) -> tuple[bool, str, dict[str, Any]]:
    bounty = p.active_bounty
    if not bounty:
        return False, "当前没有进行中的悬赏。", {}

    if p.completed_bounties and bounty["id"] in p.completed_bounties:
        p.active_bounty = None
        return False, "此悬赏已完成。", {}

    fsm = TaskFSM.from_dict(bounty.get("task_fsm", {}))
    if fsm.current_state != TaskState.COMPLETABLE:
        progress = check_bounty_progress(p)
        if not progress or not progress.get("done"):
            return False, "悬赏尚未完成。", {}
        fsm = TaskFSM.from_dict(bounty.get("task_fsm", {}))

    if not fsm.transition(TaskState.COMPLETED):
        return False, "无法完成此悬赏。", {}
    bounty["task_fsm"] = fsm.to_dict()

    reward = bounty.get("reward", {})

    coins = int(reward.get("coins", 0))
    if coins:
        from backend.systems.economy import apply_coin_delta
        apply_coin_delta(p, coins)

    rep = reward.get("rep", {})
    if rep:
        from backend.systems.reputation import apply_rep_delta
        apply_rep_delta(p, rep)

    items = reward.get("items_gain", [])
    if items:
        from backend.systems.economy import add_items
        add_items(p, items)

    favor = reward.get("favor", {})
    for nid, delta in favor.items():
        apply_favor(p, nid, delta)

    if p.completed_bounties is None:
        p.completed_bounties = []
    p.completed_bounties.append(bounty["id"])

    mind = get_or_init_mind(p, "jiang")
    mem.record_observation(
        mind,
        f"完成悬赏「{bounty['title']}」，获{coins}文钱。",
        world_day=int(p.world_day),
        world_shichen=shichen_name(p.world_shichen),
        importance=5.0,
    )

    story_evt_id = bounty.get("story_event_id", "")
    if story_evt_id:
        story_events = getattr(p, "story_events", []) or []
        for se in story_events:
            if se.get("id") == story_evt_id:
                se["resolved"] = True
                for npc_id in se.get("involved_npcs", []):
                    try:
                        npc_mind = get_or_init_mind(p, npc_id)
                        mem.record_observation(
                            npc_mind,
                            f"悬赏「{bounty['title']}」已被人完成。",
                            world_day=int(p.world_day),
                            world_shichen=shichen_name(p.world_shichen),
                            importance=4.0,
                        )
                    except Exception as _e:
                        log.debug("Failed to write bounty completion to %s memory: %s", npc_id, _e)
                break

    p.active_bounty = None
    p.last_talk_npc_id = None
    p.last_talk_message = None

    return True, f"悬赏完成！获得{coins}文钱。", reward


def abandon_bounty(p: PlayerState) -> tuple[bool, str]:
    if not p.active_bounty:
        return False, "当前没有进行中的悬赏。"
    title = p.active_bounty["title"]
    fsm = TaskFSM.from_dict(p.active_bounty.get("task_fsm", {}))
    fsm.transition(TaskState.ABANDONED)
    p.active_bounty["task_fsm"] = fsm.to_dict()
    p.active_bounty = None
    return True, f"已放弃悬赏：「{title}」。"


def format_bounty_board(p: PlayerState) -> str:
    bounties = p.bounties or []
    if not bounties:
        return ""

    story_events = getattr(p, "story_events", []) or []
    evt_map = {e.get("id", ""): e for e in story_events}

    lines = ["【悬赏榜】县衙、镖局、漕口帮坞等处可见下列悬赏："]
    for b in bounties:
        evt = evt_map.get(b.get("story_event_id", ""))
        if evt and evt.get("desc"):
            lines.append(f"  近日，{evt['desc'][:50]}")
        lines.append(f"  → [{b['type']}] {b['title']} —— {b['desc'][:60]}")
        reward_parts = []
        if b["reward"].get("coins"):
            reward_parts.append(f"{b['reward']['coins']}文")
        if b["reward"].get("rep"):
            for fac, d in b["reward"]["rep"].items():
                fac_name = FACTIONS.get(fac, fac)
                reward_parts.append(f"{fac_name}声望{d:+d}")
        if reward_parts:
            lines.append(f"    悬赏：{'; '.join(reward_parts)}")
    return "\n".join(lines)


async def refresh_bounties_with_story(p: PlayerState) -> None:
    """刷新悬赏榜：先由 LLM 生成故事事件，再派生悬赏。"""
    from backend.systems.story_events import generate_story_events, write_story_events_to_memory

    old_events = getattr(p, "story_events", []) or []
    resolved_ids = set()
    for evt in old_events:
        if evt.get("resolved"):
            resolved_ids.add(evt.get("id", ""))
    active_evt_id = ""
    if p.active_bounty:
        active_evt_id = p.active_bounty.get("story_event_id", "")

    surviving = [
        e for e in old_events
        if e.get("id", "") not in resolved_ids or e.get("id", "") == active_evt_id
    ]

    count = random.randint(*BOUNTY_COUNT_RANGE)
    events = await generate_story_events(p, count=count)

    p.story_events = surviving + events
    write_story_events_to_memory(p, events)

    p.bounties = generate_bounties_from_events(p, events)
    p.last_bounty_refresh_day = int(p.world_day)
    log.info(
        "Refreshed bounties with %d story events for player %s on day %d",
        len(events), p.player_id, int(p.world_day),
    )


def refresh_bounties(p: PlayerState) -> None:
    """同步刷新（兼容旧接口，不调用 LLM）。"""
    last_refresh_day = int(getattr(p, "last_bounty_refresh_day", 0) or 0)
    cur_day = int(p.world_day)
    if cur_day - last_refresh_day < BOUNTY_REFRESH_INTERVAL_DAYS:
        return
    p.bounties = generate_bounties(p, count=random.randint(*BOUNTY_COUNT_RANGE))
    p.last_bounty_refresh_day = cur_day
    log.info("Refreshed bounties (fallback) for player %s on day %d", p.player_id, cur_day)
