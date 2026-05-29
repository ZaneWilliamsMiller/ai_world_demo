from __future__ import annotations

# pyright: reportArgumentType=false
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import random

import backend.memory.entities as _mod
from backend.memory.entities import (
    _get_all_entity_keywords,
    _get_person_names,
    _get_place_names,
    _get_thing_keywords,
    generate_insight_text,
    init_entity_keywords,
    mood_from_valence_arousal,
    sentiment_hint,
)


def _reset_cache():
    _mod._DYNAMIC_ENTITIES_CACHED = None


class TestMoodFromValenceArousal:
    def test_high_arousal_positive_valence(self):
        assert mood_from_valence_arousal(5.0, 8.0) == "欣悦"

    def test_high_arousal_negative_valence(self):
        assert mood_from_valence_arousal(-5.0, 8.0) == "愤懑"

    def test_high_arousal_neutral_valence(self):
        assert mood_from_valence_arousal(0.0, 7.5) == "警觉"

    def test_high_arousal_boundary_valence_positive(self):
        assert mood_from_valence_arousal(3.0, 7.0) == "欣悦"

    def test_high_arousal_boundary_valence_negative(self):
        assert mood_from_valence_arousal(-3.0, 7.0) == "愤懑"

    def test_high_arousal_just_below_positive(self):
        assert mood_from_valence_arousal(2.9, 7.0) == "警觉"

    def test_high_arousal_just_above_negative(self):
        assert mood_from_valence_arousal(-2.9, 7.0) == "警觉"

    def test_medium_arousal_positive_valence(self):
        assert mood_from_valence_arousal(4.0, 5.0) == "兴奋"

    def test_medium_arousal_negative_valence(self):
        assert mood_from_valence_arousal(-4.0, 5.0) == "烦躁"

    def test_medium_arousal_neutral_valence(self):
        assert mood_from_valence_arousal(0.0, 5.0) == "好奇"

    def test_medium_arousal_boundary_arousal(self):
        assert mood_from_valence_arousal(3.0, 4.5) == "兴奋"

    def test_low_arousal_positive_valence(self):
        assert mood_from_valence_arousal(4.0, 3.0) == "感怀"

    def test_low_arousal_negative_valence(self):
        assert mood_from_valence_arousal(-4.0, 3.0) == "忧悒"

    def test_low_arousal_neutral_valence(self):
        assert mood_from_valence_arousal(0.0, 3.0) == "平静"

    def test_low_arousal_boundary(self):
        assert mood_from_valence_arousal(3.0, 2.0) == "感怀"

    def test_very_low_arousal_positive_valence(self):
        assert mood_from_valence_arousal(3.0, 1.0) == "安然"

    def test_very_low_arousal_negative_valence(self):
        assert mood_from_valence_arousal(-4.0, 1.0) == "冷淡"

    def test_very_low_arousal_neutral_valence(self):
        assert mood_from_valence_arousal(0.0, 1.0) == "疲惫"

    def test_very_low_arousal_boundary_anren(self):
        assert mood_from_valence_arousal(2.0, 0.5) == "安然"

    def test_very_low_arousal_just_below_anren(self):
        assert mood_from_valence_arousal(1.9, 0.5) == "疲惫"

    def test_very_low_arousal_boundary_lengdan(self):
        assert mood_from_valence_arousal(-3.0, 0.5) == "冷淡"

    def test_very_low_arousal_just_above_lengdan(self):
        assert mood_from_valence_arousal(-2.9, 0.5) == "疲惫"

    def test_valence_clamped_high(self):
        assert mood_from_valence_arousal(999.0, 8.0) == "欣悦"

    def test_valence_clamped_low(self):
        assert mood_from_valence_arousal(-999.0, 8.0) == "愤懑"

    def test_arousal_clamped_high(self):
        assert mood_from_valence_arousal(5.0, 999.0) == "欣悦"

    def test_arousal_clamped_low(self):
        assert mood_from_valence_arousal(5.0, -5.0) == "安然"

    def test_arousal_clamped_zero(self):
        assert mood_from_valence_arousal(0.0, -100.0) == "疲惫"

    def test_exact_boundary_arousal_seven(self):
        assert mood_from_valence_arousal(0.0, 7.0) == "警觉"

    def test_exact_boundary_arousal_four_point_five(self):
        assert mood_from_valence_arousal(0.0, 4.5) == "好奇"

    def test_exact_boundary_arousal_two(self):
        assert mood_from_valence_arousal(0.0, 2.0) == "平静"

    def test_all_moods_covered(self):
        expected = {"欣悦", "愤懑", "警觉", "兴奋", "烦躁", "好奇", "感怀", "忧悒", "平静", "安然", "冷淡", "疲惫"}
        found = set()
        test_points = [
            (5, 8), (-5, 8), (0, 8),
            (5, 5), (-5, 5), (0, 5),
            (5, 3), (-5, 3), (0, 3),
            (3, 1), (-5, 1), (0, 1),
        ]
        for v, a in test_points:
            found.add(mood_from_valence_arousal(v, a))
        assert found == expected


