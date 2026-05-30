from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.data.npcs_data import NPC_HABITS, NPCS
from backend.systems.npc_state import is_active_at, update_npc_states_from_habits
from backend.systems.time_weather import advance_clock, is_night


class TestNpcRoutine:
    def test_night_time_npcs_rest(self, game_world):
        p = game_world
        p.world_shichen = 0
        update_npc_states_from_habits(p)
        for nid, habits in NPC_HABITS.items():
            meta = NPCS.get(nid, {})
            if meta.get("always") or meta.get("hidden"):
                continue
            nocturnal = habits.get("nocturnal", False)
            if not nocturnal:
                assert p.npc_states.get(nid) == "resting", f"NPC {nid} should be resting at 子时 but is {p.npc_states.get(nid)}"

    def test_daytime_npcs_active(self, game_world):
        p = game_world
        p.world_shichen = 6
        update_npc_states_from_habits(p)
        for nid, habits in NPC_HABITS.items():
            meta = NPCS.get(nid, {})
            if meta.get("always") or meta.get("hidden"):
                continue
            active_val = habits.get("active", (4, 21))
            nocturnal = habits.get("nocturnal", False)
            if is_active_at(active_val, 6, nocturnal=nocturnal):
                state = p.npc_states.get(nid, "idle")
                assert state == "idle", f"NPC {nid} should be idle at 午时 but is {state}"

    def test_nocturnal_npc_active_at_night(self, game_world):
        p = game_world
        p.world_shichen = 0
        update_npc_states_from_habits(p)
        for nid, habits in NPC_HABITS.items():
            nocturnal = habits.get("nocturnal", False)
            if not nocturnal:
                continue
            meta = NPCS.get(nid, {})
            if meta.get("always") or meta.get("hidden"):
                continue
            active_val = habits.get("active", (4, 21))
            if is_active_at(active_val, 0, nocturnal=True):
                assert p.npc_states.get(nid) == "idle", f"Nocturnal NPC {nid} should be idle at 子时 but is {p.npc_states.get(nid)}"

    def test_all_twelve_shichen_state_transitions(self, game_world):
        p = game_world
        for shichen in range(12):
            p.world_shichen = shichen
            update_npc_states_from_habits(p)
            for nid, habits in NPC_HABITS.items():
                meta = NPCS.get(nid, {})
                if meta.get("always") or meta.get("hidden"):
                    continue
                state = p.npc_states.get(nid, "idle")
                assert state in ("idle", "resting"), f"NPC {nid} has unexpected state {state} at shichen {shichen}"

    def test_shichen_cycle_completes(self, game_world):
        p = game_world
        p.world_shichen = 0
        initial_shichen = p.world_shichen
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
            advance_clock(p, ticks=12)
        assert p.world_shichen == initial_shichen

    def test_vigor_recovers_after_rest(self, make_player, init_world):
        from backend.systems.perception import rest_at_location

        p = make_player(px=16, py=30, vigor=30, spirit=30, sleep_debt=20)
        init_world(p)
        with patch("backend.systems.perception.tile_at", return_value="T"), \
             patch("backend.agents.actor.execute_plan_step") as mock_exec, \
             patch("backend.agents.game_state.get_or_init_mind") as mock_mind, \
             patch("random.random", return_value=1.0), \
             patch("backend.systems.reputation.push_event"):
            mock_result = MagicMock()
            mock_result.action_type = MagicMock(value="idle")
            mock_exec.return_value = mock_result
            mock_mind_obj = MagicMock()
            mock_mind_obj.plan_by_shichen = {}
            mock_mind_obj.mood_decay_tick = MagicMock()
            mock_mind.return_value = mock_mind_obj
            vigor_before = p.vigor
            spirit_before = p.spirit
            result = rest_at_location(p)
            if result.get("ok"):
                assert p.vigor >= vigor_before or p.spirit >= spirit_before

    def test_night_shichen_identified_correctly(self):
        night_shichen = [0, 1, 10, 11]
        for s in range(12):
            if s in night_shichen:
                assert is_night(s), f"Shichen {s} should be night"
            else:
                assert not is_night(s), f"Shichen {s} should not be night"

    def test_npc_state_changes_through_day(self, game_world):
        p = game_world
        state_history = {}
        for nid in NPC_HABITS:
            meta = NPCS.get(nid, {})
            if meta.get("always") or meta.get("hidden"):
                continue
            state_history[nid] = []
        for shichen in range(12):
            p.world_shichen = shichen
            update_npc_states_from_habits(p)
            for nid in state_history:
                state_history[nid].append(p.npc_states.get(nid, "idle"))
        has_transition = False
        for nid, states in state_history.items():
            if len(set(states)) > 1:
                has_transition = True
                break
        assert has_transition, "At least one NPC should change state during the day"
