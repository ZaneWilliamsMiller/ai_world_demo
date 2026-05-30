import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from unittest.mock import MagicMock, patch

from conftest import make_player


class TestGetOrInitMind:
    @patch("backend.agents.game_state.AgentMind")
    @patch("backend.data.npcs_data.NPC_SEEDS", {})
    def test_first_call_creates_mind(self, MockMind):
        mock_mind = MagicMock()
        MockMind.return_value = mock_mind
        from backend.agents.game_state import get_or_init_mind
        p = make_player()
        p.minds = {}
        result = get_or_init_mind(p, "npc_a")
        MockMind.assert_called_once()
        assert result is mock_mind
        assert p.minds["npc_a"] is mock_mind

    def test_existing_mind_returned_directly(self):
        from backend.agents.game_state import get_or_init_mind
        p = make_player()
        existing = MagicMock()
        p.minds = {"npc_a": existing}
        result = get_or_init_mind(p, "npc_a")
        assert result is existing

    @patch("backend.agents.game_state.AgentMind")
    @patch("backend.data.npcs_data.NPC_SEEDS", {})
    def test_no_seeds_does_not_call_import_seeds(self, MockMind):
        mock_mind = MagicMock()
        MockMind.return_value = mock_mind
        from backend.agents.game_state import get_or_init_mind
        p = make_player()
        p.minds = {}
        with patch("backend.agents.brain.import_seeds") as mock_import:
            get_or_init_mind(p, "npc_a")
            mock_import.assert_not_called()

    @patch("backend.agents.game_state.AgentMind")
    @patch("backend.data.npcs_data.NPC_SEEDS", {"npc_a": ["seed1", "seed2"]})
    @patch("backend.agents.game_state.shichen_name", return_value="辰")
    def test_with_seeds_calls_import_seeds(self, mock_shichen, MockMind):
        mock_mind = MagicMock()
        MockMind.return_value = mock_mind
        from backend.agents.game_state import get_or_init_mind
        p = make_player()
        p.minds = {}
        with patch("backend.agents.brain.import_seeds") as mock_import:
            get_or_init_mind(p, "npc_a")
            mock_import.assert_called_once()
            mock_import.assert_called_once_with(
                mock_mind,
                ["seed1", "seed2"],
                world_day=int(p.world_day),
                world_shichen="辰",
            )