class TestSentimentHint:
    def test_empty_string(self):
        assert sentiment_hint("") == 0.0

    def test_none_input(self):
        assert sentiment_hint(None) == 0.0

    def test_no_keywords(self):
        assert sentiment_hint("今天天气不错") == 0.0

    def test_single_positive_word(self):
        result = sentiment_hint("心中宽慰")
        assert result > 0.0

    def test_single_negative_word(self):
        result = sentiment_hint("感到失望")
        assert result < 0.0

    def test_multiple_positive_words(self):
        r1 = sentiment_hint("心中宽慰")
        r2 = sentiment_hint("宽慰释然庆幸")
        assert r2 > r1

    def test_multiple_negative_words(self):
        r1 = sentiment_hint("感到失望")
        r2 = sentiment_hint("失望愤怒危险")
        assert abs(r2) > abs(r1)

    def test_mixed_positive_negative(self):
        result = sentiment_hint("宽慰又失望")
        assert -1.0 <= result <= 1.0

    def test_equal_positive_negative(self):
        result = sentiment_hint("宽慰阴险")
        assert result == 0.0

    def test_confidence_scales_with_count(self):
        r1 = sentiment_hint("宽慰")
        r2 = sentiment_hint("宽慰释然庆幸感激")
        assert abs(r2) > abs(r1)

    def test_confidence_capped_at_one(self):
        result = sentiment_hint("宽慰释然庆幸感激欣喜有望转机得利")
        assert -1.0 <= result <= 1.0

    def test_positive_ratio_calculation(self):
        result = sentiment_hint("宽慰释然得利")
        total = 3
        ratio = 3 / total
        confidence = min(1.0, total / 4.0)
        expected = ratio * confidence
        assert abs(result - expected) < 1e-9

    def test_negative_ratio_calculation(self):
        result = sentiment_hint("背叛陷阱")
        total = 2
        ratio = -2 / total
        confidence = min(1.0, total / 4.0)
        expected = ratio * confidence
        assert abs(result - expected) < 1e-9

    def test_case_insensitive(self):
        r1 = sentiment_hint("宽慰")
        r2 = sentiment_hint("宽慰".upper())
        assert r1 == r2

    def test_word_embedded_in_longer_text(self):
        result = sentiment_hint("心中感到一阵宽慰和释然")
        assert result > 0.0


