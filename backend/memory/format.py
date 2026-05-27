"""记忆格式化函数：将记忆/计划/情绪/话题转化为 LLM prompt 文本。

从 memory.py 拆分而来，职责单一：格式化输出。
"""
from __future__ import annotations

from typing import Any

from backend.memory.entities import _get_all_entity_keywords


def format_memories_for_prompt(mems: list[Any]) -> str:
    """把命中的记忆条整理为给 LLM 注入的文本。"""
    if not mems:
        return ""
    lines = ["【你的脑中浮起几条记忆(自语,不必复述)】"]
    for m in mems:
        tag = {
            "observation": "见闻",
            "reflection": "心得",
            "cross_reflection": "人事察觉",
            "insight": "顿悟",
            "condensation": "往事凝华",
            "plan": "计议",
            "seed": "本心",
            "anchor": "◆心锚",
        }.get(m.kind, "记")
        stamp = f"第{m.created_day}日·{m.created_shichen}"
        lines.append(f"· [{tag} · {stamp}] {m.text}")
    return "\n".join(lines)


def format_plan_for_prompt(mind: Any, world_shichen: str) -> str:
    if not mind.plan_summary and not mind.plan_by_shichen:
        return ""
    lines = ["【今日你心里盘算的事】"]
    if mind.plan_summary:
        lines.append(f"· 总:{mind.plan_summary}")
    if mind.plan_by_shichen:
        cur = mind.plan_by_shichen.get(world_shichen, "")
        if cur:
            lines.append(f"· 此刻({world_shichen})该做:{cur}")
        else:
            for sh, text in list(mind.plan_by_shichen.items())[:2]:
                lines.append(f"· {sh}:{text}")
    return "\n".join(lines)


def format_mood_for_prompt(mind: Any) -> str:
    """将 NPC 当前情绪状态注入 system prompt(AI情感计算落地)。"""
    mood = mind.affect_mood or "平静"
    valence = mind.affect_valence
    arousal = mind.affect_arousal
    if arousal >= 7.0:
        intensity = "情绪翻涌"
    elif arousal >= 4.5:
        intensity = "心绪浮动"
    elif arousal >= 2.0:
        intensity = "心神尚定"
    else:
        intensity = "心如止水"
    if valence >= 6:
        tone_hint = "言谈间自然流露出温煦、宽容、好说话的神色"
    elif valence >= 2:
        tone_hint = "语气比平日和缓,遇事多往好处想"
    elif valence <= -6:
        tone_hint = "话里带刺、易恼、不肯轻易通融--但也别写成歇斯底里"
    elif valence <= -2:
        tone_hint = "比起往常多了几分不耐与冷淡"
    else:
        tone_hint = "神情话语皆在常度"

    lines = [
        f"【你此刻的心绪】{mood}({intensity})。",
        f"· {tone_hint}。",
    ]
    if mind.affect_cause:
        lines.append(f"· 心绪由来:{mind.affect_cause}")
    lines.append("· 请据心绪自然写出语气、用词、耐心多寡;但不要原句复述此块内容。")
    return "\n".join(lines)


def format_plan_for_reflection(mind: Any, world_shichen: str) -> str:
    """将 NPC 当日计划格式化为反思用上下文。"""
    if not mind.plan_summary and not mind.plan_by_shichen:
        return ""

    lines = ["【你今日原定的计划】"]
    if mind.plan_summary:
        lines.append(f"· 总：{mind.plan_summary}")
    shichen_order = ["子时", "丑时", "寅时", "卯时", "辰时", "巳时",
                     "午时", "未时", "申时", "酉时", "戌时", "亥时"]
    try:
        cur_idx = shichen_order.index(world_shichen)
    except ValueError:
        cur_idx = 0
    remaining = []
    for sh in shichen_order[cur_idx:]:
        plan = mind.plan_by_shichen.get(sh)
        if plan:
            remaining.append(f"{sh} {plan}")
    for sh in shichen_order[:cur_idx]:
        plan = mind.plan_by_shichen.get(sh)
        if plan:
            remaining.append(f"{sh}(已过) {plan}")
    if remaining:
        for r in remaining[:4]:
            lines.append(f"· {r}")
    lines.append("· 对照所见，若计划未竟或形势有变，心里怎么想——可融入洞察。")
    return "\n".join(lines)


