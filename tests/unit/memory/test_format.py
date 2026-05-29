from __future__ import annotations

# pyright: reportArgumentType=false
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from types import SimpleNamespace

from backend.memory.format import (
    format_insight_block,
    format_memories_for_prompt,
    format_mood_for_prompt,
    format_mood_for_reflection,
    format_plan_for_prompt,
    format_plan_for_reflection,
    format_proactive_callbacks,
    format_topic_thread,
)


def _mem(kind="observation", is_anchor=False, created_day=1, created_shichen="午时",
         importance=5, text="某条记忆内容"):
    return SimpleNamespace(
        kind=kind,
        is_anchor=is_anchor,
        created_day=created_day,
        created_shichen=created_shichen,
        importance=importance,
        text=text,
    )


def _mind(**overrides):
    defaults = dict(
        plan_summary="",
        plan_by_shichen={},
        affect_mood="平静",
        affect_valence=0.0,
        affect_arousal=5.0,
        affect_cause="",
        items=[],
        insights=lambda: [],
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestFormatMemoriesForPrompt:
    def test_empty_list(self):
        assert format_memories_for_prompt([]) == ""

    def test_single_observation(self):
        m = _mem(kind="observation", created_day=3, created_shichen="辰时", text="看到路人")
        result = format_memories_for_prompt([m])
        assert "【你的脑中浮起几条记忆(自语,不必复述)】" in result
        assert "[见闻 · 第3日·辰时]" in result
        assert "看到路人" in result

    def test_kind_tags(self):
        pairs = [
            ("observation", "见闻"),
            ("reflection", "心得"),
            ("cross_reflection", "人事察觉"),
            ("insight", "顿悟"),
            ("condensation", "往事凝华"),
            ("plan", "计议"),
            ("seed", "本心"),
            ("anchor", "◆心锚"),
        ]
        for kind, tag in pairs:
            m = _mem(kind=kind, text="x")
            result = format_memories_for_prompt([m])
            assert f"[{tag} ·" in result

    def test_unknown_kind_defaults(self):
        m = _mem(kind="unknown_type", text="x")
        result = format_memories_for_prompt([m])
        assert "[记 ·" in result

    def test_multiple_memories(self):
        mems = [
            _mem(kind="observation", created_day=1, created_shichen="子时", text="a"),
            _mem(kind="reflection", created_day=2, created_shichen="午时", text="b"),
        ]
        result = format_memories_for_prompt(mems)
        lines = result.split("\n")
        assert len(lines) == 3
        assert "[见闻 · 第1日·子时] a" in lines[1]
        assert "[心得 · 第2日·午时] b" in lines[2]

    def test_header_present(self):
        result = format_memories_for_prompt([_mem()])
        assert result.startswith("【你的脑中浮起几条记忆(自语,不必复述)】")


class TestFormatPlanForPrompt:
    def test_no_plan(self):
        mind = _mind(plan_summary="", plan_by_shichen={})
        assert format_plan_for_prompt(mind, "午时") == ""

    def test_summary_only(self):
        mind = _mind(plan_summary="去集市采买", plan_by_shichen={})
        result = format_plan_for_prompt(mind, "午时")
        assert "【今日你心里盘算的事】" in result
        assert "· 总:去集市采买" in result
        assert "此刻" not in result

    def test_current_shichen_match(self):
        mind = _mind(
            plan_summary="日常",
            plan_by_shichen={"午时": "用午饭", "未时": "午休"},
        )
        result = format_plan_for_prompt(mind, "午时")
        assert "此刻(午时)该做:用午饭" in result

    def test_current_shichen_no_match(self):
        mind = _mind(
            plan_summary="日常",
            plan_by_shichen={"辰时": "早课", "午时": "午饭"},
        )
        result = format_plan_for_prompt(mind, "戌时")
        assert "此刻" not in result
        assert "辰时:早课" in result
        assert "午时:午饭" in result

    def test_plan_by_shichen_only_no_summary(self):
        mind = _mind(plan_summary="", plan_by_shichen={"辰时": "早课"})
        result = format_plan_for_prompt(mind, "午时")
        assert "总:" not in result
        assert "辰时:早课" in result

    def test_no_match_shows_at_most_two(self):
        plan = {f"{s}时": f"做{s}事" for s in ["子", "丑", "寅", "卯"]}
        mind = _mind(plan_summary="", plan_by_shichen=plan)
        result = format_plan_for_prompt(mind, "亥时")
        lines = [l for l in result.split("\n") if l.startswith("· ") and "时:" in l]
        assert len(lines) <= 2


class TestFormatMoodForPrompt:
    def test_default_mood(self):
        mind = _mind(affect_mood=None, affect_valence=0.0, affect_arousal=5.0, affect_cause="")
        result = format_mood_for_prompt(mind)
        assert "平静" in result

    def test_high_arousal(self):
        mind = _mind(affect_arousal=8.0, affect_valence=0.0, affect_cause="")
        result = format_mood_for_prompt(mind)
        assert "情绪翻涌" in result

    def test_medium_arousal(self):
        mind = _mind(affect_arousal=5.0, affect_valence=0.0, affect_cause="")
        result = format_mood_for_prompt(mind)
        assert "心绪浮动" in result

    def test_low_arousal(self):
        mind = _mind(affect_arousal=3.0, affect_valence=0.0, affect_cause="")
        result = format_mood_for_prompt(mind)
        assert "心神尚定" in result

    def test_very_low_arousal(self):
        mind = _mind(affect_arousal=1.0, affect_valence=0.0, affect_cause="")
        result = format_mood_for_prompt(mind)
        assert "心如止水" in result

    def test_high_valence(self):
        mind = _mind(affect_valence=7.0, affect_arousal=5.0, affect_cause="")
        result = format_mood_for_prompt(mind)
        assert "温煦" in result

    def test_moderate_valence(self):
        mind = _mind(affect_valence=3.0, affect_arousal=5.0, affect_cause="")
        result = format_mood_for_prompt(mind)
        assert "和缓" in result

    def test_very_negative_valence(self):
        mind = _mind(affect_valence=-7.0, affect_arousal=5.0, affect_cause="")
        result = format_mood_for_prompt(mind)
        assert "带刺" in result

    def test_slightly_negative_valence(self):
        mind = _mind(affect_valence=-3.0, affect_arousal=5.0, affect_cause="")
        result = format_mood_for_prompt(mind)
        assert "不耐" in result

    def test_neutral_valence(self):
        mind = _mind(affect_valence=0.0, affect_arousal=5.0, affect_cause="")
        result = format_mood_for_prompt(mind)
        assert "常度" in result

    def test_with_cause(self):
        mind = _mind(affect_valence=0.0, affect_arousal=5.0, affect_cause="被人辱骂")
        result = format_mood_for_prompt(mind)
        assert "心绪由来:被人辱骂" in result

    def test_without_cause(self):
        mind = _mind(affect_valence=0.0, affect_arousal=5.0, affect_cause="")
        result = format_mood_for_prompt(mind)
        assert "心绪由来" not in result

    def test_prompt_instruction(self):
        mind = _mind(affect_valence=0.0, affect_arousal=5.0, affect_cause="")
        result = format_mood_for_prompt(mind)
        assert "不要原句复述" in result


class TestFormatPlanForReflection:
    def test_no_plan(self):
        mind = _mind(plan_summary="", plan_by_shichen={})
        assert format_plan_for_reflection(mind, "午时") == ""

    def test_summary_only(self):
        mind = _mind(plan_summary="去集市", plan_by_shichen={})
        result = format_plan_for_reflection(mind, "午时")
        assert "【你今日原定的计划】" in result
        assert "· 总：去集市" in result

    def test_remaining_shichen(self):
        mind = _mind(
            plan_summary="",
            plan_by_shichen={"午时": "午饭", "未时": "午休", "申时": "练功"},
        )
        result = format_plan_for_reflection(mind, "午时")
        assert "午时 午饭" in result
        assert "未时 午休" in result
        assert "申时 练功" in result

    def test_passed_shichen_marked(self):
        mind = _mind(
            plan_summary="",
            plan_by_shichen={"子时": "夜巡", "午时": "午饭"},
        )
        result = format_plan_for_reflection(mind, "午时")
        assert "子时(已过) 夜巡" in result
        assert "午时 午饭" in result

    def test_invalid_shichen_defaults_to_start(self):
        mind = _mind(
            plan_summary="",
            plan_by_shichen={"子时": "夜巡", "午时": "午饭"},
        )
        result = format_plan_for_reflection(mind, "不存在的时辰")
        assert "子时 夜巡" in result
        assert "午时 午饭" in result

    def test_at_most_four_remaining(self):
        plan = {}
        shichen_order = ["子时", "丑时", "寅时", "卯时", "辰时", "巳时"]
        for s in shichen_order:
            plan[s] = f"做{s}事"
        mind = _mind(plan_summary="", plan_by_shichen=plan)
        result = format_plan_for_reflection(mind, "子时")
        remaining_lines = [l for l in result.split("\n") if l.startswith("· ") and "时" in l and "总" not in l]
        assert len(remaining_lines) <= 4

    def test_reflection_hint(self):
        mind = _mind(plan_summary="去集市", plan_by_shichen={})
        result = format_plan_for_reflection(mind, "午时")
        assert "对照所见" in result


class TestFormatMoodForReflection:
    def test_high_valence_high_arousal(self):
        mind = _mind(affect_valence=7.0, affect_arousal=7.0, affect_cause="")
        result = format_mood_for_reflection(mind)
        assert "欣悦而激动" in result

    def test_moderate_valence_moderate_arousal(self):
        mind = _mind(affect_valence=5.0, affect_arousal=5.0, affect_cause="")
        result = format_mood_for_reflection(mind)
        assert "心情不错" in result

    def test_slight_positive_valence(self):
        mind = _mind(affect_valence=2.5, affect_arousal=3.0, affect_cause="")
        result = format_mood_for_reflection(mind)
        assert "平和偏暖" in result

    def test_very_negative_high_arousal(self):
        mind = _mind(affect_valence=-7.0, affect_arousal=7.0, affect_cause="")
        result = format_mood_for_reflection(mind)
        assert "又怒又痛" in result

    def test_negative_moderate_arousal(self):
        mind = _mind(affect_valence=-5.0, affect_arousal=5.0, affect_cause="")
        result = format_mood_for_reflection(mind)
        assert "心头有气" in result

    def test_slight_negative_valence(self):
        mind = _mind(affect_valence=-3.0, affect_arousal=3.0, affect_cause="")
        result = format_mood_for_reflection(mind)
        assert "低落或戒备" in result

    def test_high_arousal_only(self):
        mind = _mind(affect_valence=0.0, affect_arousal=8.0, affect_cause="")
        result = format_mood_for_reflection(mind)
        assert "情绪激动" in result

    def test_low_arousal_only(self):
        mind = _mind(affect_valence=0.0, affect_arousal=1.0, affect_cause="")
        result = format_mood_for_reflection(mind)
        assert "心如止水" in result

    def test_neutral(self):
        mind = _mind(affect_valence=0.0, affect_arousal=4.0, affect_cause="")
        result = format_mood_for_reflection(mind)
        assert "情绪平稳" in result

    def test_with_cause(self):
        mind = _mind(affect_valence=0.0, affect_arousal=4.0, affect_cause="被朋友出卖")
        result = format_mood_for_reflection(mind)
        assert "因何而起：被朋友出卖" in result

    def test_without_cause(self):
        mind = _mind(affect_valence=0.0, affect_arousal=4.0, affect_cause="")
        result = format_mood_for_reflection(mind)
        assert "因何而起" not in result

    def test_valence_arousal_in_output(self):
        mind = _mind(affect_valence=-3.5, affect_arousal=6.2, affect_cause="")
        result = format_mood_for_reflection(mind)
        assert "效价-3.5" in result
        assert "唤醒度6.2" in result

    def test_default_mood(self):
        mind = _mind(affect_mood=None, affect_valence=0.0, affect_arousal=4.0, affect_cause="")
        result = format_mood_for_reflection(mind)
        assert "平静" in result


class TestFormatProactiveCallbacks:
    def test_no_anchors_no_unattended(self):
        mind = _mind(items=[])
        result = format_proactive_callbacks(mind, "张三")
        assert result == ""

    def test_anchors_only(self):
        anchors = [
            _mem(kind="anchor", is_anchor=True, created_day=1, created_shichen="子时",
                 text="曾经的承诺"),
        ]
        mind = _mind(items=anchors)
        result = format_proactive_callbacks(mind, "张三")
        assert "心里过不去的坎" in result
        assert "曾经的承诺" in result
        assert "自然提起这些旧事" in result

    def test_anchor_text_truncated(self):
        long_text = "x" * 200
        anchors = [
            _mem(kind="anchor", is_anchor=True, created_day=1, created_shichen="子时",
                 text=long_text),
        ]
        mind = _mind(items=anchors)
        result = format_proactive_callbacks(mind, "张三")
        for line in result.split("\n"):
            if line.startswith("· [") and "x" in line:
                assert len(line.split("] ", 1)[1]) <= 120

    def test_at_most_three_anchors(self):
        anchors = [
            _mem(kind="anchor", is_anchor=True, created_day=i, created_shichen="子时",
                 text=f"锚点{i}")
            for i in range(5)
        ]
        mind = _mind(items=anchors)
        result = format_proactive_callbacks(mind, "张三")
        anchor_lines = [l for l in result.split("\n") if l.startswith("· [第")]
        assert len(anchor_lines) <= 3

    def test_unattended_observations(self):
        obs = [
            _mem(kind="observation", text="张三说下次一定来"),
        ]
        mind = _mind(items=obs)
        result = format_proactive_callbacks(mind, "张三")
        assert "尚未回扣的话" in result
        assert "张三说下次一定来" in result

    def test_unattended_keyword_matching(self):
        keywords = ["喜欢", "怕", "想要", "答应", "改日", "回头", "下次", "等我", "一定"]
        for kw in keywords:
            obs = [_mem(kind="observation", text=f"张三{kw}了某事")]
            mind = _mind(items=obs)
            result = format_proactive_callbacks(mind, "张三")
            assert "尚未回扣的话" in result, f"keyword '{kw}' should match"

    def test_unattended_requires_player_name(self):
        obs = [
            _mem(kind="observation", text="李四说下次一定来"),
        ]
        mind = _mind(items=obs)
        result = format_proactive_callbacks(mind, "张三")
        assert "尚未回扣的话" not in result

    def test_unattended_text_truncated(self):
        long_text = "张三喜欢" + "x" * 200
        obs = [_mem(kind="observation", text=long_text)]
        mind = _mind(items=obs)
        result = format_proactive_callbacks(mind, "张三")
        for line in result.split("\n"):
            if line.startswith("· ") and "喜欢" in line and "尚未" not in line and "可以" not in line:
                assert len(line) <= 83

    def test_at_most_three_unattended(self):
        obs = [
            _mem(kind="observation", text=f"张三说下次一定做{i}事")
            for i in range(5)
        ]
        mind = _mind(items=obs)
        result = format_proactive_callbacks(mind, "张三")
        unattended_lines = [l for l in result.split("\n") if "下次" in l and not l.startswith("【")]
        assert len(unattended_lines) <= 3

    def test_both_anchors_and_unattended(self):
        items = [
            _mem(kind="anchor", is_anchor=True, created_day=1, created_shichen="子时",
                 text="旧事"),
            _mem(kind="observation", text="张三说下次一定来"),
        ]
        mind = _mind(items=items)
        result = format_proactive_callbacks(mind, "张三")
        assert "心里过不去的坎" in result
        assert "尚未回扣的话" in result

    def test_is_anchor_flag(self):
        items = [
            _mem(kind="observation", is_anchor=True, created_day=1, created_shichen="子时",
                 text="心锚记忆"),
        ]
        mind = _mind(items=items)
        result = format_proactive_callbacks(mind, "张三")
        assert "心里过不去的坎" in result
        assert "心锚记忆" in result

    def test_recent_obs_limited_to_last_ten(self):
        obs = [_mem(kind="observation", text=f"观察{i}") for i in range(15)]
        obs_with_kw = [_mem(kind="observation", text="张三说下次一定来")]
        all_obs = obs + obs_with_kw
        mind = _mind(items=all_obs)
        result = format_proactive_callbacks(mind, "张三")
        assert "尚未回扣的话" in result


class TestFormatTopicThread:
    def test_less_than_two_turns(self):
        assert format_topic_thread([]) == ""
        assert format_topic_thread([{"user": "你好"}]) == ""

    def test_no_signals_no_keywords(self):
        hist = [
            {"user": "你好", "npc": "你好啊"},
            {"user": "天气不错", "npc": "是啊"},
        ]
        assert format_topic_thread(hist) == ""

    def test_question_marker(self):
        hist = [
            {"user": "你好", "npc": "你好"},
            {"user": "你知道路引怎么拿吗？", "npc": "嗯"},
        ]
        result = format_topic_thread(hist)
        assert "待答之问" in result

    def test_chinese_question_markers(self):
        hist = [
            {"user": "你好", "npc": "你好"},
            {"user": "你可知如何去京城呢", "npc": "嗯"},
        ]
        result = format_topic_thread(hist)
        assert "待答之问" in result

    def test_transaction_marker(self):
        hist = [
            {"user": "你好", "npc": "你好"},
            {"user": "这把剑多少钱", "npc": "嗯"},
        ]
        result = format_topic_thread(hist)
        assert "待定买卖" in result

    def test_topic_keywords(self):
        hist = [
            {"user": "你好", "npc": "你好"},
            {"user": "你有药吗", "npc": "嗯"},
        ]
        result = format_topic_thread(hist)
        assert "你们正在谈论" in result
        assert "药" in result

    def test_multiple_keywords_joined(self):
        hist = [
            {"user": "你好", "npc": "你好"},
            {"user": "你有药和信物吗", "npc": "嗯"},
        ]
        result = format_topic_thread(hist)
        assert "你们正在谈论" in result

    def test_at_most_five_keywords(self):
        hist = [
            {"user": "你好", "npc": "你好"},
            {"user": "路引信物帖子信函药地图船马镖银钱毒死杀逃救帮找见等", "npc": "嗯"},
        ]
        result = format_topic_thread(hist)
        kw_line = [l for l in result.split("\n") if "你们正在谈论" in l]
        assert kw_line
        kws = kw_line[0].split(":", 1)[1].split("--")[0]
        assert len(kws.split("、")) <= 5

    def test_at_most_three_pending_signals(self):
        hist = [
            {"user": "你好", "npc": "你好"},
            {"user": "这个多少钱？", "npc": "嗯"},
            {"user": "那个多少钱？", "npc": "嗯"},
            {"user": "另一个多少钱？", "npc": "嗯"},
            {"user": "还有多少钱？", "npc": "嗯"},
        ]
        result = format_topic_thread(hist)
        signal_lines = [l for l in result.split("\n") if "待答之问" in l or "待定买卖" in l]
        assert len(signal_lines) <= 3

    def test_coherence_instruction(self):
        hist = [
            {"user": "你好", "npc": "你好"},
            {"user": "你有药吗", "npc": "嗯"},
        ]
        result = format_topic_thread(hist)
        assert "保持连贯" in result or "不要突然跳题" in result

    def test_follow_up_instruction(self):
        hist = [
            {"user": "你好", "npc": "你好"},
            {"user": "你有药吗", "npc": "嗯"},
        ]
        result = format_topic_thread(hist)
        assert "追问" in result or "给出进展" in result

    def test_only_last_three_turns_checked(self):
        hist = [
            {"user": "你有药吗", "npc": "嗯"},
            {"user": "天气好", "npc": "嗯"},
            {"user": "没事", "npc": "嗯"},
            {"user": "你好", "npc": "你好"},
        ]
        result = format_topic_thread(hist)
        assert "药" not in result or "你们正在谈论" not in result

    def test_user_none_treated_as_empty(self):
        hist = [
            {"user": None, "npc": "你好"},
            {"user": "你有药吗", "npc": "嗯"},
        ]
        result = format_topic_thread(hist)
        assert "药" in result


class TestFormatInsightBlock:
    def test_no_insights(self):
        mind = _mind(insights=lambda: [])
        assert format_insight_block(mind) == ""

    def test_with_insights(self):
        m1 = SimpleNamespace(created_at=100.0, text="顿悟了一件事")
        m2 = SimpleNamespace(created_at=200.0, text="又顿悟了另一件事")
        mind = _mind(insights=lambda: [m1, m2])
        result = format_insight_block(mind)
        assert "感悟" in result
        assert "顿悟了一件事" in result
        assert "又顿悟了另一件事" in result

    def test_sorted_by_created_at_desc(self):
        m1 = SimpleNamespace(created_at=100.0, text="旧的顿悟")
        m2 = SimpleNamespace(created_at=300.0, text="新的顿悟")
        mind = _mind(insights=lambda: [m1, m2])
        result = format_insight_block(mind)
        lines = result.split("\n")
        insight_lines = [l for l in lines if "顿悟" in l and l.startswith("· ")]
        assert "新的顿悟" in insight_lines[0]

    def test_at_most_two_insights(self):
        insights = [
            SimpleNamespace(created_at=float(i), text=f"顿悟{i}")
            for i in range(5)
        ]
        mind = _mind(insights=lambda: insights)
        result = format_insight_block(mind)
        insight_lines = [l for l in result.split("\n") if l.startswith("· ") and "顿悟" in l and "点到为止" not in l]
        assert len(insight_lines) <= 2

    def test_text_truncated(self):
        long_text = "x" * 200
        insights = [SimpleNamespace(created_at=1.0, text=long_text)]
        mind = _mind(insights=lambda: insights)
        result = format_insight_block(mind)
        for line in result.split("\n"):
            if line.startswith("· ") and "x" in line and "点到为止" not in line and "若话题" not in line:
                assert len(line) <= 123

    def test_hint_instruction(self):
        insights = [SimpleNamespace(created_at=1.0, text="顿悟")]
        mind = _mind(insights=lambda: insights)
        result = format_insight_block(mind)
        assert "点到为止" in result
