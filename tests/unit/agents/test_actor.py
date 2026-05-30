from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from conftest import make_player

from backend.agents.actor import NpcAction, NpcActionResult, act_loop, decide_next_action, execute_plan_step
from backend.memory import AgentMind


class TestDecideNextAction:

    def test_no_plan_returns_idle(self):
        p = make_player(world_shichen=4)
        mind = AgentMind()
        result = decide_next_action(mind, p, "zhanggui")
        assert result == NpcAction.IDLE

    @patch("backend.systems.npc_state._parse_plan_target", return_value=("world", 30, 30))
    def test_move_keyword_returns_move(self, _mock_parse):
        p = make_player(world_shichen=4)
        p.npc_positions["zhanggui"] = ["world", 25, 28]
        mind = AgentMind()
        mind.plan_by_shichen = {"辰时": "去集市采购"}
        result = decide_next_action(mind, p, "zhanggui")
        assert result == NpcAction.MOVE

    def test_talk_keyword_returns_talk(self):
        p = make_player(world_shichen=4)
        p.npc_positions["zhanggui"] = ["world", 25, 28]
        mind = AgentMind()
        mind.plan_by_shichen = {"辰时": "见掌柜"}
        result = decide_next_action(mind, p, "zhanggui")
        assert result == NpcAction.TALK

    def test_rest_keyword_returns_rest(self):
        p = make_player(world_shichen=4)
        p.npc_positions["zhanggui"] = ["world", 25, 28]
        mind = AgentMind()
        mind.plan_by_shichen = {"辰时": "歇息片刻"}
        result = decide_next_action(mind, p, "zhanggui")
        assert result == NpcAction.REST

    @patch("backend.systems.npc_state._parse_plan_target", return_value=("world", 26, 28))
    def test_near_target_no_move(self, _mock_parse):
        p = make_player(world_shichen=4)
        p.npc_positions["zhanggui"] = ["world", 25, 28]
        mind = AgentMind()
        mind.plan_by_shichen = {"辰时": "去集市采购"}
        result = decide_next_action(mind, p, "zhanggui")
        assert result != NpcAction.MOVE

    @patch("backend.systems.npc_state._parse_plan_target", return_value=("world", 30, 30))
    def test_move_priority_over_rest(self, _mock_parse):
        p = make_player(world_shichen=4)
        p.npc_positions["zhanggui"] = ["world", 25, 28]
        mind = AgentMind()
        mind.plan_by_shichen = {"辰时": "去集市歇息"}
        result = decide_next_action(mind, p, "zhanggui")
        assert result == NpcAction.MOVE


class TestExecutePlanStep:

    def test_idle_action(self):
        p = make_player(world_shichen=4)
        mind = AgentMind()
        result = execute_plan_step(p, "zhanggui", mind)
        assert result.action_type == NpcAction.IDLE
        assert result.success is True

    @patch("backend.systems.npc_state.plan_driven_step", return_value=("world", 26, 28))
    @patch("backend.systems.npc_state._parse_plan_target", return_value=("world", 30, 30))
    def test_move_success(self, _mock_parse, _mock_step):
        p = make_player(world_shichen=4)
        p.npc_positions["zhanggui"] = ["world", 25, 28]
        mind = AgentMind()
        mind.plan_by_shichen = {"辰时": "去集市采购"}
        result = execute_plan_step(p, "zhanggui", mind)
        assert result.action_type == NpcAction.MOVE
        assert result.success is True
        assert p.npc_positions["zhanggui"] == ("world", 26, 28)

    @patch("backend.agents.actor.NPCS", {"zhanggui": {"name": "掌柜", "short": "掌柜"}, "xiaosi": {"name": "小厮", "short": "小厮"}})
    @patch("backend.llm.client.chat_completion", new_callable=AsyncMock, return_value='{"dialogue": [{"speaker": "掌柜", "line": "近来可好？"}, {"speaker": "小厮", "line": "还好还好"}]}')
    def test_talk_with_other_npc(self, _mock_llm):
        p = make_player(world_shichen=4)
        p.npc_positions["zhanggui"] = ["world", 25, 28]
        p.npc_positions["xiaosi"] = ["world", 25, 28]
        mind = AgentMind()
        mind.plan_by_shichen = {"辰时": "见掌柜"}
        result = execute_plan_step(p, "zhanggui", mind)
        assert result.action_type == NpcAction.TALK
        assert result.success is True

    def test_talk_no_other_npc(self):
        p = make_player(world_shichen=4)
        p.npc_positions["zhanggui"] = ["world", 25, 28]
        mind = AgentMind()
        mind.plan_by_shichen = {"辰时": "见掌柜"}
        result = execute_plan_step(p, "zhanggui", mind)
        assert result.action_type == NpcAction.TALK
        assert result.success is False

    def test_rest_action(self):
        p = make_player(world_shichen=4)
        p.npc_positions["zhanggui"] = ["world", 25, 28]
        mind = AgentMind()
        mind.plan_by_shichen = {"辰时": "歇息片刻"}
        result = execute_plan_step(p, "zhanggui", mind)
        assert result.action_type == NpcAction.REST
        assert result.success is True

    @patch("backend.agents.actor._execute_move", side_effect=RuntimeError("移动失败"))
    @patch("backend.systems.npc_state._parse_plan_target", return_value=("world", 30, 30))
    def test_rollback_on_exception(self, _mock_parse, _mock_move):
        p = make_player(world_shichen=4)
        p.npc_positions["zhanggui"] = ["world", 25, 28]
        mind = AgentMind()
        mind.plan_by_shichen = {"辰时": "去集市采购"}
        result = execute_plan_step(p, "zhanggui", mind)
        assert result.success is False
        assert p.npc_positions["zhanggui"] == ["world", 25, 28]


class TestActLoop:

    @patch("backend.agents.actor.decide_next_action", return_value=NpcAction.IDLE)
    def test_idle_breaks_loop(self, _mock_decide):
        p = make_player()
        mind = AgentMind()
        result = asyncio.run(act_loop(p, "zhanggui", mind, max_steps=3))
        assert result == []

    @patch("backend.agents.actor.decide_next_action", return_value=NpcAction.MOVE)
    @patch("backend.agents.actor.execute_plan_step_async", new_callable=AsyncMock)
    def test_max_steps_limit(self, _mock_exec, _mock_decide):
        _mock_exec.return_value = NpcActionResult(
            action_type=NpcAction.MOVE, description="移动", success=True,
        )
        p = make_player()
        mind = AgentMind()
        result = asyncio.run(act_loop(p, "zhanggui", mind, max_steps=5))
        assert len(result) == 5

    @patch("backend.agents.actor.decide_next_action", return_value=NpcAction.MOVE)
    @patch("backend.agents.actor.execute_plan_step_async", new_callable=AsyncMock)
    def test_reflect_triggered(self, _mock_exec, _mock_decide):
        _mock_exec.return_value = NpcActionResult(
            action_type=NpcAction.MOVE, description="移动", success=True,
        )
        p = make_player()
        mind = AgentMind()
        mind.importance_since_reflect = 999.0
        mind.last_reflect_at = 0.0
        with patch("backend.agents.brain.reflect", new_callable=AsyncMock) as mock_reflect:
            asyncio.run(act_loop(p, "zhanggui", mind, max_steps=1))
            mock_reflect.assert_called_once()
