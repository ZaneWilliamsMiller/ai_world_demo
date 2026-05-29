"""NPC 社交八卦系统 — Multi-Agent Social Gossip (MAS 涌现行为 2026)

核心思想：当两个有关系的 NPC 在同一地图格子时，可能产生「闲聊」——
生成一段 NPC 对 NPC 的对话摘要，写入双方记忆流。

这实现了 Multi-Agent Social Simulation 的涌现行为：
- NPC 之间的社交互动不需要玩家在场
- 八卦内容基于关系数据 + 最近记忆，自动产生社交网络效应
- 玩家后来与 NPC 对话时，NPC 可能自然提及"我听 XXX 说..."

设计取舍：
- 不用 LLM 生成八卦文本（零额外开销），纯启发式拼接
- 每次移动最多触发 1 次闲聊（控制频率）
- 闲聊内容来自双方最近观察记忆 + 关系 note
- 闲聊触发概率基于关系亲疏（挚交/交好 → 高概率，互不招惹 → 极低）
"""
from __future__ import annotations

import random
import time
import logging
from typing import Any

from backend.data.npcs_data import NPCS
from backend.data.relationships import NPC_RELATIONSHIPS
from backend.data.maps_data import MAPS
from backend.game_state import get_or_init_mind
from backend import memory as mem
from backend.systems.time_weather import shichen_name

log = logging.getLogger("npc_gossip")

# ─── 常量 ──────────────────────────────────────────────
GOSSIP_PROB_BASE = 0.08          # 每次移动的基础闲聊概率
GOSSIP_COOLDOWN_S = 1200.0       # 同一对 NPC 闲聊冷却 20 分钟
GOSSIP_MAX_OBS_SNIPPET = 60      # 观察记忆截取字数
GOSSIP_IMPORTANCE = 5.0          # 闲聊记忆的重要性

# 关系态度 → 触发概率倍率
ATTITUDE_MULT = {
    "挚交": 2.5,
    "交好": 2.0,
    "旧交": 1.8,
    "暧昧线人": 2.2,
    "生意往来": 1.2,
    "老主顾": 1.3,
    "面上客气": 0.8,
    "面上恭敬": 0.7,
    "互不招惹": 0.3,
    "心存芥蒂": 0.5,
    "势同水火": 0.1,
}

# ─── 内部状态 ──────────────────────────────────────────
_last_gossip: dict[str, float] = {}
_GOSSIP_CACHE_MAX = 256


def _prune_gossip_cache() -> None:
    if len(_last_gossip) <= _GOSSIP_CACHE_MAX:
        return
    sorted_keys = sorted(_last_gossip, key=_last_gossip.get, reverse=True)
    for k in sorted_keys[_GOSSIP_CACHE_MAX:]:
        del _last_gossip[k]


def _gossip_key(npc_a: str, npc_b: str) -> str:
    """生成两个 NPC 间的唯一闲聊键（字典序，保证 a+b == b+a）。"""
    pair = sorted([npc_a, npc_b])
    return f"{pair[0]}+{pair[1]}"


def _get_attitude(npc_id: str, target_id: str) -> tuple[str, float]:
    """查找 npc_id 对 target_id 的态度和概率倍率。"""
    rels = NPC_RELATIONSHIPS.get(npc_id, [])
    for r in rels:
        if r.get("target") == target_id:
            att = r.get("attitude", "互不招惹")
            mult = ATTITUDE_MULT.get(att, 0.5)
            return att, mult
    return "面熟", 0.4  # 无明确关系 → 低概率


def _get_relation_note(npc_id: str, target_id: str) -> str:
    """获取 npc_id 对 target_id 的关系备注。"""
    rels = NPC_RELATIONSHIPS.get(npc_id, [])
    for r in rels:
        if r["target"] == target_id:
            return r.get("note", "")
    return ""


def _pick_recent_snippet(mind: mem.AgentMind, about: str | None = None) -> str:
    """从 NPC 记忆流中选取一条最近的观察记忆摘要。

    如果 about 不为空，优先选包含该关键词的观察。
    """
    obs = mind.recent_observations(k=20)
    if not obs:
        return ""

    if about:
        for m in reversed(obs):
            if about.lower() in m.text.lower():
                return m.text[:GOSSIP_MAX_OBS_SNIPPET]

    # 随机选一条较新的
    recent = obs[-8:]
    if recent:
        pick = random.choice(recent)
        return pick.text[:GOSSIP_MAX_OBS_SNIPPET]
    return ""


def _generate_gossip_text(
    npc_a: str,
    npc_b: str,
    mind_a: mem.AgentMind,
    mind_b: mem.AgentMind,
) -> tuple[str, str]:
    """生成双方的闲聊观察文本。

    返回：(写入 A 的观察, 写入 B 的观察)
    纯启发式拼接，零 LLM 调用。
    """
    name_a = NPCS.get(npc_a, {}).get("name", npc_a)
    name_b = NPCS.get(npc_b, {}).get("name", npc_b)

    # A 对 B 的关系信息
    att_ab, _ = _get_attitude(npc_a, npc_b)
    note_ab = _get_relation_note(npc_a, npc_b)

    # B 对 A 的关系信息
    att_ba, _ = _get_attitude(npc_b, npc_a)
    note_ba = _get_relation_note(npc_b, npc_a)

    # 各自的最近观察
    snippet_a = _pick_recent_snippet(mind_a)
    snippet_b = _pick_recent_snippet(mind_b)

    # 生成 A 的观察："与 XXX 闲聊，XXX 说了 YYY"
    parts_a = [f"与{name_b}（{att_ab}）闲聊"]
    if snippet_b:
        parts_a.append(f"{name_b}提到：{snippet_b}")
    if note_ab and random.random() < 0.3:
        parts_a.append(f"（心中暗想：{note_ab[:40]}）")
    obs_a = "，".join(parts_a)[:200]

    # 生成 B 的观察
    parts_b = [f"与{name_a}（{att_ba}）闲聊"]
    if snippet_a:
        parts_b.append(f"{name_a}提到：{snippet_a}")
    if note_ba and random.random() < 0.3:
        parts_b.append(f"（心中暗想：{note_ba[:40]}）")
    obs_b = "，".join(parts_b)[:200]

    return obs_a, obs_b


