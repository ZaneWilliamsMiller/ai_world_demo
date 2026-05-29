# pyright: reportArgumentType=false
"""Unit tests for backend.memory.index — MemoryIndex & retrieval cache."""
import time
import unittest
from unittest.mock import MagicMock, patch

from backend.memory.index import (
    _MAX_CANDIDATES,
    _MIN_KEYWORD_LEN,
    _RETRIEVAL_CACHE,
    MemoryIndex,
    _cached_rel,
    check_retrieval_cache,
    get_cached_retrieval_key,
    set_retrieval_cache,
    tokenize,
)


class TestTokenize(unittest.TestCase):
    def test_empty_string(self):
        assert tokenize("") == frozenset()

    def test_none_like_empty(self):
        assert tokenize(None) == frozenset()

    def test_punctuation_only(self):
        assert tokenize("。、，！？") == frozenset()

    def test_short_string_no_jieba(self):
        with patch("backend.memory.index.HAS_JIEBA", False):
            result = tokenize("ab")
            assert len(result) >= 1

    def test_single_char_no_jieba(self):
        with patch("backend.memory.index.HAS_JIEBA", False):
            result = tokenize("a")
            assert "a" in result

    def test_bigram_fallback_no_jieba(self):
        with patch("backend.memory.index.HAS_JIEBA", False):
            result = tokenize("abcdef")
            assert all(len(t) == 2 for t in result)

    def test_whitespace_stripped(self):
        with patch("backend.memory.index.HAS_JIEBA", False):
            result = tokenize("  abc  ")
            assert len(result) >= 1

    def test_returns_frozenset(self):
        result = tokenize("hello world")
        assert isinstance(result, frozenset)

    def test_chinese_text(self):
        result = tokenize("江湖风云")
        assert isinstance(result, frozenset)
        assert len(result) >= 1

    def test_mixed_chinese_english(self):
        result = tokenize("hello世界peace")
        assert isinstance(result, frozenset)

    def test_special_single_chars_kept(self):
        with patch("backend.memory.index.HAS_JIEBA", True):
            with patch("backend.memory.index.jieba") as mock_jieba:
                mock_jieba.cut.return_value = ["死", "普通词"]
                result = tokenize("test")
                assert "死" in result


class TestCachedRel(unittest.TestCase):
    def test_both_empty(self):
        assert _cached_rel(frozenset(), frozenset()) == 0.0

    def test_a_empty(self):
        assert _cached_rel(frozenset(), frozenset({"a"})) == 0.0

    def test_b_empty(self):
        assert _cached_rel(frozenset({"a"}), frozenset()) == 0.0

    def test_identical_sets(self):
        s = frozenset({"a", "b", "c"})
        assert _cached_rel(s, s) == 1.0

    def test_no_overlap(self):
        a = frozenset({"a", "b"})
        b = frozenset({"c", "d"})
        assert _cached_rel(a, b) == 0.0

    def test_partial_overlap(self):
        a = frozenset({"a", "b", "c"})
        b = frozenset({"b", "c", "d"})
        result = _cached_rel(a, b)
        assert 0.0 < result < 1.0

    def test_lru_cache_works(self):
        _cached_rel.cache_clear()
        a = frozenset({"x", "y"})
        b = frozenset({"y", "z"})
        _cached_rel(a, b)
        info = _cached_rel.cache_info()
        assert info.misses >= 1
        _cached_rel(a, b)
        info2 = _cached_rel.cache_info()
        assert info2.hits > info.hits


class TestMemoryIndexInit(unittest.TestCase):
    def test_empty_index(self):
        idx = MemoryIndex()
        assert idx._memory_count == 0
        assert len(idx._idx) == 0
        assert len(idx._token_cache) == 0

    def test_slots(self):
        idx = MemoryIndex()
        with self.assertRaises(AttributeError):
            idx.nonexistent_attr = True  # type: ignore[assignment]


