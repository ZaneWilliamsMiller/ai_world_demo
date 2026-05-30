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

from backend import memory as mem
from backend.data.npcs_data import NPCS
from backend.data.relationships import NPC_RELATIONSHIPS
from backend.llm.client import chat_completion
from backend.llm.params import (
    CROSS_REFLECT_MAX_TOKENS,
    CROSS_REFLECT_TEMPERATURE,
    PLAN_MAX_TOKENS,
    PLAN_TEMPERATURE,
    REFLECT_MAX_TOKENS,
    REFLECT_TEMPERATURE,
)
from backend.observability.tracker import CallRecord, get_tracker

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


def _plan_deviation_analysis(
    mind: mem.AgentMind,
    world_shichen: str,
    top_observations: list[mem.Memory],
) -> str:
    """启发式计划-观察偏差分析：比较当日计划项与近期实际观察。

    对每条计划项提取关键词，在近期观察中搜索匹配：
    - 匹配 → 进展提示
    - 不匹配 → 偏差提示
    - 结果为简洁摘要，注入反思 prompt 让 LLM 有的放矢
    """
    import re
    if not mind.plan_by_shichen and not mind.plan_summary:
        return ""
    # 收集所有计划条目
    plan_items: list[tuple[str, str]] = []
    if mind.plan_summary:
        plan_items.append(("总览", mind.plan_summary))
    for sh, plan in mind.plan_by_shichen.items():
        plan_items.append((sh, plan))
    # 将观察文本合并为搜索池
    obs_pool = " ".join(m.text for m in top_observations)
    matched: list[tuple[str, str]] = []
    unmatched: list[tuple[str, str]] = []
    for label, plan_text in plan_items:
        tokens = [t for t in re.findall(r'[\u4e00-\u9fff\w]+', plan_text) if len(t) >= 2]
        if not tokens:
            continue
        hits = sum(1 for t in tokens if t in obs_pool)
        coverage = hits / len(tokens)
        if coverage >= 0.3:
            matched.append((label, plan_text))
        else:
            unmatched.append((label, plan_text))
    if not matched and not unmatched:
        return ""
    lines = ["【计划-观察偏差分析（仅作反思参考，勿在输出中直述此表）】"]
    if matched:
        lines.append(f"✅ 有迹可循：共 {len(matched)} 项计划在观察中出现")
        for label, text in matched[:3]:
            lines.append(f"  · {label}：{text}")
    if unmatched:
        lines.append(f"⚠️ 未见踪影：共 {len(unmatched)} 项计划未在观察中找到对应")
        for label, text in unmatched[:3]:
            lines.append(f"  · {label}：{text}")
        lines.append("  → 反思时可想想：搁置是因为意外、变卦还是另有隐情？")
    return "\n".join(lines)


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
    2026-05-25 改进：引入结构化计划-观察偏差分析，让反思能具体比较
    「今日打算做什么」与「实际发生了什么」，产生更有根据的洞察。
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
    # ── 偏差分析：结构化对比计划项与观察覆盖情况 ──
    deviation_block = _plan_deviation_analysis(mind, world_shichen, top)

    sys = (
        f"你是「{npc_name}」（{npc_blurb}）。\n"
        f"{mood_block}\n"
        f"{plan_block}\n"
        f"{deviation_block}\n"
        "下方是你近期的所见所历。请站在**你自己的立场**上，从中提炼 3~5 条**抽象洞察**——"
        "比如对某人的判断、对某事的趋势、对自己处境的看法。\n"
        "如果今日有计划之事却未做成，也可以反思为何偏差、心里如何打算。\n"
        "注意：你的心境会影响你看问题的角度——愤怒时更容易看到恶意，欣悦时更容易宽容。这让你的洞察更真实。\n"
        "**严格按 JSON 格式输出**，返回一个包含 `insights` 数组的对象，例如：\n"
        '{"insights": ["洞察1", "洞察2", "洞察3"]}'
    )
    user = f"近期见闻：\n{bullets}"
    _reflect_violations = []
    try:
        raw = await chat_completion(
            [{"role": "system", "content": sys}, {"role": "user", "content": user}],
            temperature=REFLECT_TEMPERATURE,
            max_tokens=REFLECT_MAX_TOKENS,
            response_format={"type": "json_object"}
        )
        data = json.loads(raw)
        insights = data.get("insights", [])
        if not isinstance(insights, list):
            insights = []
            _reflect_violations.append("insights_not_list")
    except Exception as e:
        log.warning("reflect LLM failed for %s: %s", npc_id, e)
        get_tracker().record(CallRecord(
            timestamp=time.time(),
            operation="reflect",
            model="",
            npc_id=npc_id,
            parse_success=False,
            schema_violations=["parse_error"],
            status="error",
        ))
        mind.importance_since_reflect *= 0.5
        return []

    # eval 埋点
    get_tracker().record(CallRecord(
        timestamp=time.time(),
        operation="reflect",
        model="",
        npc_id=npc_id,
        parse_success=True,
        schema_violations=_reflect_violations,
        status="success",
    ))

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

    # ── 情绪印迹回写：反思内容反馈到情绪系统 ──
    _reflect_sentiment_impact(mind, insights)

    mind.importance_since_reflect = 0.0
    mind.last_reflect_at = time.time()
    return out


