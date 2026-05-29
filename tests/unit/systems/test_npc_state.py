"""离线单元测试 — npc_state 模块"""
# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportCallIssue=false
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unittest.mock import MagicMock, patch

from conftest import make_player


class TestWeatherWanderMultiplier:
    def test_shelter_weather_returns_zero(self):
        from backend.systems.npc_state import _weather_wander_multiplier
        for w in ("骤雨", "湿瘴", "重雾", "寒露", "夜霜"):
            assert _weather_wander_multiplier(w, night=False) == 0.0
            assert _weather_wander_multiplier(w, night=True) == 0.0

    def test_slow_weather_returns_04(self):
        from backend.systems.npc_state import _weather_wander_multiplier
        for w in ("薄雾", "风急", "闷热"):
            assert _weather_wander_multiplier(w, night=False) == 0.4
            assert _weather_wander_multiplier(w, night=True) == 0.4

    def test_sunny_daytime_returns_13(self):
        from backend.systems.npc_state import _weather_wander_multiplier
        assert _weather_wander_multiplier("晴", night=False) == 1.3

    def test_sunny_night_returns_10(self):
        from backend.systems.npc_state import _weather_wander_multiplier
        assert _weather_wander_multiplier("晴", night=True) == 1.0

    def test_neutral_weather_returns_10(self):
        from backend.systems.npc_state import _weather_wander_multiplier
        for w in ("薄阴", "云遮日", "小风"):
            assert _weather_wander_multiplier(w, night=False) == 1.0
            assert _weather_wander_multiplier(w, night=True) == 1.0

    def test_unknown_weather_returns_10(self):
        from backend.systems.npc_state import _weather_wander_multiplier
        assert _weather_wander_multiplier("未知天气", night=False) == 1.0
        assert _weather_wander_multiplier("未知天气", night=True) == 1.0


class TestTileIsSheltered:
    def test_shelter_tiles(self):
        from backend.systems.npc_state import _tile_is_sheltered
        for ch in ("T", "Y", "M", "I"):
            assert _tile_is_sheltered(ch) is True

    def test_non_shelter_tiles(self):
        from backend.systems.npc_state import _tile_is_sheltered
        for ch in (".", ",", "#", "~", "F", ";", "@", "B", "/", "&", "m"):
            assert _tile_is_sheltered(ch) is False

    def test_empty_string(self):
        from backend.systems.npc_state import _tile_is_sheltered
        assert _tile_is_sheltered("") is False


