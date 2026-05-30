from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.agent_service import bg_plan_for_npcs, bg_reflect

from conftest import make_player


class TestBgReflect(unittest.TestCase):
    @patch("backend.services.agent_service.room")
    def test_player_not_found(self, mock_room):
        mock_room.players.get.return_value = None
        asyncio.run(bg_reflect("nonexistent", "npc1"))
        mock_room.players.get.assert_called_once_with("nonexistent")

    @patch("backend.services.agent_service.NPCS", {})
    @patch("backend.services.agent_service.room")
    def test_npc_not_found(self, mock_room):
        p = make_player()
        mock_room.players.get.return_value = p
        asyncio.run(bg_reflect("test_player", "nonexistent_npc"))

    @patch("backend.services.agent_service.agent_brain")
    @patch("backend.services.agent_service.get_or_init_mind")
    @patch("backend.services.agent_service.NPCS", {"npc1": {"name": "测试NPC", "short": "测试"}})
    @patch("backend.services.agent_service.room")
    def test_mind_no_need_reflect(self, mock_room, mock_get_mind, mock_brain):
        p = make_player()
        mock_room.players.get.return_value = p
        mind = MagicMock()
        mind.needs_reflect.return_value = False
        mock_get_mind.return_value = mind
        asyncio.run(bg_reflect("test_player", "npc1"))
        mock_brain.reflect.assert_not_called()

    @patch("backend.services.agent_service.shichen_name", return_value="子")
    @patch("backend.services.agent_service.agent_brain")
    @patch("backend.services.agent_service.get_or_init_mind")
    @patch("backend.services.agent_service.NPCS", {"npc1": {"name": "测试NPC", "short": "测试"}})
    @patch("backend.services.agent_service.room")
    def test_night_blocked(self, mock_room, mock_get_mind, mock_brain, mock_shichen):
        p = make_player(world_shichen=0)
        mock_room.players.get.return_value = p
        mind = MagicMock()
        mind.needs_reflect.return_value = True
        mind.affect_arousal = 5.0
        mock_get_mind.return_value = mind
        asyncio.run(bg_reflect("test_player", "npc1"))
        mock_brain.reflect.assert_not_called()

    @patch("backend.services.agent_service.shichen_name", return_value="子")
    @patch("backend.services.agent_service.agent_brain")
    @patch("backend.services.agent_service.get_or_init_mind")
    @patch("backend.services.agent_service.NPCS", {"npc1": {"name": "测试NPC", "short": "测试"}})
    @patch("backend.services.agent_service.room")
    def test_night_extreme_arousal_allowed(self, mock_room, mock_get_mind, mock_brain, mock_shichen):
        p = make_player(world_shichen=0)
        mock_room.players.get.return_value = p
        mind = MagicMock()
        mind.needs_reflect.return_value = True
        mind.affect_arousal = 9.0
        mock_get_mind.return_value = mind
        mock_brain.reflect = AsyncMock()
        mock_brain.cross_reflect = AsyncMock()
        asyncio.run(bg_reflect("test_player", "npc1"))
        mock_brain.reflect.assert_called_once()
        mock_brain.cross_reflect.assert_called_once()

    @patch("backend.services.agent_service.shichen_name", return_value="辰")
    @patch("backend.services.agent_service.agent_brain")
    @patch("backend.services.agent_service.get_or_init_mind")
    @patch("backend.services.agent_service.NPCS", {"npc1": {"name": "测试NPC", "short": "测试"}})
    @patch("backend.services.agent_service.room")
    def test_normal_reflect_flow(self, mock_room, mock_get_mind, mock_brain, mock_shichen):
        p = make_player(world_shichen=4)
        mock_room.players.get.return_value = p
        mind = MagicMock()
        mind.needs_reflect.return_value = True
        mind.affect_arousal = 5.0
        mock_get_mind.return_value = mind
        mock_brain.reflect = AsyncMock()
        mock_brain.cross_reflect = AsyncMock()
        asyncio.run(bg_reflect("test_player", "npc1"))
        mock_brain.reflect.assert_called_once()
        mock_brain.cross_reflect.assert_called_once()

    @patch("backend.services.agent_service.shichen_name", return_value="辰")
    @patch("backend.services.agent_service.agent_brain")
    @patch("backend.services.agent_service.get_or_init_mind")
    @patch("backend.services.agent_service.NPCS", {"npc1": {"name": "测试NPC", "short": "测试"}})
    @patch("backend.services.agent_service.room")
    def test_reflect_exception_handled(self, mock_room, mock_get_mind, mock_brain, mock_shichen):
        p = make_player(world_shichen=4)
        mock_room.players.get.return_value = p
        mind = MagicMock()
        mind.needs_reflect.return_value = True
        mind.affect_arousal = 5.0
        mock_get_mind.return_value = mind
        mock_brain.reflect = AsyncMock(side_effect=RuntimeError("LLM error"))
        asyncio.run(bg_reflect("test_player", "npc1"))
        mock_brain.reflect.assert_called_once()


