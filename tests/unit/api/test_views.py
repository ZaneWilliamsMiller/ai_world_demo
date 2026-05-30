import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.api.views import _strip_private, build_init_response, maps_public, npcs_here, player_public

from conftest import make_player


class TestStripPrivate(unittest.TestCase):
    def test_removes_underscore_keys(self):
        data = {"_hidden": 1, "visible": 2}
        result = _strip_private(data)
        self.assertNotIn("_hidden", result)
        self.assertIn("visible", result)

    def test_nested_dict(self):
        data = {"outer": {"_inner": 1, "keep": 2}}
        result = _strip_private(data)
        self.assertNotIn("_inner", result["outer"])
        self.assertIn("keep", result["outer"])

    def test_list_of_dicts(self):
        data = [{"_a": 1, "b": 2}, {"_c": 3, "d": 4}]
        result = _strip_private(data)
        self.assertNotIn("_a", result[0])
        self.assertIn("b", result[0])
        self.assertNotIn("_c", result[1])
        self.assertIn("d", result[1])

    def test_non_dict_list_passthrough(self):
        self.assertEqual(_strip_private(42), 42)
        self.assertEqual(_strip_private("hello"), "hello")
        self.assertIsNone(_strip_private(None))


class TestPlayerPublic(unittest.TestCase):
    def test_returns_expected_fields(self):
        p = make_player()
        result = player_public(p)
        expected_keys = {
            "map_id", "px", "py", "coins", "gender", "permadeath", "dead",
            "death_reason", "ended", "ending_label", "move_locked",
            "move_lock_npc_id", "trap_reason", "trap_attempts", "enslaved",
            "enslaved_reason", "vigor", "vigor_max", "spirit", "spirit_max",
            "sleep_debt", "unconscious_ticks", "rescue_needed",
            "life_burn_ticks", "life_burn_max", "world_day",
            "world_shichen_idx", "world_shichen", "world_phase",
            "world_is_night", "weather", "inventory", "reputation",
            "npc_states", "bounties", "active_bounty", "completed_bounties",
            "flags", "favor",
        }
        self.assertTrue(expected_keys.issubset(set(result.keys())))

    def test_vigor_spirit_non_negative(self):
        p = make_player(vigor=-5, spirit=-10)
        result = player_public(p)
        self.assertGreaterEqual(result["vigor"], 0)
        self.assertGreaterEqual(result["spirit"], 0)

    def test_world_shichen_is_name(self):
        p = make_player(world_shichen=4)
        result = player_public(p)
        self.assertEqual(result["world_shichen"], "辰时")


class TestNpcsHere(unittest.TestCase):
    @patch("backend.api.views.npc_ids_for_player")
    @patch("backend.api.views.NPCS", {"npc_a": {"name": "张掌柜"}, "npc_b": {"name": "李牙人"}})
    def test_returns_npc_list(self, mock_ids):
        p = make_player()
        mock_ids.return_value = ["npc_a", "npc_b"]
        result = npcs_here(p)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "npc_a")
        self.assertEqual(result[0]["name"], "张掌柜")
        self.assertEqual(result[1]["id"], "npc_b")
        self.assertEqual(result[1]["name"], "李牙人")


class TestMapsPublic(unittest.TestCase):
    @patch("backend.api.views.MAPS", {"world": {"name": "江湖", "rows": [], "portals": []}})
    def test_returns_map_data(self):
        from backend.api import views
        views._maps_cache = None
        result = maps_public()
        self.assertIn("world", result)
        self.assertEqual(result["world"]["name"], "江湖")


class TestBuildInitResponse(unittest.TestCase):
    def test_returns_full_response(self):
        from backend.api import views
        views._maps_cache = None
        views._factions_cache = None
        views._map_locations_cache = None
        views._npc_labels_cache = None
        views._ambush_markers_cache = None
        with patch.object(views, "perception_scan", return_value=["感知内容"]), \
             patch.object(views, "danger_sense_narrative", return_value="危险感知"), \
             patch.object(views, "npc_ids_for_player", return_value=[]), \
             patch.object(views, "npc_catalog_for_player", return_value=[]), \
             patch.object(views, "MAPS", {"world": {"name": "江湖", "rows": [], "portals": []}}), \
             patch.object(views, "MAP_LOCATIONS", {}), \
             patch.object(views, "MAP_AMBUSH_MARKERS", []), \
             patch.object(views, "NPCS", {}), \
             patch.object(views, "FACTIONS", {}):
            views._maps_cache = None
            views._factions_cache = None
            views._map_locations_cache = None
            views._npc_labels_cache = None
            views._ambush_markers_cache = None
            p = make_player()
            result = build_init_response(p)
            self.assertIn("player_id", result)
            self.assertIn("display_name", result)
            self.assertIn("world_name", result)
            self.assertIn("intro", result)
            self.assertIn("maps", result)
            self.assertIn("player", result)
            self.assertIn("npcs_here", result)
            self.assertIn("danger_sense", result)
            self.assertEqual(result["player_id"], p.player_id)
            self.assertEqual(result["display_name"], p.display_name)


if __name__ == "__main__":
    unittest.main()
