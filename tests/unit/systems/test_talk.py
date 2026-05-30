# pyright: reportCallIssue=false
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from unittest.mock import MagicMock, patch

from backend.systems.bounty_board import (
    abandon_bounty,
    accept_bounty,
    can_accept_bounty,
    generate_bounties,
)
from backend.systems.encounter import should_trigger_encounter
from backend.systems.npc_gossip import maybe_npc_gossip
from backend.systems.npc_state import is_active_at, update_npc_states_from_habits
from backend.systems.reputation import apply_rep_delta, clamp_rep_delta, push_event
from backend.systems.trap import (
    apply_spirit_delta,
    apply_vigor_delta,
    enter_trap_state,
    maybe_collapse_from_attrs,
    survival_action_delta,
)

from conftest import make_player


class TestReputation:
    def test_clamp_rep_delta(self):
        d = {"yamen": 1, "biaoju": 5, "caobang": -5, "lulin": 0}
        result = clamp_rep_delta(d)
        assert result["yamen"] == 1
        assert result["biaoju"] == 2
        assert result["caobang"] == -2
        assert "lulin" not in result

    def test_clamp_rep_delta_empty(self):
        assert clamp_rep_delta({}) == {}

    def test_apply_rep_delta(self):
        p = make_player()
        p.reputation = {"yamen": 50, "biaoju": -50, "caobang": 0}
        apply_rep_delta(p, {"yamen": 1, "biaoju": -1, "caobang": 2})
        assert p.reputation["yamen"] == 51
        assert p.reputation["biaoju"] == -51
        assert p.reputation["caobang"] == 2

    def test_apply_rep_delta_none(self):
        p = make_player()
        p.reputation = {"yamen": 10}
        apply_rep_delta(p, None)
        assert p.reputation["yamen"] == 10

    def test_push_event(self):
        p = make_player()
        p.events = []
        push_event(p, "test event")
        assert len(p.events) == 1
        assert p.events[0]["text"] == "test event"
        assert p.events[0]["scope"] == "near"

    def test_push_event_scope(self):
        p = make_player()
        p.events = []
        push_event(p, "world event", scope="world", actor="npc1")
        assert p.events[0]["scope"] == "world"
        assert p.events[0]["actor"] == "npc1"

    def test_push_event_truncation(self):
        p = make_player()
        p.events = []
        long_text = "x" * 200
        push_event(p, long_text)
        assert len(p.events[0]["text"]) <= 81

    def test_push_event_empty(self):
        p = make_player()
        p.events = []
        push_event(p, "")
        push_event(p, "   ")
        assert len(p.events) == 0


