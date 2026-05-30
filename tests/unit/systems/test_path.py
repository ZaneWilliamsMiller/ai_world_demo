# pyright: reportCallIssue=false
"""离线单元测试 — pathfinding / perception / time_weather"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from conftest import make_player


class TestPathfinding:
    def test_grid_size(self):
        from backend.systems.pathfinding import grid_size
        rows = ["abc", "def", "ghi"]
        assert grid_size(rows) == (3, 3)

    def test_grid_size_empty(self):
        from backend.systems.pathfinding import grid_size
        assert grid_size([]) == (0, 0)

    def test_grid_size_single_row(self):
        from backend.systems.pathfinding import grid_size
        assert grid_size(["hello"]) == (5, 1)

    def test_is_passable(self):
        from backend.systems.pathfinding import is_passable
        assert is_passable("#") is True
        assert is_passable(".") is True
        assert is_passable("~") is True

    def test_walkable(self):
        from backend.systems.pathfinding import walkable
        assert walkable("#") is True
        assert walkable(".") is True

    def test_tile_cost_known(self):
        from backend.systems.pathfinding import tile_cost
        assert tile_cost(".") == 1
        assert tile_cost(",") == 1
        assert tile_cost("=") == 2
        assert tile_cost("~") == 4
        assert tile_cost("!") == 8
        assert tile_cost("@") == 5
        assert tile_cost(";") == 3
        assert tile_cost("#") == 99
        assert tile_cost("^") == 99

    def test_tile_cost_unknown_defaults_to_1(self):
        from backend.systems.pathfinding import tile_cost
        assert tile_cost("Z") == 1
        assert tile_cost("?") == 1

    def test_tile_elevation_known(self):
        from backend.systems.pathfinding import tile_elevation
        assert tile_elevation("#") == 99
        assert tile_elevation("^") == 9
        assert tile_elevation("=") == 1
        assert tile_elevation("~") == 1
        assert tile_elevation("!") == 99
        assert tile_elevation("@") == 5
        assert tile_elevation("m") == 7
        assert tile_elevation("/") == 6
        assert tile_elevation("F") == 4
        assert tile_elevation(";") == 3
        assert tile_elevation(",") == 2
        assert tile_elevation(".") == 2

    def test_tile_elevation_unknown_defaults_to_2(self):
        from backend.systems.pathfinding import tile_elevation
        assert tile_elevation("Z") == 2
        assert tile_elevation("?") == 2

    def test_is_dangerous_true(self):
        from backend.systems.pathfinding import is_dangerous
        for ch in ("~", "!", "@", "^"):
            assert is_dangerous(ch) is True

    def test_is_dangerous_false(self):
        from backend.systems.pathfinding import is_dangerous
        for ch in (".", ",", "T", "M", "#", "F", "&", "I"):
            assert is_dangerous(ch) is False

    def test_danger_injury_chance_dangerous(self):
        from backend.systems.pathfinding import danger_injury_chance
        assert danger_injury_chance("~") == 0.25
        assert danger_injury_chance("!") == 0.50
        assert danger_injury_chance("@") == 0.20
        assert danger_injury_chance("^") == 0.35

    def test_danger_injury_chance_safe(self):
        from backend.systems.pathfinding import danger_injury_chance
        assert danger_injury_chance(".") == 0.0
        assert danger_injury_chance("T") == 0.0
        assert danger_injury_chance("Z") == 0.0

    def test_can_step_between_flat(self):
        from backend.systems.pathfinding import can_step_between
        assert can_step_between(".", ",") is True

    def test_can_step_within_limit(self):
        from backend.systems.pathfinding import can_step_between
        assert can_step_between(".", ",") is True
        assert can_step_between(",", ";") is True

    def test_can_step_exceeds_limit(self):
        from backend.systems.pathfinding import can_step_between
        assert can_step_between(".", "^") is False

    def test_can_step_allow_steep(self):
        from backend.systems.pathfinding import can_step_between
        assert can_step_between(".", "^", allow_steep=True) is True

    def test_tile_at_valid(self):
        from backend.systems.pathfinding import invalidate_path_cache, tile_at
        invalidate_path_cache()
        mock_maps = {"test_map": {"rows": ["abc", "def"]}}
        with patch("backend.systems.pathfinding.MAPS", mock_maps):
            assert tile_at("test_map", 0, 0) == "a"
            assert tile_at("test_map", 2, 1) == "f"
            assert tile_at("test_map", 1, 0) == "b"

    def test_tile_at_out_of_bounds(self):
        from backend.systems.pathfinding import tile_at
        mock_maps = {"test_map": {"rows": ["abc"]}}
        with patch("backend.systems.pathfinding.MAPS", mock_maps):
            assert tile_at("test_map", 5, 0) is None
            assert tile_at("test_map", 0, 5) is None
            assert tile_at("test_map", -1, 0) is None

    def test_tile_at_unknown_map(self):
        from backend.systems.pathfinding import tile_at
        with patch("backend.systems.pathfinding.MAPS", {}):
            assert tile_at("nonexistent", 0, 0) is None

    def test_find_path_same_point(self):
        from backend.systems.pathfinding import find_path, invalidate_path_cache
        invalidate_path_cache()
        mock_maps = {"test_map": {"rows": ["..."]}}
        with patch("backend.systems.pathfinding.MAPS", mock_maps):
            result = find_path("test_map", 0, 0, 0, 0)
            assert result == [(0, 0)]

    def test_find_path_simple(self):
        from backend.systems.pathfinding import find_path, invalidate_path_cache
        invalidate_path_cache()
        rows = ["..."]
        mock_maps = {"test_map": {"rows": rows}}
        with patch("backend.systems.pathfinding.MAPS", mock_maps):
            result = find_path("test_map", 0, 0, 2, 0)
            assert result is not None
            assert result[0] == (0, 0)
            assert result[-1] == (2, 0)

    def test_find_path_unknown_map(self):
        from backend.systems.pathfinding import find_path, invalidate_path_cache
        invalidate_path_cache()
        with patch("backend.systems.pathfinding.MAPS", {}):
            assert find_path("no_map", 0, 0, 1, 0) is None

    def test_find_path_out_of_bounds(self):
        from backend.systems.pathfinding import find_path, invalidate_path_cache
        invalidate_path_cache()
        mock_maps = {"test_map": {"rows": ["..."]}}
        with patch("backend.systems.pathfinding.MAPS", mock_maps):
            assert find_path("test_map", 0, 0, 10, 10) is None

    def test_path_cost(self):
        from backend.systems.pathfinding import path_cost
        mock_maps = {"test_map": {"rows": ["...", ",.,"]}}
        with patch("backend.systems.pathfinding.MAPS", mock_maps):
            cost = path_cost("test_map", [(0, 0), (1, 0), (2, 0)])
            assert cost == 3

    def test_path_cost_unknown_map(self):
        from backend.systems.pathfinding import path_cost
        with patch("backend.systems.pathfinding.MAPS", {}):
            assert path_cost("no_map", [(0, 0)]) == 0

    def test_cost_to_ticks(self):
        from backend.systems.pathfinding import cost_to_ticks
        assert cost_to_ticks(0) == 0
        assert cost_to_ticks(1) == 0
        assert cost_to_ticks(2) == 0
        assert cost_to_ticks(3) == 1
        assert cost_to_ticks(6) == 1
        assert cost_to_ticks(7) == 2
        assert cost_to_ticks(12) == 2
        assert cost_to_ticks(13) == 3
        assert cost_to_ticks(20) == 3
        assert cost_to_ticks(21) == 4
        assert cost_to_ticks(100) == 4

    def test_check_danger_and_injure_safe(self):
        from backend.systems.pathfinding import check_danger_and_injure
        injured, reason = check_danger_and_injure(".")
        assert injured is False
        assert reason is None

    def test_check_danger_and_injure_dangerous_no_injury(self):
        from backend.systems.pathfinding import check_danger_and_injure
        rng = MagicMock()
        rng.random.return_value = 0.99
        injured, reason = check_danger_and_injure("~", rng=rng)
        assert injured is False
        assert reason is None

    def test_check_danger_and_injure_dangerous_injury(self):
        from backend.systems.pathfinding import check_danger_and_injure
        rng = MagicMock()
        rng.random.return_value = 0.01
        injured, reason = check_danger_and_injure("~", rng=rng)
        assert injured is True
        assert reason is not None
        assert "水" in reason

    def test_check_danger_and_injure_cliff(self):
        from backend.systems.pathfinding import check_danger_and_injure
        rng = MagicMock()
        rng.random.return_value = 0.01
        injured, reason = check_danger_and_injure("^", rng=rng)
        assert injured is True
        assert "悬崖" in (reason or "")

    def test_check_danger_and_injure_rubble(self):
        from backend.systems.pathfinding import check_danger_and_injure
        rng = MagicMock()
        rng.random.return_value = 0.01
        injured, reason = check_danger_and_injure("@", rng=rng)
        assert injured is True
        assert "废墟" in (reason or "")

    def test_check_danger_and_injure_fissure(self):
        from backend.systems.pathfinding import check_danger_and_injure
        rng = MagicMock()
        rng.random.return_value = 0.01
        injured, reason = check_danger_and_injure("!", rng=rng)
        assert injured is True
        assert "裂隙" in (reason or "")


class TestPerception:
    def test_val_in_range(self):
        from backend.systems.perception import val_in_range
        assert val_in_range(5, 1, 10) is True
        assert val_in_range(1, 1, 10) is True
        assert val_in_range(10, 1, 10) is True
        assert val_in_range(0, 1, 10) is False
        assert val_in_range(11, 1, 10) is False

    def test_can_rest_at_inn(self):
        from backend.systems.perception import can_rest_at
        p = make_player()
        mock_maps = {"world": {"rows": ["T"]}}
        with patch("backend.systems.perception.tile_at", return_value="T"):
            ok, mood = can_rest_at(p)
            assert ok is True
            assert mood == "客栈"

    def test_can_rest_at_temple(self):
        from backend.systems.perception import can_rest_at
        p = make_player()
        with patch("backend.systems.perception.tile_at", return_value="@"):
            ok, mood = can_rest_at(p)
            assert ok is True
            assert mood == "佛寺"

    def test_can_rest_at_post(self):
        from backend.systems.perception import can_rest_at
        p = make_player()
        with patch("backend.systems.perception.tile_at", return_value="Y"):
            ok, mood = can_rest_at(p)
            assert ok is True
            assert mood == "驿站"

    def test_can_rest_at_black_inn(self):
        from backend.systems.perception import can_rest_at
        p = make_player()
        with patch("backend.systems.perception.tile_at", return_value="I"):
            ok, mood = can_rest_at(p)
            assert ok is False
            assert "黑店" in mood

    def test_can_rest_at_plains(self):
        from backend.systems.perception import can_rest_at
        p = make_player()
        with patch("backend.systems.perception.tile_at", return_value="."):
            ok, mood = can_rest_at(p)
            assert ok is False
            assert "歇脚" in mood or "客栈" in mood

    def test_perception_scan_with_danger(self):
        from backend.systems.perception import perception_scan
        p = make_player(px=2, py=2, spirit=80)
        rows = [
            ".....",
            ".~...",
            ".....",
            ".....",
            ".....",
        ]
        mock_maps = {"world": {"rows": rows}}
        with patch("backend.systems.perception.MAPS", mock_maps):
            result = perception_scan(p)
            assert result is not None
            assert "warnings" in result
            assert len(result["warnings"]) > 0

    def test_perception_scan_no_danger(self):
        from backend.systems.perception import perception_scan
        p = make_player(px=2, py=2, spirit=80)
        rows = [
            ".....",
            ".....",
            ".....",
            ".....",
            ".....",
        ]
        mock_maps = {"world": {"rows": rows}}
        with patch("backend.systems.perception.MAPS", mock_maps):
            result = perception_scan(p)
            assert result is None

    def test_perception_scan_fog_reduces_radius(self):
        from backend.systems.perception import perception_scan
        p = make_player(px=2, py=2, spirit=80, weather="重雾")
        rows = [
            ".....",
            ".~...",
            ".....",
            ".....",
            ".....",
        ]
        mock_maps = {"world": {"rows": rows}}
        with patch("backend.systems.perception.MAPS", mock_maps):
            result = perception_scan(p)
            if result is not None:
                assert result["weather_penalty"] is True

    def test_perception_scan_low_spirit_reduces_radius(self):
        from backend.systems.perception import perception_scan
        p = make_player(px=2, py=2, spirit=20)
        rows = [
            ".....",
            ".~...",
            ".....",
            ".....",
            ".....",
        ]
        mock_maps = {"world": {"rows": rows}}
        with patch("backend.systems.perception.MAPS", mock_maps):
            result = perception_scan(p)
            if result is not None:
                assert result["spirit_penalty"] is True

    def test_perception_scan_unknown_map(self):
        from backend.systems.perception import perception_scan
        p = make_player()
        with patch("backend.systems.perception.MAPS", {}):
            result = perception_scan(p)
            assert result is None

    def test_danger_sense_narrative_none(self):
        from backend.systems.perception import danger_sense_narrative
        p = make_player()
        assert danger_sense_narrative(p, None) == ""

    def test_danger_sense_narrative_with_warnings(self):
        from backend.systems.perception import danger_sense_narrative
        p = make_player()
        scan = {
            "warnings": [{"x": 1, "y": 1, "dist": 1, "danger": "水声诡谲"}],
            "suspicions": [],
        }
        result = danger_sense_narrative(p, scan)
        assert "水声诡谲" in result
        assert "近旁" in result

    def test_danger_sense_narrative_far_warning(self):
        from backend.systems.perception import danger_sense_narrative
        p = make_player()
        scan = {
            "warnings": [{"x": 5, "y": 5, "dist": 3, "danger": "残垣断壁"}],
            "suspicions": [],
        }
        result = danger_sense_narrative(p, scan)
        assert "残垣断壁" in result
        assert "远处" in result

    def test_danger_sense_narrative_with_suspicion(self):
        from backend.systems.perception import danger_sense_narrative
        p = make_player()
        scan = {
            "warnings": [],
            "suspicions": [{"x": 1, "y": 1, "dist": 1, "note": "草丛深处似有动静"}],
        }
        result = danger_sense_narrative(p, scan)
        assert "草丛" in result

    def test_danger_sense_narrative_empty(self):
        from backend.systems.perception import danger_sense_narrative
        p = make_player()
        scan = {"warnings": [], "suspicions": []}
        assert danger_sense_narrative(p, scan) == ""

    def test_tile_forced_encounter_no_hidden(self):
        from backend.systems.perception import tile_forced_encounter
        p = make_player()
        with patch("backend.systems.perception.NPCS", {}):
            with patch("backend.systems.perception.tile_at", return_value="."):
                assert tile_forced_encounter(p) is None

    def test_tile_forced_encounter_hidden_match(self):
        from backend.systems.perception import tile_forced_encounter
        p = make_player(map_id="world", px=10, py=10)
        npcs = {
            "shadow": {
                "hidden": True,
                "cell": ("world", 10, 10),
                "encounter_user": "暗影乍现",
                "encounter_blurb": "夜袭",
            }
        }
        with patch("backend.systems.perception.NPCS", npcs):
            with patch("backend.systems.perception.tile_at", return_value="."):
                result = tile_forced_encounter(p)
                assert result is not None
                assert result["npc_id"] == "shadow"

    def test_tile_forced_encounter_wrong_position(self):
        from backend.systems.perception import tile_forced_encounter
        p = make_player(map_id="world", px=5, py=5)
        npcs = {
            "shadow": {
                "hidden": True,
                "cell": ("world", 10, 10),
            }
        }
        with patch("backend.systems.perception.NPCS", npcs):
            with patch("backend.systems.perception.tile_at", return_value="."):
                assert tile_forced_encounter(p) is None

    def test_tile_forced_encounter_triggers_on_tile_mismatch(self):
        from backend.systems.perception import tile_forced_encounter
        p = make_player(map_id="world", px=10, py=10)
        npcs = {
            "shadow": {
                "hidden": True,
                "cell": ("world", 10, 10),
                "triggers_on_tile": "~",
            }
        }
        with patch("backend.systems.perception.NPCS", npcs):
            with patch("backend.systems.perception.tile_at", return_value="."):
                assert tile_forced_encounter(p) is None

    def test_tile_forced_encounter_triggers_on_tile_match(self):
        from backend.systems.perception import tile_forced_encounter
        p = make_player(map_id="world", px=10, py=10)
        npcs = {
            "shadow": {
                "hidden": True,
                "cell": ("world", 10, 10),
                "triggers_on_tile": "~",
            }
        }
        with patch("backend.systems.perception.NPCS", npcs):
            with patch("backend.systems.perception.tile_at", return_value="~"):
                result = tile_forced_encounter(p)
                assert result is not None
                assert result["npc_id"] == "shadow"


class TestTimeWeather:
    def test_shichen_name_all(self):
        from backend.systems.time_weather import shichen_name
        expected = ("子时", "丑时", "寅时", "卯时", "辰时", "巳时",
                    "午时", "未时", "申时", "酉时", "戌时", "亥时")
        for i, name in enumerate(expected):
            assert shichen_name(i) == name

    def test_shichen_name_wraps(self):
        from backend.systems.time_weather import shichen_name
        assert shichen_name(12) == "子时"
        assert shichen_name(13) == "丑时"
        assert shichen_name(24) == "子时"

    def test_is_night_true(self):
        from backend.systems.time_weather import is_night
        for idx in (0, 1, 10, 11):
            assert is_night(idx) is True

    def test_is_night_false(self):
        from backend.systems.time_weather import is_night
        for idx in (2, 3, 4, 5, 6, 7, 8, 9):
            assert is_night(idx) is False

    def test_shichen_phase_deep_night(self):
        from backend.systems.time_weather import shichen_phase
        assert shichen_phase(0) == "深夜"
        assert shichen_phase(1) == "深夜"

    def test_shichen_phase_dawn(self):
        from backend.systems.time_weather import shichen_phase
        assert shichen_phase(2) == "凌晨"
        assert shichen_phase(3) == "凌晨"

    def test_shichen_phase_morning(self):
        from backend.systems.time_weather import shichen_phase
        assert shichen_phase(4) == "上午"
        assert shichen_phase(5) == "上午"

    def test_shichen_phase_noon(self):
        from backend.systems.time_weather import shichen_phase
        assert shichen_phase(6) == "正午"
        assert shichen_phase(7) == "正午"

    def test_shichen_phase_dusk(self):
        from backend.systems.time_weather import shichen_phase
        assert shichen_phase(8) == "傍晚"
        assert shichen_phase(9) == "傍晚"

    def test_shichen_phase_night(self):
        from backend.systems.time_weather import shichen_phase
        assert shichen_phase(10) == "夜里"
        assert shichen_phase(11) == "夜里"

    def test_advance_clock_basic(self):
        from backend.systems.time_weather import advance_clock
        p = make_player(world_shichen=4, world_tick=0, world_day=1)
        with patch("random.random", return_value=1.0):
            advance_clock(p, ticks=1)
        assert p.world_shichen == 5
        assert p.world_tick == 1
        assert p.world_day == 1

    def test_advance_clock_day_wrap(self):
        from backend.systems.time_weather import advance_clock
        p = make_player(world_shichen=11, world_tick=0, world_day=1)
        with patch("random.random", return_value=1.0):
            advance_clock(p, ticks=1)
        assert p.world_shichen == 0
        assert p.world_day == 2

    def test_advance_clock_zero_ticks(self):
        from backend.systems.time_weather import advance_clock
        p = make_player(world_shichen=4, world_tick=0)
        advance_clock(p, ticks=0)
        assert p.world_shichen == 4
        assert p.world_tick == 0

    def test_advance_clock_negative_ticks(self):
        from backend.systems.time_weather import advance_clock
        p = make_player(world_shichen=4, world_tick=0)
        advance_clock(p, ticks=-5)
        assert p.world_shichen == 4
        assert p.world_tick == 0

    def test_advance_clock_ticks_capped(self):
        from backend.systems.time_weather import advance_clock
        p = make_player(world_shichen=4, world_tick=0)
        with patch("random.random", return_value=1.0):
            advance_clock(p, ticks=100)
        assert p.world_tick <= 24

    def test_advance_clock_sleep_debt(self):
        from backend.systems.time_weather import advance_clock
        p = make_player(world_shichen=4, world_tick=0, sleep_debt=0)
        with patch("random.random", return_value=1.0):
            advance_clock(p, ticks=1)
        assert p.sleep_debt == 1

    def test_advance_clock_unconscious_ticks(self):
        from backend.systems.time_weather import advance_clock
        p = make_player(world_shichen=4, world_tick=0, unconscious_ticks=3)
        with patch("random.random", return_value=1.0):
            advance_clock(p, ticks=1)
        assert p.unconscious_ticks == 2
