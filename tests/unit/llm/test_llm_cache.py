from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from backend.llm.cache import (
    DEFAULT_CACHE_SIZE,
    DEFAULT_TTL_S,
    LlmResponseCache,
    _content_str,
    get_llm_cache,
)


class TestContentStr:
    def test_string_content(self):
        assert _content_str("hello") == "hello"

    def test_list_of_dicts(self):
        content = [
            {"type": "text", "text": "hello "},
            {"type": "text", "text": "world"},
        ]
        assert _content_str(content) == "hello world"

    def test_list_mixed_types(self):
        content = [
            {"type": "image", "image_url": "http://x"},
            {"type": "text", "text": "only this"},
            {"not_a_dict": True},
        ]
        assert _content_str(content) == "only this"

    def test_none_content(self):
        assert _content_str(None) == ""

    def test_empty_list(self):
        assert _content_str([]) == ""

    def test_list_with_non_dict_items(self):
        content = ["skip", {"type": "text", "text": "keep"}]
        assert _content_str(content) == "keep"


class TestLlmResponseCacheInit:
    def test_defaults(self):
        c = LlmResponseCache()
        assert c._max_size == DEFAULT_CACHE_SIZE
        assert c._ttl_s == DEFAULT_TTL_S
        assert c._hits == 0
        assert c._misses == 0
        assert len(c._store) == 0

    def test_custom_params(self):
        c = LlmResponseCache(max_size=10, ttl_s=60.0)
        assert c._max_size == 10
        assert c._ttl_s == 60.0


class TestLlmResponseCacheDigest:
    def test_same_input_same_key(self):
        msgs = [{"role": "user", "content": "hi"}]
        k1 = LlmResponseCache._digest(msgs, temperature=0.5, model="gpt-4", max_tokens=100)
        k2 = LlmResponseCache._digest(msgs, temperature=0.5, model="gpt-4", max_tokens=100)
        assert k1 == k2

    def test_different_content_different_key(self):
        k1 = LlmResponseCache._digest([{"role": "user", "content": "hi"}])
        k2 = LlmResponseCache._digest([{"role": "user", "content": "bye"}])
        assert k1 != k2

    def test_different_role_different_key(self):
        k1 = LlmResponseCache._digest([{"role": "user", "content": "hi"}])
        k2 = LlmResponseCache._digest([{"role": "assistant", "content": "hi"}])
        assert k1 != k2

    def test_different_temperature_different_key(self):
        msgs = [{"role": "user", "content": "hi"}]
        k1 = LlmResponseCache._digest(msgs, temperature=0.0)
        k2 = LlmResponseCache._digest(msgs, temperature=1.0)
        assert k1 != k2

    def test_different_model_different_key(self):
        msgs = [{"role": "user", "content": "hi"}]
        k1 = LlmResponseCache._digest(msgs, model="gpt-4")
        k2 = LlmResponseCache._digest(msgs, model="gpt-3.5")
        assert k1 != k2

    def test_different_max_tokens_different_key(self):
        msgs = [{"role": "user", "content": "hi"}]
        k1 = LlmResponseCache._digest(msgs, max_tokens=100)
        k2 = LlmResponseCache._digest(msgs, max_tokens=200)
        assert k1 != k2

    def test_digest_is_hex_string(self):
        k = LlmResponseCache._digest([{"role": "user", "content": "x"}])
        assert isinstance(k, str)
        assert len(k) == 64
        int(k, 16)

    def test_list_content_in_digest(self):
        msgs = [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]
        k1 = LlmResponseCache._digest(msgs)
        msgs2 = [{"role": "user", "content": "hello"}]
        k2 = LlmResponseCache._digest(msgs2)
        assert k1 == k2

    def test_missing_role_defaults_empty(self):
        k1 = LlmResponseCache._digest([{"content": "hi"}])
        k2 = LlmResponseCache._digest([{"role": "", "content": "hi"}])
        assert k1 == k2


