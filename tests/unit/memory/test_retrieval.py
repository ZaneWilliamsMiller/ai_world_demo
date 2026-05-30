# pyright: reportArgumentType=false
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import time
import unittest
from unittest.mock import MagicMock, patch

from backend.memory.retrieval import (
    _decay_recency,
    _mind_indexes,
    add_to_index,
    build_retrieval_query,
    condense_old_observations,
    ensure_mind_index,
    get_mind_index,
    mark_index_dirty,
    remove_mind_index,
    retrieve,
    text_relevance,
)


def _make_mem(
    mem_id="m1",
    kind="observation",
    text="test memory",
    importance=5.0,
    last_accessed=None,
    is_anchor=False,
):
    m = MagicMock()
    m.id = mem_id
    m.kind = kind
    m.text = text
    m.importance = importance
    m.last_accessed = last_accessed or time.time()
    m.is_anchor = is_anchor
    return m


def _reset_mind_indexes():
    _mind_indexes.clear()


class TestDecayRecency(unittest.TestCase):
    def test_zero_seconds_returns_one(self):
        assert _decay_recency(0) == 1.0

    def test_negative_seconds_returns_one(self):
        assert _decay_recency(-100) == 1.0

    def test_at_half_life(self):
        half = 3600.0
        result = _decay_recency(half, half_life_s=half)
        assert abs(result - 0.5) < 1e-9

    def test_double_half_life(self):
        half = 3600.0
        result = _decay_recency(half * 2, half_life_s=half)
        assert abs(result - 0.25) < 1e-9

    def test_default_half_life_six_hours(self):
        six_hours = 3600.0 * 6
        result = _decay_recency(six_hours)
        assert abs(result - 0.5) < 1e-9

    def test_monotonically_decreasing(self):
        half = 3600.0
        prev = _decay_recency(0, half)
        for t in (100, 1000, 3600, 7200, 86400):
            cur = _decay_recency(t, half)
            assert cur < prev
            prev = cur

    def test_result_between_zero_and_one(self):
        for t in (0, 1, 100, 3600, 86400, 1e6):
            val = _decay_recency(t)
            assert 0.0 < val <= 1.0

    def test_custom_half_life(self):
        result = _decay_recency(600, half_life_s=600)
        assert abs(result - 0.5) < 1e-9

    def test_very_large_seconds_approaches_zero(self):
        result = _decay_recency(1e9, half_life_s=3600)
        assert result < 1e-50


class TestTextRelevance(unittest.TestCase):
    def test_identical_strings(self):
        val = text_relevance("你好世界", "你好世界")
        assert val > 0.0

    def test_completely_different(self):
        val = text_relevance("苹果香蕉", "汽车飞机")
        assert val == 0.0

    def test_empty_query(self):
        assert text_relevance("", "some doc") == 0.0

    def test_empty_doc(self):
        assert text_relevance("some query", "") == 0.0

    def test_both_empty(self):
        assert text_relevance("", "") == 0.0

    def test_partial_overlap(self):
        val = text_relevance("你好世界", "你好明天")
        assert 0.0 < val < 1.0

    def test_self_similarity_max(self):
        text = "这是一段测试文本"
        val = text_relevance(text, text)
        assert val == 1.0

    def test_subset_query(self):
        val = text_relevance("你好", "你好世界")
        assert val > 0.0