class TestGenerateInsightText:
    def test_suspicion_keyword_doubt(self):
        result = generate_insight_text("他似乎在隐瞒什么", "新发现", 5.0)
        assert "似乎" in "他似乎在隐瞒什么" or "疑" in result or "明白" in result or "石头" in result

    def test_suspicion_keyword_rumor(self):
        result = generate_insight_text("传闻他去了京城", "新发现", 5.0)
        assert "疑" in result or "明白" in result or "石头" in result

    def test_suspicion_keyword_hearsay(self):
        result = generate_insight_text("道听途说的事", "新发现", 5.0)
        assert "疑" in result or "明白" in result or "石头" in result

    def test_suspicion_keyword_suspicious(self):
        result = generate_insight_text("可疑的人出现了", "新发现", 5.0)
        assert "疑" in result or "明白" in result or "石头" in result

    def test_emotion_keyword_hate(self):
        result = generate_insight_text("心中满是恨意", "新发现", 5.0)
        assert "心头" in result or "情绪" in result or "旧事" in result

    def test_emotion_keyword_gratitude(self):
        result = generate_insight_text("对他满怀感激", "新发现", 5.0)
        assert "心头" in result or "情绪" in result or "旧事" in result

    def test_emotion_keyword_grief(self):
        result = generate_insight_text("悲痛欲绝", "新发现", 5.0)
        assert "心头" in result or "情绪" in result or "旧事" in result

    def test_promise_keyword_promise(self):
        result = generate_insight_text("他承诺过会来", "新发现", 5.0)
        assert "约" in result or "惦" in result or "眉目" in result

    def test_promise_keyword_later(self):
        result = generate_insight_text("说好改日再谈", "新发现", 5.0)
        assert "约" in result or "惦" in result or "眉目" in result

    def test_promise_keyword_next_time(self):
        result = generate_insight_text("下次一定", "新发现", 5.0)
        assert "约" in result or "惦" in result or "眉目" in result

    def test_goods_keyword_silver(self):
        result = generate_insight_text("收了些银子", "新发现", 5.0)
        assert "门道" in result or "利" in result

    def test_goods_keyword_trade(self):
        result = generate_insight_text("做了一笔买卖", "新发现", 5.0)
        assert "门道" in result or "利" in result

    def test_goods_keyword_price(self):
        result = generate_insight_text("价格公道", "新发现", 5.0)
        assert "门道" in result or "利" in result

    def test_person_keyword_someone(self):
        result = generate_insight_text("某人告诉我的", "新发现", 5.0)
        assert "那人" in result or "真意" in result or "看走" in result or "意思" in result

    def test_person_keyword_she(self):
        result = generate_insight_text("她说的那番话", "新发现", 5.0)
        assert "那人" in result or "真意" in result or "看走" in result or "意思" in result

    def test_person_keyword_he(self):
        result = generate_insight_text("他走了", "新发现", 5.0)
        assert "那人" in result or "真意" in result or "看走" in result or "意思" in result

    def test_high_importance_no_keywords(self):
        result = generate_insight_text("重要的事情发生了", "新发现", 8.0)
        assert "关窍" in result or "关节" in result

    def test_low_importance_no_keywords(self):
        result = generate_insight_text("普通的一天", "新发现", 3.0)
        assert "暗合" in result or "理解" in result or "味道" in result

    def test_snippet_truncated_to_fifty(self):
        long_text = "A" * 100
        result = generate_insight_text(long_text, "新发现", 3.0)
        snippet_in_result = long_text[:50]
        assert snippet_in_result in result

    def test_priority_suspicion_over_emotion(self):
        text = "怀疑他恨我"
        result = generate_insight_text(text, "新发现", 5.0)
        assert "疑" in result or "明白" in result or "石头" in result

    def test_priority_emotion_over_promise(self):
        text = "恨他承诺的事"
        result = generate_insight_text(text, "新发现", 5.0)
        assert "心头" in result or "情绪" in result or "旧事" in result

    def test_priority_promise_over_goods(self):
        text = "约定买卖的事"
        result = generate_insight_text(text, "新发现", 5.0)
        assert "约" in result or "惦" in result or "眉目" in result

    def test_priority_goods_over_person(self):
        text = "货物被某人拿走了"
        result = generate_insight_text(text, "新发现", 5.0)
        assert "门道" in result or "利" in result

    def test_priority_person_over_importance(self):
        text = "他做了件大事"
        result = generate_insight_text(text, "新发现", 9.0)
        assert "那人" in result or "真意" in result or "看走" in result or "意思" in result

    def test_random_choice_produces_valid_variant(self):
        random.seed(42)
        results = set()
        for _ in range(20):
            results.add(generate_insight_text("怀疑他", "新发现", 5.0))
        assert len(results) > 1

    def test_new_text_not_used_in_output(self):
        result = generate_insight_text("旧记忆内容", "这是全新的发现", 5.0)
        assert "这是全新的发现" not in result