class TestLlmResponseCacheGet:
    @pytest.mark.asyncio
    async def test_cache_miss(self):
        c = LlmResponseCache()
        result = await c.get([{"role": "user", "content": "hi"}])
        assert result is None
        assert c._misses == 1
        assert c._hits == 0

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        c = LlmResponseCache()
        msgs = [{"role": "user", "content": "hi"}]
        await c.set(msgs, "hello")
        result = await c.get(msgs)
        assert result == "hello"
        assert c._hits == 1
        assert c._misses == 0

    @pytest.mark.asyncio
    async def test_ttl_expiration(self):
        c = LlmResponseCache(ttl_s=10.0)
        msgs = [{"role": "user", "content": "hi"}]
        with patch("backend.llm.cache.time") as mock_time:
            now = 1000.0
            mock_time.time.return_value = now
            await c.set(msgs, "hello")
            mock_time.time.return_value = now + 10.01
            result = await c.get(msgs)
        assert result is None
        assert c._misses == 1
        assert c._hits == 0

    @pytest.mark.asyncio
    async def test_ttl_not_expired(self):
        c = LlmResponseCache(ttl_s=10.0)
        msgs = [{"role": "user", "content": "hi"}]
        with patch("backend.llm.cache.time") as mock_time:
            now = 1000.0
            mock_time.time.return_value = now
            await c.set(msgs, "hello")
            mock_time.time.return_value = now + 9.99
            result = await c.get(msgs)
        assert result == "hello"
        assert c._hits == 1

    @pytest.mark.asyncio
    async def test_expired_entry_removed_from_store(self):
        c = LlmResponseCache(ttl_s=5.0)
        msgs = [{"role": "user", "content": "hi"}]
        with patch("backend.llm.cache.time") as mock_time:
            now = 1000.0
            mock_time.time.return_value = now
            await c.set(msgs, "hello")
            mock_time.time.return_value = now + 5.01
            await c.get(msgs)
        assert len(c._store) == 0

    @pytest.mark.asyncio
    async def test_hit_increments_entry_hits(self):
        c = LlmResponseCache()
        msgs = [{"role": "user", "content": "hi"}]
        await c.set(msgs, "hello")
        await c.get(msgs)
        await c.get(msgs)
        key = LlmResponseCache._digest(msgs)
        assert c._store[key].hits == 2

    @pytest.mark.asyncio
    async def test_get_with_params(self):
        c = LlmResponseCache()
        msgs = [{"role": "user", "content": "hi"}]
        await c.set(msgs, "cold", temperature=0.0)
        await c.set(msgs, "hot", temperature=1.0)
        r1 = await c.get(msgs, temperature=0.0)
        r2 = await c.get(msgs, temperature=1.0)
        assert r1 == "cold"
        assert r2 == "hot"


class TestLlmResponseCacheSet:
    @pytest.mark.asyncio
    async def test_set_then_get(self):
        c = LlmResponseCache()
        msgs = [{"role": "user", "content": "hi"}]
        await c.set(msgs, "hello")
        result = await c.get(msgs)
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_overwrite_existing_key(self):
        c = LlmResponseCache(ttl_s=9999.0)
        msgs = [{"role": "user", "content": "hi"}]
        with patch("backend.llm.cache.time") as mock_time:
            mock_time.time.return_value = 1000.0
            await c.set(msgs, "first")
            mock_time.time.return_value = 2000.0
            await c.set(msgs, "second")
            result = await c.get(msgs)
        assert result == "second"
        key = LlmResponseCache._digest(msgs)
        assert c._store[key].created_at == 2000.0

    @pytest.mark.asyncio
    async def test_overwrite_moves_to_end(self):
        c = LlmResponseCache(max_size=3)
        for i in range(3):
            await c.set([{"role": "user", "content": str(i)}], f"v{i}")
        msgs0 = [{"role": "user", "content": "0"}]
        await c.set(msgs0, "updated0")
        keys = list(c._store.keys())
        assert keys[-1] == LlmResponseCache._digest(msgs0)

    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        c = LlmResponseCache(max_size=2)
        await c.set([{"role": "user", "content": "a"}], "va")
        await c.set([{"role": "user", "content": "b"}], "vb")
        await c.set([{"role": "user", "content": "c"}], "vc")
        assert len(c._store) == 2
        result = await c.get([{"role": "user", "content": "a"}])
        assert result is None
        assert await c.get([{"role": "user", "content": "b"}]) == "vb"
        assert await c.get([{"role": "user", "content": "c"}]) == "vc"

    @pytest.mark.asyncio
    async def test_lru_eviction_after_access(self):
        c = LlmResponseCache(max_size=2)
        msgs_a = [{"role": "user", "content": "a"}]
        await c.set(msgs_a, "va")
        await c.set([{"role": "user", "content": "b"}], "vb")
        await c.get(msgs_a)
        await c.set([{"role": "user", "content": "c"}], "vc")
        assert await c.get(msgs_a) == "va"
        assert await c.get([{"role": "user", "content": "b"}]) is None