class TestMindIndexOperations(unittest.TestCase):
    def setUp(self):
        _reset_mind_indexes()

    def tearDown(self):
        _reset_mind_indexes()

    def test_ensure_mind_index_creates_new(self):
        mind = MagicMock()
        idx = ensure_mind_index(mind)
        mind_id = id(mind)
        assert mind_id in _mind_indexes
        assert idx is _mind_indexes[mind_id]

    def test_ensure_mind_index_returns_existing(self):
        mind = MagicMock()
        idx1 = ensure_mind_index(mind)
        idx2 = ensure_mind_index(mind)
        assert idx1 is idx2

    def test_get_mind_index_exists(self):
        mind = MagicMock()
        ensure_mind_index(mind)
        result = get_mind_index(id(mind))
        assert result is not None

    def test_get_mind_index_not_exists(self):
        result = get_mind_index(999999)
        assert result is None

    def test_remove_mind_index(self):
        mind = MagicMock()
        ensure_mind_index(mind)
        mind_id = id(mind)
        assert mind_id in _mind_indexes
        remove_mind_index(mind)
        assert mind_id not in _mind_indexes

    def test_remove_mind_index_idempotent(self):
        mind = MagicMock()
        remove_mind_index(mind)
        remove_mind_index(mind)

    def test_mark_index_dirty_rebuilds(self):
        mind = MagicMock()
        m1 = _make_mem("m1", text="测试文本一")
        m2 = _make_mem("m2", text="测试文本二")
        mind.items = [m1, m2]
        idx = ensure_mind_index(mind)
        idx.index("m1", "测试文本一")
        idx.index("m2", "测试文本二")
        mark_index_dirty(mind)
        assert "m1" in idx._token_cache
        assert "m2" in idx._token_cache

    def test_mark_index_dirty_no_index(self):
        mind = MagicMock()
        mark_index_dirty(mind)

    def test_add_to_index_existing(self):
        mind = MagicMock()
        idx = ensure_mind_index(mind)
        add_to_index(mind, "new_id", "新记忆文本")
        assert "new_id" in idx._token_cache

    def test_add_to_index_no_index(self):
        mind = MagicMock()
        add_to_index(mind, "x", "text")

    def test_prune_mind_indexes(self):
        from backend.memory.index import MemoryIndex
        from backend.memory.retrieval import _MIND_INDEX_MAX, _prune_mind_indexes

        _reset_mind_indexes()
        for i in range(_MIND_INDEX_MAX + 5):
            _mind_indexes[i] = MemoryIndex()
        assert len(_mind_indexes) == _MIND_INDEX_MAX + 5
        _prune_mind_indexes()
        assert len(_mind_indexes) <= _MIND_INDEX_MAX


