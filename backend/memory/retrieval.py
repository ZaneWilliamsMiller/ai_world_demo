"""记忆检索逻辑：斯坦福式评分检索、代词消解、查询构建。

从 memory.py 拆分而来，职责：
- retrieve() 检索评分
- build_retrieval_query() 查询构建
- _resolve_deictic() 代词消解
- text_relevance() 文本相似度
"""
from __future__ import annotations

import logging
import math
import re
import time

from backend.memory_index import (
    MemoryIndex,
    tokenize,
    check_retrieval_cache,
    set_retrieval_cache,
    get_cached_retrieval_key,
)
from backend.memory.entities import (
    _get_all_entity_keywords,
    _get_person_names,
    _get_place_names,
    _get_thing_keywords,
    _MOOD_BIAS_THRESHOLD,
    _MOOD_BIAS_WEIGHT,
    sentiment_hint,
)

log = logging.getLogger("memory.retrieval")

# ─── 检索权重(仿斯坦福小镇论文取近似) ─────────────────────
W_RECENCY = 0.55
W_IMPORTANCE = 0.25
W_RELEVANCE = 0.50

# 重要性触发反思的阈值
REFLECTION_IMPORTANCE_TRIGGER = 35.0
REFLECTION_MIN_INTERVAL_S = 30.0

# ── Fast Memory Index ──
_mind_indexes: dict[int, MemoryIndex] = {}

# ─── 工具:分词与相似度 ─────────────────────
_PUNCT_RE = re.compile(r"[\s,。、,.;;::!?!?\"'「」『』《》()【】]+")


def _tokenize_internal(text: str) -> set[str]:
    """分词（向后兼容：内部调用 memory_index.tokenize）。"""
    return set(tokenize(text))


def text_relevance(query: str, doc: str) -> float:
    """基于词/字符二元组的 Jaccard 相似度。0..1。"""
    a, b = tokenize(query), tokenize(doc)
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _decay_recency(seconds_since: float, half_life_s: float = 3600.0 * 6) -> float:
    """指数衰减;默认 6 小时半衰期。返回 0..1。"""
    if seconds_since <= 0:
        return 1.0
    return math.exp(-math.log(2.0) * seconds_since / max(1.0, half_life_s))


def ensure_mind_index(mind: Any) -> MemoryIndex:
    """延迟初始化记忆索引。"""
    mind_id = id(mind)
    if mind_id not in _mind_indexes:
        _mind_indexes[mind_id] = MemoryIndex()
    return _mind_indexes[mind_id]


def get_mind_index(mind_id: int) -> MemoryIndex | None:
    """获取已有索引（不创建）。"""
    return _mind_indexes.get(mind_id)


def mark_index_dirty(mind: Any) -> None:
    """标记索引需重建。"""
    idx = _mind_indexes.get(id(mind))
    if idx is not None:
        idx.rebuild(mind.items)


def add_to_index(mind: Any, mem_id: str, mem_text: str) -> None:
    """索引增量更新（仅新增记忆，不重建）。"""
    idx = _mind_indexes.get(id(mind))
    if idx is not None:
        idx.index(mem_id, mem_text)


def retrieve(
    mind: Any,
    query: str,
    *,
    k: int = 6,
    half_life_s: float = 3600.0 * 6,
    player_name: str | None = None,
) -> list[Any]:
    """按斯坦福式分数检索:recency × importance × relevance(线性加权)。

    融入心境一致性偏差（mood-congruent memory）。
    使用 Fast Memory Index 索引辅助检索。
    """
    from backend.memory.entities import MOOD_LABELS  # noqa: F401 — backward compat

    if not mind.items:
        return []
    now = time.time()

    query_tokens = tokenize(query)

    cache_key = get_cached_retrieval_key(id(mind), hash(query))
    cached_ids = check_retrieval_cache(cache_key)
    if cached_ids is not None:
        id_to_mem = {m.id: m for m in mind.items}
        candidates = [id_to_mem[mid] for mid in cached_ids if mid in id_to_mem]
    else:
        idx: MemoryIndex = ensure_mind_index(mind)
        candidate_ids = idx.candidates(query_tokens, mind)
        id_to_mem = {m.id: m for m in mind.items}
        if candidate_ids:
            candidates = [id_to_mem[mid] for mid in candidate_ids if mid in id_to_mem]
        else:
            candidates = list(mind.items)

    if not candidates:
        return []

    idx_ref: MemoryIndex | None = _mind_indexes.get(id(mind)) if _mind_indexes else None

    rels: list[float] = []
    rel_max = 0.0
    for m in candidates:
        if idx_ref is not None:
            rel = idx_ref.relevance(query_tokens, m.id)
        else:
            rel = text_relevance(query, m.text)
        rels.append(rel)
        if rel > rel_max:
            rel_max = rel

    mood_valence = float(getattr(mind, 'affect_valence', 0.0) or 0.0)
    apply_mood_bias = abs(mood_valence) >= _MOOD_BIAS_THRESHOLD

    scored: list[tuple[float, Any]] = []
    for m, rel in zip(candidates, rels):
        rec = _decay_recency(now - m.last_accessed, half_life_s)
        imp = m.importance / 10.0
        rel_norm = (rel / rel_max) if rel_max > 0 else 0.0
        bonus = 0.05 if m.kind in ("reflection", "cross_reflection", "seed", "insight") else 0.0
        if m.is_anchor or m.kind == "anchor":
            bonus += 0.35
        if player_name and player_name in m.text:
            bonus += 0.06
        if apply_mood_bias:
            sent = sentiment_hint(m.text)
            mood_congruence = sent * (mood_valence / 10.0)
            bonus += mood_congruence * _MOOD_BIAS_WEIGHT
        score = (W_RECENCY * rec) + (W_IMPORTANCE * imp) + (W_RELEVANCE * rel_norm) + bonus
        scored.append((score, m))

    scored.sort(key=lambda kv: kv[0], reverse=True)
    top = [m for _, m in scored[: max(1, int(k))]]

    set_retrieval_cache(cache_key, [m.id for m in top])

    for m in top:
        m.last_accessed = now
    return top


