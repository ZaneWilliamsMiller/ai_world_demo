"""个人记忆流(参考斯坦福「Generative Agents」论文核心机制)

从原 memory.py 拆分为子模块：
- memory (本文件): Memory/AgentMind 数据结构 + CRUD
- memory.retrieval: 检索逻辑、代词消解
- memory.format: 格式化输出（prompt 注入文本）
- memory.entities: 实体关键词、情感计算、CMA凝结、A-Mem顿悟

所有旧 `from backend.memory import xxx` 仍可用——本模块重新导出了关键 API。
"""
from __future__ import annotations

import logging
import math
import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("memory")

# ─── 从子模块重新导出（保持向后兼容；新代码请直接从子模块导入）───
from backend.memory.entities import (           # noqa: F401
    MOOD_LABELS,
    ANCHOR_VALENCE_THRESHOLD,
    ANCHOR_AROUSAL_THRESHOLD,
    ANCHOR_IMPORTANCE,
    ANCHOR_HALF_LIFE_S,
    OBS_CONDENSE_THRESHOLD,
    OBS_CONDENSE_BATCH,
    OBS_KEEP_RECENT,
    INSIGHT_LINK_THRESHOLD,
    INSIGHT_IMPORTANCE_BOOST,
    INSIGHT_MAX_PER_ADD,
    INSIGHT_COOLDOWN_S,
    PERSON_NAMES,
    PLACE_NAMES,
    THING_KEYWORDS,
    EVENT_KEYWORDS,
    ALL_ENTITY_KEYWORDS,
    _POSITIVE_MEMORY_WORDS,
    _NEGATIVE_MEMORY_WORDS,
    _MOOD_BIAS_THRESHOLD,
    _MOOD_BIAS_WEIGHT,
    init_entity_keywords,
    generate_insight_text,
    mood_from_valence_arousal,
    sentiment_hint,
    affective_memory_importance,
    _build_dynamic_entities,
    _get_person_names,
    _get_place_names,
    _get_thing_keywords,
    _get_all_entity_keywords,
)

from backend.memory.retrieval import (           # noqa: F401
    W_RECENCY,
    W_IMPORTANCE,
    W_RELEVANCE,
    REFLECTION_IMPORTANCE_TRIGGER,
    REFLECTION_MIN_INTERVAL_S,
    text_relevance,
    retrieve,
    build_retrieval_query,
    condense_old_observations,
    _resolve_deictic,
    _decay_recency,
    ensure_mind_index,
    mark_index_dirty,
    add_to_index,
)

from backend.memory.format import (              # noqa: F401
    format_memories_for_prompt,
    format_plan_for_prompt,
    format_mood_for_prompt,
    format_plan_for_reflection,
    format_mood_for_reflection,
    format_proactive_callbacks,
    format_topic_thread,
    format_insight_block,
)


# ─── 核心数据结构 ─────────────────────
@dataclass
class Memory:
    id: str
    kind: str                    # observation | reflection | insight | plan | seed | anchor
    text: str
    importance: float            # 1..10
    created_day: int             # 世界第几日
    created_shichen: str         # 世界时辰名
    created_at: float            # epoch 秒
    last_accessed: float         # epoch 秒
    refs: list[str] = field(default_factory=list)  # 反思记忆引用的来源记忆 id
    is_anchor: bool = False      # 情感锚点:关键时刻永久写入

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "text": self.text,
            "importance": float(self.importance),
            "created_day": int(self.created_day),
            "created_shichen": self.created_shichen,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "refs": list(self.refs),
            "is_anchor": self.is_anchor,
        }