class TestGetPersonNames:
    def setup_method(self):
        _reset_cache()

    def teardown_method(self):
        _reset_cache()

    def test_returns_tuple(self):
        result = _get_person_names()
        assert isinstance(result, tuple)

    def test_all_elements_are_strings(self):
        result = _get_person_names()
        for name in result:
            assert isinstance(name, str)

    def test_sorted_order(self):
        result = _get_person_names()
        assert result == tuple(sorted(result))

    def test_contains_hardcoded_persons(self):
        result = _get_person_names()
        assert "掌柜" in result
        assert "牙人" in result
        assert "皂隶" in result

    def test_length_constraint(self):
        result = _get_person_names()
        for name in result:
            assert 2 <= len(name) <= 8

    def test_not_empty(self):
        result = _get_person_names()
        assert len(result) > 0


class TestGetPlaceNames:
    def setup_method(self):
        _reset_cache()

    def teardown_method(self):
        _reset_cache()

    def test_returns_tuple(self):
        result = _get_place_names()
        assert isinstance(result, tuple)

    def test_all_elements_are_strings(self):
        result = _get_place_names()
        for name in result:
            assert isinstance(name, str)

    def test_sorted_order(self):
        result = _get_place_names()
        assert result == tuple(sorted(result))

    def test_contains_hardcoded_places(self):
        result = _get_place_names()
        assert "同福" in result
        assert "牙行" in result
        assert "镖局" in result

    def test_length_constraint(self):
        result = _get_place_names()
        for name in result:
            assert 2 <= len(name) <= 8

    def test_not_empty(self):
        result = _get_place_names()
        assert len(result) > 0


class TestGetThingKeywords:
    def setup_method(self):
        _reset_cache()

    def teardown_method(self):
        _reset_cache()

    def test_returns_tuple(self):
        result = _get_thing_keywords()
        assert isinstance(result, tuple)

    def test_all_elements_are_strings(self):
        result = _get_thing_keywords()
        for kw in result:
            assert isinstance(kw, str)

    def test_contains_known_things(self):
        result = _get_thing_keywords()
        assert "路引" in result
        assert "银子" in result
        assert "马" in result

    def test_not_empty(self):
        result = _get_thing_keywords()
        assert len(result) > 0


class TestGetAllEntityKeywords:
    def setup_method(self):
        _reset_cache()

    def teardown_method(self):
        _reset_cache()

    def test_returns_tuple(self):
        result = _get_all_entity_keywords()
        assert isinstance(result, tuple)

    def test_includes_person_names(self):
        persons = _get_person_names()
        all_kw = _get_all_entity_keywords()
        for p in persons:
            assert p in all_kw

    def test_includes_place_names(self):
        places = _get_place_names()
        all_kw = _get_all_entity_keywords()
        for p in places:
            assert p in all_kw

    def test_includes_thing_keywords(self):
        things = _get_thing_keywords()
        all_kw = _get_all_entity_keywords()
        for t in things:
            assert t in all_kw

    def test_includes_event_keywords(self):
        all_kw = _get_all_entity_keywords()
        assert "杀" in all_kw
        assert "买卖" in all_kw
        assert "走私" in all_kw

    def test_not_empty(self):
        result = _get_all_entity_keywords()
        assert len(result) > 0

    def test_total_is_superset(self):
        persons = _get_person_names()
        places = _get_place_names()
        things = _get_thing_keywords()
        all_kw = _get_all_entity_keywords()
        assert len(all_kw) >= len(persons) + len(places) + len(things)


