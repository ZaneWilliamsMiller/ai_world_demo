"""
悬赏榜系统（2026-05-26 新增）

玩家可在县衙、镖局、漕口帮坞看到悬赏榜。
悬赏任务类型：
  - 缉拿逃犯（需要找到特定 NPC 或地点）
  - 押送镖物（移动类任务，护送 NPC 到指定格）
  - 打探消息（打探类任务，与特定 NPC 对话获取情报）
  - 寻回失物（探索类任务，在指定地图格触发）

完成悬赏可获得：
  - 制钱（coin_delta）
  - 声望（rep_delta）
  - 信物（items_gain）
  - NPC 好感（favor_delta）

设计要点：
  - 悬赏榜动态生成，基于当前世界状态（时辰、天气、玩家声望）
  - 拒绝「空气完成任务」：必须有真实的行动/对话/移动才能判定完成
  - 与记忆系统集成：完成任务后写入记忆流
"""
from __future__ import annotations
import json
import logging
import random
from typing import Any

from backend.models.player import PlayerState
from backend.data.npcs_data import NPCS
from backend.data.factions import FACTIONS
from backend.data.maps_data import MAPS, MAP_LOCATIONS
from backend.systems.constants import BOUNTY_REFRESH_INTERVAL_DAYS, BOUNTY_COUNT_RANGE
from backend.systems.time_weather import shichen_name
from backend.systems.reputation import apply_rep_delta
from backend.systems.core import push_rumor, apply_favor
from backend.game_state import get_or_init_mind
import backend.memory as mem

log = logging.getLogger("bounty")

# ─── 悬赏任务模板 ─────────────────────
_BOUNTY_TEMPLATES = [
    {
        "id": "bounty_capture",
        "type": "缉拿",
        "title": "缉拿逃犯{target_name}",
        "desc": "衙门通缉{target_name}（{target_short}），有人见其在{location}一带出没。",
        "requires": {"talk_to_npc": "{target_id}", "ask_about": "逃犯下落"},
        "reward": {"coins": 200, "rep": {"yamen": 2}, "favor": {"{target_id}": -2}},
        "min_rep": {"yamen": 1},  # 至少需要衙门声望 1 才能接
    },
    {
        "id": "bounty_escort",
        "type": "押送",
        "title": "护送{target_name}至{dest_name}",
        "desc": "{target_name}需从{location}被护送至{dest_name}，途中可能遇袭。",
        "requires": {"move_to": "{location_id}", "with_npc": "{target_id}"},
        "reward": {"coins": 300, "rep": {"biaoju": 2, "yamen": 1}},
        "min_rep": {"biaoju": 1},
    },
    {
        "id": "bounty_investigate",
        "type": "打探",
        "title": "打探{target_name}之虚实",
        "desc": "有人想了解{target_name}（{target_short}）最近在干什么，去向{location}的人打听。",
        "requires": {"talk_to_npc": "{location_npc_id}", "ask_about": "{target_name}"},
        "reward": {"coins": 150, "rep": {"caobang": 1, "yamen": 1}, "items_gain": ["密信"]},
        "min_rep": {},
    },
    {
        "id": "bounty_retrieve",
        "type": "寻回",
        "title": "寻回遗失的{lost_item}",
        "desc": "有人在{location}遗失了{lost_item}，捡到者请送至{target_name}处。",
        "requires": {"move_to": "{location_id}", "have_item": "{lost_item}"},
        "reward": {"coins": 100, "favor": {"{target_id}": 3}, "items_gain": ["谢礼"]},
        "min_rep": {},
    },
]

# ─── 活跃悬赏榜（每个玩家独立）─────────────────────
#  p.bounties: list[dict] = []  玩家当前可接的悬赏
#  p.active_bounty: dict | None  当前正在做的悬赏
#  p.completed_bounties: list[str]  已完成的悬赏 ID


def _random_target_npc(p: PlayerState) -> str | None:
    """随机选一个非玩家、非隐藏的 NPC。"""
    candidates = [nid for nid, m in NPCS.items() if not m.get("hidden") and nid != "jiang"]
    if not candidates:
        return None
    return random.choice(candidates)