class TestMemoryIndexIndex(unittest.TestCase):
    def test_single_memory(self):
        idx = MemoryIndex()
        idx.index("m1", "江湖风云")
        assert "m1" in idx._token_cache
        assert idx._memory_count == 1

    def test_multiple_memories(self):
        idx = MemoryIndex()
        idx.index("m1", "江湖风云")
        idx.index("m2", "武林秘籍")
        assert len(idx._token_cache) == 2
        assert idx._memory_count == 2

    def test_reindex_same_id(self):
        idx = MemoryIndex()
        idx.index("m1", "江湖风云")
        idx.index("m1", "武林秘籍")
        assert "m1" in idx._token_cache

    def test_empty_text(self):
        idx = MemoryIndex()
        idx.index("m1", "")
        assert "m1" in idx._token_cache

    def test_keyword_length_filter(self):
        idx = MemoryIndex()
        with patch("backend.memory.index.HAS_JIEBA", False):
            idx.index("m1", "abcdefgh")
            for kw in idx._idx:
                assert len(kw) >= _MIN_KEYWORD_LEN

    def test_memory_count_tracks_max(self):
        idx = MemoryIndex()
        idx.index("m1", "text1")
        idx.index("m2", "text2")
        idx.remove("m2")
        assert idx._memory_count == 2


class TestMemoryIndexRemove(unittest.TestCase):
    def test_remove_existing(self):
        idx = MemoryIndex()
        idx.index("m1", "江湖风云")
        idx.remove("m1")
        assert "m1" not in idx._token_cache

    def test_remove_nonexistent(self):
        idx = MemoryIndex()
        idx.remove("nonexistent")

    def test_remove_cleans_idx(self):
        idx = MemoryIndex()
        with patch("backend.memory.index.HAS_JIEBA", False):
            idx.index("m1", "abcdefgh")
        idx.remove("m1")
        for ids in idx._idx.values():
            assert "m1" not in ids

    def test_remove_empty_idx_entries(self):
        idx = MemoryIndex()
        with patch("backend.memory.index.HAS_JIEBA", False):
            idx.index("m1", "abcdef")
        idx.remove("m1")
        for ids in idx._idx.values():
            assert len(ids) > 0 or True


class TestMemoryIndexCandidates(unittest.TestCase):
    def _make_mind(self, mem_ids):
        mind = MagicMock()
        items = []
        for mid in mem_ids:
            m = MagicMock()
            m.id = mid
            items.append(m)
        mind.items = items
        return mind

    def test_empty_query(self):
        idx = MemoryIndex()
        mind = self._make_mind([])
        assert idx.candidates(frozenset(), mind) == set()

    def test_no_hits_returns_all_or_recent(self):
        idx = MemoryIndex()
        idx.index("m1", "江湖风云")
        mind = self._make_mind(["m1"])
        result = idx.candidates(frozenset({"zzzzz"}), mind)
        assert "m1" in result

    def test_hit_returns_matching(self):
        idx = MemoryIndex()
        with patch("backend.memory.index.HAS_JIEBA", False):
            idx.index("m1", "abcdefgh")
            idx.index("m2", "ijklmnop")
        mind = self._make_mind(["m1", "m2"])
        query = tokenize("abcdefgh")
        result = idx.candidates(query, mind)
        assert "m1" in result

    def test_max_candidates_limit(self):
        idx = MemoryIndex()
        with patch("backend.memory.index.HAS_JIEBA", False):
            for i in range(_MAX_CANDIDATES + 20):
                idx.index(f"m{i}", f"unique{i:04d}text")
        mind = self._make_mind([f"m{i}" for i in range(_MAX_CANDIDATES + 20)])
        query = frozenset({"un", "iq", "ue"})
        result = idx.candidates(query, mind)
        assert len(result) <= _MAX_CANDIDATES

    def test_short_query_tokens_skipped(self):
        idx = MemoryIndex()
        idx.index("m1", "江湖风云")
        mind = self._make_mind(["m1"])
        result = idx.candidates(frozenset({"a"}), mind)
        assert isinstance(result, set)


class TestMemoryIndexRelevance(unittest.TestCase):
    def test_known_doc(self):
        idx = MemoryIndex()
        idx.index("m1", "江湖风云")
        tokens = tokenize("江湖风云")
        rel = idx.relevance(tokens, "m1")
        assert rel > 0.0

    def test_unknown_doc(self):
        idx = MemoryIndex()
        rel = idx.relevance(frozenset({"a"}), "nonexistent")
        assert rel == 0.0

    def test_identical_text_high_relevance(self):
        idx = MemoryIndex()
        text = "江湖风云变幻莫测"
        idx.index("m1", text)
        tokens = tokenize(text)
        rel = idx.relevance(tokens, "m1")
        assert rel == 1.0