class TestMaybeWanderNpcs:
    @patch("backend.systems.npc_state.can_step_between", return_value=True)
    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.core.init_npc_positions")
    def test_wander_moves_npc(self, mock_init, mock_night, mock_step):
        from backend.systems.npc_state import maybe_wander_npcs
        p = make_player(weather="晴")
        p.npc_positions = {"npc_a": ("world", 2, 2), "npc_b": ("world", 2, 2)}
        mock_npcs = {"npc_a": {"cell": ("world", 2, 2)}, "npc_b": {"cell": ("world", 2, 2)}}
        mock_maps = {"world": {"rows": [".....", ".....", ".....", ".....", "....."]}}
        with patch("backend.systems.npc_state.NPCS", mock_npcs), \
             patch("backend.systems.npc_state.LONG_DISTANCE_WANDERERS", ()), \
             patch("backend.systems.npc_state.NPC_WANDER_BASE_CHANCE", 1.0), \
             patch("backend.systems.npc_state.MAPS", mock_maps), \
             patch("random.random", return_value=0.0), \
             patch("random.choice", side_effect=lambda c: c[0]):
            maybe_wander_npcs(p, ticks=1)
        assert p.npc_positions["npc_a"] != ("world", 2, 2) or p.npc_positions["npc_b"] != ("world", 2, 2)

    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.core.init_npc_positions")
    def test_zero_ticks_does_nothing(self, mock_init, mock_night):
        from backend.systems.npc_state import maybe_wander_npcs
        p = make_player()
        p.npc_positions = {"npc_a": ("world", 2, 2)}
        maybe_wander_npcs(p, ticks=0)
        mock_init.assert_not_called()

    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.core.init_npc_positions")
    def test_negative_ticks_does_nothing(self, mock_init, mock_night):
        from backend.systems.npc_state import maybe_wander_npcs
        p = make_player()
        p.npc_positions = {"npc_a": ("world", 2, 2)}
        maybe_wander_npcs(p, ticks=-1)
        mock_init.assert_not_called()

    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.core.init_npc_positions")
    def test_always_npc_skipped(self, mock_init, mock_night):
        from backend.systems.npc_state import maybe_wander_npcs
        p = make_player(weather="晴")
        p.npc_positions = {"npc_a": ("world", 2, 2)}
        with patch("backend.systems.npc_state.NPCS", {"npc_a": {"always": True}}), \
             patch("random.random", return_value=0.0):
            maybe_wander_npcs(p, ticks=1)
        assert p.npc_positions["npc_a"] == ("world", 2, 2)

    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.core.init_npc_positions")
    def test_hidden_npc_skipped(self, mock_init, mock_night):
        from backend.systems.npc_state import maybe_wander_npcs
        p = make_player(weather="晴")
        p.npc_positions = {"npc_a": ("world", 2, 2)}
        with patch("backend.systems.npc_state.NPCS", {"npc_a": {"hidden": True}}), \
             patch("random.random", return_value=0.0):
            maybe_wander_npcs(p, ticks=1)
        assert p.npc_positions["npc_a"] == ("world", 2, 2)

    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.core.init_npc_positions")
    def test_shelter_weather_skips_wander(self, mock_init, mock_night):
        from backend.systems.npc_state import maybe_wander_npcs
        p = make_player(weather="骤雨")
        p.npc_positions = {"npc_a": ("world", 2, 2)}
        with patch("backend.systems.npc_state.NPCS", {"npc_a": {"cell": ("world", 2, 2)}}), \
             patch("backend.systems.npc_state.LONG_DISTANCE_WANDERERS", ()), \
             patch("random.random", return_value=0.0):
            maybe_wander_npcs(p, ticks=1)
        assert p.npc_positions["npc_a"] == ("world", 2, 2)

    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.core.init_npc_positions")
    def test_random_high_skips_wander(self, mock_init, mock_night):
        from backend.systems.npc_state import maybe_wander_npcs
        p = make_player(weather="晴")
        p.npc_positions = {"npc_a": ("world", 2, 2)}
        with patch("backend.systems.npc_state.NPCS", {"npc_a": {"cell": ("world", 2, 2)}}), \
             patch("backend.systems.npc_state.LONG_DISTANCE_WANDERERS", ()), \
             patch("random.random", return_value=1.0):
            maybe_wander_npcs(p, ticks=1)
        assert p.npc_positions["npc_a"] == ("world", 2, 2)

    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.core.init_npc_positions")
    def test_invalid_position_skipped(self, mock_init, mock_night):
        from backend.systems.npc_state import maybe_wander_npcs
        p = make_player(weather="晴")
        p.npc_positions = {"npc_a": "invalid"}
        with patch("backend.systems.npc_state.NPCS", {"npc_a": {"cell": ("world", 2, 2)}}), \
             patch("backend.systems.npc_state.LONG_DISTANCE_WANDERERS", ()), \
             patch("random.random", return_value=0.0):
            maybe_wander_npcs(p, ticks=1)
        assert p.npc_positions["npc_a"] == "invalid"

    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.core.init_npc_positions")
    def test_short_position_tuple_skipped(self, mock_init, mock_night):
        from backend.systems.npc_state import maybe_wander_npcs
        p = make_player(weather="晴")
        p.npc_positions = {"npc_a": ("world", 2)}
        with patch("backend.systems.npc_state.NPCS", {"npc_a": {"cell": ("world", 2, 2)}}), \
             patch("backend.systems.npc_state.LONG_DISTANCE_WANDERERS", ()), \
             patch("random.random", return_value=0.0):
            maybe_wander_npcs(p, ticks=1)
        assert p.npc_positions["npc_a"] == ("world", 2)

    @patch("backend.systems.npc_state.can_step_between", return_value=True)
    @patch("backend.systems.npc_state.is_night", return_value=True)
    @patch("backend.systems.core.init_npc_positions")
    def test_night_outdoor_tile_stays(self, mock_init, mock_night, mock_step):
        from backend.systems.npc_state import maybe_wander_npcs
        p = make_player(weather="晴")
        p.npc_positions = {"npc_a": ("world", 2, 2)}
        mock_maps = {"world": {"rows": [",,,,,", ",,,,,", ",,,,,", ",,,,,", ",,,,,"]}}
        with patch("backend.systems.npc_state.NPCS", {"npc_a": {"cell": ("world", 2, 2)}}), \
             patch("backend.systems.npc_state.LONG_DISTANCE_WANDERERS", ()), \
             patch("backend.systems.npc_state.NPC_WANDER_BASE_CHANCE", 1.0), \
             patch("backend.systems.npc_state.MAPS", mock_maps), \
             patch("random.random", return_value=0.0):
            maybe_wander_npcs(p, ticks=1)
        assert p.npc_positions["npc_a"] == ("world", 2, 2)

    @patch("backend.systems.npc_state.can_step_between", return_value=True)
    @patch("backend.systems.npc_state.is_night", return_value=True)
    @patch("backend.systems.core.init_npc_positions")
    def test_night_indoor_tile_can_wander(self, mock_init, mock_night, mock_step):
        from backend.systems.npc_state import maybe_wander_npcs
        p = make_player(weather="晴")
        p.npc_positions = {"npc_a": ("world", 2, 2)}
        mock_maps = {"world": {"rows": ["TTTTT", "TTTTT", "TTTTT", "TTTTT", "TTTTT"]}}
        with patch("backend.systems.npc_state.NPCS", {"npc_a": {"cell": ("world", 2, 2)}}), \
             patch("backend.systems.npc_state.LONG_DISTANCE_WANDERERS", ()), \
             patch("backend.systems.npc_state.NPC_WANDER_BASE_CHANCE", 1.0), \
             patch("backend.systems.npc_state.MAPS", mock_maps), \
             patch("random.random", return_value=0.0), \
             patch("random.choice", side_effect=lambda c: c[0]):
            maybe_wander_npcs(p, ticks=1)
        assert p.npc_positions["npc_a"] != ("world", 2, 2)

    @patch("backend.systems.npc_state.can_step_between", return_value=True)
    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.core.init_npc_positions")
    def test_anchor_radius_respected(self, mock_init, mock_night, mock_step):
        from backend.systems.npc_state import maybe_wander_npcs
        p = make_player(weather="晴")
        p.npc_positions = {"npc_a": ("world", 2, 2)}
        mock_maps = {"world": {"rows": ["TTTTT", "TTTTT", "TTTTT", "TTTTT", "TTTTT"]}}
        with patch("backend.systems.npc_state.NPCS", {"npc_a": {"cell": ("world", 2, 2), "wander_anchor_radius": 1}}), \
             patch("backend.systems.npc_state.LONG_DISTANCE_WANDERERS", ()), \
             patch("backend.systems.npc_state.NPC_WANDER_BASE_CHANCE", 1.0), \
             patch("backend.systems.npc_state.MAPS", mock_maps), \
             patch("random.random", return_value=0.0), \
             patch("random.choice", side_effect=lambda c: c[0]):
            maybe_wander_npcs(p, ticks=1)
        new_pos = p.npc_positions["npc_a"]
        dist = abs(new_pos[1] - 2) + abs(new_pos[2] - 2)
        assert dist <= 1

    @patch("backend.systems.npc_state.can_step_between", return_value=True)
    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.core.init_npc_positions")
    def test_whitelist_allows_same_map(self, mock_init, mock_night, mock_step):
        from backend.systems.npc_state import maybe_wander_npcs
        p = make_player(weather="晴")
        p.npc_positions = {"npc_a": ("world", 2, 2)}
        mock_maps = {"world": {"rows": [".....", ".....", ".....", ".....", "....."]}}
        with patch("backend.systems.npc_state.NPCS", {"npc_a": {"cell": ("world", 2, 2), "wander_maps_whitelist": ("world",)}}), \
             patch("backend.systems.npc_state.LONG_DISTANCE_WANDERERS", ()), \
             patch("backend.systems.npc_state.NPC_WANDER_BASE_CHANCE", 1.0), \
             patch("backend.systems.npc_state.MAPS", mock_maps), \
             patch("random.random", return_value=0.0), \
             patch("random.choice", side_effect=lambda c: c[0]):
            maybe_wander_npcs(p, ticks=1)
        assert p.npc_positions["npc_a"][0] == "world"

    @patch("backend.systems.npc_state.can_step_between", return_value=True)
    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.core.init_npc_positions")
    def test_whitelist_snaps_to_anchor_on_wrong_map(self, mock_init, mock_night, mock_step):
        from backend.systems.npc_state import maybe_wander_npcs
        p = make_player(weather="晴")
        p.npc_positions = {"npc_a": ("other", 1, 1)}
        mock_maps = {"other": {"rows": [".....", ".....", "....."]}}
        with patch("backend.systems.npc_state.NPCS", {"npc_a": {"cell": ("world", 2, 2), "wander_maps_whitelist": ("world",)}}), \
             patch("backend.systems.npc_state.LONG_DISTANCE_WANDERERS", ()), \
             patch("backend.systems.npc_state.NPC_WANDER_BASE_CHANCE", 1.0), \
             patch("backend.systems.npc_state.MAPS", mock_maps), \
             patch("random.random", return_value=0.0):
            maybe_wander_npcs(p, ticks=1)
        assert p.npc_positions["npc_a"] == ("world", 2, 2)

    @patch("backend.systems.npc_state.can_step_between", return_value=True)
    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.core.init_npc_positions")
    def test_seeks_shelter_in_bad_weather(self, mock_init, mock_night, mock_step):
        from backend.systems.npc_state import maybe_wander_npcs
        p = make_player(weather="骤雨")
        p.npc_positions = {"npc_a": ("world", 2, 2)}
        mock_maps = {"world": {"rows": ["..T..", "..T..", "..T..", "..T..", "..T.."]}}
        with patch("backend.systems.npc_state.NPCS", {"npc_a": {"cell": ("world", 2, 2)}}), \
             patch("backend.systems.npc_state.LONG_DISTANCE_WANDERERS", ()), \
             patch("backend.systems.npc_state.NPC_WANDER_BASE_CHANCE", 1.0), \
             patch("backend.systems.npc_state.MAPS", mock_maps), \
             patch("random.random", side_effect=[0.0, 0.0]), \
             patch("random.choice", side_effect=lambda c: c[0]):
            maybe_wander_npcs(p, ticks=1)
        new_pos = p.npc_positions["npc_a"]
        target_ch = mock_maps["world"]["rows"][new_pos[2]][new_pos[1]]
        assert target_ch == "T"

    @patch("backend.systems.npc_state.can_step_between", return_value=True)
    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.core.init_npc_positions")
    def test_unbounded_wanderer_ignores_anchor(self, mock_init, mock_night, mock_step):
        from backend.systems.npc_state import maybe_wander_npcs
        p = make_player(weather="晴")
        p.npc_positions = {"npc_a": ("world", 2, 2)}
        mock_maps = {"world": {"rows": [".....", ".....", ".....", ".....", "....."]}}
        with patch("backend.systems.npc_state.NPCS", {"npc_a": {"cell": ("world", 2, 2)}}), \
             patch("backend.systems.npc_state.LONG_DISTANCE_WANDERERS", ("npc_a",)), \
             patch("backend.systems.npc_state.NPC_WANDER_BASE_CHANCE", 1.0), \
             patch("backend.systems.npc_state.MAPS", mock_maps), \
             patch("random.random", return_value=0.0), \
             patch("random.choice", side_effect=lambda c: c[0]):
            maybe_wander_npcs(p, ticks=1)
        assert p.npc_positions["npc_a"] != ("world", 2, 2)

    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.core.init_npc_positions")
    def test_empty_map_skipped(self, mock_init, mock_night):
        from backend.systems.npc_state import maybe_wander_npcs
        p = make_player(weather="晴")
        p.npc_positions = {"npc_a": ("world", 2, 2)}
        with patch("backend.systems.npc_state.NPCS", {"npc_a": {"cell": ("world", 2, 2)}}), \
             patch("backend.systems.npc_state.LONG_DISTANCE_WANDERERS", ()), \
             patch("backend.systems.npc_state.MAPS", {}), \
             patch("random.random", return_value=0.0):
            maybe_wander_npcs(p, ticks=1)
        assert p.npc_positions["npc_a"] == ("world", 2, 2)

    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.core.init_npc_positions")
    def test_out_of_bounds_position_skipped(self, mock_init, mock_night):
        from backend.systems.npc_state import maybe_wander_npcs
        p = make_player(weather="晴")
        p.npc_positions = {"npc_a": ("world", 50, 50)}
        with patch("backend.systems.npc_state.NPCS", {"npc_a": {"cell": ("world", 2, 2)}}), \
             patch("backend.systems.npc_state.LONG_DISTANCE_WANDERERS", ()), \
             patch("backend.systems.npc_state.MAPS", {"world": {"rows": [".."]}}), \
             patch("random.random", return_value=0.0):
            maybe_wander_npcs(p, ticks=1)
        assert p.npc_positions["npc_a"] == ("world", 50, 50)

    @patch("backend.systems.npc_state.can_step_between", return_value=False)
    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.core.init_npc_positions")
    def test_no_passable_candidates_stays(self, mock_init, mock_night, mock_step):
        from backend.systems.npc_state import maybe_wander_npcs
        p = make_player(weather="晴")
        p.npc_positions = {"npc_a": ("world", 2, 2)}
        mock_maps = {"world": {"rows": [".....", ".....", ".....", ".....", "....."]}}
        with patch("backend.systems.npc_state.NPCS", {"npc_a": {"cell": ("world", 2, 2)}}), \
             patch("backend.systems.npc_state.LONG_DISTANCE_WANDERERS", ()), \
             patch("backend.systems.npc_state.NPC_WANDER_BASE_CHANCE", 1.0), \
             patch("backend.systems.npc_state.MAPS", mock_maps), \
             patch("random.random", return_value=0.0):
            maybe_wander_npcs(p, ticks=1)
        assert p.npc_positions["npc_a"] == ("world", 2, 2)

    @patch("backend.systems.npc_state.can_step_between", return_value=True)
    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.core.init_npc_positions")
    def test_wander_unbounded_flag(self, mock_init, mock_night, mock_step):
        from backend.systems.npc_state import maybe_wander_npcs
        p = make_player(weather="晴")
        p.npc_positions = {"npc_a": ("world", 2, 2)}
        mock_maps = {"world": {"rows": [".....", ".....", ".....", ".....", "....."]}}
        with patch("backend.systems.npc_state.NPCS", {"npc_a": {"cell": ("world", 2, 2), "wander_unbounded": True}}), \
             patch("backend.systems.npc_state.LONG_DISTANCE_WANDERERS", ()), \
             patch("backend.systems.npc_state.NPC_WANDER_BASE_CHANCE", 1.0), \
             patch("backend.systems.npc_state.MAPS", mock_maps), \
             patch("random.random", return_value=0.0), \
             patch("random.choice", side_effect=lambda c: c[0]):
            maybe_wander_npcs(p, ticks=1)
        assert p.npc_positions["npc_a"] != ("world", 2, 2)

    @patch("backend.systems.npc_state.can_step_between", return_value=True)
    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.core.init_npc_positions")
    def test_negative_y_position_skipped(self, mock_init, mock_night, mock_step):
        from backend.systems.npc_state import maybe_wander_npcs
        p = make_player(weather="晴")
        p.npc_positions = {"npc_a": ("world", 2, -1)}
        mock_maps = {"world": {"rows": [".....", ".....", "....."]}}
        with patch("backend.systems.npc_state.NPCS", {"npc_a": {"cell": ("world", 2, 2)}}), \
             patch("backend.systems.npc_state.LONG_DISTANCE_WANDERERS", ()), \
             patch("backend.systems.npc_state.NPC_WANDER_BASE_CHANCE", 1.0), \
             patch("backend.systems.npc_state.MAPS", mock_maps), \
             patch("random.random", return_value=0.0):
            maybe_wander_npcs(p, ticks=1)
        assert p.npc_positions["npc_a"] == ("world", 2, -1)

    @patch("backend.systems.npc_state.can_step_between", return_value=True)
    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.core.init_npc_positions")
    def test_negative_x_position_skipped(self, mock_init, mock_night, mock_step):
        from backend.systems.npc_state import maybe_wander_npcs
        p = make_player(weather="晴")
        p.npc_positions = {"npc_a": ("world", -1, 1)}
        mock_maps = {"world": {"rows": [".....", ".....", "....."]}}
        with patch("backend.systems.npc_state.NPCS", {"npc_a": {"cell": ("world", 2, 2)}}), \
             patch("backend.systems.npc_state.LONG_DISTANCE_WANDERERS", ()), \
             patch("backend.systems.npc_state.NPC_WANDER_BASE_CHANCE", 1.0), \
             patch("backend.systems.npc_state.MAPS", mock_maps), \
             patch("random.random", return_value=0.0):
            maybe_wander_npcs(p, ticks=1)
        assert p.npc_positions["npc_a"] == ("world", -1, 1)

    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.core.init_npc_positions")
    def test_whitelist_wrong_map_no_anchor_stays(self, mock_init, mock_night):
        from backend.systems.npc_state import maybe_wander_npcs
        p = make_player(weather="晴")
        p.npc_positions = {"npc_a": ("other", 1, 1)}
        with patch("backend.systems.npc_state.NPCS", {"npc_a": {"wander_maps_whitelist": ("world",)}}), \
             patch("backend.systems.npc_state.LONG_DISTANCE_WANDERERS", ()), \
             patch("backend.systems.npc_state.NPC_WANDER_BASE_CHANCE", 1.0), \
             patch("random.random", return_value=0.0):
            maybe_wander_npcs(p, ticks=1)
        assert p.npc_positions["npc_a"] == ("other", 1, 1)


