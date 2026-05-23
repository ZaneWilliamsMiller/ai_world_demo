"""NPC 的「反思」与「规划」——参考斯坦福小镇 Generative Agents。

- reflect(): 取最近高重要性记忆 → 让 LLM 提炼 3~5 条**抽象洞察**回写为 reflection 记忆
- plan_day(): 让 LLM 基于人物身份/反思生成当日各时辰一句话计划

两者都是后台/手动触发，**不阻塞**主对话。LLM 解析采用 JSON Mode，
失败时不抛异常，仅记录到 logs（不会污染玩家可见层）。
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from backend import memory as mem
from backend.llm_client import chat_completion
from backend.data.relationships import NPC_RELATIONSHIPS

log = logging.getLogger("agent_brain")

# ── 跨NPC反思常量 ──
CROSS_REFLECT_MAX_TARGETS = 4       # 每次反思最多关心几个熟人
CROSS_REFLECT_MIN_OBS = 2           # 关于某个目标至少要有几条观察才反思

SHICHEN_LIST = (
    "子时", "丑时", "寅时", "卯时", "辰时", "巳时",
    "午时", "未时", "申时", "酉时", "戌时", "亥时",
)

def _deduplicate_observations(
    obs: list[mem.Memory],
    sim_threshold: float = 0.55,
) -> list[mem.Memory]:
    """语义去重：将相似度高于阈值的观察归为一组，每组仅保留最重要的那一条。

    这样可以避免把「同一件事说了三遍」塞给 LLM，既省 token 又提升反思质量。
    """
    if not obs:
        return []
    # 按重要性降序排列，确保每组保留的是最重要的
    sorted_obs = sorted(obs, key=lambda m: m.importance, reverse=True)
    groups: list[list[mem.Memory]] = []
    for m in sorted_obs:
        placed = False
        for grp in groups:
            # 检查与组内第一条（最重要）的相似度
            if mem.text_relevance(m.text, grp[0].text) >= sim_threshold:
                grp.append(m)
                placed = True
                break
        if not placed:
            groups.append([m])
    # 每组只保留最重要的一条
    return [grp[0] for grp in groups]


def _select_with_recency(
    obs: list[mem.Memory],
    top_k: int = 12,
    recency_half_life_s: float = 3600.0 * 4,
) -> list[mem.Memory]:
    """时效加权选择：综合重要性 × 时效衰减系数排序，取 top_k。

    纯按重要性排序会让一周前的「重大事件」永远压过今天刚发生的「小事」，
    而反思更应该关注最近发生的事。引入时效衰减让近期观察有适度优势。
    """
    now = time.time()
    scored = []
    for m in obs:
        age_s = max(0.0, now - m.created_at)
        recency_w = mem._decay_recency(age_s, half_life_s=recency_half_life_s)
        score = m.importance * (0.6 + 0.4 * recency_w)  # 重要性占主导，时效作微调
        scored.append((score, m))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored[:top_k]]


async def reflect(
    *,
    npc_id: str,
    npc_name: str,
    npc_blurb: str,
    mind: mem.AgentMind,
    world_day: int,
    world_shichen: str,
) -> list[mem.Memory]:
    """让 LLM 读最近高分记忆，写出 3~5 条抽象洞察。

    2026-05-24 改进：引入语义去重（同一件事不重复喂给 LLM）与时效加权选择
    （综合重要性×时效衰减），让反思更关注近期多样化的经历而非历史重复。
    """
    obs = mind.recent_observations(k=24)
    if not obs:
        return []
    # 1) 语义去重：避免「同一件事说了三遍」挤占上下文
    deduped = _deduplicate_observations(obs)
    # 2) 时效加权：综合重要性 × 时效衰减取前 12 条
    top = _select_with_recency(deduped, top_k=12)
    bullets = "\n".join(
        f"({i+1}) [第{m.created_day}日·{m.created_shichen}, 重要={m.importance:.0f}] {m.text}"
        for i, m in enumerate(top)
    )
    # ── 情绪注入：反思时的心境染色 ──
    mood_block = mem.format_mood_for_reflection(mind)
    
    # ── 计划对照：让 NPC 比较「今日计划」与「实际所见」 ──
    plan_block = mem.format_plan_for_reflection(mind, world_shichen)
    
    sys = (
        f"你是「{npc_name}」（{npc_blurb}）。\n"
        f"{mood_block}\n"
        f"{plan_block}\n"
        "下方是你近期的所见所历。请站在**你自己的立场**上，从中提炼 3~5 条**抽象洞察**——"
        "比如对某人的判断、对某事的趋势、对自己处境的看法。\n"
        "如果今日有计划之事却未做成，也可以反思为何偏差、心里如何打算。\n"
        "注意：你的心境会影响你看问题的角度——愤怒时更容易看到恶意，欣悦时更容易宽容。这让你的洞察更真实。\n"
        "**严格按 JSON 格式输出**，返回一个包含 `insights` 数组的对象，例如：\n"
        '{"insights": ["洞察1", "洞察2", "洞察3"]}'
    )
    user = f"近期见闻：\n{bullets}"
    try:
        raw = await chat_completion(
            [{"role": "system", "content": sys}, {"role": "user", "content": user}],
            temperature=0.7,
            max_tokens=400,
            response_format={"type": "json_object"}
        )
        data = json.loads(raw)
        insights = data.get("insights", [])
    except Exception as e:  # noqa: BLE001
        log.warning("reflect LLM failed for %s: %s", npc_id, e)
        return []

    insights = [i for i in (s.strip().strip("「」『』\"'") for s in insights) if i]
    insights = insights[:5]
    if not insights:
        log.info("reflect returned no insights for %s; raw=%r", npc_id, (raw or "")[:120])
        return []

    out: list[mem.Memory] = []
    refs = [m.id for m in top]
    for text in insights:
        # 反思的重要性默认略高于其源材料
        imp = max((m.importance for m in top), default=5.0)
        rmem = mem.make_memory(
            kind="reflection",
            text=text[:200],
            importance=min(10.0, imp + 0.5),
            world_day=world_day,
            world_shichen=world_shichen,
            refs=refs,
        )
        mind.add(rmem)
        out.append(rmem)

    mind.importance_since_reflect = 0.0
    mind.last_reflect_at = time.time()
    return out


async def cross_reflect(
    *,
    npc_id: str,
    npc_name: str,
    npc_blurb: str,
    mind: mem.AgentMind,
    world_day: int,
    world_shichen: str,
) -> list[mem.Memory]:
    """多智能体交叉反思协同（2026前沿）：NPC在反思自身后，
    针对关系网中的熟人进行专门反思，形成社交洞察。

    这是Multi-Agent Reflection Collaboration的落地实现：
    智能体之间不仅各自反思，还互相审视彼此的行为与变化，
    形成去中心化的社交认知网络。"""
    own_rels = NPC_RELATIONSHIPS.get(npc_id)
    if not own_rels:
        return []

    obs = mind.recent_observations(k=30)
    if len(obs) < 4:
        return []

    # 统计每个熟人被提及的观察记忆数
    target_obs: dict[str, list[mem.Memory]] = {}
    for m in obs:
        text_lower = m.text.lower()
        for rel in own_rels:
            tid = rel["target"]
            from backend.data.npcs_data import NPCS
            tname = (NPCS.get(tid, {}).get("name") or "").lower()
            tshort = (NPCS.get(tid, {}).get("short") or "").lower()
            if not tname:
                continue
            hit = (tname in text_lower) or (tshort and tshort in text_lower)
            if not hit:
                note_kw = rel.get("note", "").lower()
                if note_kw:
                    for kw in note_kw.split():
                        if len(kw) >= 2 and kw in text_lower:
                            hit = True
                            break
            if hit:
                target_obs.setdefault(tid, []).append(m)

    for tid in target_obs:
        target_obs[tid] = list({m.id: m for m in target_obs[tid]}.values())

    candidates = sorted(
        [(tid, tobs) for tid, tobs in target_obs.items()
         if len(tobs) >= CROSS_REFLECT_MIN_OBS],
        key=lambda kv: len(kv[1]),
        reverse=True,
    )[:CROSS_REFLECT_MAX_TARGETS]

    if not candidates:
        return []

    out: list[mem.Memory] = []
    for target_id, tobs in candidates:
        rel_info = next((r for r in own_rels if r["target"] == target_id), None)
        attitude = rel_info.get("attitude", "面熟") if rel_info else "面熟"
        note = rel_info.get("note", "") if rel_info else ""

        from backend.data.npcs_data import NPCS
        tname = NPCS.get(target_id, {}).get("name", target_id)

        recent_tobs = sorted(tobs, key=lambda m: m.created_at, reverse=True)[:5]
        obs_bullets = "\n".join(
            f"({j+1}) [第{m.created_day}日·{m.created_shichen}] {m.text[:180]}"
            for j, m in enumerate(recent_tobs)
        )

        # ── 情绪注入：反思时的心境染色 ──
        mood_block = mem.format_mood_for_reflection(mind)
        # ── 计划对照 ──
        plan_block = mem.format_plan_for_reflection(mind, world_shichen)
        
        sys = (
            f"你是「{npc_name}」（{npc_blurb}）。\n"
            f"{mood_block}\n"
            f"{plan_block}\n"
            f"你与「{tname}」的关系是「{attitude}」。\n"
            f"你对他/她的旧印象：{note}\n\n"
            "下面是近期你听闻或见闻的关于此人的事。请站在你自己的立场上，"
            "给出1~3句关于此人的社交洞察——你对他/她现在的看法、"
            "此人靠谱/危险/可拉拢/需提防的变化、你下一步该如何与他/她相处。\n"
            "你的心境会影响你对他的判断——愤怒时可能看谁都不顺眼，欣悦时也可能高估善意。保持真实。\n"
            "严格按JSON格式输出，包含一个insights数组：\n"
            '{"insights": ["洞察1", "洞察2"]}'
        )
        user = f"关于「{tname}」近期的见闻：\n{obs_bullets}"

        try:
            raw = await chat_completion(
                [{"role": "system", "content": sys},
                 {"role": "user", "content": user}],
                temperature=0.7,
                max_tokens=250,
                response_format={"type": "json_object"},
            )
            data = json.loads(raw)
            social_insights = data.get("insights", [])
        except Exception as e:
            log.warning("cross_reflect LLM failed for %s->%s: %s",
                        npc_id, target_id, e)
            continue

        social_insights = [
            i for i in (s.strip().strip("「」『』\"'") for s in social_insights) if i
        ][:3]

        for text in social_insights:
            imp = max((m.importance for m in tobs), default=5.0)
            deep_attitudes = {"挚交", "交好", "势同水火", "暧昧线人", "旧交"}
            imp_bonus = 0.5 if attitude in deep_attitudes else 0.0
            rmem = mem.make_memory(
                kind="cross_reflection",
                text=f"[关于{tname}] {text}"[:200],
                importance=min(10.0, imp + 0.8 + imp_bonus),
                world_day=world_day,
                world_shichen=world_shichen,
                refs=[m.id for m in recent_tobs],
            )
            mind.add(rmem)
            out.append(rmem)

    return out

async def plan_day(
    *,
    npc_id: str,
    npc_name: str,
    npc_blurb: str,
    mind: mem.AgentMind,
    world_day: int,
) -> bool:
    """为某 NPC 生成当日的时辰级计划；写入 mind.plan_*。"""
    if mind.plan_day == world_day and mind.plan_by_shichen:
        return False  # 今天已规划过

    refl_lines = "\n".join(f"· {m.text}" for m in mind.reflections()[-5:]) or "（暂无反思）"
    seed_lines = "\n".join(f"· {m.text}" for m in mind.seeds()[:6]) or "（无）"

    sys = (
        f"你是「{npc_name}」（{npc_blurb}）。请为今天写一份简短的**时辰计划**，"
        "用一行总览 + 各时辰一句话；不要解释。**严格按 JSON 格式输出**，包含 `summary` 和 `schedule`（键为时辰名，值为计划），例如：\n"
        '{"summary": "今日总览", "schedule": {"辰时": "做某事", "巳时": "做某事"}}'
    )
    user = (
        f"今天是第 {world_day} 日。\n"
        f"你近期心得：\n{refl_lines}\n\n"
        f"你的本心（角色设定切片）：\n{seed_lines}\n"
    )

    try:
        raw = await chat_completion(
            [{"role": "system", "content": sys}, {"role": "user", "content": user}],
            temperature=0.7,
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        data = json.loads(raw)
        summary = data.get("summary", "")[:60]
        by_shichen = data.get("schedule", {})
    except Exception as e:  # noqa: BLE001
        log.warning("plan_day LLM failed for %s: %s", npc_id, e)
        return False

    valid_shichen = {}
    for sh, txt in by_shichen.items():
        if sh in SHICHEN_LIST and isinstance(txt, str) and txt.strip():
            valid_shichen[sh] = txt.strip()[:40]

    if not summary and not valid_shichen:
        log.info("plan_day got no parseable plan for %s; raw=%r", npc_id, (raw or "")[:120])
        return False

    mind.plan_day = int(world_day)
    mind.plan_summary = summary
    mind.plan_by_shichen = valid_shichen
    
    # 计划入库
    plan_text = f"今日计划：{summary}。" + " ".join([f"{k} {v}" for k, v in valid_shichen.items()])
    mind.add(mem.make_memory(
        kind="plan",
        text=plan_text[:200],
        importance=5.0,
        world_day=world_day,
        world_shichen="辰时", # 假设早上规划
    ))

    return True

def import_seeds(mind: mem.AgentMind, seeds: list[str], *, world_day: int, world_shichen: str) -> None:
    """把 NPC 个人世界观切片植入为 seed 记忆（去中心化的「圣经」）。"""
    for s in seeds:
        s = (s or "").strip()
        if not s:
            continue
        mind.add(
            mem.make_memory(
                kind="seed",
                text=s,
                importance=6.0,  # 比较稳的"自己的人生信条"
                world_day=world_day,
                world_shichen=world_shichen,
            )
        )

def record_observation(
    mind: mem.AgentMind,
    text: str,
    *,
    world_day: int,
    world_shichen: str,
    importance: float | None = None,
) -> mem.Memory:
    imp = importance if importance is not None else mem.estimate_importance_heuristic(text)
    m = mem.make_memory(
        kind="observation",
        text=text,
        importance=imp,
        world_day=world_day,
        world_shichen=world_shichen,
    )
    mind.add(m)
    return m