@dataclass
class AgentMind:
    """单个 NPC(在某玩家会话下)的心智:记忆流 + 当日计划 + 情感状态。"""

    items: list[Memory] = field(default_factory=list)
    importance_since_reflect: float = 0.0  # 自上次反思以来累计的重要性
    last_reflect_at: float = 0.0
    plan_day: int | None = None              # 计划是为哪一日编的
    plan_by_shichen: dict[str, str] = field(default_factory=dict)  # shichen -> 一句话日程
    plan_summary: str = ""                   # 整日计划摘要(用于注入 system prompt)
    # ── 情感状态(AI情感计算)──
    affect_valence: float = 0.0      # 效价 -10..10(负→正情绪)
    affect_arousal: float = 5.0      # 唤醒度 0..10(平静→激动)
    affect_mood: str = "平静"        # 当前情绪标签
    affect_cause: str = ""           # 最近情绪变化缘由(一句白话)
    affect_updated_at: float = 0.0   # epoch 秒,最近一次情绪更新
    last_insight_at: float = 0.0      # epoch 秒,最近一次顿悟(A-Mem记忆演化)
    linked_memory_ids: set = field(default_factory=set)  # 已建立过链接的记忆ID集合(防重复链接)

    def _ensure_index(self):
        """延迟初始化记忆索引。"""
        return ensure_mind_index(self)

    def _dirty_index(self) -> None:
        """标记索引需重建。"""
        mark_index_dirty(self)

    def add(self, mem: Memory, *, _skip_evolve: bool = False) -> None:
        self.items.append(mem)
        # 索引增量更新
        add_to_index(self, mem.id, mem.text)
        if mem.kind == "observation":
            self.importance_since_reflect += mem.importance
            # A-Mem 记忆演化
            if not _skip_evolve:
                self._try_evolve_on_new_observation(mem)

    def _try_evolve_on_new_observation(self, new_obs: Memory) -> None:
        """A-Mem 记忆演化落地。"""
        from backend.memory.retrieval import _tokenize_internal, _mind_indexes
        from backend.memory.entities import (
            INSIGHT_COOLDOWN_S, INSIGHT_LINK_THRESHOLD,
            INSIGHT_IMPORTANCE_BOOST, generate_insight_text,
        )

        now = time.time()
        if (now - self.last_insight_at) < INSIGHT_COOLDOWN_S:
            return

        new_tokens = _tokenize_internal(new_obs.text)
        if len(new_tokens) < 2:
            return

        best_link: Memory | None = None
        best_score = 0.0

        for old in self.items:
            if old.kind != "observation":
                continue
            if old.id == new_obs.id:
                continue
            if old.id in self.linked_memory_ids:
                continue
            if (now - old.created_at) > 7 * 86400:
                continue
            if old.created_at >= new_obs.created_at:
                continue

            old_tokens = _tokenize_internal(old.text)
            if not old_tokens:
                continue

            overlap = len(new_tokens & old_tokens)
            union = len(new_tokens | old_tokens)
            score = overlap / union if union else 0.0
            score *= (old.importance / 10.0)

            if score > best_score:
                best_score = score
                best_link = old

        if best_link is None or best_score < INSIGHT_LINK_THRESHOLD:
            return

        old_summary = best_link.text[:60]
        new_summary = new_obs.text[:60]

        insight_text = generate_insight_text(old_summary, new_summary, best_link.importance)

        insight_mem = make_memory(
            kind="insight",
            text=insight_text[:200],
            importance=min(10.0, best_link.importance + INSIGHT_IMPORTANCE_BOOST),
            world_day=new_obs.created_day,
            world_shichen=new_obs.created_shichen,
            refs=[best_link.id, new_obs.id],
        )

        self.linked_memory_ids.add(best_link.id)
        self.last_insight_at = now

        self.add(insight_mem, _skip_evolve=True)

        log.info("记忆演化顿悟: [%s] ← [%s] → %s",
                 best_link.id[:8], new_obs.id[:8], insight_text[:60])

    def needs_reflect(self) -> bool:
        effective_threshold = self._emotion_adjusted_reflect_threshold()
        if self.importance_since_reflect < effective_threshold:
            return False
        if (time.time() - self.last_reflect_at) < REFLECTION_MIN_INTERVAL_S:
            return False
        return True

    def _emotion_adjusted_reflect_threshold(self) -> float:
        """情绪越极端，反思阈值越低。"""
        from backend.memory.retrieval import REFLECTION_IMPORTANCE_TRIGGER
        threshold = REFLECTION_IMPORTANCE_TRIGGER
        valence_impact = max(0.0, abs(self.affect_valence) - 5.0) * 2.5
        threshold -= valence_impact
        arousal_impact = max(0.0, self.affect_arousal - 6.0) * 1.5
        threshold -= arousal_impact
        return max(13.0, threshold)

    def update_mood(self, valence_delta: float = 0.0, arousal_delta: float = 0.0, cause: str = "") -> bool:
        """演化 NPC 情绪。返回 True 表示产生了情感锚点。"""
        from backend.memory.entities import (
            ANCHOR_VALENCE_THRESHOLD, ANCHOR_AROUSAL_THRESHOLD, mood_from_valence_arousal,
        )

        self.affect_valence = max(-10.0, min(10.0, self.affect_valence + valence_delta))
        self.affect_arousal = max(0.0, min(10.0, self.affect_arousal + arousal_delta))
        self.affect_mood = mood_from_valence_arousal(self.affect_valence, self.affect_arousal)
        if cause:
            self.affect_cause = cause[:80]
        self.affect_updated_at = time.time()

        is_anchor = (
            abs(valence_delta) >= ANCHOR_VALENCE_THRESHOLD
            or abs(arousal_delta) >= ANCHOR_AROUSAL_THRESHOLD
        )
        return is_anchor

    def mood_decay_tick(self, world_shichen: str) -> None:
        """时辰推进时情绪的缓慢回归。"""
        night_shichen = {"子时", "丑时", "寅时", "戌时", "亥时"}
        if world_shichen in night_shichen:
            self.update_mood(arousal_delta=-0.6, cause="夜深人倦")
        else:
            self.update_mood(arousal_delta=+0.15, cause="白昼渐醒")
        if abs(self.affect_valence) > 1.0:
            drift = -0.3 if self.affect_valence > 0 else +0.3
            self.update_mood(valence_delta=drift, cause="情绪渐平")

    def recent_observations(self, k: int = 30) -> list[Memory]:
        kinds = ("observation",)
        out = [m for m in self.items if m.kind in kinds]
        return out[-k:]

    def memory_stats(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for m in self.items:
            counts[m.kind] = counts.get(m.kind, 0) + 1
        return counts

    def reflections(self) -> list[Memory]:
        return [m for m in self.items if m.kind == "reflection"]

    def seeds(self) -> list[Memory]:
        return [m for m in self.items if m.kind == "seed"]

    def insights(self) -> list[Memory]:
        return [m for m in self.items if m.kind == "insight"]

    def serialize(self) -> dict[str, Any]:
        return {
            "items": [m.to_dict() for m in self.items],
            "importance_since_reflect": float(self.importance_since_reflect),
            "last_reflect_at": float(self.last_reflect_at),
            "plan_day": self.plan_day,
            "plan_by_shichen": dict(self.plan_by_shichen),
            "plan_summary": self.plan_summary,
            "affect_valence": float(self.affect_valence),
            "affect_arousal": float(self.affect_arousal),
            "affect_mood": self.affect_mood,
            "affect_cause": self.affect_cause,
            "last_insight_at": float(self.last_insight_at),
            "linked_memory_ids": list(self.linked_memory_ids),
        }


# ─── 操作 ─────────────────────
def make_memory(
    *,
    kind: str,
    text: str,
    importance: float,
    world_day: int,
    world_shichen: str,
    refs: Iterable[str] | None = None,
) -> Memory:
    now = time.time()
    return Memory(
        id=uuid.uuid4().hex[:10],
        kind=kind,
        text=(text or "").strip()[:500],
        importance=max(1.0, min(10.0, float(importance))),
        created_day=int(world_day),
        created_shichen=str(world_shichen),
        created_at=now,
        last_accessed=now,
        refs=list(refs or []),
    )


def estimate_importance_heuristic(text: str) -> float:
    """轻量启发式:用关键词与长度估重要性。"""
    s = text or ""
    if not s:
        return 1.0
    base = 3.0
    base += min(2.0, len(s) / 80.0)
    for kw, w in (
        ("死", 3.0), ("杀", 3.0), ("毒", 2.5), ("命", 1.5),
        ("贿", 1.5), ("银", 1.0), ("钱", 0.5), ("票", 1.0),
        ("信物", 2.0), ("信函", 1.5), ("路引", 1.5), ("帖子", 1.5),
        ("叛", 2.5), ("仇", 2.0), ("救", 1.5), ("赎身", 2.0),
        ("县衙", 1.0), ("漕口", 1.0), ("书院", 0.8), ("镖局", 1.0), ("绿林", 1.5),
    ):
        if kw in s:
            base += w
    return max(1.0, min(10.0, base))