# ── 反思情绪印迹常量 ──
# 正向情绪词（反思出好事 → 效价+、心绪更平静）
_REFLECT_POSITIVE = {
    "宽慰", "释然", "庆幸", "感激", "欣喜", "有望", "转机", "得利", "可靠",
    "放心", "信得过", "有缘", "仗义", "成事", "顺遂", "可交", "厚道", "稳妥",
    "帮衬", "照应", "结纳", "援手", "化解", "平息", "和睦", "坦荡",
}
# 负向情绪词（反思出坏事 → 效价-、心绪扰动）
_REFLECT_NEGATIVE = {
    "失望", "愤怒", "危险", "背叛", "陷阱", "算计", "提防", "戒备", "凶险",
    "无可挽回", "走投无路", "出卖", "辜负", "寒心", "阴险", "刁难", "逼迫",
    "暗算", "勾结", "图谋", "杀意", "灾祸", "绝路", "蒙冤", "受辱", "被迫",
}
# 唤醒度增幅词（反思中感到紧张/警觉 → 唤醒度+）
_REFLECT_AGITATION = {
    "险", "危", "杀", "死", "叛", "寇", "伏", "劫", "仇", "急", "变", "惊",
    "追", "逼", "截", "围", "灾", "祸", "噬", "冲",
}
# 唤醒度降幅词（反思后心平气和 → 唤醒度-）
_REFLECT_CALMING = {
    "安", "稳", "定", "常", "静", "平", "释", "淡", "宁", "妥", "顺",
}


def _reflect_sentiment_impact(mind: mem.AgentMind, insights: list[str]) -> None:
    """反思情绪印迹回写：在反思生成的洞察上做简单情感分析，
    将内心反思的结果反馈到情绪系统，让"想通了什么"真实影响"心情如何"。

    每次反思最多产生 ±4 效价偏移与 ±3 唤醒度偏移（多洞察聚类后取平均）。
    """
    if not insights:
        return
    total_v = 0.0
    total_a = 0.0
    causes: list[str] = []

    for text in insights:
        t = text.lower()
        # 正向 + 负向 情绪检测
        pos_hits = sum(1 for kw in _REFLECT_POSITIVE if kw in t)
        neg_hits = sum(1 for kw in _REFLECT_NEGATIVE if kw in t)
        agi_hits = sum(1 for kw in _REFLECT_AGITATION if kw in t)
        cal_hits = sum(1 for kw in _REFLECT_CALMING if kw in t)

        # 效价：正向词推升、负向词推降（每词 ~1.2）
        v_contribution = (pos_hits * 1.2) - (neg_hits * 1.5)
        total_v += max(-4.0, min(4.0, v_contribution))

        # 唤醒度：激荡词推升、沉静词推降（每词 ~1.0）
        a_contribution = (agi_hits * 1.0) - (cal_hits * 0.8)
        total_a += max(-2.5, min(2.5, a_contribution))

        # 记录原因（截取最显著的 1 句）
        if pos_hits >= 2 and "宽慰" not in causes:
            causes.append("思及顺遂")
        if neg_hits >= 2 and "心生戒备" not in causes:
            causes.append("虑及险恶")
        if agi_hits >= 2 and "心潮翻涌" not in causes:
            causes.append("心潮翻涌")
        if cal_hits >= 2 and "心绪渐平" not in causes:
            causes.append("心绪渐平")

    # 去重 + 截取前 2 条
    causes = list(dict.fromkeys(causes))[:2]
    if not causes:
        # 无显著情感信号 → 轻量效价回归
        drift = -0.8 if mind.affect_valence > 0 else 0.8 if mind.affect_valence < 0 else 0.0
        mind.update_mood(valence_delta=drift, arousal_delta=-0.4, cause="反思后心绪稍平")
        return

    cause_str = "；".join(causes)
    mind.update_mood(
        valence_delta=round(total_v / len(insights), 2),
        arousal_delta=round(total_a / len(insights), 2),
        cause=cause_str,
    )
    log.info(
        "reflect sentiment impact for mind: v=%+.2f a=%+.2f cause=%s",
        round(total_v / len(insights), 2),
        round(total_a / len(insights), 2),
        cause_str,
    )


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
            tid = rel.get("target")
            if not tid:
                continue
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

    for tid, tobs in target_obs.items():
        target_obs[tid] = list({m.id: m for m in tobs}.values())

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
                temperature=CROSS_REFLECT_TEMPERATURE,
                max_tokens=CROSS_REFLECT_MAX_TOKENS,
                response_format={"type": "json_object"},
            )
            data = json.loads(raw)
            social_insights = data.get("insights", [])
            if not isinstance(social_insights, list):
                social_insights = []
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

    _plan_violations = []
    try:
        raw = await chat_completion(
            [{"role": "system", "content": sys}, {"role": "user", "content": user}],
            temperature=PLAN_TEMPERATURE,
            max_tokens=PLAN_MAX_TOKENS,
            response_format={"type": "json_object"}
        )
        data = json.loads(raw)
        summary = str(data.get("summary", ""))[:60]
        by_shichen = data.get("schedule", {})
        if not isinstance(by_shichen, dict):
            by_shichen = {}
            _plan_violations.append("schedule_not_dict")
        if not summary:
            _plan_violations.append("summary_missing")
    except Exception as e:
        log.warning("plan_day LLM failed for %s: %s", npc_id, e)
        get_tracker().record(CallRecord(
            timestamp=time.time(),
            operation="plan_day",
            model="",
            npc_id=npc_id,
            parse_success=False,
            schema_violations=["parse_error"],
            status="error",
        ))
        mind.plan_day = int(world_day)
        mind.plan_summary = "（计划未定，随遇而安）"
        return False

    # eval 埋点
    get_tracker().record(CallRecord(
        timestamp=time.time(),
        operation="plan_day",
        model="",
        npc_id=npc_id,
        parse_success=True,
        schema_violations=_plan_violations,
        status="success",
    ))

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
    for raw_seed in seeds:
        s = (raw_seed or "").strip()
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