def format_mood_for_reflection(mind: Any) -> str:
    """将 NPC 情绪状态格式化为反思用内部描述。"""
    mood = mind.affect_mood or "平静"
    v = mind.affect_valence
    a = mind.affect_arousal

    if v >= 6 and a >= 6:
        tint = "你此刻心境欣悦而激动，容易对人事往好处想，对善意格外敏感"
    elif v >= 4 and a >= 4:
        tint = "你心情不错，精神亢奋，反思时更容易联想到积极的可能"
    elif v >= 2:
        tint = "你心气平和偏暖，反思时倾向宽容与理解"
    elif v <= -6 and a >= 6:
        tint = "你又怒又痛，此刻的反思容易被愤懑染色——对得罪过你的人印象会更恶"
    elif v <= -4 and a >= 4:
        tint = "你心头有气，反思时容易往阴谋、恶意的方向揣测"
    elif v <= -2:
        tint = "你心情低落或戒备，反思时更难信任他人"
    elif a >= 7:
        tint = "你情绪激动，反思时思绪跳跃，容易从一件小事牵扯出很多旧事"
    elif a <= 2:
        tint = "你心如止水，反思时格外冷静，像个旁观者"
    else:
        tint = "你情绪平稳，反思时较为中立"

    lines = [
        f"【反思时的心境】{mood}（效价{v:+.1f}，唤醒度{a:.1f}）。",
        f"· {tint}。",
    ]
    if mind.affect_cause:
        lines.append(f"· 这份心绪因何而起：{mind.affect_cause}")
    return "\n".join(lines)


def format_proactive_callbacks(mind: Any, player_name: str) -> str:
    """NPC 主动回扣:从记忆流中抽取 NPC 应该主动提及的关键细节。"""
    anchors = [m for m in mind.items if m.is_anchor or m.kind == "anchor"]
    recent_obs = [m for m in mind.items if m.kind == "observation"][-10:]

    callback_lines: list[str] = []

    if anchors:
        callback_lines.append("【你心里过不去的坎/放不下的时刻】")
        for a in anchors[-3:]:
            stamp = f"第{a.created_day}日·{a.created_shichen}"
            callback_lines.append(f"· [{stamp}] {a.text[:120]}")
        callback_lines.append("· 在对话中可以自然提起这些旧事--不必生硬,像人想起旧事那样。")

    unattended: list[str] = []
    for m in recent_obs:
        t = m.text
        for kw in ("喜欢", "怕", "想要", "答应", "改日", "回头", "下次", "等我", "一定"):
            if kw in t and player_name in t:
                unattended.append(t[:80])
                break
    if unattended:
        callback_lines.append("【此人曾对你说过但尚未回扣的话】")
        for u in unattended[-3:]:
            callback_lines.append(f"· {u}")
        callback_lines.append("· 如果合适,可以自然地提起--像记得朋友说过的话那样。")

    if not callback_lines:
        return ""

    return "\n".join(callback_lines)


def format_topic_thread(hist_slice: list[dict[str, str]]) -> str:
    """对话话题线程跟踪。"""
    if len(hist_slice) < 2:
        return ""

    recent = hist_slice[-3:]

    pending_signals: list[str] = []
    topic_keywords: set[str] = set()

    for turn in recent:
        user_msg = (turn.get("user") or "").lower()
        for q_marker in ("?", "?", "吗", "呢", "如何", "怎么", "可否", "能否"):
            if q_marker in user_msg:
                q_idx = user_msg.index(q_marker)
                start = max(0, q_idx - 15)
                pending_signals.append(f"待答之问:...{user_msg[start:q_idx+2]}")
                break
        for tx_marker in ("价", "多少钱", "多少文", "买", "卖", "换", "抵押", "典当"):
            if tx_marker in user_msg:
                pending_signals.append(f"待定买卖:{user_msg[:30]}")
                break
        for kw in ("路引", "信物", "帖子", "信函", "药", "地图", "船", "马", "镖", "银", "钱",
                   "毒", "死", "杀", "逃", "救", "帮", "找", "见", "等"):
            if kw in user_msg and kw not in topic_keywords:
                topic_keywords.add(kw)

    if not pending_signals and not topic_keywords:
        return ""

    lines = ["【对话线程·保持连贯】"]
    if topic_keywords:
        kws = "、".join(list(topic_keywords)[:5])
        lines.append(f"· 你们正在谈论:{kws}--请围绕这些事回话,不要突然跳题。")
    if pending_signals:
        for ps in pending_signals[-3:]:
            lines.append(f"· {ps}--如果你还没正面回答,请先回应。")
    lines.append("· 如果玩家追问同一件事,说明他在意--别岔开,给出进展或新信息。")

    return "\n".join(lines)


def format_insight_block(mind: Any) -> str:
    """A-Mem 记忆演化顿悟注入。"""
    all_insights = mind.insights()
    if not all_insights:
        return ""

    recent = sorted(all_insights, key=lambda m: m.created_at, reverse=True)[:2]

    lines = ["【你近日的感悟（若话题触发，可自然流露——像不轻意间想通了一桩旧事）】"]
    for m in recent:
        lines.append(f"· {m.text[:120]}")
    lines.append("· 提及时点到为止，不必长篇大论——像想起一桩忽然通了的旧事。")

    return "\n".join(lines)