class TestIsActiveAt:
    def test_active_during_day(self):
        from backend.systems.npc_state import is_active_at
        assert is_active_at((4, 21), 4) is True

    def test_inactive_at_night_non_nocturnal(self):
        from backend.systems.npc_state import is_active_at
        assert is_active_at((4, 21), 0, nocturnal=False) is False
        assert is_active_at((4, 21), 1, nocturnal=False) is False
        assert is_active_at((4, 21), 2, nocturnal=False) is False

    def test_nocturnal_active_at_night(self):
        from backend.systems.npc_state import is_active_at
        assert is_active_at((18, 29), 0, nocturnal=True) is True
        assert is_active_at((18, 29), 1, nocturnal=True) is True

    def test_invalid_active_val_returns_true(self):
        from backend.systems.npc_state import is_active_at
        assert is_active_at(None, 4) is True
        assert is_active_at((), 4) is True
        assert is_active_at((4,), 4) is True

    def test_wrap_around_active_nocturnal(self):
        from backend.systems.npc_state import is_active_at
        assert is_active_at((22, 28), 0, nocturnal=True) is True

    def test_wrap_around_active_non_nocturnal_early_morning(self):
        from backend.systems.npc_state import is_active_at
        assert is_active_at((22, 28), 2, nocturnal=False) is False

    def test_shichen_to_hour_mapping(self):
        from backend.systems.npc_state import is_active_at
        assert is_active_at((7, 21), 4) is True

    def test_active_range_single_hour(self):
        from backend.systems.npc_state import is_active_at
        assert is_active_at((7, 7), 4) is True