class TestRetrieve(unittest.TestCase):
    def setUp(self):
        _reset_mind_indexes()

    def tearDown(self):
        _reset_mind_indexes()

    @patch("backend.memory.retrieval.set_retrieval_cache")
    @patch("backend.memory.retrieval.check_retrieval_cache", return_value=None)
    @patch("backend.memory.retrieval.get_cached_retrieval_key", return_value="key1")
    def test_empty_items_returns_empty(self, mock_key, mock_check, mock_set):
        mind = MagicMock()
        mind.items = []
        result = retrieve(mind, "query")
        assert result == []

    @patch("backend.memory.retrieval.set_retrieval_cache")
    @patch("backend.memory.retrieval.check_retrieval_cache", return_value=None)
    @patch("backend.memory.retrieval.get_cached_retrieval_key", return_value="key1")
    def test_returns_top_k(self, mock_key, mock_check, mock_set):
        mind = MagicMock()
        mind.affect_valence = 0.0
        now = time.time()
        items = [
            _make_mem(f"m{i}", text=f"记忆内容{i}", importance=float(i + 1), last_accessed=now - i * 100)
            for i in range(10)
        ]
        mind.items = items
        result = retrieve(mind, "记忆", k=3)
        assert len(result) <= 3
        assert len(result) >= 1

    @patch("backend.memory.retrieval.set_retrieval_cache")
    @patch("backend.memory.retrieval.check_retrieval_cache", return_value=None)
    @patch("backend.memory.retrieval.get_cached_retrieval_key", return_value="key1")
    def test_anchor_gets_bonus(self, mock_key, mock_check, mock_set):
        mind = MagicMock()
        mind.affect_valence = 0.0
        now = time.time()
        anchor = _make_mem("anchor1", kind="anchor", text="锚点记忆", importance=5.0, last_accessed=now, is_anchor=True)
        normal = _make_mem("normal1", kind="observation", text="普通记忆", importance=5.0, last_accessed=now)
        mind.items = [normal, anchor]
        result = retrieve(mind, "记忆", k=2)
        ids = [m.id for m in result]
        assert "anchor1" in ids

    @patch("backend.memory.retrieval.set_retrieval_cache")
    @patch("backend.memory.retrieval.check_retrieval_cache", return_value=None)
    @patch("backend.memory.retrieval.get_cached_retrieval_key", return_value="key1")
    def test_player_name_bonus(self, mock_key, mock_check, mock_set):
        mind = MagicMock()
        mind.affect_valence = 0.0
        now = time.time()
        with_name = _make_mem("m1", text="张三做了事", importance=5.0, last_accessed=now)
        without = _make_mem("m2", text="李四做了事", importance=5.0, last_accessed=now)
        mind.items = [without, with_name]
        result = retrieve(mind, "做了事", k=2, player_name="张三")
        ids = [m.id for m in result]
        assert "m1" in ids

    @patch("backend.memory.retrieval.set_retrieval_cache")
    @patch("backend.memory.retrieval.check_retrieval_cache", return_value=None)
    @patch("backend.memory.retrieval.get_cached_retrieval_key", return_value="key1")
    def test_reflection_kind_bonus(self, mock_key, mock_check, mock_set):
        mind = MagicMock()
        mind.affect_valence = 0.0
        now = time.time()
        reflection = _make_mem("r1", kind="reflection", text="反思记忆内容", importance=5.0, last_accessed=now)
        obs = _make_mem("o1", kind="observation", text="观察记忆内容", importance=5.0, last_accessed=now)
        mind.items = [obs, reflection]
        result = retrieve(mind, "记忆", k=2)
        ids = [m.id for m in result]
        assert "r1" in ids

    @patch("backend.memory.retrieval.set_retrieval_cache")
    @patch("backend.memory.retrieval.check_retrieval_cache")
    @patch("backend.memory.retrieval.get_cached_retrieval_key", return_value="key1")
    def test_cached_result_used(self, mock_key, mock_check, mock_set):
        m1 = _make_mem("cached1", text="缓存记忆", importance=5.0, last_accessed=time.time())
        m2 = _make_mem("cached2", text="其他记忆", importance=5.0, last_accessed=time.time())
        mock_check.return_value = ["cached1"]
        mind = MagicMock()
        mind.affect_valence = 0.0
        mind.items = [m1, m2]
        result = retrieve(mind, "缓存")
        ids = [m.id for m in result]
        assert "cached1" in ids

    @patch("backend.memory.retrieval.set_retrieval_cache")
    @patch("backend.memory.retrieval.check_retrieval_cache", return_value=None)
    @patch("backend.memory.retrieval.get_cached_retrieval_key", return_value="key1")
    def test_updates_last_accessed(self, mock_key, mock_check, mock_set):
        mind = MagicMock()
        mind.affect_valence = 0.0
        old_time = 1000.0
        m1 = _make_mem("m1", text="测试记忆", importance=5.0, last_accessed=old_time)
        mind.items = [m1]
        retrieve(mind, "测试", k=1)
        assert m1.last_accessed > old_time

    @patch("backend.memory.retrieval.set_retrieval_cache")
    @patch("backend.memory.retrieval.check_retrieval_cache", return_value=None)
    @patch("backend.memory.retrieval.get_cached_retrieval_key", return_value="key1")
    def test_mood_bias_applied(self, mock_key, mock_check, mock_set):
        mind = MagicMock()
        mind.affect_valence = 8.0
        now = time.time()
        positive = _make_mem("p1", text="宽慰欣喜", importance=5.0, last_accessed=now)
        negative = _make_mem("n1", text="失望愤怒", importance=5.0, last_accessed=now)
        mind.items = [negative, positive]
        result = retrieve(mind, "记忆", k=2)
        ids = [m.id for m in result]
        assert "p1" in ids

    @patch("backend.memory.retrieval.set_retrieval_cache")
    @patch("backend.memory.retrieval.check_retrieval_cache", return_value=None)
    @patch("backend.memory.retrieval.get_cached_retrieval_key", return_value="key1")
    def test_k_at_least_one(self, mock_key, mock_check, mock_set):
        mind = MagicMock()
        mind.affect_valence = 0.0
        m1 = _make_mem("m1", text="唯一记忆", importance=5.0, last_accessed=time.time())
        mind.items = [m1]
        result = retrieve(mind, "唯一", k=0)
        assert len(result) >= 1


