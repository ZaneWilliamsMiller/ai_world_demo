from __future__ import annotations

from backend.data.maps_data import MAPS
from backend.systems.economy import NPC_INVENTORY_SEEDS
from backend.systems.npc_state import maybe_wander_npcs, update_npc_states_from_habits
from backend.systems.time_weather import advance_clock


class TestWorldStability:
    def test_100_tick_npc_positions_in_bounds(self, game_world, map_bounds):
        p = game_world
        max_x, max_y = map_bounds()
        for _ in range(100):
            advance_clock(p, ticks=1)
            maybe_wander_npcs(p, ticks=1)
            update_npc_states_from_habits(p)
        for nid, pos in p.npc_positions.items():
            if not isinstance(pos, (list, tuple)) or len(pos) < 3:
                continue
            mid, x, y = str(pos[0]), int(pos[1]), int(pos[2])
            rows = MAPS.get(mid, {}).get("rows", [])
            if not rows:
                continue
            row_max_y = len(rows) - 1
            row_max_x = max(len(r) for r in rows) - 1
            assert 0 <= x <= row_max_x, f"NPC {nid} x={x} out of bounds [0, {row_max_x}]"
            assert 0 <= y <= row_max_y, f"NPC {nid} y={y} out of bounds [0, {row_max_y}]"

    def test_100_tick_vigor_spirit_in_range(self, game_world):
        p = game_world
        for _ in range(100):
            advance_clock(p, ticks=1)
            maybe_wander_npcs(p, ticks=1)
            update_npc_states_from_habits(p)
        assert 0 <= p.vigor <= p.vigor_max, f"vigor {p.vigor} out of [0, {p.vigor_max}]"
        assert 0 <= p.spirit <= p.spirit_max, f"spirit {p.spirit} out of [0, {p.spirit_max}]"

    def test_100_tick_economy_no_negative_inventory(self, game_world):
        p = game_world
        for _ in range(100):
            advance_clock(p, ticks=1)
            maybe_wander_npcs(p, ticks=1)
            update_npc_states_from_habits(p)
        for npc_id, inv in p.npc_inventories.items():
            for item_name, count in inv.items():
                assert count >= 0, f"NPC {npc_id} item {item_name} count is {count}"

    def test_100_tick_coins_non_negative(self, game_world):
        p = game_world
        for _ in range(100):
            advance_clock(p, ticks=1)
            maybe_wander_npcs(p, ticks=1)
            update_npc_states_from_habits(p)
        assert p.coins >= 0

    def test_100_tick_world_day_increases(self, game_world):
        p = game_world
        initial_day = p.world_day
        for _ in range(100):
            advance_clock(p, ticks=1)
            maybe_wander_npcs(p, ticks=1)
            update_npc_states_from_habits(p)
        assert p.world_day > initial_day

    def test_100_tick_npc_states_valid(self, game_world):
        p = game_world
        valid_states = {"idle", "resting", "busy", "alert", "hostile", "traveling"}
        for _ in range(100):
            advance_clock(p, ticks=1)
            maybe_wander_npcs(p, ticks=1)
            update_npc_states_from_habits(p)
        for nid, state in p.npc_states.items():
            assert state in valid_states, f"NPC {nid} has invalid state: {state}"

    def test_100_tick_player_not_dead(self, game_world):
        p = game_world
        for _ in range(100):
            advance_clock(p, ticks=1)
            maybe_wander_npcs(p, ticks=1)
            update_npc_states_from_habits(p)
        assert not p.dead

    def test_100_tick_no_duplicate_npc_positions(self, game_world):
        p = game_world
        for _ in range(100):
            advance_clock(p, ticks=1)
            maybe_wander_npcs(p, ticks=1)
            update_npc_states_from_habits(p)
        positions = {}
        for nid, pos in p.npc_positions.items():
            if not isinstance(pos, (list, tuple)) or len(pos) < 3:
                continue
            key = (str(pos[0]), int(pos[1]), int(pos[2]))
            positions.setdefault(key, []).append(nid)

    def test_100_tick_restock_preserves_vendor_inventories(self, game_world):
        p = game_world
        for _ in range(100):
            advance_clock(p, ticks=1)
            maybe_wander_npcs(p, ticks=1)
            update_npc_states_from_habits(p)
        for npc_id in NPC_INVENTORY_SEEDS:
            assert npc_id in p.npc_inventories, f"Vendor {npc_id} lost inventory after 100 ticks"