def _random_location(p: PlayerState) -> tuple[str, str, int, int]:
    """随机选一个地图格作为地点，返回 (map_id, loc_name, px, py)。"""
    map_id = p.map_id
    maps_data = MAPS.get(map_id, {})
    locations = maps_data.get("locations", [])
    if locations:
        loc = random.choice(locations)
        loc_name = loc["name"]
        # 查 MAP_LOCATIONS 获取坐标
        coords = MAP_LOCATIONS.get(map_id, {}).get(loc_name, (10, 14))
        return (map_id, loc_name, coords[0], coords[1])
    return (map_id, "市口", 13, 13)


def generate_bounties(p: PlayerState, count: int = 3) -> list[dict[str, Any]]:
    """为玩家生成悬赏榜（基于当前世界状态）。"""
    result = []
    used_templates = set()

    for _ in range(count):
        # 随机选一个模板（不重复）
        available = [t for t in _BOUNTY_TEMPLATES if t["id"] not in used_templates]
        if not available:
            break
        tmpl = random.choice(available)
        used_templates.add(tmpl["id"])

        # 填充模板变量
        target_id = _random_target_npc(p)
        if not target_id:
            continue
        target_meta = NPCS.get(target_id, {})
        target_name = target_meta.get("name", target_id)
        target_short = target_meta.get("short", target_id)

        map_id, loc_name, loc_px, loc_py = _random_location(p)
        # 再随机选一个目的地 NPC/位置（用于押送类）
        dest_id = _random_target_npc(p)
        if not dest_id:
            dest_id = target_id
        dest_meta = NPCS.get(dest_id, {})
        dest_name = dest_meta.get("name", dest_id)
        dest_coords = MAP_LOCATIONS.get(map_id, {}).get(dest_name, (10, 16))

        # 对于 location_npc：选一个在当前地点活跃的 NPC
        location_npc_id = target_id  # 兜底用目标 NPC
        for nid, m in NPCS.items():
            if m.get("hidden") or nid == "jiang":
                continue
            location_npc_id = nid
            break
        location_npc_meta = NPCS.get(location_npc_id, {})
        location_npc_name = location_npc_meta.get("name", location_npc_id)

        fmt = {
            "target_name": target_name,
            "target_short": target_short,
            "target_id": target_id,
            "location": loc_name,
            "location_id": loc_name,
            "location_npc_id": location_npc_id,   # NPC id (用于 requires 匹配)
            "location_npc": location_npc_name,    # NPC 显示名 (用于用户展示)
            "dest_name": dest_name,
            "dest_id": dest_name,
            "lost_item": "旧信物",
        }

        title = tmpl["title"].format(**fmt)
        desc = tmpl["desc"].format(**fmt)

        # 填充 requires 字典（模板占位符替换为实际值）
        raw_req = tmpl["requires"].copy()
        requires: dict[str, str] = {}
        for k, v in raw_req.items():
            requires[k] = str(v).format(**fmt)

        bounty: dict[str, Any] = {
            "id": f"{tmpl['id']}_{random.randint(1000, 9999)}",
            "type": tmpl["type"],
            "title": title,
            "desc": desc,
            "reward": tmpl["reward"].copy(),
            "requires": requires,
            "min_rep": tmpl.get("min_rep", {}),
            "issued_at_day": int(p.world_day),
            "issued_at_shichen": shichen_name(p.world_shichen),
            # 押送/寻回类：预设目的地坐标，供 accept 时快照
            "_target_coords": (map_id, loc_px, loc_py),
        }
        result.append(bounty)

    return result


