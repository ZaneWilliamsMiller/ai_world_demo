# pyright: reportCallIssue=false
"""离线单元测试 — backend/systems/world_evolution.py"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from unittest.mock import AsyncMock, MagicMock, patch

from conftest import make_player


class TestWorldEvolutionInit:
    def test_init_sets_defaults(self):
        from backend.systems.world_evolution import WorldEvolution

        p = make_player()
        we = WorldEvolution(p, "测试名")
        assert we._cancelled is False

    def test_init_stores_player(self):
        from backend.systems.world_evolution import WorldEvolution

        p = make_player()
        we = WorldEvolution(p, "测试名")
        assert we.p is p


class TestWorldEvolutionCancel:
    def test_cancel_sets_flag(self):
        from backend.systems.world_evolution import WorldEvolution

        p = make_player()
        we = WorldEvolution(p, "测试名")
        we.cancel()
        assert we._cancelled is True

    def test_cancel_idempotent(self):
        from backend.systems.world_evolution import WorldEvolution

        p = make_player()
        we = WorldEvolution(p, "测试名")
        we.cancel()
        we.cancel()
        we.cancel()
        assert we._cancelled is True


class TestGetRelationshipType:
    def test_known_attitudes(self):
        from backend.systems.world_evolution import _get_relationship_type

        cases = [
            ("挚交", "交好"),
            ("交好", "交好"),
            ("旧交", "交好"),
            ("暧昧线人", "交好"),
            ("生意伙伴", "生意往来"),
            ("主顾", "生意往来"),
            ("老主顾", "生意往来"),
            ("面上客气", "面上客气"),
            ("面熟", "面上客气"),
            ("面上恭敬", "面上客气"),
            ("心存芥蒂", "心存芥蒂"),
            ("势同水火", "心存芥蒂"),
            ("互不招惹", "互不招惹"),
        ]
        for attitude, expected in cases:
            fake_rels = {"npc_a": [{"target": "npc_b", "attitude": attitude}]}
            with patch("backend.data.relationships.NPC_RELATIONSHIPS", fake_rels):
                result = _get_relationship_type("npc_a", "npc_b")
                assert result == expected, (
                    f"attitude={attitude!r}: got {result!r}, expected {expected!r}"
                )

    def test_unknown_attitude_returns_default(self):
        from backend.systems.world_evolution import _get_relationship_type

        with patch("backend.data.relationships.NPC_RELATIONSHIPS", {"npc_x": [{"target": "npc_y", "attitude": "未知态度"}]}):
            assert _get_relationship_type("npc_x", "npc_y") == "default"

    def test_no_relationship_returns_default(self):
        from backend.systems.world_evolution import _get_relationship_type

        assert _get_relationship_type("nonexistent_a", "nonexistent_b") == "default"


class TestTemplateDialogue:
    def test_generate_template_dialogue_returns_string(self):
        from backend.systems.world_evolution import _generate_template_dialogue

        p = make_player()
        p.npc_positions["zhanggui"] = ("world", 16, 30)
        result = _generate_template_dialogue(p, "zhanggui", "yaren")
        assert result is not None
        assert isinstance(result["line"], str)
        assert len(result["line"]) > 0

    def test_template_format_no_unreplaced_placeholders(self):
        from backend.systems.world_evolution import _generate_template_dialogue

        p = make_player()
        p.npc_positions["zhanggui"] = ("world", 16, 30)
        result = _generate_template_dialogue(p, "zhanggui", "yaren")
        assert result is not None
        line = result["line"]
        assert "{loc}" not in line
        assert "{a}" not in line
        assert "{b}" not in line


class TestPlayerAction:
    def test_player_action_returns_string(self):
        from backend.systems.world_evolution import WorldEvolution

        p = make_player()
        p.npc_positions["zhanggui"] = ("world", 16, 30)
        we = WorldEvolution(p, "测试名")
        result = we._player_action(p)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_player_action_sets_position(self):
        from backend.systems.world_evolution import WorldEvolution

        p = make_player()
        p.npc_positions["zhanggui"] = ("world", 16, 30)
        we = WorldEvolution(p, "测试名")
        we._player_action(p)
        assert "player" in p.npc_positions


class TestHelperFunctions:
    def test_get_visible_npcs_excludes_hidden(self):
        from backend.systems.world_evolution import _get_visible_npcs

        visible = _get_visible_npcs()
        from backend.data.npcs_data import NPCS

        hidden_ids = [nid for nid, m in NPCS.items() if m.get("hidden")]
        for hid in hidden_ids:
            assert hid not in visible, f"hidden NPC {hid!r} should not be in visible list"

    def test_get_visible_npcs_excludes_always(self):
        from backend.systems.world_evolution import _get_visible_npcs

        visible = _get_visible_npcs()
        assert "jiang" not in visible

    def test_npcs_at_same_location(self):
        from backend.systems.world_evolution import _npcs_at_same_location

        p = make_player()
        p.npc_positions["zhanggui"] = ("world", 16, 30)
        p.npc_positions["yaren"] = ("world", 16, 31)
        p.npc_positions["bullya"] = ("world", 50, 50)
        result = _npcs_at_same_location(p, "zhanggui")
        assert "yaren" in result
        assert "bullya" not in result

    def test_pick_location_for_npc_returns_string(self):
        from backend.systems.world_evolution import _pick_location_for_npc

        p = make_player()
        p.npc_positions["zhanggui"] = ("world", 16, 30)
        result = _pick_location_for_npc(p, "zhanggui")
        assert isinstance(result, str)
        assert len(result) > 0


class TestGetEvolution:
    def test_register_and_get(self):
        from backend.systems.world_evolution import (
            WorldEvolution,
            _active_evolutions,
            get_evolution,
            register_evolution,
        )

        p = make_player()
        we = WorldEvolution(p, "测试名")
        pid = "test_reg_get"
        _active_evolutions.pop(pid, None)
        try:
            register_evolution(pid, we)
            assert get_evolution(pid) is we
        finally:
            _active_evolutions.pop(pid, None)

    def test_unregister(self):
        from backend.systems.world_evolution import (
            WorldEvolution,
            _active_evolutions,
            get_evolution,
            register_evolution,
            unregister_evolution,
        )

        p = make_player()
        we = WorldEvolution(p, "测试名")
        pid = "test_unregister"
        _active_evolutions.pop(pid, None)
        try:
            register_evolution(pid, we)
            unregister_evolution(pid)
            assert get_evolution(pid) is None
        finally:
            _active_evolutions.pop(pid, None)

    def test_get_nonexistent(self):
        from backend.systems.world_evolution import get_evolution

        assert get_evolution("absolutely_nonexistent_id_999") is None


class TestWorldEvolutionRun:
    def _make_evolution(self):
        from backend.systems.world_evolution import WorldEvolution

        p = make_player()
        return WorldEvolution(p, "测试侠客")

    @patch("backend.systems.save_system.save_game", new_callable=MagicMock)
    @patch("backend.systems.world_evolution.generate_story_events", new_callable=AsyncMock, return_value=[])
    @patch("backend.systems.world_evolution.write_story_events_to_memory", new_callable=MagicMock)
    @patch("backend.systems.world_evolution.generate_bounties_from_events", return_value=[])
    @patch("backend.systems.world_evolution.reflect", new_callable=AsyncMock)
    @patch("backend.systems.world_evolution.plan_day", new_callable=AsyncMock)
    @patch("backend.systems.world_evolution.execute_plan_step_async", new_callable=AsyncMock)
    @patch("backend.systems.world_evolution.decide_next_action")
    @patch("backend.systems.world_evolution.maybe_wander_npcs")
    @patch("backend.systems.world_evolution.update_npc_state_dynamic")
    @patch("backend.systems.world_evolution.init_npc_inventories")
    @patch("backend.systems.world_evolution.init_npc_positions")
    @patch("backend.systems.world_evolution._fallback_story_events", return_value=[])
    @patch("backend.systems.world_evolution.get_or_init_mind")
    def test_run_yields_done_event(
        self,
        mock_get_mind,
        mock_fallback,
        mock_init_pos,
        mock_init_inv,
        mock_update_npc,
        mock_wander,
        mock_decide,
        mock_exec_async,
        mock_plan_day,
        mock_reflect,
        mock_gen_bounties,
        mock_write_mem,
        mock_gen_events,
        mock_save,
    ):
        from backend.memory import AgentMind

        mock_get_mind.return_value = AgentMind()
        mock_decide.return_value = MagicMock(value="idle")
        mock_exec_async.return_value = MagicMock(
            success=True, description="闲坐", action_type=MagicMock(value="idle"), raw_dialogue=None
        )

        we = self._make_evolution()

        async def _collect():
            events = []
            async for evt in we.run():
                events.append(evt)
            return events

        events = asyncio.run(_collect())
        types = [e["type"] for e in events]
        assert "done" in types

    @patch("backend.systems.save_system.save_game", new_callable=MagicMock)
    @patch("backend.systems.world_evolution.generate_story_events", new_callable=AsyncMock, return_value=[])
    @patch("backend.systems.world_evolution.write_story_events_to_memory", new_callable=MagicMock)
    @patch("backend.systems.world_evolution.generate_bounties_from_events", return_value=[])
    @patch("backend.systems.world_evolution._fallback_story_events", return_value=[])
    @patch("backend.systems.world_evolution.get_or_init_mind")
    @patch("backend.systems.world_evolution.init_npc_inventories")
    @patch("backend.systems.world_evolution.init_npc_positions")
    def test_run_respects_cancel(
        self,
        mock_init_pos,
        mock_init_inv,
        mock_get_mind,
        mock_fallback,
        mock_gen_bounties,
        mock_write_mem,
        mock_gen_events,
        mock_save,
    ):
        from backend.memory import AgentMind

        mock_get_mind.return_value = AgentMind()

        we = self._make_evolution()

        async def _collect():
            events = []
            async for evt in we.run():
                events.append(evt)
                if len(events) == 1:
                    we.cancel()
            return events

        events = asyncio.run(_collect())
        types = [e["type"] for e in events]
        assert "cancelled" in types

    @patch("backend.systems.save_system.save_game", new_callable=MagicMock)
    @patch("backend.systems.world_evolution.generate_story_events", new_callable=AsyncMock, return_value=[])
    @patch("backend.systems.world_evolution.write_story_events_to_memory", new_callable=MagicMock)
    @patch("backend.systems.world_evolution.generate_bounties_from_events", return_value=[])
    @patch("backend.systems.world_evolution.reflect", new_callable=AsyncMock)
    @patch("backend.systems.world_evolution.plan_day", new_callable=AsyncMock)
    @patch("backend.systems.world_evolution.execute_plan_step_async", new_callable=AsyncMock)
    @patch("backend.systems.world_evolution.decide_next_action")
    @patch("backend.systems.world_evolution.maybe_wander_npcs")
    @patch("backend.systems.world_evolution.update_npc_state_dynamic")
    @patch("backend.systems.world_evolution.init_npc_inventories")
    @patch("backend.systems.world_evolution.init_npc_positions")
    @patch("backend.systems.world_evolution._fallback_story_events", return_value=[])
    @patch("backend.systems.world_evolution.get_or_init_mind")
    def test_run_yields_progress(
        self,
        mock_get_mind,
        mock_fallback,
        mock_init_pos,
        mock_init_inv,
        mock_update_npc,
        mock_wander,
        mock_decide,
        mock_exec_async,
        mock_plan_day,
        mock_reflect,
        mock_gen_bounties,
        mock_write_mem,
        mock_gen_events,
        mock_save,
    ):
        from backend.memory import AgentMind

        mock_get_mind.return_value = AgentMind()
        mock_decide.return_value = MagicMock(value="idle")
        mock_exec_async.return_value = MagicMock(
            success=True, description="闲坐", action_type=MagicMock(value="idle"), raw_dialogue=None
        )

        we = self._make_evolution()

        async def _collect():
            events = []
            async for evt in we.run():
                events.append(evt)
            return events

        events = asyncio.run(_collect())
        progress_events = [e for e in events if e["type"] == "progress"]
        assert len(progress_events) > 0