class TestUpdateNpcStatesFromHabits:
    @patch("backend.systems.npc_state.shichen_name", return_value="辰")
    @patch("backend.systems.npc_state.NPC_HABITS", {})
    @patch("backend.systems.npc_state.NPCS", {})
    def test_empty_habits_no_changes(self, mock_shichen):
        from backend.systems.npc_state import update_npc_states_from_habits
        p = make_player()
        p.npc_states = {}
        changes = update_npc_states_from_habits(p)
        assert changes == {}

    @patch("backend.systems.npc_state.shichen_name", return_value="辰")
    @patch("backend.systems.npc_state.NPC_HABITS", {"npc_a": {"active": (4, 21)}})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_active_npc_set_to_idle(self, mock_shichen):
        from backend.systems.npc_state import update_npc_states_from_habits
        p = make_player(world_shichen=4)
        p.npc_states = {"npc_a": "resting"}
        changes = update_npc_states_from_habits(p)
        assert p.npc_states["npc_a"] == "idle"
        assert "npc_a" in changes

    @patch("backend.systems.npc_state.shichen_name", return_value="子")
    @patch("backend.systems.npc_state.NPC_HABITS", {"npc_a": {"active": (4, 21)}})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_inactive_npc_set_to_resting(self, mock_shichen):
        from backend.systems.npc_state import update_npc_states_from_habits
        p = make_player(world_shichen=0)
        p.npc_states = {"npc_a": "idle"}
        changes = update_npc_states_from_habits(p)
        assert p.npc_states["npc_a"] == "resting"
        assert "npc_a" in changes

    @patch("backend.systems.npc_state.shichen_name", return_value="辰")
    @patch("backend.systems.npc_state.NPC_HABITS", {"npc_a": {"active": (4, 21)}})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_no_change_when_state_same(self, mock_shichen):
        from backend.systems.npc_state import update_npc_states_from_habits
        p = make_player(world_shichen=4)
        p.npc_states = {"npc_a": "idle"}
        changes = update_npc_states_from_habits(p)
        assert changes == {}

    @patch("backend.systems.npc_state.shichen_name", return_value="辰")
    @patch("backend.systems.npc_state.NPC_HABITS", {"npc_a": {"active": (4, 21)}})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {"always": True}})
    def test_always_npc_skipped(self, mock_shichen):
        from backend.systems.npc_state import update_npc_states_from_habits
        p = make_player(world_shichen=0)
        p.npc_states = {"npc_a": "idle"}
        changes = update_npc_states_from_habits(p)
        assert "npc_a" not in changes

    @patch("backend.systems.npc_state.shichen_name", return_value="辰")
    @patch("backend.systems.npc_state.NPC_HABITS", {"npc_a": {"active": (4, 21)}})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {"hidden": True}})
    def test_hidden_npc_skipped(self, mock_shichen):
        from backend.systems.npc_state import update_npc_states_from_habits
        p = make_player(world_shichen=0)
        p.npc_states = {"npc_a": "idle"}
        changes = update_npc_states_from_habits(p)
        assert "npc_a" not in changes

    @patch("backend.systems.npc_state.shichen_name", return_value="辰")
    @patch("backend.systems.npc_state.NPC_HABITS", {"npc_a": {"active": (18, 29), "nocturnal": True}})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_nocturnal_npc_active_at_night(self, mock_shichen):
        from backend.systems.npc_state import update_npc_states_from_habits
        p = make_player(world_shichen=0)
        p.npc_states = {"npc_a": "resting"}
        changes = update_npc_states_from_habits(p)
        assert p.npc_states["npc_a"] == "idle"

    @patch("backend.systems.npc_state.shichen_name", return_value="辰")
    @patch("backend.systems.npc_state.NPC_HABITS", {"npc_a": {"active": (4, 21)}})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_creates_npc_states_if_missing(self, mock_shichen):
        from backend.systems.npc_state import update_npc_states_from_habits
        p = make_player(world_shichen=4)
        p.npc_states = None
        changes = update_npc_states_from_habits(p)
        assert isinstance(p.npc_states, dict)

    @patch("backend.systems.npc_state.shichen_name", return_value="辰")
    @patch("backend.systems.npc_state.NPC_HABITS", {"npc_a": {"active": (4, 21)}})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_default_state_is_idle(self, mock_shichen):
        from backend.systems.npc_state import update_npc_states_from_habits
        p = make_player(world_shichen=0)
        p.npc_states = {}
        changes = update_npc_states_from_habits(p)
        assert p.npc_states["npc_a"] == "resting"
        assert changes["npc_a"] == "idle→resting"

    @patch("backend.systems.npc_state.shichen_name", return_value="辰")
    @patch("backend.systems.npc_state.NPC_HABITS", {"npc_a": {"active": (4, 21)}})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_mood_decay_called(self, mock_shichen):
        from backend.systems.npc_state import update_npc_states_from_habits
        p = make_player(world_shichen=4)
        p.npc_states = {}
        mock_mind = MagicMock()
        mock_mind.affect_valence = 0
        p.minds = {"npc_a": mock_mind}
        update_npc_states_from_habits(p)
        mock_mind.mood_decay_tick.assert_called_once_with("辰")

    @patch("backend.systems.npc_state.shichen_name", return_value="辰")
    @patch("backend.systems.npc_state.NPC_HABITS", {"npc_a": {"active": (4, 21)}})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_mood_decay_skips_none_mind(self, mock_shichen):
        from backend.systems.npc_state import update_npc_states_from_habits
        p = make_player(world_shichen=4)
        p.npc_states = {}
        p.minds = {"npc_a": None}
        update_npc_states_from_habits(p)

    @patch("backend.systems.npc_state.shichen_name", return_value="辰")
    @patch("backend.systems.npc_state.NPC_HABITS", {"npc_a": {"active": (4, 21)}})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_mood_decay_skips_mind_without_affect(self, mock_shichen):
        from backend.systems.npc_state import update_npc_states_from_habits
        p = make_player(world_shichen=4)
        p.npc_states = {}
        p.minds = {"npc_a": MagicMock(spec=[])}
        update_npc_states_from_habits(p)

    @patch("backend.systems.npc_state.shichen_name", return_value="辰")
    @patch("backend.systems.npc_state.NPC_HABITS", {})
    @patch("backend.systems.npc_state.NPCS", {})
    def test_none_shichen_defaults_to_6(self, mock_shichen):
        from backend.systems.npc_state import update_npc_states_from_habits
        p = make_player()
        p.world_shichen = None
        p.npc_states = {}
        update_npc_states_from_habits(p)
        mock_shichen.assert_called_once()

    @patch("backend.systems.npc_state.shichen_name", return_value="辰")
    @patch("backend.systems.npc_state.NPC_HABITS", {"npc_a": {"active": (4, 21)}, "npc_b": {"active": (18, 29), "nocturnal": True}})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}, "npc_b": {}})
    def test_multiple_npcs_mixed(self, mock_shichen):
        from backend.systems.npc_state import update_npc_states_from_habits
        p = make_player(world_shichen=4)
        p.npc_states = {"npc_a": "resting", "npc_b": "idle"}
        changes = update_npc_states_from_habits(p)
        assert p.npc_states["npc_a"] == "idle"
        assert "npc_a" in changes

    @patch("backend.systems.npc_state.shichen_name", return_value="辰")
    @patch("backend.systems.npc_state.NPC_HABITS", {"npc_a": {"active": (4, 21)}})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_changes_format(self, mock_shichen):
        from backend.systems.npc_state import update_npc_states_from_habits
        p = make_player(world_shichen=0)
        p.npc_states = {"npc_a": "busy"}
        changes = update_npc_states_from_habits(p)
        assert changes["npc_a"] == "busy→resting"


