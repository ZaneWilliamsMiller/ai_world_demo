from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from backend.llm.cache import LlmResponseCache


class TestCacheConcurrency:

    async def test_concurrent_get_set_different_keys(self):
        cache = LlmResponseCache(max_size=256, ttl_s=300.0)
        n = 50

        async def write_read(i: int) -> None:
            msgs = [{"role": "user", "content": f"key_{i}"}]
            await cache.set(msgs, f"value_{i}")
            result = await cache.get(msgs)
            assert result == f"value_{i}"

        await asyncio.gather(*[write_read(i) for i in range(n)])

    async def test_concurrent_writes_same_key(self):
        cache = LlmResponseCache(max_size=256, ttl_s=300.0)
        msgs = [{"role": "user", "content": "shared_key"}]
        n = 50

        async def write_val(i: int) -> None:
            await cache.set(msgs, f"value_{i}")

        await asyncio.gather(*[write_val(i) for i in range(n)])

        result = await cache.get(msgs)
        assert result is not None
        assert result.startswith("value_")

    async def test_concurrent_reads_after_write(self):
        cache = LlmResponseCache(max_size=256, ttl_s=300.0)
        msgs = [{"role": "user", "content": "read_key"}]
        await cache.set(msgs, "stored_value")
        n = 100

        results = await asyncio.gather(*[cache.get(msgs) for _ in range(n)])

        for r in results:
            assert r == "stored_value"

    async def test_concurrent_get_set_no_data_corruption(self):
        cache = LlmResponseCache(max_size=256, ttl_s=300.0)
        n = 50

        async def write(i: int) -> None:
            msgs = [{"role": "user", "content": f"corrupt_{i}"}]
            await cache.set(msgs, f"val_{i}")

        async def read(i: int) -> str | None:
            msgs = [{"role": "user", "content": f"corrupt_{i}"}]
            return await cache.get(msgs)

        await asyncio.gather(*[write(i) for i in range(n)])

        results = await asyncio.gather(*[read(i) for i in range(n)])

        for i, r in enumerate(results):
            assert r == f"val_{i}"

    async def test_concurrent_mixed_operations(self):
        cache = LlmResponseCache(max_size=256, ttl_s=300.0)
        n = 50

        async def mixed_op(i: int) -> None:
            msgs = [{"role": "user", "content": f"mix_{i % 10}"}]
            await cache.set(msgs, f"v_{i}")
            await cache.get(msgs)

        await asyncio.gather(*[mixed_op(i) for i in range(n)])

        for i in range(10):
            msgs = [{"role": "user", "content": f"mix_{i}"}]
            result = await cache.get(msgs)
            assert result is not None

    async def test_stats_consistent_after_concurrent_ops(self):
        cache = LlmResponseCache(max_size=256, ttl_s=300.0)
        n = 50

        async def op(i: int) -> None:
            msgs = [{"role": "user", "content": f"stat_{i}"}]
            await cache.set(msgs, f"val_{i}")
            await cache.get(msgs)

        await asyncio.gather(*[op(i) for i in range(n)])

        s = await cache.stats()
        assert s["size"] <= n
        assert s["hits"] + s["misses"] == n
