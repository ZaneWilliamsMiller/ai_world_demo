import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.systems.perception import (
    can_rest_at,
    danger_sense_narrative,
    perception_scan,
    relevant_events_for,
    val_in_range,
    world_status_block,
)

from conftest import make_player


class TestPerceptionScan(unittest.TestCase):
    def _make_map(self, center_ch, surround_chars):
        row = list(surround_chars)
        cx = len(row) // 2
        row.insert(cx, center_ch)
        return {"world": {"rows": ["".join(row)]}}

    @patch("backend.systems.perception.is_dangerous", return_value=False)
    @patch("backend.systems.perception.MAPS", {"world": {"rows": [".....", ".....", "..T..", ".....", "....."]}})
    def test_no_danger_returns_none(self, mock_danger):
        p = make_player(px=2, py=2, weather="薄阴", spirit=80)
        result = perception_scan(p)
        self.assertIsNone(result)

    @patch("backend.systems.perception.is_dangerous", return_value=True)
    @patch("backend.systems.perception.MAPS", {"world": {"rows": ["~.!.","..T..","..@..","..^..","....."]}})
    def test_has_danger_returns_result(self, mock_danger):
        p = make_player(px=2, py=2, weather="薄阴", spirit=80)
        result = perception_scan(p)
        self.assertIsNotNone(result)
        self.assertIn("warnings", result)
        self.assertGreater(len(result["warnings"]), 0)

    @patch("backend.systems.perception.is_dangerous", return_value=True)
    @patch("backend.systems.perception.MAPS", {"world": {"rows": ["~.!.","..T..","..@..","..^..","....."]}})
    def test_fog_reduces_radius(self, mock_danger):
        p_clear = make_player(px=2, py=2, weather="薄阴", spirit=80)
        p_fog = make_player(px=2, py=2, weather="重雾", spirit=80)
        result_clear = perception_scan(p_clear)
        result_fog = perception_scan(p_fog)
        self.assertIsNotNone(result_clear)
        self.assertIsNotNone(result_fog)
        self.assertTrue(result_fog["weather_penalty"])
        self.assertLessEqual(result_fog["radius"], result_clear["radius"])

    @patch("backend.systems.perception.is_dangerous", return_value=True)
    @patch("backend.systems.perception.MAPS", {"world": {"rows": ["~.!.","..T..","..@..","..^..","....."]}})
    def test_low_spirit_reduces_radius(self, mock_danger):
        p_high = make_player(px=2, py=2, weather="薄阴", spirit=80)
        p_low = make_player(px=2, py=2, weather="薄阴", spirit=20)
        result_high = perception_scan(p_high)
        result_low = perception_scan(p_low)
        self.assertIsNotNone(result_low)
        self.assertTrue(result_low["spirit_penalty"])
        self.assertLessEqual(result_low["radius"], result_high["radius"])

    @patch("backend.systems.perception.MAPS", {})
    def test_no_map_returns_none(self):
        p = make_player(map_id="nonexistent", px=2, py=2)
        result = perception_scan(p)
        self.assertIsNone(result)

    @patch("backend.systems.perception.is_dangerous", return_value=False)
    @patch("backend.systems.perception.MAPS", {"world": {"rows": ["..&..", "..T..", "..I..", ".....", "....."]}})
    def test_suspicion_tiles_nearby(self, mock_danger):
        p = make_player(px=2, py=2, weather="薄阴", spirit=80)
        result = perception_scan(p)
        if result is not None:
            self.assertIn("suspicions", result)

    @patch("backend.systems.perception.is_dangerous", return_value=True)
    @patch("backend.systems.perception.MAPS", {"world": {"rows": ["~.!.","..T..","..@..","..^..","....."]}})
    def test_fog_and_low_spirit_minimum_radius(self, mock_danger):
        p = make_player(px=2, py=2, weather="重雾", spirit=10)
        result = perception_scan(p)
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result["radius"], 1)