class TestTrap:
    def test_apply_vigor_delta_positive(self):
        p = make_player()
        p.vigor = 50
        p.vigor_max = 100
        actual = apply_vigor_delta(p, 20)
        assert p.vigor == 70
        assert actual == 20

    def test_apply_vigor_delta_negative(self):
        p = make_player()
        p.vigor = 50
        p.vigor_max = 100
        actual = apply_vigor_delta(p, -30)
        assert p.vigor == 20
        assert actual == -30

    def test_apply_vigor_delta_clamp_zero(self):
        p = make_player()
        p.vigor = 5
        p.vigor_max = 100
        actual = apply_vigor_delta(p, -20)
        assert p.vigor == 0
        assert actual == -5

    def test_apply_vigor_delta_clamp_max(self):
        p = make_player()
        p.vigor = 90
        p.vigor_max = 100
        actual = apply_vigor_delta(p, 30)
        assert p.vigor == 100
        assert actual == 10

    def test_apply_vigor_delta_zero(self):
        p = make_player()
        p.vigor = 50
        actual = apply_vigor_delta(p, 0)
        assert p.vigor == 50
        assert actual == 0

    def test_apply_spirit_delta_positive(self):
        p = make_player()
        p.spirit = 50
        p.spirit_max = 100
        actual = apply_spirit_delta(p, 20)
        assert p.spirit == 70
        assert actual == 20

    def test_apply_spirit_delta_negative(self):
        p = make_player()
        p.spirit = 50
        p.spirit_max = 100
        actual = apply_spirit_delta(p, -30)
        assert p.spirit == 20
        assert actual == -30

    def test_apply_spirit_delta_clamp_zero(self):
        p = make_player()
        p.spirit = 5
        p.spirit_max = 100
        actual = apply_spirit_delta(p, -20)
        assert p.spirit == 0
        assert actual == -5

    def test_apply_spirit_delta_clamp_max(self):
        p = make_player()
        p.spirit = 90
        p.spirit_max = 100
        actual = apply_spirit_delta(p, 30)
        assert p.spirit == 100
        assert actual == 10

    def test_apply_spirit_delta_zero(self):
        p = make_player()
        p.spirit = 50
        actual = apply_spirit_delta(p, 0)
        assert p.spirit == 50
        assert actual == 0

    def test_enter_trap_state(self):
        p = make_player()
        enter_trap_state(p, "ambush", lock_npc_id="bandit")
        assert p.move_locked is True
        assert p.move_lock_npc_id == "bandit"
        assert p.trap_reason == "ambush"
        assert p.trap_attempts == 0

    def test_enter_trap_state_default_npc(self):
        p = make_player()
        enter_trap_state(p, "pit")
        assert p.move_lock_npc_id == "jiang"

    def test_enter_trap_state_reason_truncation(self):
        p = make_player()
        long_reason = "x" * 200
        enter_trap_state(p, long_reason)
        assert len(p.trap_reason or "") <= 80

    def test_maybe_collapse_from_attrs_both_zero(self):
        p = make_player()
        p.vigor = 0
        p.spirit = 0
        result = maybe_collapse_from_attrs(p)
        assert result is not None
        assert result["outcome"] == "dead"
        assert p.dead is True

    def test_maybe_collapse_from_attrs_vigor_zero(self):
        p = make_player()
        p.vigor = 0
        p.spirit = 10
        p.life_burn_ticks = 0
        result = maybe_collapse_from_attrs(p)
        assert result is not None
        assert result["outcome"] == "burning"
        assert p.move_locked is True

    def test_maybe_collapse_from_attrs_vigor_zero_already_burning(self):
        p = make_player()
        p.vigor = 0
        p.spirit = 10
        p.life_burn_ticks = 3
        result = maybe_collapse_from_attrs(p)
        assert result is not None
        assert result["outcome"] == "burning"

    def test_maybe_collapse_from_attrs_spirit_zero(self):
        p = make_player()
        p.vigor = 10
        p.spirit = 0
        result = maybe_collapse_from_attrs(p)
        assert result is not None
        assert result["outcome"] == "dead"
        assert p.dead is True

    def test_maybe_collapse_from_attrs_healthy(self):
        p = make_player()
        p.vigor = 50
        p.spirit = 50
        result = maybe_collapse_from_attrs(p)
        assert result is None

    def test_survival_action_delta_empty(self):
        p = make_player()
        result = survival_action_delta(p, "")
        assert result["vigor"] == 0
        assert result["spirit"] == 0
        assert result["items_gain"] == []
        assert result["items_lose"] == []

    def test_survival_action_delta_dry_ration(self):
        p = make_player()
        p.vigor = 50
        p.spirit = 50
        p.inventory = {"干粮": 1}
        with patch("backend.systems.trap.tile_at", return_value="."):
            result = survival_action_delta(p, "吃干粮")
        assert "干粮" not in p.inventory or p.inventory.get("干粮", 0) == 0
        assert result["vigor"] > 0
        assert "干粮" in result["items_lose"]

    def test_survival_action_delta_fish(self):
        p = make_player()
        p.vigor = 50
        p.spirit = 50
        p.inventory = {}
        with patch("backend.systems.trap.tile_at", return_value="~"):
            result = survival_action_delta(p, "打鱼")
        assert "鲜鱼" in result["items_gain"]

    def test_survival_action_delta_rest(self):
        p = make_player()
        p.vigor = 50
        p.spirit = 50
        p.sleep_debt = 20
        with patch("backend.systems.trap.tile_at", return_value="T"):
            result = survival_action_delta(p, "歇息")
        assert result["spirit"] > 0

    def test_survival_action_delta_climb(self):
        p = make_player()
        p.spirit = 50
        with patch("backend.systems.trap.tile_at", return_value="."):
            result = survival_action_delta(p, "攀爬")
        assert p.allow_steep_next_move is True
        assert result["spirit"] < 0


