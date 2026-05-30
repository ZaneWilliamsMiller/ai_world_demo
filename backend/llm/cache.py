"""LLM Response Cache — 2026 优化

基于 prompt 前缀哈希的 LRU 响应缓存，减少对相同 NPC 的重复 LLM 调用。
与 Prompt Cache（API 层）互补：Prompt Cache 在 5 min 窗口内复用相同前缀，
本模块在更长时间窗口内记忆「同一段 prompt → 同一段回复」的结果。

设计取舍：
- 仅缓存 JSON Mode 调用（parseable），不缓存普通文本
- 基于 messages 内容的 SHA256 哈希去重
- 仅缓存最后 N 条（LRU eviction），默认 128 条
- TTL: 300s（与 API Prompt Cache 窗口一致，避免返回过期内容）
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("llm_cache")

DEFAULT_CACHE_SIZE = 128
DEFAULT_TTL_S = 300.0  # 5 min


@dataclass
class CacheEntry:
    content: str
    created_at: float
    hits: int = 0


class LlmResponseCache:
    """LRU + TTL 响应缓存"""

    __slots__ = ("_hits", "_lock", "_max_size", "_misses", "_store", "_ttl_s")

    def __init__(self, max_size: int = DEFAULT_CACHE_SIZE, ttl_s: float = DEFAULT_TTL_S):
        self._store: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = max_size
        self._ttl_s = ttl_s
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _digest(messages: list[dict[str, Any]], *, temperature: float = 0.0, model: str = "", max_tokens: int = 0, response_format: dict[str, Any] | None = None, base_url: str = "") -> str:
        """生成 messages 的固定哈希（包含 content、role 和调用参数）。"""
        h = hashlib.sha256()
        for m in messages:
            h.update(m.get("role", "").encode())
            h.update(_content_str(m.get("content", "")).encode())
        params = f"{base_url}:{temperature}:{model}:{max_tokens}:{response_format or ''}"
        h.update(params.encode())
        return h.hexdigest()

    async def get(self, messages: list[dict[str, Any]], *, temperature: float = 0.0, model: str = "", max_tokens: int = 0, response_format: dict[str, Any] | None = None, base_url: str = "") -> str | None:
        key = self._digest(messages, temperature=temperature, model=model, max_tokens=max_tokens, response_format=response_format, base_url=base_url)
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            if time.time() - entry.created_at > self._ttl_s:
                del self._store[key]
                self._misses += 1
                return None
            # LRU: move to end (most recently used)
            self._store.move_to_end(key)
            entry.hits += 1
            self._hits += 1
            log.debug("LLM cache hit (total hits=%d, rate=%.1f%%)",
                      self._hits, self.hit_rate * 100)
            return entry.content

    async def set(self, messages: list[dict[str, Any]], content: str, *, temperature: float = 0.0, model: str = "", max_tokens: int = 0, response_format: dict[str, Any] | None = None, base_url: str = "") -> None:
        key = self._digest(messages, temperature=temperature, model=model, max_tokens=max_tokens, response_format=response_format, base_url=base_url)
        async with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                self._store[key].content = content
                self._store[key].created_at = time.time()
                return
            # Evict oldest if at capacity
            while len(self._store) >= self._max_size:
                self._store.popitem(last=False)
            self._store[key] = CacheEntry(content=content, created_at=time.time())

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    async def stats(self) -> dict[str, Any]:
        async with self._lock:
            return {
                "size": len(self._store),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self.hit_rate, 4),
                "ttl_s": self._ttl_s,
            }


def _content_str(content: str | list[dict[str, Any]] | None) -> str:
    """标准化 content 字段为字符串用于哈希。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            c.get("text", "")
            for c in content
            if isinstance(c, dict) and c.get("type") == "text"
        )
    return ""


# 全局单例
_cache: LlmResponseCache | None = None


def get_llm_cache() -> LlmResponseCache:
    global _cache
    if _cache is None:
        from backend.config import settings
        _cache = LlmResponseCache(
            max_size=settings.llm_cache_size,
            ttl_s=settings.llm_cache_ttl_s,
        )
    return _cache