class TestLlmResponseCacheHitRate:
    def test_zero_when_no_accesses(self):
        c = LlmResponseCache()
        assert c.hit_rate == 0.0

    @pytest.mark.asyncio
    async def test_all_hits(self):
        c = LlmResponseCache()
        msgs = [{"role": "user", "content": "hi"}]
        await c.set(msgs, "hello")
        await c.get(msgs)
        assert c.hit_rate == 1.0

    @pytest.mark.asyncio
    async def test_mixed_hits_misses(self):
        c = LlmResponseCache()
        msgs = [{"role": "user", "content": "hi"}]
        await c.set(msgs, "hello")
        await c.get(msgs)
        await c.get([{"role": "user", "content": "miss"}])
        assert c.hit_rate == 0.5

    @pytest.mark.asyncio
    async def test_all_misses(self):
        c = LlmResponseCache()
        await c.get([{"role": "user", "content": "miss"}])
        assert c.hit_rate == 0.0


class TestLlmResponseCacheStats:
    @pytest.mark.asyncio
    async def test_empty_stats(self):
        c = LlmResponseCache(max_size=64, ttl_s=120.0)
        s = await c.stats()
        assert s == {
            "size": 0,
            "max_size": 64,
            "hits": 0,
            "misses": 0,
            "hit_rate": 0.0,
            "ttl_s": 120.0,
        }

    @pytest.mark.asyncio
    async def test_stats_after_operations(self):
        c = LlmResponseCache()
        msgs = [{"role": "user", "content": "hi"}]
        await c.set(msgs, "hello")
        await c.get(msgs)
        await c.get([{"role": "user", "content": "miss"}])
        s = await c.stats()
        assert s["size"] == 1
        assert s["hits"] == 1
        assert s["misses"] == 1
        assert s["hit_rate"] == 0.5
        assert s["max_size"] == DEFAULT_CACHE_SIZE
        assert s["ttl_s"] == DEFAULT_TTL_S


class TestGetLlmCache:
    def setup_method(self):
        import backend.llm.cache as mod
        mod._cache = None

    def teardown_method(self):
        import backend.llm.cache as mod
        mod._cache = None

    def test_creates_singleton(self):
        mock_settings = MagicMock()
        mock_settings.llm_cache_size = 256
        mock_settings.llm_cache_ttl_s = 600.0
        with patch.dict("sys.modules", {"backend.config": MagicMock(settings=mock_settings)}):
            import backend.llm.cache as mod
            mod._cache = None
            cache = get_llm_cache()
            assert cache._max_size == 256
            assert cache._ttl_s == 600.0

    def test_returns_same_instance(self):
        mock_settings = MagicMock()
        mock_settings.llm_cache_size = 128
        mock_settings.llm_cache_ttl_s = 300.0
        with patch.dict("sys.modules", {"backend.config": MagicMock(settings=mock_settings)}):
            import backend.llm.cache as mod
            mod._cache = None
            c1 = get_llm_cache()
            c2 = get_llm_cache()
            assert c1 is c2

    def test_resets_after_none(self):
        import backend.llm.cache as mod
        mod._cache = None
        mock_settings = MagicMock()
        mock_settings.llm_cache_size = 32
        mock_settings.llm_cache_ttl_s = 60.0
        with patch.dict("sys.modules", {"backend.config": MagicMock(settings=mock_settings)}):
            c1 = get_llm_cache()
        mod._cache = None
        with patch.dict("sys.modules", {"backend.config": MagicMock(settings=mock_settings)}):
            c2 = get_llm_cache()
        assert c1 is not c2
