from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


from backend.agents.brain import (
    _plan_deviation_analysis,
    _reflect_sentiment_impact,
    _select_with_recency,
    cross_reflect,
    plan_day,
    reflect,
)
from backend.memory import AgentMind, make_memory


class TestSelectWithRecency:

    def test_empty_list_returns_empty(self):
        result = _select_with_recency([])
        assert result == []

    @patch("backend.agents.brain.mem._decay_recency", return_value=1.0)
    def test_sorted_by_importance_times_recency(self, _mock_decay):
        now = time.time()
        m_low = make_memory(kind="observation", text="低重要性", importance=2.0, world_day=1, world_shichen="辰时")
        m_low.created_at = now
        m_high = make_memory(kind="observation", text="高重要性", importance=9.0, world_day=1, world_shichen="辰时")
        m_high.created_at = now
        result = _select_with_recency([m_low, m_high], top_k=12)
        assert result[0] is m_high
        assert result[1] is m_low

    @patch("backend.agents.brain.mem._decay_recency", return_value=1.0)
    def test_top_k_limits_count(self, _mock_decay):
        now = time.time()
        obs = []
        for i in range(10):
            m = make_memory(kind="observation", text=f"事件{i}", importance=5.0, world_day=1, world_shichen="辰时")
            m.created_at = now
            obs.append(m)
        result = _select_with_recency(obs, top_k=3)
        assert len(result) == 3

    def test_high_importance_old_vs_low_importance_new(self):
        now = time.time()
        m_old_high = make_memory(kind="observation", text="旧大事", importance=9.0, world_day=1, world_shichen="辰时")
        m_old_high.created_at = now - 3600 * 24
        m_new_low = make_memory(kind="observation", text="新小事", importance=2.0, world_day=1, world_shichen="辰时")
        m_new_low.created_at = now

        def _fake_decay(age_s, half_life_s=3600.0 * 4):
            if age_s <= 0:
                return 1.0
            if age_s > 3600 * 12:
                return 0.1
            return 0.9

        with patch("backend.agents.brain.mem._decay_recency", side_effect=_fake_decay):
            result = _select_with_recency([m_old_high, m_new_low], top_k=2)
            assert result[0] is m_old_high


class TestPlanDeviationAnalysis:

    def test_no_plan_returns_empty(self):
        mind = AgentMind()
        result = _plan_deviation_analysis(mind, "辰时", [])
        assert result == ""

    def test_plan_without_observations_all_unmatched(self):
        mind = AgentMind()
        mind.plan_summary = "去集市采购"
        mind.plan_by_shichen = {"辰时": "巡视铺面"}
        result = _plan_deviation_analysis(mind, "辰时", [])
        assert "未见踪影" in result

    def test_plan_with_matching_observations_partial_matched(self):
        mind = AgentMind()
        mind.plan_summary = "去集市采购货物"
        obs = [make_memory(kind="observation", text="去集市采购货物，一切顺利", importance=5.0, world_day=1, world_shichen="辰时")]
        result = _plan_deviation_analysis(mind, "辰时", obs)
        assert "有迹可循" in result

    def test_both_summary_and_shichen_analyzed(self):
        mind = AgentMind()
        mind.plan_summary = "去集市采购"
        mind.plan_by_shichen = {"辰时": "巡视铺面", "午时": "约见掌柜"}
        obs = [make_memory(kind="observation", text="在集市采购了很多货物", importance=5.0, world_day=1, world_shichen="辰时")]
        result = _plan_deviation_analysis(mind, "辰时", obs)
        assert "有迹可循" in result or "未见踪影" in result


class TestReflectSentimentImpact:

    def test_empty_insights_no_update_mood(self):
        mind = AgentMind()
        with patch.object(mind, "update_mood") as mock_mood:
            _reflect_sentiment_impact(mind, [])
            mock_mood.assert_not_called()

    def test_positive_words_increase_valence(self):
        mind = AgentMind()
        initial_v = mind.affect_valence
        _reflect_sentiment_impact(mind, ["今日宽慰释然，事情顺遂有成"])
        assert mind.affect_valence > initial_v

    def test_negative_words_decrease_valence(self):
        mind = AgentMind()
        initial_v = mind.affect_valence
        _reflect_sentiment_impact(mind, ["遭遇背叛，心中失望愤怒"])
        assert mind.affect_valence < initial_v

    def test_agitation_words_increase_arousal(self):
        mind = AgentMind()
        initial_a = mind.affect_arousal
        _reflect_sentiment_impact(mind, ["险危杀意逼近，形势危急"])
        assert mind.affect_arousal > initial_a

    def test_calming_words_decrease_arousal(self):
        mind = AgentMind()
        mind.affect_arousal = 7.0
        initial_a = mind.affect_arousal
        _reflect_sentiment_impact(mind, ["一切安稳平静，心定神宁"])
        assert mind.affect_arousal < initial_a

    def test_no_significant_signal_light_regression(self):
        mind = AgentMind()
        mind.affect_valence = 3.0
        mind.affect_arousal = 6.0
        _reflect_sentiment_impact(mind, ["今天做了些日常琐事"])
        assert mind.affect_valence < 3.0