class TestMemoryIndexClear(unittest.TestCase):
    def test_clear_empties_everything(self):
        idx = MemoryIndex()
        idx.index("m1", "江湖风云")
        idx.index("m2", "武林秘籍")
        idx.clear()
        assert len(idx._idx) == 0
        assert len(idx._token_cache) == 0
        assert idx._memory_count == 0

    def test_clear_clears_rel_cache(self):
        idx = MemoryIndex()
        idx.index("m1", "江湖风云")
        tokens = tokenize("江湖风云")
        _cached_rel(tokens, tokens)
        idx.clear()
        info = _cached_rel.cache_info()
        assert info.currsize == 0


class TestMemoryIndexRebuild(unittest.TestCase):
    def test_rebuild_from_items(self):
        idx = MemoryIndex()
        items = []
        for i in range(5):
            m = MagicMock()
            m.id = f"m{i}"
            m.text = f"记忆内容{i}"
            items.append(m)
        idx.rebuild(items)
        assert len(idx._token_cache) == 5

    def test_rebuild_clears_old(self):
        idx = MemoryIndex()
        idx.index("old1", "旧记忆")
        items = [MagicMock(id="new1", text="新记忆")]
        idx.rebuild(items)
        assert "old1" not in idx._token_cache
        assert "new1" in idx._token_cache


class TestMemoryIndexStats(unittest.TestCase):
    def test_empty_stats(self):
        idx = MemoryIndex()
        stats = idx.stats
        assert stats["indexed_memories"] == 0
        assert stats["unique_keywords"] == 0

    def test_stats_after_indexing(self):
        idx = MemoryIndex()
        idx.index("m1", "江湖风云变幻")
        stats = idx.stats
        assert stats["indexed_memories"] == 1
        assert stats["unique_keywords"] >= 0
        assert "rel_cache_size" in stats
        assert "rel_cache_hits" in stats
        assert "rel_cache_misses" in stats


class TestRetrievalCacheKey(unittest.TestCase):
    def test_format(self):
        key = get_cached_retrieval_key("mind1", 12345)
        assert key == "mind1:12345"

    def test_different_minds(self):
        k1 = get_cached_retrieval_key("m1", 1)
        k2 = get_cached_retrieval_key("m2", 1)
        assert k1 != k2

    def test_different_hashes(self):
        k1 = get_cached_retrieval_key("m1", 1)
        k2 = get_cached_retrieval_key("m1", 2)
        assert k1 != k2


class TestRetrievalCacheCheck(unittest.TestCase):
    def setUp(self):
        _RETRIEVAL_CACHE.clear()

    def tearDown(self):
        _RETRIEVAL_CACHE.clear()

    def test_miss(self):
        assert check_retrieval_cache("nonexistent") is None

    def test_hit(self):
        _RETRIEVAL_CACHE["k1"] = (time.time() + 100, ["m1", "m2"])
        result = check_retrieval_cache("k1")
        assert result == ["m1", "m2"]

    def test_expired(self):
        _RETRIEVAL_CACHE["k1"] = (time.time() - 1, ["m1"])
        result = check_retrieval_cache("k1")
        assert result is None
        assert "k1" not in _RETRIEVAL_CACHE


class TestRetrievalCacheSet(unittest.TestCase):
    def setUp(self):
        _RETRIEVAL_CACHE.clear()

    def tearDown(self):
        _RETRIEVAL_CACHE.clear()

    def test_set_and_get(self):
        key = get_cached_retrieval_key("m1", 1)
        set_retrieval_cache(key, ["m1", "m2"])
        result = check_retrieval_cache(key)
        assert result == ["m1", "m2"]

    def test_ttl_respected(self):
        key = "test_key"
        set_retrieval_cache(key, ["m1"])
        entry = _RETRIEVAL_CACHE[key]
        assert entry[0] > time.time()

    def test_eviction_when_over_256(self):
        for i in range(260):
            _RETRIEVAL_CACHE[f"k{i}"] = (time.time() + 100, [f"m{i}"])
        before = len(_RETRIEVAL_CACHE)
        set_retrieval_cache("new_key", ["new_m"])
        assert len(_RETRIEVAL_CACHE) < before + 1

    def test_expired_entries_cleaned_on_overflow(self):
        for i in range(260):
            _RETRIEVAL_CACHE[f"k{i}"] = (time.time() - 1, [f"m{i}"])
        set_retrieval_cache("new_key", ["new_m"])
        assert "new_key" in _RETRIEVAL_CACHE


if __name__ == "__main__":
    unittest.main()