class TestUpdateNpcStateDynamic:
    @patch("backend.systems.npc_state.NPC_FACTION", {"npc_a": "yamen"})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_hostile_from_low_rep(self):
        from backend.systems.npc_state import update_npc_state_dynamic
        p = make_player()
        p.npc_states = {"npc_a": "idle"}
        p.reputation = {"yamen": -30}
        result = update_npc_state_dynamic(p, "npc_a")
        assert result == "hostile"
        assert p.npc_states["npc_a"] == "hostile"

    @patch("backend.systems.npc_state.NPC_FACTION", {"npc_a": "yamen"})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_hostile_from_low_favor(self):
        from backend.systems.npc_state import update_npc_state_dynamic
        p = make_player()
        p.npc_states = {"npc_a": "idle"}
        p.favor = {"npc_a": -35}
        result = update_npc_state_dynamic(p, "npc_a")
        assert result == "hostile"
        assert p.npc_states["npc_a"] == "hostile"

    @patch("backend.systems.npc_state.NPC_FACTION", {"npc_a": "yamen"})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_alert_from_low_rep(self):
        from backend.systems.npc_state import update_npc_state_dynamic
        p = make_player()
        p.npc_states = {"npc_a": "idle"}
        p.reputation = {"yamen": -10}
        result = update_npc_state_dynamic(p, "npc_a")
        assert result == "alert"
        assert p.npc_states["npc_a"] == "alert"

    @patch("backend.systems.npc_state.NPC_FACTION", {"npc_a": "yamen"})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_alert_from_low_favor(self):
        from backend.systems.npc_state import update_npc_state_dynamic
        p = make_player()
        p.npc_states = {"npc_a": "idle"}
        p.favor = {"npc_a": -10}
        result = update_npc_state_dynamic(p, "npc_a")
        assert result == "alert"
        assert p.npc_states["npc_a"] == "alert"

    @patch("backend.systems.npc_state.NPC_FACTION", {"npc_a": "yamen"})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_alert_from_trap_target(self):
        from backend.systems.npc_state import update_npc_state_dynamic
        p = make_player()
        p.npc_states = {"npc_a": "idle"}
        p.move_locked = True
        p.move_lock_npc_id = "npc_a"
        result = update_npc_state_dynamic(p, "npc_a")
        assert result == "alert"
        assert p.npc_states["npc_a"] == "alert"

    @patch("backend.systems.npc_state.NPC_FACTION", {"npc_a": "yamen"})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_trap_target_different_npc_no_alert(self):
        from backend.systems.npc_state import update_npc_state_dynamic
        p = make_player()
        p.npc_states = {"npc_a": "idle"}
        p.move_locked = True
        p.move_lock_npc_id = "npc_b"
        result = update_npc_state_dynamic(p, "npc_a")
        assert result is None

    @patch("backend.systems.npc_state.NPC_FACTION", {"npc_a": "yamen"})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_recovery_from_hostile_to_idle(self):
        from backend.systems.npc_state import update_npc_state_dynamic
        p = make_player()
        p.npc_states = {"npc_a": "hostile"}
        p.reputation = {"yamen": 10}
        result = update_npc_state_dynamic(p, "npc_a")
        assert result == "idle"
        assert p.npc_states["npc_a"] == "idle"

    @patch("backend.systems.npc_state.NPC_FACTION", {"npc_a": "yamen"})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_recovery_from_alert_to_idle(self):
        from backend.systems.npc_state import update_npc_state_dynamic
        p = make_player()
        p.npc_states = {"npc_a": "alert"}
        p.reputation = {"yamen": 10}
        result = update_npc_state_dynamic(p, "npc_a")
        assert result == "idle"
        assert p.npc_states["npc_a"] == "idle"

    @patch("backend.systems.npc_state.NPC_FACTION", {"npc_a": "yamen"})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_no_change_when_idle_and_good_rep(self):
        from backend.systems.npc_state import update_npc_state_dynamic
        p = make_player()
        p.npc_states = {"npc_a": "idle"}
        p.reputation = {"yamen": 10}
        result = update_npc_state_dynamic(p, "npc_a")
        assert result is None

    @patch("backend.systems.npc_state.NPCS", {"npc_a": {"always": True}})
    def test_always_npc_returns_none(self):
        from backend.systems.npc_state import update_npc_state_dynamic
        p = make_player()
        p.npc_states = {}
        result = update_npc_state_dynamic(p, "npc_a")
        assert result is None

    @patch("backend.systems.npc_state.NPCS", {"npc_a": {"hidden": True}})
    def test_hidden_npc_returns_none(self):
        from backend.systems.npc_state import update_npc_state_dynamic
        p = make_player()
        p.npc_states = {}
        result = update_npc_state_dynamic(p, "npc_a")
        assert result is None

    @patch("backend.systems.npc_state.NPC_FACTION", {"npc_a": None})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_no_faction_uses_zero_rep(self):
        from backend.systems.npc_state import update_npc_state_dynamic
        p = make_player()
        p.npc_states = {"npc_a": "idle"}
        p.reputation = {}
        result = update_npc_state_dynamic(p, "npc_a")
        assert result is None

    def test_creates_npc_states_if_missing(self):
        from backend.systems.npc_state import update_npc_state_dynamic
        p = make_player()
        p.npc_states = None
        with patch("backend.systems.npc_state.NPCS", {"npc_a": {"always": True}}):
            result = update_npc_state_dynamic(p, "npc_a")
        assert isinstance(p.npc_states, dict)

    @patch("backend.systems.npc_state.NPC_FACTION", {"npc_a": "yamen"})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_same_state_no_return(self):
        from backend.systems.npc_state import update_npc_state_dynamic
        p = make_player()
        p.npc_states = {"npc_a": "hostile"}
        p.reputation = {"yamen": -30}
        result = update_npc_state_dynamic(p, "npc_a")
        assert result is None
        assert p.npc_states["npc_a"] == "hostile"

    @patch("backend.systems.npc_state.NPC_FACTION", {"npc_a": "yamen"})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_busy_state_unchanged_with_good_rep(self):
        from backend.systems.npc_state import update_npc_state_dynamic
        p = make_player()
        p.npc_states = {"npc_a": "busy"}
        p.reputation = {"yamen": 10}
        result = update_npc_state_dynamic(p, "npc_a")
        assert result is None
        assert p.npc_states["npc_a"] == "busy"

    @patch("backend.systems.npc_state.NPC_FACTION", {"npc_a": "yamen"})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_hostile_takes_priority_over_alert(self):
        from backend.systems.npc_state import update_npc_state_dynamic
        p = make_player()
        p.npc_states = {"npc_a": "idle"}
        p.reputation = {"yamen": -30}
        p.favor = {"npc_a": -10}
        result = update_npc_state_dynamic(p, "npc_a")
        assert result == "hostile"

    @patch("backend.systems.npc_state.NPC_FACTION", {"npc_a": "yamen"})
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_alert_threshold_boundary(self):
        from backend.systems.npc_state import update_npc_state_dynamic
        p = make_player()
        p.npc_states = {"npc_a": "idle"}
        p.reputation = {"yamen": -8}
        result = update_npc_state_dynamic(p, "npc_a")
        assert result == "alert"