class TestDangerSenseNarrative(unittest.TestCase):
    def test_empty_scan_returns_empty(self):
        p = make_player()
        result = danger_sense_narrative(p, None)
        self.assertEqual(result, "")

    def test_scan_with_warnings_returns_text(self):
        p = make_player()
        scan = {
            "warnings": [{"x": 3, "y": 2, "dist": 1, "danger": "水声诡谲，似有暗流"}],
            "suspicions": [],
        }
        result = danger_sense_narrative(p, scan)
        self.assertNotEqual(result, "")
        self.assertIn("水声诡谲", result)

    def test_scan_with_suspicions_returns_text(self):
        p = make_player()
        scan = {
            "warnings": [],
            "suspicions": [{"x": 3, "y": 2, "dist": 1, "note": "草丛深处似有动静"}],
        }
        result = danger_sense_narrative(p, scan)
        self.assertNotEqual(result, "")
        self.assertIn("草丛深处似有动静", result)

    def test_nearby_warning_wording(self):
        p = make_player()
        scan = {
            "warnings": [{"x": 3, "y": 2, "dist": 1, "danger": "水声诡谲，似有暗流"}],
            "suspicions": [],
        }
        result = danger_sense_narrative(p, scan)
        self.assertIn("近旁", result)

    def test_medium_dist_warning_wording(self):
        p = make_player()
        scan = {
            "warnings": [{"x": 4, "y": 2, "dist": 2, "danger": "水声诡谲，似有暗流"}],
            "suspicions": [],
        }
        result = danger_sense_narrative(p, scan)
        self.assertIn("左近", result)

    def test_far_dist_warning_wording(self):
        p = make_player()
        scan = {
            "warnings": [{"x": 5, "y": 2, "dist": 3, "danger": "水声诡谲，似有暗流"}],
            "suspicions": [],
        }
        result = danger_sense_narrative(p, scan)
        self.assertIn("远处", result)

    def test_empty_warnings_and_suspicions_returns_empty(self):
        p = make_player()
        scan = {"warnings": [], "suspicions": []}
        result = danger_sense_narrative(p, scan)
        self.assertEqual(result, "")


class TestCanRestAt(unittest.TestCase):
    @patch("backend.systems.perception.tile_at", return_value="T")
    def test_inn_can_rest(self, mock_tile):
        p = make_player()
        can, msg = can_rest_at(p)
        self.assertTrue(can)
        self.assertEqual(msg, "客栈")

    @patch("backend.systems.perception.tile_at", return_value="@")
    def test_temple_can_rest(self, mock_tile):
        p = make_player()
        can, msg = can_rest_at(p)
        self.assertTrue(can)
        self.assertEqual(msg, "佛寺")

    @patch("backend.systems.perception.tile_at", return_value="I")
    def test_black_shop_cannot_rest(self, mock_tile):
        p = make_player()
        can, msg = can_rest_at(p)
        self.assertFalse(can)
        self.assertIn("黑店", msg)

    @patch("backend.systems.perception.MAPS", {"world": {"rows": [".....", "..T..", ".....", ".....", "....."]}})
    @patch("backend.systems.perception.tile_at", return_value=".")
    def test_plain_tile_cannot_rest(self, mock_tile):
        p = make_player(px=2, py=2)
        can, msg = can_rest_at(p)
        self.assertFalse(can)
        self.assertIn("无歇脚之所", msg)

    @patch("backend.systems.perception.tile_at", return_value="Y")
    def test_station_can_rest(self, mock_tile):
        p = make_player()
        can, msg = can_rest_at(p)
        self.assertTrue(can)
        self.assertEqual(msg, "驿站")

    @patch("backend.systems.perception.tile_at", return_value="M")
    def test_market_can_rest(self, mock_tile):
        p = make_player()
        can, msg = can_rest_at(p)
        self.assertTrue(can)
        self.assertEqual(msg, "市集")

    @patch("backend.systems.perception.tile_at", return_value="B")
    def test_barracks_can_rest(self, mock_tile):
        p = make_player()
        can, msg = can_rest_at(p)
        self.assertTrue(can)
        self.assertEqual(msg, "兵站")


class TestValInRange(unittest.TestCase):
    def test_value_in_range(self):
        self.assertTrue(val_in_range(5, 1, 10))

    def test_value_at_lower_bound(self):
        self.assertTrue(val_in_range(1, 1, 10))

    def test_value_at_upper_bound(self):
        self.assertTrue(val_in_range(10, 1, 10))

    def test_value_below_range(self):
        self.assertFalse(val_in_range(0, 1, 10))

    def test_value_above_range(self):
        self.assertFalse(val_in_range(11, 1, 10))

    def test_single_value_range(self):
        self.assertTrue(val_in_range(5, 5, 5))

    def test_negative_range(self):
        self.assertTrue(val_in_range(-3, -5, -1))