def _resolve_deictic(user_message: str, hist_slice: list[dict[str, str]]) -> str:
    """中文代词/指示词消解。"""
    if not hist_slice or len(hist_slice) < 1:
        return ""

    msg = user_message.strip()
    if not msg:
        return ""

    # ── 中文指代词检测 ──
    PERSON_PRONOUNS = {"他们", "她们", "它们", "其"}
    PERSON_PRONOUN_SINGLE = {"他", "她", "它"}
    DEICTIC_NOUNS = {"这人", "那人", "此人", "彼", "这位", "那位", "该人"}
    DEICTIC_PREFIX = {"这", "那", "此", "该"}
    DEICTIC_THINGS = {"这事", "那事", "那件事", "这件事", "此", "这个", "那个", "这种", "那种"}

    has_person_pronoun = any(p in msg for p in PERSON_PRONOUNS)
    if not has_person_pronoun:
        for p in PERSON_PRONOUN_SINGLE:
            if re.search(rf"(?<![一-龟]){re.escape(p)}(?![一-龟])", msg):
                has_person_pronoun = True
                break
    has_deictic_noun = any(d in msg for d in DEICTIC_NOUNS)
    has_deictic_thing = any(d in msg for d in DEICTIC_THINGS)

    ALL_ENTITIES = _get_all_entity_keywords()
    has_deictic_entity = False
    for ent in ALL_ENTITIES:
        for prefix in ("这", "那", "此"):
            if f"{prefix}{ent}" in msg:
                has_deictic_entity = True
                break
        if has_deictic_entity:
            break

    if not (has_person_pronoun or has_deictic_noun or has_deictic_thing or has_deictic_entity):
        return ""

    _person_names = _get_person_names()
    _place_names = _get_place_names()
    _thing_kws = _get_thing_keywords()
    recent = hist_slice[-2:]
    found_persons: list[str] = []
    found_places: list[str] = []
    found_things: list[str] = []
    seen: set[str] = set()

    for turn in recent:
        assistant_text = (turn.get("assistant", "") or "").lower()
        user_text = (turn.get("user", "") or "").lower()
        combined = assistant_text + " " + user_text

        for pn in _person_names:
            if pn.lower() in combined and pn not in seen:
                found_persons.append(pn)
                seen.add(pn)
        for pl in _place_names:
            if pl.lower() in combined and pl not in seen:
                found_places.append(pl)
                seen.add(pl)
        for tk in _thing_kws:
            if tk.lower() in combined and tk not in seen:
                found_things.append(tk)
                seen.add(tk)

    resolved_terms: list[str] = []

    if has_person_pronoun or has_deictic_noun or has_deictic_entity:
        for turn in reversed(recent):
            assistant_text = (turn.get("assistant", "") or "").lower()
            for pn in _person_names:
                if pn.lower() in assistant_text:
                    if pn not in resolved_terms:
                        resolved_terms.append(pn)
                    break
            if resolved_terms:
                break
        if not resolved_terms:
            for pn in reversed(found_persons[:2]):
                resolved_terms.append(pn)

    if has_deictic_thing or has_deictic_entity:
        for turn in reversed(recent):
            assistant_text = (turn.get("assistant", "") or "").lower()
            for tk in _thing_kws:
                if tk.lower() in assistant_text:
                    if tk not in resolved_terms:
                        resolved_terms.append(tk)
                    break
            if any(t in _thing_kws for t in resolved_terms):
                break
        if not any(t in _thing_kws for t in resolved_terms):
            for tk in reversed(found_things[:2]):
                if tk not in resolved_terms:
                    resolved_terms.append(tk)

    if not resolved_terms:
        return ""

    resolved_phrase = " ".join(resolved_terms[:3])
    return f"{user_message} {resolved_phrase}"


