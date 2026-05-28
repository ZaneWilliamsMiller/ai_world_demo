"""Fast Memory Index — 2026 优化

将记忆检索从 O(n) 线性扫描优化为索引辅助的候选过滤。

设计策略：
1. 预计算 Token Set：记忆创建时存储分词结果，检索时直接使用
2. 关键词倒排索引：按重要关键词建立 word → [memory_ids] 映射
3. 候选过滤：先用倒排索引快速过滤候选集，再对候选做精确评分
4. LRU Relevance Cache：高频查询的 relevance 结果缓存

收益预期：
- n=100 记忆：从 100 次分词+Jaccard → ~15 次精确评分（~85% 减少）
- n=500 记忆：从 500 次分词+Jaccard → ~40 次精确评分（~92% 减少）
"""

from __future__ import annotations

import math
import re
import time
from collections import defaultdict
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.memory import Memory, AgentMind

# 尝试导入 jieba
try:
    import jieba

    HAS_JIEBA = True
except ImportError:
    HAS_JIEBA = False

_PUNCT_RE = re.compile(r"[\s,。、,.;;::!?!?\"'「」『』《》()()【】]+")

# 关键词最小长度（短于此的不入索引）
_MIN_KEYWORD_LEN = 2

# 候选过滤上限：倒排索引返回的最多候选数
_MAX_CANDIDATES = 60

# LRU Relevance Cache 大小
_REL_CACHE_SIZE = 512


def tokenize(text: str) -> frozenset[str]:
    """分词 → 不可变集合（可哈希，用于缓存）。"""
    s = (_PUNCT_RE.sub("", text or "")).strip()
    if not s:
        return frozenset()
    if HAS_JIEBA:
        words = set(jieba.cut(s))
        return frozenset({
            w for w in words
            if len(w) > 1 or w in ("死", "杀", "毒", "银", "钱", "仇", "救")
        })
    # 回退到字符 bigram
    if len(s) < 2:
        return frozenset({s})
    return frozenset({s[i:i + 2] for i in range(len(s) - 1)})


@lru_cache(maxsize=_REL_CACHE_SIZE)
def _cached_rel(a: frozenset[str], b: frozenset[str]) -> float:
    """缓存的 Jaccard 相似度（参数是 frozenset 可哈希）。"""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


class MemoryIndex:
    """轻量倒排索引：按词 → 记忆 ID 快速定位候选。"""

    __slots__ = ("_idx", "_token_cache", "_memory_count")

    def __init__(self):
        self._idx: dict[str, set[str]] = defaultdict(set)
        self._token_cache: dict[str, frozenset[str]] = {}  # mem_id → tokens
        self._memory_count = 0

    def index(self, mem_id: str, text: str) -> None:
        """将记忆编入索引。"""
        tokens = tokenize(text)
        # 移除旧索引（如果存在）
        old_tokens = self._token_cache.get(mem_id)
        if old_tokens:
            for t in old_tokens:
                if t in self._idx:
                    self._idx[t].discard(mem_id)
        # 写入新索引
        self._token_cache[mem_id] = tokens
        for t in tokens:
            if len(t) >= _MIN_KEYWORD_LEN:
                self._idx[t].add(mem_id)
        self._memory_count = max(self._memory_count, len(self._token_cache))

    def remove(self, mem_id: str) -> None:
        """从索引中移除记忆。"""
        tokens = self._token_cache.pop(mem_id, frozenset())
        for t in tokens:
            if t in self._idx:
                self._idx[t].discard(mem_id)
                if not self._idx[t]:
                    del self._idx[t]

    def candidates(self, query_tokens: frozenset[str], mind: "AgentMind") -> set[str]:
        """用倒排索引快速过滤候选记忆 ID。

        策略：
        1. 查询词命中倒排索引 → 收集所有命中词的文档 ID
        2. 文档 ID 按命中次数排序，取 Top-K 候选
        3. 若倒排索引无命中 → 退回所有观察类记忆

        返回：候选记忆 ID 集合。
        """
        if not query_tokens:
            return set()

        # 统计每个 doc_id 命中了几个查询词
        hit_counts: dict[str, int] = defaultdict(int)
        for qt in query_tokens:
            if len(qt) < _MIN_KEYWORD_LEN:
                continue
            for doc_id in self._idx.get(qt, ()):
                hit_counts[doc_id] += 1

        if not hit_counts:
            # 无命中：退回全量候选（限制数量，避免全扫描）
            all_ids = {m.id for m in mind.items}
            if len(all_ids) <= _MAX_CANDIDATES:
                return all_ids
            # 候选过多时返回最近的一部分（按时间倒序取前N条）
            recent_ids = {m.id for m in list(mind.items)[-_MAX_CANDIDATES:]}
            return recent_ids

        # 按命中次数排序
        sorted_ids = sorted(hit_counts, key=hit_counts.get, reverse=True)
        return set(sorted_ids[:_MAX_CANDIDATES])

    def relevance(self, query_tokens: frozenset[str], doc_id: str) -> float:
        """计算查询与文档的 Jaccard 相似度（使用缓存的 token 集）。"""
        doc_tokens = self._token_cache.get(doc_id)
        if doc_tokens is None:
            return 0.0
        return _cached_rel(query_tokens, doc_tokens)

    def clear(self) -> None:
        """清空索引。"""
        self._idx.clear()
        self._token_cache.clear()
        self._memory_count = 0
        _cached_rel.cache_clear()

    def rebuild(self, items: list["Memory"]) -> None:
        """从记忆列表重建索引。"""
        self.clear()
        for m in items:
            self.index(m.id, m.text)

    @property
    def stats(self) -> dict:
        return {
            "indexed_memories": self._memory_count,
            "unique_keywords": len(self._idx),
            "rel_cache_size": _cached_rel.cache_info().currsize,
            "rel_cache_hits": _cached_rel.cache_info().hits,
            "rel_cache_misses": _cached_rel.cache_info().misses,
        }


# ── 模块级缓存：按 (npcs_id, query) 缓存检索结果（高频调用场景）
# 使用简单的 TTL 字典而非 functools.lru_cache（支持动态失效）
_RETRIEVAL_CACHE: dict[str, tuple[float, list[str]]] = {}  # key → (expires_at, [mem_ids])
_RETRIEVAL_CACHE_TTL = 15.0  # 15s TTL


def get_cached_retrieval_key(mind_id: str, query_hash: int) -> str:
    return f"{mind_id}:{query_hash}"


def check_retrieval_cache(key: str) -> list[str] | None:
    """检查检索结果缓存。返回 memory_id 列表或 None。"""
    entry = _RETRIEVAL_CACHE.get(key)
    if entry is None:
        return None
    expires_at, ids = entry
    if time.time() > expires_at:
        del _RETRIEVAL_CACHE[key]
        return None
    return ids


def set_retrieval_cache(key: str, ids: list[str]) -> None:
    _RETRIEVAL_CACHE[key] = (time.time() + _RETRIEVAL_CACHE_TTL, ids)
    if len(_RETRIEVAL_CACHE) > 256:
        now = time.time()
        expired = [k for k, (exp, _) in _RETRIEVAL_CACHE.items() if now > exp]
        for k in expired:
            del _RETRIEVAL_CACHE[k]
        if len(_RETRIEVAL_CACHE) > 256:
            oldest = min(_RETRIEVAL_CACHE, key=lambda k: _RETRIEVAL_CACHE[k][0])
            del _RETRIEVAL_CACHE[oldest]