class TestUpdateAllNpcStatesDynamic:
    @patch("backend.systems.npc_state.update_npc_state_dynamic", return_value="hostile")
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}, "npc_b": {}})
    def test_collects_all_changes(self, mock_dynamic):
        from backend.systems.npc_state import update_all_npc_states_dynamic
        p = make_player()
        p.npc_states = {"npc_a": "idle", "npc_b": "idle"}
        changes = update_all_npc_states_dynamic(p)
        assert "npc_a" in changes
        assert "npc_b" in changes
        assert "idle→hostile" in changes["npc_a"]

    @patch("backend.systems.npc_state.update_npc_state_dynamic", return_value=None)
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_no_changes_when_none_returned(self, mock_dynamic):
        from backend.systems.npc_state import update_all_npc_states_dynamic
        p = make_player()
        p.npc_states = {"npc_a": "idle"}
        changes = update_all_npc_states_dynamic(p)
        assert changes == {}

    @patch("backend.systems.npc_state.update_npc_state_dynamic", return_value="alert")
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {"always": True}, "npc_b": {}})
    def test_skips_always_npc(self, mock_dynamic):
        from backend.systems.npc_state import update_all_npc_states_dynamic
        p = make_player()
        p.npc_states = {"npc_a": "idle", "npc_b": "idle"}
        changes = update_all_npc_states_dynamic(p)
        assert "npc_a" not in changes
        assert "npc_b" in changes

    @patch("backend.systems.npc_state.update_npc_state_dynamic", return_value="alert")
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {"hidden": True}, "npc_b": {}})
    def test_skips_hidden_npc(self, mock_dynamic):
        from backend.systems.npc_state import update_all_npc_states_dynamic
        p = make_player()
        p.npc_states = {"npc_a": "idle", "npc_b": "idle"}
        changes = update_all_npc_states_dynamic(p)
        assert "npc_a" not in changes
        assert "npc_b" in changes

    @patch("backend.systems.npc_state.update_npc_state_dynamic", return_value="hostile")
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}})
    def test_default_old_state_is_idle(self, mock_dynamic):
        from backend.systems.npc_state import update_all_npc_states_dynamic
        p = make_player()
        changes = update_all_npc_states_dynamic(p)
        assert changes["npc_a"] == "idle→hostile"

    @patch("backend.systems.npc_state.update_npc_state_dynamic", return_value="alert")
    @patch("backend.systems.npc_state.NPCS", {"npc_a": {}, "npc_b": {}})
    def test_multiple_npcs(self, mock_dynamic):
        from backend.systems.npc_state import update_all_npc_states_dynamic
        p = make_player()
        p.npc_states = {"npc_a": "idle", "npc_b": "hostile"}
        changes = update_all_npc_states_dynamic(p)
        assert len(changes) == 2
        assert changes["npc_a"] == "idle→alert"
        assert changes["npc_b"] == "hostile→alert"