class TestReflect:

    @patch("backend.agents.brain.mem.format_plan_for_reflection", return_value="")
    @patch("backend.agents.brain.mem.format_mood_for_reflection", return_value="")
    def test_no_observations_returns_empty(self, _mock_mood, _mock_plan):
        mind = AgentMind()
        result = []
        import asyncio

        async def _run():
            return await reflect(
                npc_id="npc_a",
                npc_name="张三",
                npc_blurb="江湖人",
                mind=mind,
                world_day=1,
                world_shichen="辰时",
            )

        result = asyncio.run(_run())
        assert result == []

    @patch("backend.agents.brain.chat_completion", new_callable=AsyncMock)
    @patch("backend.agents.brain.mem.format_plan_for_reflection", return_value="")
    @patch("backend.agents.brain.mem.format_mood_for_reflection", return_value="")
    def test_llm_returns_insights_writes_to_mind(self, _mock_mood, _mock_plan, mock_llm):
        import json

        mock_llm.return_value = json.dumps({"insights": ["此人不可信", "局势有变"]})
        mind = AgentMind()
        m = make_memory(kind="observation", text="看到了一些事情", importance=5.0, world_day=1, world_shichen="辰时")
        mind.add(m, _skip_evolve=True)

        import asyncio

        async def _run():
            return await reflect(
                npc_id="npc_a",
                npc_name="张三",
                npc_blurb="江湖人",
                mind=mind,
                world_day=1,
                world_shichen="辰时",
            )

        result = asyncio.run(_run())
        assert len(result) == 2
        assert all(r.kind == "reflection" for r in result)
        assert len(mind.reflections()) == 2

    @patch("backend.agents.brain.chat_completion", new_callable=AsyncMock, side_effect=RuntimeError("LLM down"))
    @patch("backend.agents.brain.mem.format_plan_for_reflection", return_value="")
    @patch("backend.agents.brain.mem.format_mood_for_reflection", return_value="")
    def test_llm_failure_returns_empty_no_crash(self, _mock_mood, _mock_plan, mock_llm):
        mind = AgentMind()
        m = make_memory(kind="observation", text="看到了一些事情", importance=5.0, world_day=1, world_shichen="辰时")
        mind.add(m, _skip_evolve=True)

        import asyncio

        async def _run():
            return await reflect(
                npc_id="npc_a",
                npc_name="张三",
                npc_blurb="江湖人",
                mind=mind,
                world_day=1,
                world_shichen="辰时",
            )

        result = asyncio.run(_run())
        assert result == []

    @patch("backend.agents.brain.chat_completion", new_callable=AsyncMock)
    @patch("backend.agents.brain.mem.format_plan_for_reflection", return_value="")
    @patch("backend.agents.brain.mem.format_mood_for_reflection", return_value="")
    def test_insights_truncated_at_five(self, _mock_mood, _mock_plan, mock_llm):
        import json

        insights_list = [f"洞察{i}" for i in range(8)]
        mock_llm.return_value = json.dumps({"insights": insights_list})
        mind = AgentMind()
        m = make_memory(kind="observation", text="看到了一些事情", importance=5.0, world_day=1, world_shichen="辰时")
        mind.add(m, _skip_evolve=True)

        import asyncio

        async def _run():
            return await reflect(
                npc_id="npc_a",
                npc_name="张三",
                npc_blurb="江湖人",
                mind=mind,
                world_day=1,
                world_shichen="辰时",
            )

        result = asyncio.run(_run())
        assert len(result) == 5


