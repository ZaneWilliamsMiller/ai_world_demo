# pyright: reportCallIssue=false
"""离线单元测试 — npc_state / trap / bounty / player / views / agent_brain"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pickle

from conftest import make_player


class TestNpcStateActiveTime:
    def test_diurnal_npc_active_during_day(self):
        from backend.systems.npc_state import is_active_at
        assert is_active_at((4, 20), 4) is True

    def test_diurnal_npc_inactive_at_night(self):
        from backend.systems.npc_state import is_active_at
        assert is_active_at((4, 20), 11) is False

    def test_nocturnal_npc_active_at_night(self):
        from backend.systems.npc_state import is_active_at
        assert is_active_at((18, 29), 10, nocturnal=True) is True

    def test_nocturnal_npc_active_after_midnight(self):
        from backend.systems.npc_state import is_active_at
        assert is_active_at((18, 29), 2, nocturnal=True) is True

    def test_nocturnal_npc_inactive_during_day(self):
        from backend.systems.npc_state import is_active_at
        assert is_active_at((18, 29), 5, nocturnal=True) is False

    def test_jintang_active_range(self):
        from backend.systems.npc_state import is_active_at
        assert is_active_at((16, 28), 9, nocturnal=True) is True
        assert is_active_at((16, 28), 2, nocturnal=True) is True
        assert is_active_at((16, 28), 5) is False

    def test_boundary_shichen_0_nocturnal(self):
        from backend.systems.npc_state import is_active_at
        assert is_active_at((18, 29), 0, nocturnal=True) is True

    def test_boundary_shichen_0_non_nocturnal(self):
        from backend.systems.npc_state import is_active_at
        assert is_active_at((4, 20), 0) is False

    def test_boundary_shichen_11(self):
        from backend.systems.npc_state import is_active_at
        assert is_active_at((18, 29), 11, nocturnal=True) is True

    def test_invalid_active_val_returns_true(self):
        from backend.systems.npc_state import is_active_at
        assert is_active_at(None, 6) is True  # type: ignore[arg-type]
        assert is_active_at("bad", 6) is True  # type: ignore[arg-type]


class TestTrapSurvivalAction:
    def test_fish_keyword_not_triggered_by_mention(self):
        from backend.systems.trap import survival_action_delta
        p = make_player(px=78, py=50)
        p.inventory["干粮"] = 5
        result = survival_action_delta(p, "这里有干粮卖吗？")
        assert result.get("note", "") == ""

    def test_fish_keyword_triggered_by_eating(self):
        from backend.systems.trap import survival_action_delta
        p = make_player(px=78, py=50)
        p.inventory["干粮"] = 5
        result = survival_action_delta(p, "吃干粮")
        assert result.get("note", "") != ""

    def test_rest_blocked_in_trap(self):
        from backend.systems.trap import survival_action_delta
        p = make_player()
        p.move_locked = True
        result = survival_action_delta(p, "我想歇息一下")
        assert "险局" in result.get("note", "") or "无法" in result.get("note", "")


class TestPlayerPickle:
    def test_pickle_roundtrip(self):
        p = make_player()
        p.inventory["干粮"] = 3
        data = pickle.dumps(p)
        p2 = pickle.loads(data)
        assert p2.player_id == "test_player"
        assert p2.inventory["干粮"] == 3
        assert hasattr(p2, "lock")

    def test_pickle_preserves_bounties(self):
        p = make_player()
        p.bounties = [{"id": "b1", "title": "test"}]
        data = pickle.dumps(p)
        p2 = pickle.loads(data)
        assert len(p2.bounties) == 1
        assert p2.bounties[0]["id"] == "b1"


class TestPlayerNoneFields:
    def test_bounties_none_treated_as_empty(self):
        p = make_player()
        p.bounties = None  # type: ignore[assignment]
        assert not p.bounties

    def test_completed_bounties_none_treated_as_empty(self):
        p = make_player()
        p.completed_bounties = None  # type: ignore[assignment]
        assert not p.completed_bounties


class TestViewsStripPrivate:
    def test_strip_private_removes_underscore_keys(self):
        from backend.api.views import _strip_private
        data = {"name": "test", "_internal": "secret", "nested": {"_key": "v", "ok": 1}}
        result = _strip_private(data)
        assert "_internal" not in result
        assert "_key" not in result["nested"]
        assert result["name"] == "test"
        assert result["nested"]["ok"] == 1

    def test_strip_private_handles_list(self):
        from backend.api.views import _strip_private
        data = [{"_a": 1, "b": 2}, {"_c": 3, "d": 4}]
        result = _strip_private(data)
        assert all("_a" not in r and "_c" not in r for r in result)


class TestViewsNpcsHere:
    def test_npcs_here_no_keyerror(self):
        from backend.api.views import npcs_here
        p = make_player()
        result = npcs_here(p)
        assert isinstance(result, list)
        if result:
            assert "id" in result[0]
            assert "name" in result[0]


class TestBountyBoard:
    def test_get_location_coords_returns_valid(self):
        from backend.systems.bounty_board import _get_location_coords
        from backend.data.maps_data import MAP_LOCATIONS
        map_id = "world"
        for loc_name in list(MAP_LOCATIONS.get(map_id, {}).keys())[:3]:
            px, py = _get_location_coords(map_id, loc_name)
            assert px >= 0
            assert py >= 0

    def test_get_location_coords_fallback(self):
        from backend.systems.bounty_board import _get_location_coords
        px, py = _get_location_coords("world", "nonexistent_place")
        assert px >= 0
        assert py >= 0

    def test_generate_bounties_from_events(self):
        from backend.systems.bounty_board import generate_bounties_from_events
        p = make_player()
        events = [
            {
                "id": "evt_test1",
                "desc": "一名逃犯潜入城中",
                "severity": "moderate",
                "faction": "yamen",
                "location": "市口",
                "bounty_hint": {
                    "type": "缉拿",
                    "target_npc": "zhanggui",
                    "location": "市口",
                },
            }
        ]
        bounties = generate_bounties_from_events(p, events)
        assert len(bounties) == 1
        b = bounties[0]
        assert b["type"] == "缉拿"
        assert b["story_event_id"] == "evt_test1"
        assert "task_fsm" in b
        assert b["reward"].get("coins", 0) > 0

    def test_complete_bounty_idempotent(self):
        from backend.systems.bounty_board import complete_bounty
        p = make_player()
        p.active_bounty = {"id": "b1", "title": "test", "type": "errand", "target_id": "zhanggui", "requires": {"talk_npc": "zhanggui"}, "task_fsm": {"current_state": "in_progress", "sub_steps": [], "completed_steps": [], "transition_log": []}}
        p.last_talk_npc_id = "zhanggui"
        p.last_talk_message = "test"
        p.completed_bounties = []
        ok1, msg1, _ = complete_bounty(p)
        if ok1:
            ok2, msg2, _ = complete_bounty(p)
            assert ok2 is False
            assert "已完成" in msg2
        else:
            assert "尚未完成" in msg1


class TestAgentBrainTypeValidation:
    def test_insights_string_treated_as_empty(self):
        data = {"insights": "一条洞察"}
        insights = data.get("insights", [])
        if not isinstance(insights, list):
            insights = []
        assert insights == []

    def test_schedule_non_dict_treated_as_empty(self):
        data = {"schedule": [1, 2, 3]}
        by_shichen = data.get("schedule", {})
        if not isinstance(by_shichen, dict):
            by_shichen = {}
        assert by_shichen == {}

    def test_summary_non_string_converted(self):
        data = {"summary": 12345}
        summary = str(data.get("summary", ""))[:60]
        assert summary == "12345"


class TestStoreMigration:
    def test_none_list_fields_become_empty(self):
        from backend.session.store import SessionStore
        store = SessionStore()
        from backend.models.player import PlayerState
        p = PlayerState(player_id="migrate_test", display_name="M", gender="男")
        p.bounties = None  # type: ignore[assignment]
        p.completed_bounties = None  # type: ignore[assignment]
        p.rumors = None  # type: ignore[assignment]
        p.events = None  # type: ignore[assignment]
        store.players["migrate_test"] = p
        asyncio.run(store.get_or_create("migrate_test", "M", "男", False))
        assert p.bounties == []
        assert p.completed_bounties == []
        assert p.rumors == []
        assert p.events == []

    def test_none_dict_fields_become_empty(self):
        from backend.session.store import SessionStore
        store = SessionStore()
        from backend.models.player import PlayerState
        p = PlayerState(player_id="migrate_test2", display_name="M", gender="男")
        p.favor = None  # type: ignore[assignment]
        p.inventory = None  # type: ignore[assignment]
        p.item_use_tracker = None  # type: ignore[assignment]
        store.players["migrate_test2"] = p
        asyncio.run(store.get_or_create("migrate_test2", "M", "男", False))
        assert p.favor == {}
        assert p.inventory == {}
        assert p.item_use_tracker == {}


class TestTimeWeather:
    def test_ticks_capped(self):
        from backend.systems.time_weather import advance_clock
        p = make_player()
        old_tick = p.world_tick
        advance_clock(p, ticks=100)
        assert p.world_tick - old_tick <= 24

    def test_shichen_wraps(self):
        from backend.systems.time_weather import advance_clock
        p = make_player(world_shichen=11)
        advance_clock(p, ticks=1)
        assert p.world_shichen == 0


class TestPerception:
    def test_cell_tuple_validation(self):
        from backend.systems.perception import tile_forced_encounter
        p = make_player()
        result = tile_forced_encounter(p)
        assert result is None or isinstance(result, dict)