class TestNpcStateForDialogue:
    @patch("backend.systems.npc_state.is_night", return_value=False)
    def test_idle_state_returns_empty(self, mock_night):
        from backend.systems.npc_state import npc_state_for_dialogue
        p = make_player()
        p.npc_states = {"npc_a": "idle"}
        result = npc_state_for_dialogue(p, "npc_a")
        assert result == ""

    @patch("backend.systems.npc_state.is_night", return_value=False)
    def test_resting_state_day(self, mock_night):
        from backend.systems.npc_state import npc_state_for_dialogue
        p = make_player()
        p.npc_states = {"npc_a": "resting"}
        result = npc_state_for_dialogue(p, "npc_a")
        assert "你现在状态" in result
        assert "憩" in result
        assert "困倦" in result

    @patch("backend.systems.npc_state.is_night", return_value=True)
    def test_resting_state_night(self, mock_night):
        from backend.systems.npc_state import npc_state_for_dialogue
        p = make_player()
        p.npc_states = {"npc_a": "resting"}
        result = npc_state_for_dialogue(p, "npc_a")
        assert "火气" in result

    @patch("backend.systems.npc_state.is_night", return_value=False)
    def test_busy_state(self, mock_night):
        from backend.systems.npc_state import npc_state_for_dialogue
        p = make_player()
        p.npc_states = {"npc_a": "busy"}
        result = npc_state_for_dialogue(p, "npc_a")
        assert "忙" in result
        assert "急促" in result

    @patch("backend.systems.npc_state.is_night", return_value=False)
    def test_alert_state(self, mock_night):
        from backend.systems.npc_state import npc_state_for_dialogue
        p = make_player()
        p.npc_states = {"npc_a": "alert"}
        result = npc_state_for_dialogue(p, "npc_a")
        assert "警" in result
        assert "谨慎" in result

    @patch("backend.systems.npc_state.is_night", return_value=False)
    def test_hostile_state(self, mock_night):
        from backend.systems.npc_state import npc_state_for_dialogue
        p = make_player()
        p.npc_states = {"npc_a": "hostile"}
        result = npc_state_for_dialogue(p, "npc_a")
        assert "敌" in result
        assert "带刺" in result

    @patch("backend.systems.npc_state.is_night", return_value=False)
    def test_traveling_state(self, mock_night):
        from backend.systems.npc_state import npc_state_for_dialogue
        p = make_player()
        p.npc_states = {"npc_a": "traveling"}
        result = npc_state_for_dialogue(p, "npc_a")
        assert "行" in result
        assert "赶路" in result

    @patch("backend.systems.npc_state.is_night", return_value=False)
    def test_unknown_state_returns_empty(self, mock_night):
        from backend.systems.npc_state import npc_state_for_dialogue
        p = make_player()
        p.npc_states = {"npc_a": "unknown_state"}
        result = npc_state_for_dialogue(p, "npc_a")
        assert result == ""

    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.npc_state.NPC_FACTION", {"npc_a": "yamen"})
    @patch("backend.systems.npc_state.FACTIONS", {"yamen": "衙门"})
    def test_hostile_with_low_rep_shows_reason(self, mock_night):
        from backend.systems.npc_state import npc_state_for_dialogue
        p = make_player()
        p.npc_states = {"npc_a": "hostile"}
        p.reputation = {"yamen": -30}
        result = npc_state_for_dialogue(p, "npc_a")
        assert "衙门" in result
        assert "声名狼藉" in result

    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.npc_state.NPC_FACTION", {"npc_a": "yamen"})
    @patch("backend.systems.npc_state.FACTIONS", {"yamen": "衙门"})
    def test_alert_with_low_rep_shows_reason(self, mock_night):
        from backend.systems.npc_state import npc_state_for_dialogue
        p = make_player()
        p.npc_states = {"npc_a": "alert"}
        p.reputation = {"yamen": -10}
        result = npc_state_for_dialogue(p, "npc_a")
        assert "衙门" in result
        assert "名声不佳" in result

    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.npc_state.NPC_FACTION", {"npc_a": None})
    def test_hostile_with_low_favor_shows_reason(self, mock_night):
        from backend.systems.npc_state import npc_state_for_dialogue
        p = make_player()
        p.npc_states = {"npc_a": "hostile"}
        p.favor = {"npc_a": -35}
        result = npc_state_for_dialogue(p, "npc_a")
        assert "旧怨极深" in result

    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.npc_state.NPC_FACTION", {"npc_a": None})
    def test_alert_with_low_favor_shows_reason(self, mock_night):
        from backend.systems.npc_state import npc_state_for_dialogue
        p = make_player()
        p.npc_states = {"npc_a": "alert"}
        p.favor = {"npc_a": -10}
        result = npc_state_for_dialogue(p, "npc_a")
        assert "过节" in result

    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.npc_state.NPC_FACTION", {"npc_a": "yamen"})
    @patch("backend.systems.npc_state.FACTIONS", {"yamen": "衙门"})
    def test_hostile_no_reason_when_rep_good(self, mock_night):
        from backend.systems.npc_state import npc_state_for_dialogue
        p = make_player()
        p.npc_states = {"npc_a": "hostile"}
        p.reputation = {"yamen": 50}
        p.favor = {"npc_a": 50}
        result = npc_state_for_dialogue(p, "npc_a")
        assert "声名狼藉" not in result
        assert "旧怨" not in result

    @patch("backend.systems.npc_state.is_night", return_value=False)
    def test_output_contains_state_header(self, mock_night):
        from backend.systems.npc_state import npc_state_for_dialogue
        p = make_player()
        p.npc_states = {"npc_a": "busy"}
        result = npc_state_for_dialogue(p, "npc_a")
        assert "【你现在状态】" in result

    @patch("backend.systems.npc_state.is_night", return_value=False)
    def test_output_contains_no_repeat_instruction(self, mock_night):
        from backend.systems.npc_state import npc_state_for_dialogue
        p = make_player()
        p.npc_states = {"npc_a": "busy"}
        result = npc_state_for_dialogue(p, "npc_a")
        assert "不要复述" in result

    @patch("backend.systems.npc_state.is_night", return_value=False)
    def test_missing_npc_states_attr(self, mock_night):
        from backend.systems.npc_state import npc_state_for_dialogue
        p = make_player()
        del p.npc_states
        result = npc_state_for_dialogue(p, "npc_a")
        assert result == ""

    @patch("backend.systems.npc_state.is_night", return_value=False)
    @patch("backend.systems.npc_state.NPC_FACTION", {"npc_a": "yamen"})
    @patch("backend.systems.npc_state.FACTIONS", {"yamen": "衙门"})
    def test_hostile_both_rep_and_favor_reasons(self, mock_night):
        from backend.systems.npc_state import npc_state_for_dialogue
        p = make_player()
        p.npc_states = {"npc_a": "hostile"}
        p.reputation = {"yamen": -30}
        p.favor = {"npc_a": -35}
        result = npc_state_for_dialogue(p, "npc_a")
        assert "声名狼藉" in result
        assert "旧怨极深" in result

    @patch("backend.systems.npc_state.is_night", return_value=False)
    def test_state_uses_npc_state_label_and_icon(self, mock_night):
        from backend.systems.npc_state import npc_state_for_dialogue
        p = make_player()
        p.npc_states = {"npc_a": "resting"}
        result = npc_state_for_dialogue(p, "npc_a")
        assert "💤" in result
        assert "憩" in result