def build_retrieval_query(user_message: str, hist_slice: list[dict[str, str]]) -> str:
    """上下文感知的记忆检索查询构建。"""
    pronoun_resolved = _resolve_deictic(user_message, hist_slice)

    if len(hist_slice) < 2:
        return pronoun_resolved or user_message

    recent = hist_slice[-4:]
    topic_words: list[str] = []

    _all_kw = _get_all_entity_keywords()
    seen_words: set[str] = set()
    for turn in recent:
        combined = (turn.get("user", "") + " " + turn.get("assistant", "")).lower()
        for kw in _all_kw:
            if kw in combined and kw not in seen_words:
                topic_words.append(kw)
                seen_words.add(kw)

    for turn in recent:
        user_msg = (turn.get("user") or "").lower()
        for q_marker in ("?", "？", "吗", "呢", "如何", "怎么", "可否"):
            if q_marker in user_msg:
                q_idx = max(0, user_msg.index(q_marker) - 20)
                snippet = user_msg[q_idx:q_idx + 30]
                for kw in _all_kw:
                    if kw in snippet and kw not in seen_words:
                        topic_words.append(kw)
                        seen_words.add(kw)
                break

    if pronoun_resolved:
        if topic_words:
            topic_chain = " ".join(topic_words[:4])
            return f"{pronoun_resolved} {topic_chain}"
        return pronoun_resolved

    if not topic_words:
        return user_message

    topic_chain = " ".join(topic_words[:6])
    return f"{user_message} {topic_chain}"


def condense_old_observations(mind: Any, world_day: int, world_shichen: str) -> int:
    """CMA式记忆凝结。"""
    from backend.memory.entities import (
        OBS_CONDENSE_THRESHOLD, OBS_CONDENSE_BATCH, OBS_KEEP_RECENT,
    )
    from backend.memory import make_memory

    obs = [m for m in mind.items if m.kind == "observation" and not m.is_anchor]
    if len(obs) <= OBS_CONDENSE_THRESHOLD:
        return 0

    if len(obs) <= OBS_KEEP_RECENT:
        return 0
    to_condense = obs[: min(OBS_CONDENSE_BATCH, len(obs) - OBS_KEEP_RECENT)]
    if not to_condense:
        return 0

    groups: dict[str, list[str]] = {}

    KW_GROUPS = {
        "银钱往来": {"银", "钱", "制钱", "铜板", "佣金", "抽头", "孝敬", "赊欠", "进账", "盘店", "搭股"},
        "江湖恩怨": {"杀", "仇", "刀", "血", "命案", "火并", "伏", "截", "绑"},
        "官府事务": {"县衙", "皂隶", "缉文", "班头", "案", "例", "引", "册"},
        "行旅见闻": {"渡", "驿", "马", "镖", "路", "卡", "哨", "桥"},
        "人情往来": {"谢", "求", "托", "帮", "恩", "情", "面", "荐"},
        "货物交易": {"货", "米", "粮", "铜", "瓷", "布", "盐", "茶", "药"},
    }

    for m in to_condense:
        t = m.text
        matched = False
        for grp, kws in KW_GROUPS.items():
            if any(kw in t for kw in kws):
                groups.setdefault(grp, []).append(t)
                matched = True
                break
        if not matched:
            groups.setdefault("日常琐碎", []).append(t)

    summaries: list[str] = []
    for grp, texts in groups.items():
        n = len(texts)
        sample = texts[0][:80] + ("..." if len(texts[0]) > 80 else "")
        summaries.append(f"{grp}约{n}事。如:{sample}")

    to_condense_ids = {m.id for m in to_condense}
    mind.items = [m for m in mind.items if m.id not in to_condense_ids]

    summary_text = f"记忆凝结：回想往昔，" + ";".join(summaries)[:400]
    mind.add(make_memory(
        kind="condensation",
        text=summary_text,
        importance=7.5,
        world_day=world_day,
        world_shichen=world_shichen,
    ), _skip_evolve=True)

    return len(to_condense)


# 类型别名
from typing import Any