class TestNpcState:
    def test_is_active_at_daytime(self):
        assert is_active_at((4, 21), 4) is True
        assert is_active_at((4, 21), 10) is True
        assert is_active_at((4, 21), 0) is False

    def test_is_active_at_night_nocturnal(self):
        assert is_active_at((18, 29), 0, nocturnal=True) is True
        assert is_active_at((18, 29), 1, nocturnal=True) is True

    def test_is_active_at_night_non_nocturnal(self):
        assert is_active_at((18, 29), 0, nocturnal=False) is False
        assert is_active_at((18, 29), 1, nocturnal=False) is False

    def test_is_active_at_invalid_input(self):
        assert is_active_at(None, 4) is True  # type: ignore[arg-type]
        assert is_active_at((), 4) is True
        assert is_active_at((5,), 4) is True

    def test_is_active_at_wrap_around(self):
        assert is_active_at((22, 28), 0, nocturnal=True) is True

    @patch("backend.systems.npc_state.shichen_name", return_value="辰")
    @patch("backend.systems.npc_state.NPC_HABITS", {
        "zhanggui": {"active": (4, 21), "nocturnal": False},
        "hei": {"active": (18, 29), "nocturnal": True},
    })
    @patch("backend.systems.npc_state.NPCS", {
        "zhanggui": {"name": "沈掌柜"},
        "hei": {"name": "黑店掌柜", "nocturnal": True},
    })
    def test_update_npc_states_from_habits(self, mock_shichen):
        p = make_player()
        p.npc_states = {}
        p.world_shichen = 4
        changes = update_npc_states_from_habits(p)
        assert "zhanggui" in p.npc_states or "hei" in p.npc_states

    @patch("backend.systems.npc_state.shichen_name", return_value="子")
    @patch("backend.systems.npc_state.NPC_HABITS", {
        "zhanggui": {"active": (4, 21), "nocturnal": False},
    })
    @patch("backend.systems.npc_state.NPCS", {
        "zhanggui": {"name": "沈掌柜"},
    })
    def test_update_npc_states_from_habits_night_resting(self, mock_shichen):
        p = make_player()
        p.npc_states = {"zhanggui": "idle"}
        p.world_shichen = 0
        changes = update_npc_states_from_habits(p)
        assert p.npc_states["zhanggui"] == "resting"

    @patch("backend.systems.npc_state.shichen_name", return_value="辰")
    @patch("backend.systems.npc_state.NPC_HABITS", {})
    @patch("backend.systems.npc_state.NPCS", {})
    def test_update_npc_states_from_habits_empty(self, mock_shichen):
        p = make_player()
        p.npc_states = {}
        changes = update_npc_states_from_habits(p)
        assert changes == {}


class TestBountyBoard:
    @patch("backend.systems.bounty_board.shichen_name", return_value="辰")
    @patch("backend.systems.bounty_board.NPCS", {
        "npc_a": {"name": "NPC A", "short": "A"},
        "npc_b": {"name": "NPC B", "short": "B"},
    })
    @patch("backend.systems.bounty_board.MAP_LOCATIONS", {
        "world": {"市口": (25, 28)},
    })
    def test_generate_bounties(self, mock_shichen):
        p = make_player()
        p.map_id = "world"
        bounties = generate_bounties(p, count=2)
        assert len(bounties) <= 2
        for b in bounties:
            assert "id" in b
            assert "type" in b
            assert "title" in b
            assert "desc" in b
            assert "reward" in b
            assert "requires" in b

    def test_can_accept_bounty_ok(self):
        p = make_player()
        p.active_bounty = None
        p.completed_bounties = []
        p.reputation = {"yamen": 5}
        bounty = {"id": "b1", "min_rep": {"yamen": 1}}
        ok, reason = can_accept_bounty(p, bounty)
        assert ok is True
        assert reason == ""

    def test_can_accept_bounty_already_completed(self):
        p = make_player()
        p.active_bounty = None
        p.completed_bounties = ["b1"]
        bounty = {"id": "b1", "min_rep": {}}
        ok, _reason = can_accept_bounty(p, bounty)
        assert ok is False

    def test_can_accept_bounty_has_active(self):
        p = make_player()
        p.active_bounty = {"id": "other"}
        p.completed_bounties = []
        bounty = {"id": "b1", "min_rep": {}}
        ok, _reason = can_accept_bounty(p, bounty)
        assert ok is False

    def test_can_accept_bounty_low_rep(self):
        p = make_player()
        p.active_bounty = None
        p.completed_bounties = []
        p.reputation = {"yamen": 0}
        bounty = {"id": "b1", "min_rep": {"yamen": 2}}
        ok, _reason = can_accept_bounty(p, bounty)
        assert ok is False

    def test_accept_bounty_success(self):
        p = make_player()
        p.active_bounty = None
        p.completed_bounties = []
        p.reputation = {"yamen": 5}
        bounty = {"id": "b1", "min_rep": {}, "requires": {}, "title": "Test Bounty"}
        p.bounties = [bounty]
        ok, _msg = accept_bounty(p, "b1")
        assert ok is True
        assert p.active_bounty is not None
        assert p.active_bounty["id"] == "b1"

    def test_accept_bounty_not_found(self):
        p = make_player()
        p.bounties = []
        ok, _msg = accept_bounty(p, "nonexistent")
        assert ok is False

    def test_abandon_bounty_success(self):
        p = make_player()
        p.active_bounty = {"id": "b1", "title": "Test Bounty"}
        ok, _msg = abandon_bounty(p)
        assert ok is True
        assert p.active_bounty is None

    def test_abandon_bounty_none(self):
        p = make_player()
        p.active_bounty = None
        ok, _msg = abandon_bounty(p)
        assert ok is False