class TestResolveDeictic(unittest.TestCase):
    @patch("backend.memory.retrieval._get_all_entity_keywords", return_value=())
    @patch("backend.memory.retrieval._get_thing_keywords", return_value=())
    @patch("backend.memory.retrieval._get_place_names", return_value=())
    @patch("backend.memory.retrieval._get_person_names", return_value=("张三", "李四"))
    def test_person_pronoun_single(self, mock_pers, mock_place, mock_thing, mock_all):
        from backend.memory.retrieval import _resolve_deictic

        hist = [{"user": "张三来了", "assistant": "张三到了"}]
        result = _resolve_deictic("他, 在哪里", hist)
        assert "张三" in result

    @patch("backend.memory.retrieval._get_all_entity_keywords", return_value=())
    @patch("backend.memory.retrieval._get_thing_keywords", return_value=())
    @patch("backend.memory.retrieval._get_place_names", return_value=())
    @patch("backend.memory.retrieval._get_person_names", return_value=("王五",))
    def test_person_pronoun_plural(self, mock_pers, mock_place, mock_thing, mock_all):
        from backend.memory.retrieval import _resolve_deictic

        hist = [{"user": "王五来了", "assistant": "王五到了"}]
        result = _resolve_deictic("他们在哪里", hist)
        assert "王五" in result

    @patch("backend.memory.retrieval._get_all_entity_keywords", return_value=())
    @patch("backend.memory.retrieval._get_thing_keywords", return_value=())
    @patch("backend.memory.retrieval._get_place_names", return_value=())
    @patch("backend.memory.retrieval._get_person_names", return_value=("赵六",))
    def test_deictic_noun(self, mock_pers, mock_place, mock_thing, mock_all):
        from backend.memory.retrieval import _resolve_deictic

        hist = [{"user": "赵六来了", "assistant": "赵六到了"}]
        result = _resolve_deictic("这人是谁", hist)
        assert "赵六" in result

    @patch("backend.memory.retrieval._get_all_entity_keywords", return_value=())
    @patch("backend.memory.retrieval._get_thing_keywords", return_value=("银子",))
    @patch("backend.memory.retrieval._get_place_names", return_value=())
    @patch("backend.memory.retrieval._get_person_names", return_value=())
    def test_deictic_thing(self, mock_pers, mock_place, mock_thing, mock_all):
        from backend.memory.retrieval import _resolve_deictic

        hist = [{"user": "提到银子", "assistant": "银子很重要"}]
        result = _resolve_deictic("那件事怎么样", hist)
        assert "银子" in result

    @patch("backend.memory.retrieval._get_all_entity_keywords", return_value=())
    @patch("backend.memory.retrieval._get_thing_keywords", return_value=())
    @patch("backend.memory.retrieval._get_place_names", return_value=())
    @patch("backend.memory.retrieval._get_person_names", return_value=())
    def test_no_pronoun_returns_empty(self, mock_pers, mock_place, mock_thing, mock_all):
        from backend.memory.retrieval import _resolve_deictic

        hist = [{"user": "你好", "assistant": "你好"}]
        result = _resolve_deictic("今天天气不错", hist)
        assert result == ""

    @patch("backend.memory.retrieval._get_all_entity_keywords", return_value=())
    @patch("backend.memory.retrieval._get_thing_keywords", return_value=())
    @patch("backend.memory.retrieval._get_place_names", return_value=())
    @patch("backend.memory.retrieval._get_person_names", return_value=())
    def test_empty_hist_returns_empty(self, mock_pers, mock_place, mock_thing, mock_all):
        from backend.memory.retrieval import _resolve_deictic

        result = _resolve_deictic("他在哪", [])
        assert result == ""

    @patch("backend.memory.retrieval._get_all_entity_keywords", return_value=())
    @patch("backend.memory.retrieval._get_thing_keywords", return_value=())
    @patch("backend.memory.retrieval._get_place_names", return_value=())
    @patch("backend.memory.retrieval._get_person_names", return_value=())
    def test_empty_message_returns_empty(self, mock_pers, mock_place, mock_thing, mock_all):
        from backend.memory.retrieval import _resolve_deictic

        result = _resolve_deictic("", [{"user": "hi", "assistant": "hello"}])
        assert result == ""

    @patch("backend.memory.retrieval._get_all_entity_keywords", return_value=("镖局",))
    @patch("backend.memory.retrieval._get_thing_keywords", return_value=("镖局",))
    @patch("backend.memory.retrieval._get_place_names", return_value=())
    @patch("backend.memory.retrieval._get_person_names", return_value=())
    def test_deictic_entity_prefix(self, mock_pers, mock_place, mock_thing, mock_all):
        from backend.memory.retrieval import _resolve_deictic

        hist = [{"user": "镖局如何", "assistant": "镖局很好"}]
        result = _resolve_deictic("这镖局怎么样", hist)
        assert result != ""

    @patch("backend.memory.retrieval._get_all_entity_keywords", return_value=())
    @patch("backend.memory.retrieval._get_thing_keywords", return_value=())
    @patch("backend.memory.retrieval._get_place_names", return_value=())
    @patch("backend.memory.retrieval._get_person_names", return_value=("张三",))
    def test_resolved_includes_original_message(self, mock_pers, mock_place, mock_thing, mock_all):
        from backend.memory.retrieval import _resolve_deictic

        hist = [{"user": "张三来了", "assistant": "张三到了"}]
        result = _resolve_deictic("他, 在哪", hist)
        assert result.startswith("他, 在哪")


