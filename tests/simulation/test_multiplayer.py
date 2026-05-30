from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.systems.constants import MAX_FAVOR_DELTA
from backend.systems.core import apply_favor
from backend.systems.economy import apply_coin_delta
from backend.systems.time_weather import advance_clock


class TestMultiplayer:
    def test_two_players_independent_states(self, make_player, init_world):
        p1 = make_player(player_id="player_1", display_name="侠客甲", px=16, py=30)
        p2 = make_player(player_id="player_2", display_name="侠客乙", px=78, py=50)
        init_world(p1)
        init_world(p2)
        apply_coin_delta(p1, 50)
        apply_coin_delta(p2, -30)
        assert p1.coins != p2.coins
        assert p1.px != p2.px or p1.py != p2.py

    def test_favor_independent_per_player(self, make_player, init_world):
        p1 = make_player(player_id="player_1", display_name="侠客甲")
        p2 = make_player(player_id="player_2", display_name="侠客乙")
        init_world(p1)
        init_world(p2)
        apply_favor(p1, "zhanggui", MAX_FAVOR_DELTA)
        apply_favor(p2, "zhanggui", -MAX_FAVOR_DELTA)
        assert p1.favor.get("zhanggui", 0) > 0
        assert p2.favor.get("zhanggui", 0) < 0
        assert p1.favor.get("zhanggui", 0) != p2.favor.get("zhanggui", 0)

    def test_clock_independent_per_player(self, make_player, init_world):
        with patch("backend.agents.actor.execute_plan_step") as mock_exec, \
             patch("backend.agents.game_state.get_or_init_mind") as mock_mind, \
             patch("random.random", return_value=1.0):
            mock_result = MagicMock()
            mock_result.action_type = MagicMock(value="idle")
            mock_exec.return_value = mock_result
            mock_mind_obj = MagicMock()
            mock_mind_obj.plan_by_shichen = {}
            mock_mind_obj.mood_decay_tick = MagicMock()
            mock_mind.return_value = mock_mind_obj

            p1 = make_player(player_id="player_1", display_name="侠客甲")
            p2 = make_player(player_id="player_2", display_name="侠客乙")
            init_world(p1)
            init_world(p2)
            advance_clock(p1, ticks=5)
            assert p1.world_tick == 5
            assert p2.world_tick == 0

    def test_npc_positions_independent_per_player(self, make_player, init_world):
        p1 = make_player(player_id="player_1", display_name="侠客甲")
        p2 = make_player(player_id="player_2", display_name="侠客乙")
        init_world(p1)
        init_world(p2)
        p1.npc_positions["test_npc"] = ("world", 10, 10)
        assert "test_npc" not in p2.npc_positions

    def test_inventory_independent_per_player(self, make_player, init_world):
        p1 = make_player(player_id="player_1", display_name="侠客甲")
        p2 = make_player(player_id="player_2", display_name="侠客乙")
        init_world(p1)
        init_world(p2)
        p1.inventory["干粮"] = 5
        assert "干粮" not in p2.inventory

    def test_reputation_independent_per_player(self, make_player, init_world):
        p1 = make_player(player_id="player_1", display_name="侠客甲")
        p2 = make_player(player_id="player_2", display_name="侠客乙")
        init_world(p1)
        init_world(p2)
        p1.reputation["yamen"] = 20
        p2.reputation["yamen"] = -10
        assert p1.reputation["yamen"] != p2.reputation["yamen"]

    def test_npc_inventories_independent_per_player(self, make_player, init_world):
        p1 = make_player(player_id="player_1", display_name="侠客甲")
        p2 = make_player(player_id="player_2", display_name="侠客乙")
        init_world(p1)
        init_world(p2)
        if "zhanggui" in p1.npc_inventories:
            p1.npc_inventories["zhanggui"]["干粮"] = 0
        if "zhanggui" in p2.npc_inventories:
            assert p2.npc_inventories["zhanggui"].get("干粮", 0) > 0

    def test_death_does_not_affect_other_player(self, make_player, init_world):
        p1 = make_player(player_id="player_1", display_name="侠客甲", permadeath=True)
        p2 = make_player(player_id="player_2", display_name="侠客乙")
        init_world(p1)
        init_world(p2)
        p1.dead = True
        p1.death_reason = "test"
        assert not p2.dead
        assert p2.death_reason is None

    def test_advancing_clock_for_one_player_does_not_affect_other(self, make_player, init_world):
        with patch("backend.agents.actor.execute_plan_step") as mock_exec, \
             patch("backend.agents.game_state.get_or_init_mind") as mock_mind, \
             patch("random.random", return_value=1.0):
            mock_result = MagicMock()
            mock_result.action_type = MagicMock(value="idle")
            mock_exec.return_value = mock_result
            mock_mind_obj = MagicMock()
            mock_mind_obj.plan_by_shichen = {}
            mock_mind_obj.mood_decay_tick = MagicMock()
            mock_mind.return_value = mock_mind_obj

            p1 = make_player(player_id="player_1", display_name="侠客甲")
            p2 = make_player(player_id="player_2", display_name="侠客乙")
            init_world(p1)
            init_world(p2)
            advance_clock(p1, ticks=3)
            assert p1.world_shichen != p2.world_shichen