def maybe_npc_gossip(p, *, ticks: int = 1) -> int:
    """检查并触发 NPC 间的社交闲聊。

    在 /api/move 之后调用，基于 NPC 当前位置检查同格子的 NPC 对。
    返回触发的闲聊次数。

    实现 Multi-Agent Social Simulation 的涌现行为：
    同一地图格子上的有关系的 NPC 小概率闲聊，
    闲聊内容基于各自最近的观察记忆 + 关系数据。
    """
    from backend.models.player import PlayerState
    from backend.systems.core import init_npc_positions

    if ticks <= 0:
        return 0

    init_npc_positions(p)

    # 收集每个格子上的 NPC 列表
    cell_npcs: dict[tuple[str, int, int], list[str]] = {}
    for nid, pos in p.npc_positions.items():
        meta = NPCS.get(nid, {})
        if meta.get("hidden"):
            continue
        mid, x, y = pos
        cell_npcs.setdefault((mid, x, y), []).append(nid)

    gossip_count = 0
    now = time.time()
    _prune_gossip_cache()

    for cell, nids in cell_npcs.items():
        if len(nids) < 2:
            continue

        # 检查每一对有关系的 NPC
        random.shuffle(nids)
        checked_pairs = 0
        for i in range(len(nids)):
            if gossip_count >= 1:  # 每次移动最多 1 次闲聊
                break
            for j in range(i + 1, len(nids)):
                if gossip_count >= 1:
                    break
                if checked_pairs >= 6:  # 最多检查 6 对
                    break
                checked_pairs += 1

                npc_a, npc_b = nids[i], nids[j]

                # 必须有至少一方有关系记录
                rels_a = NPC_RELATIONSHIPS.get(npc_a, [])
                rels_b = NPC_RELATIONSHIPS.get(npc_b, [])
                has_rel = any(r.get("target") == npc_b for r in rels_a) or \
                          any(r.get("target") == npc_a for r in rels_b)
                if not has_rel:
                    continue

                # 冷却检查
                gk = _gossip_key(npc_a, npc_b)
                last = _last_gossip.get(gk, 0)
                if (now - last) < GOSSIP_COOLDOWN_S:
                    continue

                # 概率判定：取双方态度中较高的倍率
                _, mult_a = _get_attitude(npc_a, npc_b)
                _, mult_b = _get_attitude(npc_b, npc_a)
                best_mult = max(mult_a, mult_b)

                prob = min(1.0, GOSSIP_PROB_BASE * best_mult * ticks)
                if random.random() > prob:
                    continue

                # 触发闲聊！
                mind_a = get_or_init_mind(p, npc_a)
                mind_b = get_or_init_mind(p, npc_b)

                obs_a, obs_b = _generate_gossip_text(npc_a, npc_b, mind_a, mind_b)

                # 写入双方记忆流
                sh_name = shichen_name(p.world_shichen)
                mind_a.add(mem.make_memory(
                    kind="observation",
                    text=obs_a,
                    importance=GOSSIP_IMPORTANCE,
                    world_day=int(p.world_day),
                    world_shichen=sh_name,
                ))
                mind_b.add(mem.make_memory(
                    kind="observation",
                    text=obs_b,
                    importance=GOSSIP_IMPORTANCE,
                    world_day=int(p.world_day),
                    world_shichen=sh_name,
                ))

                _last_gossip[gk] = now
                gossip_count += 1

                name_a = NPCS.get(npc_a, {}).get("name", npc_a)
                name_b = NPCS.get(npc_b, {}).get("name", npc_b)
                log.info("NPC闲聊: %s ↔ %s 于 %s(%d,%d)", name_a, name_b, cell[0], cell[1], cell[2])

    return gossip_count


def format_gossip_awareness_block(mind: mem.AgentMind, _npc_id: str) -> str:
    """从 NPC 记忆流中提取最近的闲聊观察，格式化为对话注入块。

    让 NPC 在对话中自然提及「刚跟 XXX 聊过」「XXX 那边听说……」。
    只取最近 1 条（避免信息过载），且只在近 2 时辰内的闲聊才注入。
    """
    import time as _time
    cutoff = _time.time() - 7200  # 2 小时内的闲聊
    obs = mind.recent_observations(k=30)
    gossip_obs = []
    for m in reversed(obs):
        if m.created_at < cutoff:
            break
        if "闲聊" in m.text and len(gossip_obs) < 1:
            gossip_obs.append(m)
    if not gossip_obs:
        return ""
    lines = ["【近日闲话（你可能在对话中顺带提及，点到为止）】"]
    for m in gossip_obs:
        lines.append(f"· {m.text[:120]}")
    return "\n".join(lines)