class TestNpcWeatherAwarenessBlock:
    def test_known_weather_returns_block(self):
        from backend.systems.npc_state import npc_weather_awareness_block
        p = make_player(weather="骤雨")
        result = npc_weather_awareness_block(p)
        assert "天气影响" in result
        assert "瓢泼大雨" in result

    def test_unknown_weather_returns_empty(self):
        from backend.systems.npc_state import npc_weather_awareness_block
        p = make_player(weather="晴")
        result = npc_weather_awareness_block(p)
        assert result == ""

    def test_heavy_rain_night(self):
        from backend.systems.npc_state import npc_weather_awareness_block
        p = make_player(weather="骤雨", world_shichen=0)
        result = npc_weather_awareness_block(p)
        assert "夜雨" in result

    def test_heavy_rain_day(self):
        from backend.systems.npc_state import npc_weather_awareness_block
        p = make_player(weather="骤雨", world_shichen=4)
        result = npc_weather_awareness_block(p)
        assert "夜雨" not in result

    def test_wet_miasma(self):
        from backend.systems.npc_state import npc_weather_awareness_block
        p = make_player(weather="湿瘴")
        result = npc_weather_awareness_block(p)
        assert "湿" in result
        assert "闷" in result

    def test_heavy_fog(self):
        from backend.systems.npc_state import npc_weather_awareness_block
        p = make_player(weather="重雾")
        result = npc_weather_awareness_block(p)
        assert "浓雾" in result
        assert "警觉" in result

    def test_thin_fog(self):
        from backend.systems.npc_state import npc_weather_awareness_block
        p = make_player(weather="薄雾")
        result = npc_weather_awareness_block(p)
        assert "薄雾" in result

    def test_strong_wind(self):
        from backend.systems.npc_state import npc_weather_awareness_block
        p = make_player(weather="风急")
        result = npc_weather_awareness_block(p)
        assert "风" in result

    def test_cold_dew(self):
        from backend.systems.npc_state import npc_weather_awareness_block
        p = make_player(weather="寒露")
        result = npc_weather_awareness_block(p)
        assert "露" in result
        assert "冷" in result

    def test_night_frost(self):
        from backend.systems.npc_state import npc_weather_awareness_block
        p = make_player(weather="夜霜")
        result = npc_weather_awareness_block(p)
        assert "霜" in result

    def test_muggy(self):
        from backend.systems.npc_state import npc_weather_awareness_block
        p = make_player(weather="闷热")
        result = npc_weather_awareness_block(p)
        assert "闷热" in result
        assert "烦躁" in result

    def test_output_format(self):
        from backend.systems.npc_state import npc_weather_awareness_block
        p = make_player(weather="骤雨")
        result = npc_weather_awareness_block(p)
        assert result.startswith("【此时天气影响你的举止】")
        assert "不要原句宣告天气" in result

    def test_neutral_weather_returns_empty(self):
        from backend.systems.npc_state import npc_weather_awareness_block
        for w in ("薄阴", "云遮日", "小风"):
            p = make_player(weather=w)
            result = npc_weather_awareness_block(p)
            assert result == ""
