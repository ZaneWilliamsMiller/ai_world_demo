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

import re
import time
from collections import defaultdict
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.memory import AgentMind, Memory

try:
    import jieba

    HAS_JIEBA = True
except ImportError:
    HAS_JIEBA = False
    jieba = None  # type: ignore[misc]

_PUNCT_RE = re.compile(r"[\s,。、,.;;::!?!?\"'「」『』《》()()【】]+")

_MIN_KEYWORD_LEN = 2

_MAX_CANDIDATES = 60

_REL_CACHE_SIZE = 512


def tokenize(text: str) -> frozenset[str]:
    s = (_PUNCT_RE.sub("", text or "")).strip()
    if not s:
        return frozenset()
    if HAS_JIEBA and jieba is not None:
        words = set(jieba.cut(s))
        return frozenset({
            w for w in words
            if len(w) > 1 or w in ("死", "杀", "毒", "银", "钱", "仇", "救")
        })
    if len(s) < 2:
        return frozenset({s})
    return frozenset({s[i:i + 2] for i in range(len(s) - 1)})


@lru_cache(maxsize=_REL_CACHE_SIZE)
def _cached_rel(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


class MemoryIndex:

    __slots__ = ("_idx", "_memory_count", "_token_cache")

    def __init__(self):
        self._idx: dict[str, set[str]] = defaultdict(set)
        self._token_cache: dict[str, frozenset[str]] = {}
        self._memory_count = 0

    def index(self, mem_id: str, text: str) -> None:
        tokens = tokenize(text)
        old_tokens = self._token_cache.get(mem_id)
        if old_tokens:
            for t in old_tokens:
                if t in self._idx:
                    self._idx[t].discard(mem_id)
        self._token_cache[mem_id] = tokens
        for t in tokens:
            if len(t) >= _MIN_KEYWORD_LEN:
                self._idx[t].add(mem_id)
        self._memory_count = max(self._memory_count, len(self._token_cache))

    def remove(self, mem_id: str) -> None:
        tokens = self._token_cache.pop(mem_id, frozenset())
        for t in tokens:
            if t in self._idx:
                self._idx[t].discard(mem_id)
                if not self._idx[t]:
                    del self._idx[t]

    def candidates(self, query_tokens: frozenset[str], mind: AgentMind) -> set[str]:
        if not query_tokens:
            return set()

        hit_counts: dict[str, int] = defaultdict(int)
        for qt in query_tokens:
            if len(qt) < _MIN_KEYWORD_LEN:
                continue
            for doc_id in self._idx.get(qt, ()):
                hit_counts[doc_id] += 1

        if not hit_counts:
            all_ids = {m.id for m in mind.items}
            if len(all_ids) <= _MAX_CANDIDATES:
                return all_ids
            recent_ids = {m.id for m in list(mind.items)[-_MAX_CANDIDATES:]}
            return recent_ids

        sorted_ids = sorted(hit_counts, key=lambda k: hit_counts.get(k, 0), reverse=True)
        return set(sorted_ids[:_MAX_CANDIDATES])

    def relevance(self, query_tokens: frozenset[str], doc_id: str) -> float:
        doc_tokens = self._token_cache.get(doc_id)
        if doc_tokens is None:
            return 0.0
        return _cached_rel(query_tokens, doc_tokens)

    def clear(self) -> None:
        self._idx.clear()
        self._token_cache.clear()
        self._memory_count = 0
        _cached_rel.cache_clear()

    def rebuild(self, items: list[Memory]) -> None:
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


_RETRIEVAL_CACHE: dict[str, tuple[float, list[str]]] = {}
_RETRIEVAL_CACHE_TTL = 15.0


def get_cached_retrieval_key(mind_id: str, query_hash: int) -> str:
    return f"{mind_id}:{query_hash}"


def check_retrieval_cache(key: str) -> list[str] | None:
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
