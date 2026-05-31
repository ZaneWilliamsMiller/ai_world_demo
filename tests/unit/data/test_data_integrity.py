import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import unittest

from backend.data.atmosphere import TILE_ATMOSPHERE, WORLD_REGIONS
from backend.data.factions import FACTIONS
from backend.data.maps_data import MAP_AMBUSH_MARKERS, MAP_LOCATIONS, MAPS
from backend.data.npcs_data import NPC_FACTION, NPC_HABITS, NPC_SEEDS, NPCS
from backend.data.prompts import FIXED_INTRO, WORLD_NAME
from backend.data.relationships import NPC_RELATIONSHIPS
from backend.data.zones import ECONOMY_ZONES, SAFE_ZONES


class TestAtmosphere(unittest.TestCase):
    def test_tile_atmosphere_is_dict(self):
        self.assertIsInstance(TILE_ATMOSPHERE, dict)

    def test_tile_atmosphere_keys_are_str(self):
        for key in TILE_ATMOSPHERE:
            self.assertIsInstance(key, str)

    def test_tile_atmosphere_values_are_list_of_str(self):
        for key, val in TILE_ATMOSPHERE.items():
            self.assertIsInstance(val, list)
            for item in val:
                self.assertIsInstance(item, str)

    def test_world_regions_is_dict(self):
        self.assertIsInstance(WORLD_REGIONS, dict)

    def test_world_regions_keys_are_str(self):
        for key in WORLD_REGIONS:
            self.assertIsInstance(key, str)

    def test_world_regions_values_are_list_of_str(self):
        for key, val in WORLD_REGIONS.items():
            self.assertIsInstance(val, list)
            for item in val:
                self.assertIsInstance(item, str)


class TestFactions(unittest.TestCase):
    def test_factions_is_dict(self):
        self.assertIsInstance(FACTIONS, dict)

    def test_factions_keys_are_str(self):
        for key in FACTIONS:
            self.assertIsInstance(key, str)

    def test_factions_values_are_str(self):
        for val in FACTIONS.values():
            self.assertIsInstance(val, str)

    def test_factions_at_least_five(self):
        self.assertGreaterEqual(len(FACTIONS), 5)


class TestMapsData(unittest.TestCase):
    def test_maps_is_dict(self):
        self.assertIsInstance(MAPS, dict)

    def test_each_map_has_name(self):
        for map_id, map_data in MAPS.items():
            self.assertIn("name", map_data, f"Map '{map_id}' missing 'name'")

    def test_each_map_has_rows(self):
        for map_id, map_data in MAPS.items():
            self.assertIn("rows", map_data, f"Map '{map_id}' missing 'rows'")

    def test_rows_is_list(self):
        for map_id, map_data in MAPS.items():
            self.assertIsInstance(map_data["rows"], list, f"Map '{map_id}' rows is not list")

    def test_map_locations_is_dict(self):
        self.assertIsInstance(MAP_LOCATIONS, dict)

    def test_map_ambush_markers_is_tuple(self):
        self.assertIsInstance(MAP_AMBUSH_MARKERS, tuple)


class TestNpcsData(unittest.TestCase):
    def test_npcs_is_dict(self):
        self.assertIsInstance(NPCS, dict)

    def test_each_npc_has_name(self):
        for npc_id, npc_data in NPCS.items():
            self.assertIn("name", npc_data, f"NPC '{npc_id}' missing 'name'")

    def test_npc_seeds_is_dict(self):
        self.assertIsInstance(NPC_SEEDS, dict)

    def test_seeds_values_are_list(self):
        for npc_id, seeds in NPC_SEEDS.items():
            self.assertIsInstance(seeds, list, f"NPC_SEEDS['{npc_id}'] is not list")


class TestPrompts(unittest.TestCase):
    def test_fixed_intro_is_non_empty_str(self):
        self.assertIsInstance(FIXED_INTRO, str)
        self.assertGreater(len(FIXED_INTRO), 0)

    def test_world_name_is_non_empty_str(self):
        self.assertIsInstance(WORLD_NAME, str)
        self.assertGreater(len(WORLD_NAME), 0)


class TestRelationships(unittest.TestCase):
    def test_npc_relationships_is_dict(self):
        self.assertIsInstance(NPC_RELATIONSHIPS, dict)

    def test_each_relationship_entry_has_target(self):
        for npc_id, rels in NPC_RELATIONSHIPS.items():
            for rel in rels:
                self.assertIn("target", rel, f"NPC '{npc_id}' relationship missing 'target'")