class TestBuildRetrievalQuery(unittest.TestCase):
    @patch("backend.memory.retrieval._resolve_deictic", return_value="")
    @patch("backend.memory.retrieval._get_all_entity_keywords", return_value=("银子", "镖局"))
    def test_short_history_returns_message(self, mock_kw, mock_deic):
        result = build_retrieval_query("你好", [{"user": "hi", "assistant": "hello"}])
        assert result == "你好"

    @patch("backend.memory.retrieval._resolve_deictic", return_value="他 张三")
    @patch("backend.memory.retrieval._get_all_entity_keywords", return_value=("银子",))
    def test_pronoun_resolved_no_topic(self, mock_kw, mock_deic):
        hist = [
            {"user": "hi", "assistant": "hello"},
            {"user": "hi2", "assistant": "hello2"},
        ]
        result = build_retrieval_query("他在哪", hist)
        assert "张三" in result

    @patch("backend.memory.retrieval._resolve_deictic", return_value="")
    @patch("backend.memory.retrieval._get_all_entity_keywords", return_value=("银子", "镖局"))
    def test_topic_words_appended(self, mock_kw, mock_deic):
        hist = [
            {"user": "银子的事", "assistant": "银子如何"},
            {"user": "镖局的事", "assistant": "镖局如何"},
        ]
        result = build_retrieval_query("查询", hist)
        assert "银子" in result or "镖局" in result

    @patch("backend.memory.retrieval._resolve_deictic", return_value="")
    @patch("backend.memory.retrieval._get_all_entity_keywords", return_value=())
    def test_no_topic_words_returns_message(self, mock_kw, mock_deic):
        hist = [
            {"user": "hello", "assistant": "world"},
            {"user": "foo", "assistant": "bar"},
        ]
        result = build_retrieval_query("查询", hist)
        assert result == "查询"

    @patch("backend.memory.retrieval._resolve_deictic", return_value="他 张三")
    @patch("backend.memory.retrieval._get_all_entity_keywords", return_value=("银子",))
    def test_pronoun_with_topic_words(self, mock_kw, mock_deic):
        hist = [
            {"user": "银子如何", "assistant": "银子不错"},
            {"user": "他来了", "assistant": "张三到了"},
        ]
        result = build_retrieval_query("他在哪", hist)
        assert "张三" in result

    @patch("backend.memory.retrieval._resolve_deictic", return_value="")
    @patch("backend.memory.retrieval._get_all_entity_keywords", return_value=("银子",))
    def test_question_marker_extracts_snippet(self, mock_kw, mock_deic):
        hist = [
            {"user": "银子的价格如何？", "assistant": "价格公道"},
            {"user": "继续", "assistant": "好的"},
        ]
        result = build_retrieval_query("查询", hist)
        assert "银子" in result