class TestNpcGossip:
    def test_maybe_npc_gossip_triggers(self):
        p = make_player()
        p.npc_positions = {"npc_a": ("world", 10, 10), "npc_b": ("world", 10, 10)}
        p.world_shichen = 4
        p.world_day = 1
        from backend.systems import npc_gossip
        npc_gossip._last_gossip.clear()
        with patch("backend.systems.core.init_npc_positions"), \
             patch("backend.systems.npc_gossip.get_or_init_mind") as mock_mind, \
             patch("backend.systems.npc_gossip.shichen_name", return_value="辰"), \
             patch("backend.systems.npc_gossip._generate_gossip_text", return_value=("obs_a", "obs_b")), \
             patch("backend.systems.npc_gossip.NPC_RELATIONSHIPS", {
                 "npc_a": [{"target": "npc_b", "attitude": "交好", "note": "test"}],
                 "npc_b": [{"target": "npc_a", "attitude": "交好", "note": "test"}],
             }), \
             patch("backend.systems.npc_gossip.NPCS", {
                 "npc_a": {"name": "NPC A"},
                 "npc_b": {"name": "NPC B"},
             }), \
             patch("backend.systems.npc_gossip.random.random", return_value=0.01), \
             patch("backend.systems.npc_gossip.time.time", return_value=100000.0):
            mock_mind_a = MagicMock()
            mock_mind_b = MagicMock()
            mock_mind.side_effect = [mock_mind_a, mock_mind_b]
            count = maybe_npc_gossip(p, ticks=1)
            assert count == 1

    def test_maybe_npc_gossip_no_npcs(self):
        p = make_player()
        p.npc_positions = {}
        with patch("backend.systems.core.init_npc_positions"), \
             patch("backend.systems.npc_gossip.NPCS", {}):
            count = maybe_npc_gossip(p, ticks=1)
            assert count == 0

    def test_maybe_npc_gossip_zero_ticks(self):
        p = make_player()
        count = maybe_npc_gossip(p, ticks=0)
        assert count == 0


class TestEncounter:
    def test_should_trigger_encounter_cooldown(self):
        p = make_player()
        p.world_tick = 10
        p.last_dynamic_encounter_tick = 8
        p.world_shichen = 4
        p.weather = "晴"
        result = should_trigger_encounter(p)
        assert result is False

    @patch("backend.systems.encounter.random.random", return_value=0.01)
    def test_should_trigger_encounter_success(self, mock_rand):
        p = make_player()
        p.world_tick = 100
        p.last_dynamic_encounter_tick = 0
        p.world_shichen = 4
        p.weather = "晴"
        p.map_id = "world"
        p.px = 16
        p.py = 30
        result = should_trigger_encounter(p)
        assert result is True

    @patch("backend.systems.encounter.random.random", return_value=0.99)
    def test_should_trigger_encounter_fail(self, mock_rand):
        p = make_player()
        p.world_tick = 100
        p.last_dynamic_encounter_tick = 0
        p.world_shichen = 4
        p.weather = "晴"
        p.map_id = "world"
        p.px = 16
        p.py = 30
        result = should_trigger_encounter(p)
        assert result is False

    @patch("backend.systems.encounter.random.random", return_value=0.20)
    def test_should_trigger_encounter_night_bonus(self, mock_rand):
        p = make_player()
        p.world_tick = 100
        p.last_dynamic_encounter_tick = 0
        p.world_shichen = 0
        p.weather = "晴"
        p.map_id = "world"
        p.px = 16
        p.py = 30
        with patch("backend.systems.encounter.is_night", return_value=True), \
             patch("backend.systems.encounter._is_wild", return_value=False):
            result = should_trigger_encounter(p)
        assert result is False

    @patch("backend.systems.encounter.random.random", return_value=0.01)
    def test_should_trigger_encounter_bad_weather(self, mock_rand):
        p = make_player()
        p.world_tick = 100
        p.last_dynamic_encounter_tick = 0
        p.world_shichen = 4
        p.weather = "骤雨"
        p.map_id = "world"
        p.px = 16
        p.py = 30
        with patch("backend.systems.encounter.is_night", return_value=False):
            result = should_trigger_encounter(p)
        assert result is True

    @patch("backend.systems.encounter.random.random", return_value=0.01)
    def test_should_trigger_encounter_low_spirit(self, mock_rand):
        p = make_player()
        p.world_tick = 100
        p.last_dynamic_encounter_tick = 0
        p.world_shichen = 4
        p.weather = "晴"
        p.spirit = 10
        p.map_id = "world"
        p.px = 16
        p.py = 30
        with patch("backend.systems.encounter.is_night", return_value=False):
            result = should_trigger_encounter(p)
        assert result is True