class TestZones(unittest.TestCase):
    def test_economy_zones_is_dict(self):
        self.assertIsInstance(ECONOMY_ZONES, dict)

    def test_each_economy_zone_has_label(self):
        for zone_id, zone_data in ECONOMY_ZONES.items():
            self.assertIn("label", zone_data, f"Economy zone '{zone_id}' missing 'label'")

    def test_safe_zones_is_dict(self):
        self.assertIsInstance(SAFE_ZONES, dict)

    def test_each_safe_zone_has_label(self):
        for zone_id, zone_data in SAFE_ZONES.items():
            self.assertIn("label", zone_data, f"Safe zone '{zone_id}' missing 'label'")


MAP_MAX_X = 149
MAP_MAX_Y = 99


class TestNpcsDataExtended(unittest.TestCase):
    def test_non_always_npcs_have_cell(self):
        for npc_id, npc_data in NPCS.items():
            if npc_data.get("always"):
                continue
            self.assertIn("cell", npc_data, f"Non-always NPC '{npc_id}' missing 'cell'")
            cell = npc_data["cell"]
            self.assertIsInstance(cell, tuple, f"NPC '{npc_id}' cell is not tuple")
            self.assertEqual(len(cell), 3, f"NPC '{npc_id}' cell must be (map_id, x, y)")
            x = cell[1]
            y = cell[2]
            self.assertGreaterEqual(x, 0, f"NPC '{npc_id}' cell x={x} < 0")
            self.assertLessEqual(x, MAP_MAX_X, f"NPC '{npc_id}' cell x={x} > {MAP_MAX_X}")
            self.assertGreaterEqual(y, 0, f"NPC '{npc_id}' cell y={y} < 0")
            self.assertLessEqual(y, MAP_MAX_Y, f"NPC '{npc_id}' cell y={y} > {MAP_MAX_Y}")

    def test_habits_npcs_in_npcs_dict(self):
        for npc_id in NPC_HABITS:
            self.assertIn(npc_id, NPCS, f"NPC_HABITS key '{npc_id}' not in NPCS")

    def test_seeds_have_three_entries(self):
        for npc_id, seeds in NPC_SEEDS.items():
            self.assertEqual(len(seeds), 3, f"NPC_SEEDS['{npc_id}'] has {len(seeds)} entries, expected 3")

    def test_faction_values_valid(self):
        valid_factions = {"yamen", "biaoju", "caobang", "lulin", "shuyuan", None}
        for npc_id, faction in NPC_FACTION.items():
            self.assertIn(
                faction, valid_factions,
                f"NPC_FACTION['{npc_id}'] = {faction!r} not in valid set"
            )

    def test_wander_npcs_have_anchor_radius(self):
        for npc_id, npc_data in NPCS.items():
            if "wander_anchor_radius" in npc_data:
                self.assertIn(
                    "wander_maps_whitelist", npc_data,
                    f"NPC '{npc_id}' has wander_anchor_radius but missing wander_maps_whitelist"
                )


class TestRelationshipsExtended(unittest.TestCase):
    def test_target_npcs_exist(self):
        for npc_id, rels in NPC_RELATIONSHIPS.items():
            for rel in rels:
                target = rel.get("target", "")
                self.assertIn(
                    target, NPCS,
                    f"NPC '{npc_id}' relationship target '{target}' not in NPCS"
                )

    def test_attitude_values_valid(self):
        known_attitudes = {
            "挚交", "交好", "面上客气", "互不招惹", "心存芥蒂",
            "势同水火", "生意往来", "旧交", "暧昧线人", "面上恭敬", "老主顾",
        }
        for npc_id, rels in NPC_RELATIONSHIPS.items():
            for rel in rels:
                attitude = rel.get("attitude", "")
                self.assertIn(
                    attitude, known_attitudes,
                    f"NPC '{npc_id}' relationship attitude '{attitude}' not in known values"
                )

    def test_no_self_reference(self):
        for npc_id, rels in NPC_RELATIONSHIPS.items():
            for rel in rels:
                target = rel.get("target", "")
                self.assertNotEqual(
                    npc_id, target,
                    f"NPC '{npc_id}' has self-referencing relationship"
                )

    def test_note_non_empty(self):
        for npc_id, rels in NPC_RELATIONSHIPS.items():
            for rel in rels:
                note = rel.get("note", "")
                self.assertTrue(
                    note and note.strip(),
                    f"NPC '{npc_id}' relationship with '{rel.get('target')}' has empty note"
                )


if __name__ == "__main__":
    unittest.main()