class TestCondenseOldObservations(unittest.TestCase):
    def setUp(self):
        _reset_mind_indexes()

    def tearDown(self):
        _reset_mind_indexes()

    @patch("backend.memory.entities.OBS_CONDENSE_THRESHOLD", 5)
    @patch("backend.memory.entities.OBS_KEEP_RECENT", 3)
    @patch("backend.memory.entities.OBS_CONDENSE_BATCH", 2)
    def test_below_threshold_returns_zero(self):
        mind = MagicMock()
        items = [_make_mem(f"m{i}", kind="observation", text=f"观察{i}") for i in range(3)]
        mind.items = items
        result = condense_old_observations(mind, 1, "子时")
        assert result == 0

    @patch("backend.memory.entities.OBS_CONDENSE_THRESHOLD", 5)
    @patch("backend.memory.entities.OBS_KEEP_RECENT", 3)
    @patch("backend.memory.entities.OBS_CONDENSE_BATCH", 2)
    def test_condense_removes_old_obs(self):
        mind = MagicMock()
        items = [_make_mem(f"m{i}", kind="observation", text=f"观察{i}银子") for i in range(8)]
        mind.items = items
        original_len = len(mind.items)
        result = condense_old_observations(mind, 1, "子时")
        assert result > 0
        assert len(mind.items) < original_len
        mind.add.assert_called_once()

    @patch("backend.memory.entities.OBS_CONDENSE_THRESHOLD", 5)
    @patch("backend.memory.entities.OBS_KEEP_RECENT", 3)
    @patch("backend.memory.entities.OBS_CONDENSE_BATCH", 2)
    def test_anchor_not_condensed(self):
        mind = MagicMock()
        items = [
            _make_mem("a1", kind="observation", text="锚点观察", is_anchor=True),
        ] + [_make_mem(f"m{i}", kind="observation", text=f"观察{i}银子") for i in range(7)]
        mind.items = items
        result = condense_old_observations(mind, 1, "子时")
        remaining_ids = [m.id for m in mind.items]
        assert "a1" in remaining_ids

    @patch("backend.memory.entities.OBS_CONDENSE_THRESHOLD", 5)
    @patch("backend.memory.entities.OBS_KEEP_RECENT", 3)
    @patch("backend.memory.entities.OBS_CONDENSE_BATCH", 2)
    def test_non_observation_not_condensed(self):
        mind = MagicMock()
        items = [
            _make_mem("r1", kind="reflection", text="反思内容"),
            _make_mem("r2", kind="reflection", text="反思内容2"),
        ] + [_make_mem(f"m{i}", kind="observation", text=f"观察{i}银子") for i in range(6)]
        mind.items = items
        result = condense_old_observations(mind, 1, "子时")
        remaining_kinds = [m.kind for m in mind.items]
        assert "reflection" in remaining_kinds

    @patch("backend.memory.entities.OBS_CONDENSE_THRESHOLD", 5)
    @patch("backend.memory.entities.OBS_KEEP_RECENT", 3)
    @patch("backend.memory.entities.OBS_CONDENSE_BATCH", 2)
    def test_condensation_memory_added(self):
        mind = MagicMock()
        items = [_make_mem(f"m{i}", kind="observation", text=f"观察{i}银子") for i in range(8)]
        mind.items = items
        condense_old_observations(mind, 1, "子时")
        call_args = mind.add.call_args
        mem_arg = call_args[0][0]
        assert mem_arg.kind == "condensation"

    @patch("backend.memory.entities.OBS_CONDENSE_THRESHOLD", 5)
    @patch("backend.memory.entities.OBS_KEEP_RECENT", 3)
    @patch("backend.memory.entities.OBS_CONDENSE_BATCH", 2)
    def test_keyword_grouping(self):
        mind = MagicMock()
        items = [
            _make_mem("m0", kind="observation", text="银钱往来制钱"),
            _make_mem("m1", kind="observation", text="杀人仇怨"),
            _make_mem("m2", kind="observation", text="日常琐事"),
            _make_mem("m3", kind="observation", text="观察3"),
            _make_mem("m4", kind="observation", text="观察4"),
            _make_mem("m5", kind="observation", text="观察5"),
            _make_mem("m6", kind="observation", text="观察6"),
            _make_mem("m7", kind="observation", text="观察7"),
        ]
        mind.items = items
        condense_old_observations(mind, 1, "子时")
        call_args = mind.add.call_args
        mem_arg = call_args[0][0]
        assert "记忆凝结" in mem_arg.text

    @patch("backend.memory.entities.OBS_KEEP_RECENT", 100)
    def test_keep_recent_prevents_condense(self):
        mind = MagicMock()
        items = [_make_mem(f"m{i}", kind="observation", text=f"观察{i}") for i in range(5)]
        mind.items = items
        result = condense_old_observations(mind, 1, "子时")
        assert result == 0


if __name__ == "__main__":
    unittest.main()