class TestBgPlanForNpcs(unittest.TestCase):
    @patch("backend.services.agent_service.room")
    def test_player_not_found(self, mock_room):
        mock_room.players.get.return_value = None
        asyncio.run(bg_plan_for_npcs("nonexistent", ["npc1"], world_day=1))
        mock_room.players.get.assert_called_once_with("nonexistent")

    @patch("backend.services.agent_service.agent_brain")
    @patch("backend.services.agent_service.get_or_init_mind")
    @patch("backend.services.agent_service.NPCS", {"npc1": {"name": "NPC1", "short": "N1"}})
    @patch("backend.services.agent_service.room")
    def test_npc_not_found_skipped(self, mock_room, mock_get_mind, mock_brain):
        p = make_player()
        mock_room.players.get.return_value = p
        asyncio.run(bg_plan_for_npcs("test_player", ["nonexistent_npc"], world_day=1))
        mock_brain.plan_day.assert_not_called()

    @patch("backend.services.agent_service.agent_brain")
    @patch("backend.services.agent_service.get_or_init_mind")
    @patch("backend.services.agent_service.NPCS", {"npc1": {"name": "NPC1", "short": "N1"}})
    @patch("backend.services.agent_service.room")
    def test_already_planned_skipped(self, mock_room, mock_get_mind, mock_brain):
        p = make_player()
        mock_room.players.get.return_value = p
        mind = MagicMock()
        mind.plan_day = 1
        mock_get_mind.return_value = mind
        asyncio.run(bg_plan_for_npcs("test_player", ["npc1"], world_day=1))
        mock_brain.plan_day.assert_not_called()

    @patch("backend.services.agent_service.agent_brain")
    @patch("backend.services.agent_service.get_or_init_mind")
    @patch("backend.services.agent_service.NPCS", {"npc1": {"name": "NPC1", "short": "N1"}})
    @patch("backend.services.agent_service.room")
    def test_normal_plan_flow(self, mock_room, mock_get_mind, mock_brain):
        p = make_player()
        mock_room.players.get.return_value = p
        mind = MagicMock()
        mind.plan_day = None
        mock_get_mind.return_value = mind
        mock_brain.plan_day = AsyncMock()
        asyncio.run(bg_plan_for_npcs("test_player", ["npc1"], world_day=1))
        mock_brain.plan_day.assert_called_once()

    @patch("backend.services.agent_service.agent_brain")
    @patch("backend.services.agent_service.get_or_init_mind")
    @patch("backend.services.agent_service.NPCS", {
        "npc1": {"name": "NPC1", "short": "N1"},
        "npc2": {"name": "NPC2", "short": "N2"},
    })
    @patch("backend.services.agent_service.room")
    def test_plan_exception_continues(self, mock_room, mock_get_mind, mock_brain):
        p = make_player()
        mock_room.players.get.return_value = p
        mind1 = MagicMock()
        mind1.plan_day = None
        mind2 = MagicMock()
        mind2.plan_day = None
        mock_get_mind.side_effect = [mind1, mind2]
        mock_brain.plan_day = AsyncMock(side_effect=RuntimeError("LLM error"))
        asyncio.run(bg_plan_for_npcs("test_player", ["npc1", "npc2"], world_day=1))
        assert mock_brain.plan_day.call_count == 2


if __name__ == "__main__":
    unittest.main()