class TestWorldStatusBlock(unittest.TestCase):
    @patch("backend.systems.perception.is_night", return_value=False)
    @patch("backend.systems.perception.shichen_phase", return_value="晨")
    @patch("backend.systems.perception.shichen_name", return_value="辰时")
    def test_basic_output(self, mock_name, mock_phase, mock_night):
        p = make_player(world_day=3, world_shichen=4, weather="薄阴", coins=50)
        result = world_status_block(p)
        self.assertIn("世态此刻", result)
        self.assertIn("第 3 日", result)
        self.assertIn("辰时", result)
        self.assertIn("薄阴", result)
        self.assertIn("50 文", result)

    @patch("backend.systems.perception.is_night", return_value=True)
    @patch("backend.systems.perception.shichen_phase", return_value="夜")
    @patch("backend.systems.perception.shichen_name", return_value="子时")
    def test_night_marker(self, mock_name, mock_phase, mock_night):
        p = make_player(world_shichen=0)
        result = world_status_block(p)
        self.assertIn("(夜)", result)

    @patch("backend.systems.perception.is_night", return_value=False)
    @patch("backend.systems.perception.shichen_phase", return_value="晨")
    @patch("backend.systems.perception.shichen_name", return_value="辰时")
    def test_empty_inventory(self, mock_name, mock_phase, mock_night):
        p = make_player(inventory={})
        result = world_status_block(p)
        self.assertIn("身无长物", result)

    @patch("backend.systems.perception.is_night", return_value=False)
    @patch("backend.systems.perception.shichen_phase", return_value="晨")
    @patch("backend.systems.perception.shichen_name", return_value="辰时")
    def test_with_inventory(self, mock_name, mock_phase, mock_night):
        p = make_player(inventory={"干粮": 2, "金创药": 1})
        result = world_status_block(p)
        self.assertIn("干粮", result)
        self.assertIn("金创药", result)

    @patch("backend.systems.perception.is_night", return_value=False)
    @patch("backend.systems.perception.shichen_phase", return_value="晨")
    @patch("backend.systems.perception.shichen_name", return_value="辰时")
    def test_with_reputation(self, mock_name, mock_phase, mock_night):
        p = make_player(reputation={"lulin": 10, "caobang": -5})
        result = world_status_block(p)
        self.assertIn("声望", result)
        self.assertIn("绿林", result)


class TestRelevantEventsFor(unittest.TestCase):
    def test_empty_events_returns_empty(self):
        p = make_player(events=[])
        result = relevant_events_for(p, "zhanggui")
        self.assertEqual(result, [])

    def test_returns_up_to_k_events(self):
        events = [{"text": f"事件{i}", "shichen": i} for i in range(10)]
        p = make_player(events=events)
        result = relevant_events_for(p, "zhanggui", k=4)
        self.assertLessEqual(len(result), 4)

    def test_jiang_returns_all_within_k(self):
        events = [{"text": f"事件{i}", "shichen": i} for i in range(6)]
        p = make_player(events=events)
        result = relevant_events_for(p, "jiang", k=4)
        self.assertEqual(len(result), 4)

    @patch("backend.systems.perception.NPC_FACTION", {"biaotou": "biaoju"})
    @patch("backend.systems.perception.NPCS", {"biaotou": {"cell": ("world", 10, 10)}})
    def test_faction_priority_events(self):
        events = [
            {"text": "镖局事务", "shichen": 1, "actor": "镖局"},
            {"text": "无关事件", "shichen": 2, "actor": "路人"},
            {"text": "镖局再报", "shichen": 3, "actor": "镖局"},
            {"text": "闲事", "shichen": 4, "actor": "闲人"},
        ]
        p = make_player(events=events)
        result = relevant_events_for(p, "biaotou", k=4)
        actors = [e.get("actor", "") for e in result]
        biaoju_count = sum(1 for a in actors if "镖局" in a)
        self.assertGreater(biaoju_count, 0)

    @patch("backend.systems.perception.NPC_FACTION", {"yaren": "yamen"})
    @patch("backend.systems.perception.NPCS", {"yaren": {"cell": ("world", 5, 5)}})
    def test_no_matching_faction_still_returns_events(self):
        events = [
            {"text": "闲事一", "shichen": 1, "actor": "路人"},
            {"text": "闲事二", "shichen": 2, "actor": "闲人"},
        ]
        p = make_player(events=events)
        result = relevant_events_for(p, "yaren", k=4)
        self.assertGreater(len(result), 0)


if __name__ == "__main__":
    unittest.main()