class TestCrossReflect:

    @patch("backend.agents.brain.NPC_RELATIONSHIPS", {})
    def test_no_relationships_returns_empty(self):
        mind = AgentMind()
        import asyncio

        async def _run():
            return await cross_reflect(
                npc_id="npc_a",
                npc_name="张三",
                npc_blurb="江湖人",
                mind=mind,
                world_day=1,
                world_shichen="辰时",
            )

        result = asyncio.run(_run())
        assert result == []

    @patch("backend.agents.brain.NPC_RELATIONSHIPS", {"npc_a": [{"target": "npc_b", "attitude": "交好", "note": "旧友"}]})
    @patch("backend.agents.brain.NPCS", {"npc_b": {"name": "李四", "short": "四哥"}})
    def test_insufficient_observations_returns_empty(self):
        mind = AgentMind()
        m = make_memory(kind="observation", text="李四来了", importance=5.0, world_day=1, world_shichen="辰时")
        mind.add(m, _skip_evolve=True)

        import asyncio

        async def _run():
            return await cross_reflect(
                npc_id="npc_a",
                npc_name="张三",
                npc_blurb="江湖人",
                mind=mind,
                world_day=1,
                world_shichen="辰时",
            )

        result = asyncio.run(_run())
        assert result == []

    @patch("backend.agents.brain.chat_completion", new_callable=AsyncMock)
    @patch("backend.agents.brain.mem.format_plan_for_reflection", return_value="")
    @patch("backend.agents.brain.mem.format_mood_for_reflection", return_value="")
    @patch("backend.agents.brain.NPC_RELATIONSHIPS", {"npc_a": [{"target": "npc_b", "attitude": "交好", "note": "旧友"}]})
    @patch("backend.agents.brain.NPCS", {"npc_b": {"name": "李四", "short": "四哥"}})
    def test_llm_returns_social_insights_writes_to_mind(self, _mock_mood, _mock_plan, mock_llm):
        import json

        mock_llm.return_value = json.dumps({"insights": ["李四最近行踪可疑", "需要提防"]})
        mind = AgentMind()
        for i in range(5):
            m = make_memory(kind="observation", text=f"李四做了第{i}件事", importance=5.0, world_day=1, world_shichen="辰时")
            mind.add(m, _skip_evolve=True)

        import asyncio

        async def _run():
            return await cross_reflect(
                npc_id="npc_a",
                npc_name="张三",
                npc_blurb="江湖人",
                mind=mind,
                world_day=1,
                world_shichen="辰时",
            )

        result = asyncio.run(_run())
        assert len(result) == 2
        assert all(m.kind == "cross_reflection" for m in result)

    @patch("backend.agents.brain.chat_completion", new_callable=AsyncMock, side_effect=RuntimeError("LLM down"))
    @patch("backend.agents.brain.mem.format_plan_for_reflection", return_value="")
    @patch("backend.agents.brain.mem.format_mood_for_reflection", return_value="")
    @patch("backend.agents.brain.NPC_RELATIONSHIPS", {"npc_a": [{"target": "npc_b", "attitude": "交好", "note": "旧友"}]})
    @patch("backend.agents.brain.NPCS", {"npc_b": {"name": "李四", "short": "四哥"}})
    def test_llm_failure_skips_no_crash(self, _mock_mood, _mock_plan, mock_llm):
        mind = AgentMind()
        for i in range(5):
            m = make_memory(kind="observation", text=f"李四做了第{i}件事", importance=5.0, world_day=1, world_shichen="辰时")
            mind.add(m, _skip_evolve=True)

        import asyncio

        async def _run():
            return await cross_reflect(
                npc_id="npc_a",
                npc_name="张三",
                npc_blurb="江湖人",
                mind=mind,
                world_day=1,
                world_shichen="辰时",
            )

        result = asyncio.run(_run())
        assert result == []


class TestPlanDay:

    def test_already_planned_returns_false(self):
        mind = AgentMind()
        mind.plan_day = 1
        mind.plan_by_shichen = {"辰时": "做某事"}
        import asyncio

        async def _run():
            return await plan_day(
                npc_id="npc_a",
                npc_name="张三",
                npc_blurb="江湖人",
                mind=mind,
                world_day=1,
            )

        result = asyncio.run(_run())
        assert result is False

    @patch("backend.agents.brain.chat_completion", new_callable=AsyncMock)
    def test_llm_returns_valid_plan_writes_mind(self, mock_llm):
        import json

        mock_llm.return_value = json.dumps({
            "summary": "今日总览",
            "schedule": {"辰时": "巡视铺面", "午时": "约见掌柜"},
        })
        mind = AgentMind()

        import asyncio

        async def _run():
            return await plan_day(
                npc_id="npc_a",
                npc_name="张三",
                npc_blurb="江湖人",
                mind=mind,
                world_day=2,
            )

        result = asyncio.run(_run())
        assert result is True
        assert mind.plan_day == 2
        assert mind.plan_summary == "今日总览"
        assert "辰时" in mind.plan_by_shichen
        assert "午时" in mind.plan_by_shichen

    @patch("backend.agents.brain.chat_completion", new_callable=AsyncMock, side_effect=RuntimeError("LLM down"))
    def test_llm_failure_sets_default_plan_returns_false(self, mock_llm):
        mind = AgentMind()

        import asyncio

        async def _run():
            return await plan_day(
                npc_id="npc_a",
                npc_name="张三",
                npc_blurb="江湖人",
                mind=mind,
                world_day=2,
            )

        result = asyncio.run(_run())
        assert result is False
        assert mind.plan_day == 2
        assert mind.plan_summary == "（计划未定，随遇而安）"

    @patch("backend.agents.brain.chat_completion", new_callable=AsyncMock)
    def test_invalid_shichen_filtered(self, mock_llm):
        import json

        mock_llm.return_value = json.dumps({
            "summary": "今日总览",
            "schedule": {"辰时": "做正事", "凌晨": "无效时辰", "午时": "午休"},
        })
        mind = AgentMind()

        import asyncio

        async def _run():
            return await plan_day(
                npc_id="npc_a",
                npc_name="张三",
                npc_blurb="江湖人",
                mind=mind,
                world_day=2,
            )

        result = asyncio.run(_run())
        assert result is True
        assert "辰时" in mind.plan_by_shichen
        assert "午时" in mind.plan_by_shichen
        assert "凌晨" not in mind.plan_by_shichen