def can_accept_bounty(p: PlayerState, bounty: dict[str, Any]) -> tuple[bool, str]:
    """检查玩家是否满足接取悬赏的条件。"""
    # 已完成的不许重复接
    if bounty["id"] in (p.completed_bounties or []):
        return False, "此悬赏已完成，不可重复接取。"
    # 已有进行中的悬赏
    if p.active_bounty is not None:
        return False, "请先完成或放弃当前悬赏。"
    # 声望门槛
    min_rep = bounty.get("min_rep", {})
    for fac, threshold in min_rep.items():
        cur = int((p.reputation or {}).get(fac, 0))
        if cur < threshold:
            fac_name = FACTIONS.get(fac, fac)
            return False, f"需要{fac_name}声望达到{threshold}才能接此悬赏（当前{cur}）。"
    return True, ""


def accept_bounty(p: PlayerState, bounty_id: str) -> tuple[bool, str]:
    """接取一个悬赏。接取时快照目标坐标（押送类后续用）。"""
    bounties = p.bounties or []
    bounty = next((b for b in bounties if b["id"] == bounty_id), None)
    if not bounty:
        return False, "悬赏不存在。"

    ok, reason = can_accept_bounty(p, bounty)
    if not ok:
        return False, reason

    # ── 押送类：快照目的地坐标（用于 check_bounty_progress 的精确判定）──
    requires = bounty.get("requires", {})
    if "move_to" in requires:
        # 使用生成时预设的坐标
        coords = bounty.get("_target_coords")
        if coords:
            bounty["_target_pos"] = coords
        else:
            bounty["_target_pos"] = (p.map_id, p.px, p.py)

    p.active_bounty = bounty
    return True, f"已接取悬赏：「{bounty['title']}」。"


def check_bounty_progress(p: PlayerState) -> dict[str, Any] | None:
    """检查当前悬赏的完成进度（在玩家行动后调用）。

    非简化实现：真实判定玩家是否完成了悬赏要求。
    - 缉拿/打探类：需与目标 NPC 对话，且内容涉及关键话题
    - 押送类：需移动到目的地坐标
    - 寻回类：需拥有目标物品
    """
    bounty = p.active_bounty
    if not bounty:
        return None

    requires = bounty.get("requires", {})
    progress: dict[str, Any] = {"done": False, "reason": ""}

    # ── 缉拿/打探类：需要与目标 NPC 对话并问及关键词 ──
    if "talk_to_npc" in requires:
        target_npc = requires["talk_to_npc"]
        ask_about = requires.get("ask_about", "")
        last_npc = getattr(p, "last_talk_npc_id", None)
        last_msg = getattr(p, "last_talk_message", None) or ""

        if last_npc == target_npc:
            # 检查对话内容是否包含关键话题词
            if ask_about and ask_about.lower() in last_msg.lower():
                progress["done"] = True
                npc_name = NPCS.get(target_npc, {}).get("name", target_npc)
                progress["reason"] = f"已向{npc_name}打探「{ask_about}」。"
            elif not ask_about:
                # 无关键词限制：与目标 NPC 对话即算完成
                progress["done"] = True
                npc_name = NPCS.get(target_npc, {}).get("name", target_npc)
                progress["reason"] = f"已与{npc_name}交谈。"
            else:
                npc_name = NPCS.get(target_npc, {}).get("name", target_npc)
                progress["reason"] = f"已找到{npc_name}，但尚未问及「{ask_about}」。"
        else:
            npc_name = NPCS.get(target_npc, {}).get("name", target_npc)
            progress["reason"] = f"尚未找到{npc_name}（目标：{target_npc}）。"

    # ── 押送类：需要移动到目的地 ──
    elif "move_to" in requires:
        dest_map_id = requires.get("move_to", "")
        # 使用 bounty 中存的目标坐标或 last_move 的坐标
        target_pos = bounty.get("_target_pos")
        if target_pos:
            t_map, t_px, t_py = target_pos
            if p.map_id == t_map and p.px == t_px and p.py == t_py:
                progress["done"] = True
                progress["reason"] = f"已抵达目的地坐标 ({t_px},{t_py})。"
            else:
                progress["reason"] = f"尚在途中，未到目的地。"
        else:
            # 兜底：检查最近的一次移动
            last_map = getattr(p, "last_move_map_id", None)
            if last_map and last_map == dest_map_id:
                progress["done"] = True
                progress["reason"] = f"已抵达{dest_map_id}。"
            else:
                progress["reason"] = f"尚未到达目的地。"

    # ── 寻回类：需要获得物品 ──
    elif "have_item" in requires:
        item = requires["have_item"]
        if (p.inventory or {}).get(item, 0) > 0:
            progress["done"] = True
            progress["reason"] = f"已找到{item}。"
        else:
            progress["reason"] = f"尚未获得{item}。"

    return progress