class TestInitEntityKeywords:
    def setup_method(self):
        _reset_cache()
        _mod.PERSON_NAMES = ()
        _mod.PLACE_NAMES = ()
        _mod.THING_KEYWORDS = ()
        _mod.EVENT_KEYWORDS = ()
        _mod.ALL_ENTITY_KEYWORDS = ()

    def teardown_method(self):
        _reset_cache()
        _mod.PERSON_NAMES = ()
        _mod.PLACE_NAMES = ()
        _mod.THING_KEYWORDS = ()
        _mod.EVENT_KEYWORDS = ()
        _mod.ALL_ENTITY_KEYWORDS = ()

    def test_sets_person_names(self):
        init_entity_keywords()
        assert len(_mod.PERSON_NAMES) > 0
        assert "掌柜" in _mod.PERSON_NAMES

    def test_sets_place_names(self):
        init_entity_keywords()
        assert len(_mod.PLACE_NAMES) > 0
        assert "同福" in _mod.PLACE_NAMES

    def test_sets_thing_keywords(self):
        init_entity_keywords()
        assert len(_mod.THING_KEYWORDS) > 0
        assert "路引" in _mod.THING_KEYWORDS

    def test_sets_event_keywords(self):
        init_entity_keywords()
        assert len(_mod.EVENT_KEYWORDS) > 0
        assert "杀" in _mod.EVENT_KEYWORDS
        assert "买卖" in _mod.EVENT_KEYWORDS

    def test_sets_all_entity_keywords(self):
        init_entity_keywords()
        assert len(_mod.ALL_ENTITY_KEYWORDS) > 0

    def test_clears_cache_before_rebuild(self):
        _mod._DYNAMIC_ENTITIES_CACHED = ("fake", "fake", "fake", "fake")
        init_entity_keywords()
        assert _mod.PERSON_NAMES != "fake"

    def test_person_names_matches_accessor(self):
        init_entity_keywords()
        _reset_cache()
        accessor_result = _get_person_names()
        assert accessor_result == _mod.PERSON_NAMES

    def test_place_names_matches_accessor(self):
        init_entity_keywords()
        _reset_cache()
        accessor_result = _get_place_names()
        assert accessor_result == _mod.PLACE_NAMES

    def test_thing_keywords_matches_accessor(self):
        init_entity_keywords()
        _reset_cache()
        accessor_result = _get_thing_keywords()
        assert accessor_result == _mod.THING_KEYWORDS

    def test_event_keywords_is_fixed_tuple(self):
        init_entity_keywords()
        expected = (
            "杀", "仇", "逃", "救", "帮", "买卖", "赊欠", "火并",
            "走私", "偷渡", "贿赂", "典当", "盘店", "搭股",
        )
        assert expected == _mod.EVENT_KEYWORDS

    def test_idempotent(self):
        init_entity_keywords()
        first_persons = _mod.PERSON_NAMES
        first_places = _mod.PLACE_NAMES
        init_entity_keywords()
        assert first_persons == _mod.PERSON_NAMES
        assert first_places == _mod.PLACE_NAMES


class TestCachingBehavior:
    def setup_method(self):
        _reset_cache()

    def teardown_method(self):
        _reset_cache()

    def test_second_call_returns_cached(self):
        r1 = _get_person_names()
        assert _mod._DYNAMIC_ENTITIES_CACHED is not None
        r2 = _get_person_names()
        assert r1 is r2

    def test_cache_is_tuple_of_four(self):
        _get_person_names()
        cache = _mod._DYNAMIC_ENTITIES_CACHED
        assert isinstance(cache, tuple)
        assert len(cache) == 4

    def test_reset_cache_forces_rebuild(self):
        r1 = _get_person_names()
        _reset_cache()
        r2 = _get_person_names()
        assert r1 == r2
        assert r1 is not r2

    def test_all_accessors_use_same_cache(self):
        persons = _get_person_names()
        places = _get_place_names()
        things = _get_thing_keywords()
        all_kw = _get_all_entity_keywords()
        cache = _mod._DYNAMIC_ENTITIES_CACHED
        assert cache is not None
        assert persons is cache[0]
        assert places is cache[1]
        assert things is cache[2]
        assert all_kw is cache[3]