def complete_bounty(p: PlayerState) -> tuple[bool, str, dict[str, Any]]:
    """完成当前悬赏，发放奖励。"""
    bounty = p.active_bounty
    if not bounty:
        return False, "当前没有进行中的悬赏。", {}

    if p.completed_bounties and bounty["id"] in p.completed_bounties:
        p.active_bounty = None
        return False, "此悬赏已完成。", {}

    progress = check_bounty_progress(p)
    if not progress or not progress.get("done"):
        return False, "悬赏尚未完成。", {}

    reward = bounty.get("reward", {})

    # 发钱
    coins = int(reward.get("coins", 0))
    if coins:
        from backend.systems.economy import apply_coin_delta
        apply_coin_delta(p, coins)

    # 发声望
    rep = reward.get("rep", {})
    if rep:
        from backend.systems.reputation import apply_rep_delta
        apply_rep_delta(p, rep)

    # 发物品
    items = reward.get("items_gain", [])
    if items:
        from backend.systems.economy import add_items
        add_items(p, items)

    # 发好感
    favor = reward.get("favor", {})
    for nid, delta in favor.items():
        apply_favor(p, nid, delta)

    # 记录完成
    if p.completed_bounties is None:
        p.completed_bounties = []
    p.completed_bounties.append(bounty["id"])

    # 写入记忆
    mind = get_or_init_mind(p, "jiang")  # 风闻子记录
    mem.record_observation(
        mind,
        f"完成悬赏「{bounty['title']}」，获{coins}文钱。",
        world_day=int(p.world_day),
        world_shichen=shichen_name(p.world_shichen),
        importance=5.0,
    )

    # 清除活跃悬赏
    p.active_bounty = None

    return True, f"悬赏完成！获得{coins}文钱。", reward


def abandon_bounty(p: PlayerState) -> tuple[bool, str]:
    """放弃当前悬赏。"""
    if not p.active_bounty:
        return False, "当前没有进行中的悬赏。"
    title = p.active_bounty["title"]
    p.active_bounty = None
    return True, f"已放弃悬赏：「{title}」。"


def format_bounty_board(p: PlayerState) -> str:
    """格式化悬赏榜，用于 LLM prompt 注入。"""
    bounties = p.bounties or []
    if not bounties:
        return ""

    lines = ["【悬赏榜】县衙、镖局、漕口帮坞等处可见下列悬赏："]
    for b in bounties:
        lines.append(f"· [{b['type']}] {b['title']} —— {b['desc'][:60]}")
        reward_parts = []
        if b["reward"].get("coins"):
            reward_parts.append(f"{b['reward']['coins']}文")
        if b["reward"].get("rep"):
            for fac, d in b["reward"]["rep"].items():
                fac_name = FACTIONS.get(fac, fac)
                reward_parts.append(f"{fac_name}声望{d:+d}")
        if reward_parts:
            lines.append(f"  悬赏：{'; '.join(reward_parts)}")
    return "\n".join(lines)


def refresh_bounties(p: PlayerState) -> None:
    """刷新悬赏榜（每 3 日可刷新一次）。"""
    last_refresh_day = int(getattr(p, "last_bounty_refresh_day", 0) or 0)
    cur_day = int(p.world_day)
    if cur_day - last_refresh_day < BOUNTY_REFRESH_INTERVAL_DAYS:
        return
    p.bounties = generate_bounties(p, count=random.randint(*BOUNTY_COUNT_RANGE))
    p.last_bounty_refresh_day = cur_day
    log.info("Refreshed bounties for player %s on day %d", p.player_id, cur_day)
