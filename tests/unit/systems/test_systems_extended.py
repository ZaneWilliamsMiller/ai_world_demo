# pyright: reportCallIssue=false,reportArgumentType=false,reportOptionalSubscript=false,reportIndexIssue=false,reportOperatorIssue=false
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from unittest.mock import MagicMock, patch

from backend.models.npc import format_npc_character_sheet
from backend.systems.bounty_board import (
    check_bounty_progress,
    format_bounty_board,
    refresh_bounties,
)
from backend.systems.encounter import (
    _build_encounter_context,
    _fallback_encounter,
    _is_wild,
    apply_encounter,
    format_encounter_perception_block,
)
from backend.systems.npc_gossip import (
    _generate_gossip_text,
    _get_attitude,
    _get_relation_note,
    _gossip_key,
    _pick_recent_snippet,
    _prune_gossip_cache,
    format_gossip_awareness_block,
)
from backend.systems.perception import (
    hazard_roll_death,
    recent_events_block,
    relevant_events_for,
    rest_at_location,
    world_status_block,
)

from conftest import make_player

# ════════════════════════════════════════════════════════════════
#  bounty_board — check_bounty_progress / format_bounty_board / refresh_bounties
# ════════════════════════════════════════════════════════════════


class TestCheckBountyProgress:
    def test_no_active_bounty(self):
        p = make_player()
        p.active_bounty = None
        assert check_bounty_progress(p) is None

    def test_capture_talked_with_keyword(self):
        p = make_player()
        p.active_bounty = {
            "id": "b1",
            "type": "缉拿",
            "requires": {"talk_to_npc": "npc_a", "ask_about": "逃犯下落"},
        }
        p.last_talk_npc_id = "npc_a"
        p.last_talk_message = "我问你逃犯下落如何"
        with patch("backend.systems.bounty_board.NPCS", {"npc_a": {"name": "NPC甲"}}):
            result = check_bounty_progress(p)
        assert result is not None
        assert result["done"] is True
        assert "NPC甲" in result["reason"]

    def test_capture_talked_without_keyword(self):
        p = make_player()
        p.active_bounty = {
            "id": "b2",
            "type": "缉拿",
            "requires": {"talk_to_npc": "npc_a", "ask_about": "逃犯下落"},
        }
        p.last_talk_npc_id = "npc_a"
        p.last_talk_message = "今天天气不错"
        with patch("backend.systems.bounty_board.NPCS", {"npc_a": {"name": "NPC甲"}}):
            result = check_bounty_progress(p)
        assert result is not None
        assert result["done"] is False
        assert "尚未问及" in result["reason"]

    def test_capture_no_ask_about(self):
        p = make_player()
        p.active_bounty = {
            "id": "b3",
            "type": "缉拿",
            "requires": {"talk_to_npc": "npc_a"},
        }
        p.last_talk_npc_id = "npc_a"
        p.last_talk_message = ""
        with patch("backend.systems.bounty_board.NPCS", {"npc_a": {"name": "NPC甲"}}):
            result = check_bounty_progress(p)
        assert result is not None
        assert result["done"] is True

    def test_capture_wrong_npc(self):
        p = make_player()
        p.active_bounty = {
            "id": "b4",
            "type": "缉拿",
            "requires": {"talk_to_npc": "npc_a", "ask_about": "逃犯下落"},
        }
        p.last_talk_npc_id = "npc_b"
        p.last_talk_message = "逃犯下落"
        with patch("backend.systems.bounty_board.NPCS", {"npc_a": {"name": "NPC甲"}}):
            result = check_bounty_progress(p)
        assert result is not None
        assert result["done"] is False
        assert "尚未找到" in result["reason"]

    def test_escort_at_destination(self):
        p = make_player()
        p.map_id = "world"
        p.px = 10
        p.py = 20
        p.active_bounty = {
            "id": "b5",
            "type": "押送",
            "requires": {"move_to": "市口"},
            "_target_pos": ("world", 10, 20),
        }
        result = check_bounty_progress(p)
        assert result is not None
        assert result["done"] is True

    def test_escort_not_at_destination(self):
        p = make_player()
        p.map_id = "world"
        p.px = 5
        p.py = 5
        p.active_bounty = {
            "id": "b6",
            "type": "押送",
            "requires": {"move_to": "市口"},
            "_target_pos": ("world", 10, 20),
        }
        result = check_bounty_progress(p)
        assert result is not None
        assert result["done"] is False
        assert "途中" in result["reason"]

    def test_escort_no_target_pos_fallback_match(self):
        p = make_player()
        p.map_id = "world"
        p.last_move_map_id = "world"
        p.active_bounty = {
            "id": "b7",
            "type": "押送",
            "requires": {"move_to": "world"},
        }
        result = check_bounty_progress(p)
        assert result is not None
        assert result["done"] is True

    def test_escort_no_target_pos_fallback_no_match(self):
        p = make_player()
        p.map_id = "world"
        p.last_move_map_id = None
        p.active_bounty = {
            "id": "b8",
            "type": "押送",
            "requires": {"move_to": "other_map"},
        }
        result = check_bounty_progress(p)
        assert result is not None
        assert result["done"] is False

    def test_retrieve_has_item(self):
        p = make_player()
        p.inventory = {"旧信物": 1}
        p.active_bounty = {
            "id": "b9",
            "type": "寻回",
            "requires": {"have_item": "旧信物"},
        }
        result = check_bounty_progress(p)
        assert result is not None
        assert result["done"] is True
        assert "旧信物" in result["reason"]

    def test_retrieve_no_item(self):
        p = make_player()
        p.inventory = {}
        p.active_bounty = {
            "id": "b10",
            "type": "寻回",
            "requires": {"have_item": "旧信物"},
        }
        result = check_bounty_progress(p)
        assert result is not None
        assert result["done"] is False
        assert "尚未获得" in result["reason"]

    def test_capture_keyword_case_insensitive(self):
        p = make_player()
        p.active_bounty = {
            "id": "b11",
            "type": "缉拿",
            "requires": {"talk_to_npc": "npc_a", "ask_about": "逃犯下落"},
        }
        p.last_talk_npc_id = "npc_a"
        p.last_talk_message = "我问你逃犯下落如何"
        with patch("backend.systems.bounty_board.NPCS", {"npc_a": {"name": "NPC甲"}}):
            result = check_bounty_progress(p)
        assert result["done"] is True


class TestFormatBountyBoard:
    def test_empty_bounties(self):
        p = make_player()
        p.bounties = []
        assert format_bounty_board(p) == ""

    def test_none_bounties(self):
        p = make_player()
        p.bounties = None
        assert format_bounty_board(p) == ""

    def test_single_bounty(self):
        p = make_player()
        p.bounties = [
            {
                "type": "缉拿",
                "title": "缉拿逃犯张三",
                "desc": "衙门通缉张三",
                "reward": {"coins": 200, "rep": {"yamen": 2}},
            }
        ]
        with patch("backend.systems.bounty_board.FACTIONS", {"yamen": "衙门"}):
            result = format_bounty_board(p)
        assert "悬赏榜" in result
        assert "缉拿" in result
        assert "200文" in result
        assert "衙门声望+2" in result

    def test_multiple_bounties(self):
        p = make_player()
        p.bounties = [
            {
                "type": "缉拿",
                "title": "缉拿逃犯",
                "desc": "A" * 80,
                "reward": {"coins": 100},
            },
            {
                "type": "寻回",
                "title": "寻回失物",
                "desc": "B" * 40,
                "reward": {"coins": 50},
            },
        ]
        result = format_bounty_board(p)
        assert "缉拿" in result
        assert "寻回" in result

    def test_bounty_desc_truncated(self):
        p = make_player()
        long_desc = "X" * 200
        p.bounties = [
            {
                "type": "缉拿",
                "title": "测试",
                "desc": long_desc,
                "reward": {"coins": 100},
            }
        ]
        result = format_bounty_board(p)
        for line in result.split("\n"):
            if "测试" in line:
                assert len(line) < len(long_desc) + 30

    def test_bounty_no_coins(self):
        p = make_player()
        p.bounties = [
            {
                "type": "打探",
                "title": "打探消息",
                "desc": "打听虚实",
                "reward": {"rep": {"caobang": 1}},
            }
        ]
        with patch("backend.systems.bounty_board.FACTIONS", {"caobang": "漕帮"}):
            result = format_bounty_board(p)
        assert "漕帮声望+1" in result


class TestRefreshBounties:
    @patch("backend.systems.bounty_board.generate_bounties", return_value=[{"id": "b1"}])
    @patch("backend.systems.bounty_board.random.randint", return_value=3)
    def test_refresh_after_interval(self, mock_rand, mock_gen):
        p = make_player()
        p.world_day = 10
        p.last_bounty_refresh_day = 0
        refresh_bounties(p)
        assert p.bounties == [{"id": "b1"}]
        assert p.last_bounty_refresh_day == 10

    def test_no_refresh_within_interval(self):
        p = make_player()
        p.world_day = 1
        p.last_bounty_refresh_day = 0
        p.bounties = [{"id": "old"}]
        refresh_bounties(p)
        assert p.bounties == [{"id": "old"}]

    def test_no_refresh_same_day(self):
        p = make_player()
        p.world_day = 2
        p.last_bounty_refresh_day = 2
        p.bounties = [{"id": "old"}]
        refresh_bounties(p)
        assert p.bounties == [{"id": "old"}]

    @patch("backend.systems.bounty_board.generate_bounties", return_value=[{"id": "new"}])
    @patch("backend.systems.bounty_board.random.randint", return_value=2)
    def test_refresh_with_none_last_day(self, mock_rand, mock_gen):
        p = make_player()
        p.world_day = 5
        p.last_bounty_refresh_day = None
        refresh_bounties(p)
        assert p.bounties == [{"id": "new"}]

    @patch("backend.systems.bounty_board.generate_bounties", return_value=[])
    @patch("backend.systems.bounty_board.random.randint", return_value=2)
    def test_refresh_generates_empty(self, mock_rand, mock_gen):
        p = make_player()
        p.world_day = 10
        p.last_bounty_refresh_day = 0
        refresh_bounties(p)
        assert p.bounties == []


# ════════════════════════════════════════════════════════════════
#  perception — hazard_roll_death / rest_at_location / relevant_events_for / world_status_block / recent_events_block
# ════════════════════════════════════════════════════════════════


class TestHazardRollDeath:
    @patch("random.random", return_value=1.0)
    @patch("backend.systems.perception.is_night", return_value=False)
    @patch("backend.systems.perception.tile_at", return_value="I")
    def test_inn_no_death_high_roll(self, mock_tile, mock_night, mock_rand):
        p = make_player()
        result = hazard_roll_death(p)
        assert result is None

    @patch("random.random", return_value=0.0)
    @patch("backend.systems.perception.is_night", return_value=False)
    @patch("backend.systems.perception.tile_at", return_value="I")
    def test_inn_death_low_roll(self, mock_tile, mock_night, mock_rand):
        p = make_player()
        p.coins = 50
        result = hazard_roll_death(p)
        assert result is not None
        assert "蒙汗药" in result

    @patch("random.random", return_value=0.0)
    @patch("backend.systems.perception.is_night", return_value=False)
    @patch("backend.systems.perception.tile_at", return_value="&")
    def test_bush_death(self, mock_tile, mock_night, mock_rand):
        p = make_player()
        result = hazard_roll_death(p)
        assert result is not None
        assert "剪径" in result

    @patch("random.random", return_value=0.0)
    @patch("backend.systems.perception.is_night", return_value=False)
    @patch("backend.systems.perception.tile_at", return_value="~")
    def test_water_death(self, mock_tile, mock_night, mock_rand):
        p = make_player()
        result = hazard_roll_death(p)
        assert result is not None
        assert "水鬼" in result

    @patch("backend.systems.perception.tile_at", return_value=".")
    def test_safe_tile_no_death(self, mock_tile):
        p = make_player()
        result = hazard_roll_death(p)
        assert result is None

    @patch("random.random", return_value=0.0)
    @patch("backend.systems.perception.is_night", return_value=True)
    @patch("backend.systems.perception.tile_at", return_value="I")
    def test_night_multiplier_increases_prob(self, mock_tile, mock_night, mock_rand):
        p = make_player()
        p.coins = 50
        result = hazard_roll_death(p)
        assert result is not None

    @patch("random.random", return_value=0.0)
    @patch("backend.systems.perception.is_night", return_value=False)
    @patch("backend.systems.perception.tile_at", return_value="I")
    def test_poor_coin_mult(self, mock_tile, mock_night, mock_rand):
        p = make_player()
        p.coins = 10
        result = hazard_roll_death(p)
        assert result is not None

    @patch("random.random", return_value=0.0)
    @patch("backend.systems.perception.is_night", return_value=False)
    @patch("backend.systems.perception.tile_at", return_value="&")
    def test_lulin_rep_protect(self, mock_tile, mock_night, mock_rand):
        p = make_player()
        p.reputation = {"lulin": 25}
        result = hazard_roll_death(p)
        assert result is not None

    @patch("random.random", return_value=0.0)
    @patch("backend.systems.perception.is_night", return_value=False)
    @patch("backend.systems.perception.tile_at", return_value="~")
    def test_caobang_rep_protect(self, mock_tile, mock_night, mock_rand):
        p = make_player()
        p.reputation = {"caobang": 25}
        result = hazard_roll_death(p)
        assert result is not None

    @patch("random.random", return_value=0.0)
    @patch("backend.systems.perception.is_night", return_value=False)
    @patch("backend.systems.perception.tile_at", return_value="I")
    def test_rich_coin_mult(self, mock_tile, mock_night, mock_rand):
        p = make_player()
        p.coins = 500
        result = hazard_roll_death(p)
        assert result is not None

    @patch("random.random", return_value=0.0)
    @patch("backend.systems.perception.is_night", return_value=False)
    @patch("backend.systems.perception.tile_at", return_value="I")
    def test_bad_weather_rain(self, mock_tile, mock_night, mock_rand):
        p = make_player()
        p.weather = "骤雨"
        p.coins = 50
        result = hazard_roll_death(p)
        assert result is not None

    @patch("random.random", return_value=0.0)
    @patch("backend.systems.perception.is_night", return_value=False)
    @patch("backend.systems.perception.tile_at", return_value="I")
    def test_bad_weather_fog(self, mock_tile, mock_night, mock_rand):
        p = make_player()
        p.weather = "重雾"
        p.coins = 50
        result = hazard_roll_death(p)
        assert result is not None


class TestRestAtLocation:
    @patch("backend.systems.perception.tile_at", return_value="T")
    @patch("backend.systems.time_weather.advance_clock")
    @patch("backend.systems.perception.apply_vigor_delta", return_value=25)
    @patch("backend.systems.perception.apply_spirit_delta", return_value=20)
    @patch("backend.systems.reputation.push_event")
    def test_rest_at_inn(self, mock_push, mock_spirit, mock_vigor, mock_clock, mock_tile):
        p = make_player()
        p.vigor = 50
        p.vigor_max = 100
        p.spirit = 50
        p.spirit_max = 100
        p.sleep_debt = 10
        result = rest_at_location(p)
        assert result["ok"] is True
        assert result["delta"]["vigor"] > 0
        assert result["delta"]["spirit"] > 0
        mock_clock.assert_called_once()

    @patch("backend.systems.perception.tile_at", return_value=".")
    def test_rest_not_allowed(self, mock_tile):
        p = make_player()
        result = rest_at_location(p)
        assert result["ok"] is False
        assert result["delta"]["vigor"] == 0

    @patch("backend.systems.perception.tile_at", return_value="T")
    @patch("backend.systems.time_weather.advance_clock")
    @patch("backend.systems.reputation.push_event")
    def test_rest_already_full(self, mock_push, mock_clock, mock_tile):
        p = make_player()
        p.vigor = 100
        p.vigor_max = 100
        p.spirit = 100
        p.spirit_max = 100
        p.sleep_debt = 0
        result = rest_at_location(p)
        assert result["ok"] is True
        assert result["delta"]["vigor"] == 0
        assert result["delta"]["spirit"] == 0

    @patch("backend.systems.perception.tile_at", return_value="@")
    @patch("backend.systems.time_weather.advance_clock")
    @patch("backend.systems.perception.apply_vigor_delta", return_value=10)
    @patch("backend.systems.perception.apply_spirit_delta", return_value=10)
    @patch("backend.systems.reputation.push_event")
    def test_rest_at_temple(self, mock_push, mock_spirit, mock_vigor, mock_clock, mock_tile):
        p = make_player()
        p.vigor = 50
        p.vigor_max = 100
        p.spirit = 50
        p.spirit_max = 100
        p.sleep_debt = 5
        result = rest_at_location(p)
        assert result["ok"] is True
        assert "佛寺" in result["note"]

    @patch("backend.systems.perception.tile_at", return_value="I")
    def test_rest_at_inn_black_shop(self, mock_tile):
        p = make_player()
        result = rest_at_location(p)
        assert result["ok"] is False
        assert "黑店" in result["reason"]

    @patch("backend.systems.perception.tile_at", return_value="T")
    @patch("backend.systems.time_weather.advance_clock")
    @patch("backend.systems.perception.apply_vigor_delta", return_value=25)
    @patch("backend.systems.perception.apply_spirit_delta", return_value=20)
    @patch("backend.systems.reputation.push_event")
    def test_rest_reduces_sleep_debt(self, mock_push, mock_spirit, mock_vigor, mock_clock, mock_tile):
        p = make_player()
        p.vigor = 50
        p.vigor_max = 100
        p.spirit = 50
        p.spirit_max = 100
        p.sleep_debt = 10
        result = rest_at_location(p)
        assert result["ok"] is True
        assert p.sleep_debt < 10


class TestRelevantEventsFor:
    def test_no_events(self):
        p = make_player()
        p.events = []
        result = relevant_events_for(p, "jiang")
        assert result == []

    def test_with_events_jiang(self):
        p = make_player()
        p.events = [
            {"text": "event1", "scope": "near"},
            {"text": "event2", "scope": "world"},
        ]
        result = relevant_events_for(p, "jiang", k=3)
        assert len(result) == 2

    def test_k_limit(self):
        p = make_player()
        p.events = [{"text": f"ev{i}"} for i in range(10)]
        result = relevant_events_for(p, "jiang", k=3)
        assert len(result) == 3

    def test_prioritized_by_faction(self):
        p = make_player()
        p.events = [
            {"text": "general event", "actor": "someone"},
            {"text": "faction event", "actor": "衙门差事"},
        ]
        with patch("backend.systems.perception.NPC_FACTION", {"npc_a": "yamen"}), \
             patch("backend.systems.perception.NPCS", {"npc_a": {"cell": ("world",)}}), \
             patch("backend.systems.perception.FACTIONS", {"yamen": "衙门"}):
            result = relevant_events_for(p, "npc_a", k=4)
        assert len(result) == 2
        assert result[0]["text"] == "faction event"


class TestWorldStatusBlock:
    def test_basic_output(self):
        p = make_player()
        p.world_day = 5
        p.world_shichen = 4
        p.weather = "晴"
        p.coins = 100
        p.inventory = {"干粮": 2}
        p.reputation = {"yamen": 3}
        with patch("backend.systems.perception.shichen_name", return_value="辰"), \
             patch("backend.systems.perception.shichen_phase", return_value="朝"), \
             patch("backend.systems.perception.is_night", return_value=False), \
             patch("backend.systems.perception.FACTIONS", {"yamen": "衙门"}):
            result = world_status_block(p)
        assert "第 5 日" in result
        assert "辰" in result
        assert "晴" in result
        assert "100" in result

    def test_night_indicator(self):
        p = make_player()
        with patch("backend.systems.perception.shichen_name", return_value="子"), \
             patch("backend.systems.perception.shichen_phase", return_value="夜"), \
             patch("backend.systems.perception.is_night", return_value=True), \
             patch("backend.systems.perception.FACTIONS", {}):
            result = world_status_block(p)
        assert "(夜)" in result

    def test_empty_inventory(self):
        p = make_player()
        p.inventory = {}
        p.reputation = {}
        with patch("backend.systems.perception.shichen_name", return_value="辰"), \
             patch("backend.systems.perception.shichen_phase", return_value="朝"), \
             patch("backend.systems.perception.is_night", return_value=False):
            result = world_status_block(p)
        assert "身无长物" in result

    def test_reputation_line(self):
        p = make_player()
        p.reputation = {"yamen": 5, "lulin": -3}
        with patch("backend.systems.perception.shichen_name", return_value="辰"), \
             patch("backend.systems.perception.shichen_phase", return_value="朝"), \
             patch("backend.systems.perception.is_night", return_value=False), \
             patch("backend.systems.perception.FACTIONS", {"yamen": "衙门", "lulin": "绿林"}):
            result = world_status_block(p)
        assert "衙门+5" in result
        assert "绿林-3" in result


class TestRecentEventsBlock:
    def test_no_events(self):
        p = make_player()
        p.events = []
        result = recent_events_block(p, "jiang")
        assert result == ""

    def test_with_events(self):
        p = make_player()
        p.events = [
            {"text": "something happened", "shichen": "辰"},
        ]
        with patch("backend.systems.perception.relevant_events_for", return_value=p.events):
            result = recent_events_block(p, "jiang")
        assert "近日江湖事" in result
        assert "something happened" in result

    def test_multiple_events(self):
        p = make_player()
        evts = [
            {"text": f"event {i}", "shichen": "辰"}
            for i in range(3)
        ]
        with patch("backend.systems.perception.relevant_events_for", return_value=evts):
            result = recent_events_block(p, "jiang")
        assert result.count("·") == 3


# ════════════════════════════════════════════════════════════════
#  encounter — _is_wild / _build_encounter_context / _fallback_encounter / apply_encounter / format_encounter_perception_block
# ════════════════════════════════════════════════════════════════


class TestIsWild:
    @patch("backend.systems.encounter.is_safe_zone", return_value=False)
    def test_wild_area(self, mock_safe):
        p = make_player()
        assert _is_wild(p) is True

    @patch("backend.systems.encounter.is_safe_zone", return_value=True)
    def test_safe_area(self, mock_safe):
        p = make_player()
        assert _is_wild(p) is False


class TestBuildEncounterContext:
    @patch("backend.systems.encounter.tile_at", return_value=".")
    @patch("backend.systems.encounter.tile_atmosphere", return_value="荒野小径")
    @patch("backend.systems.encounter.is_night", return_value=False)
    @patch("backend.systems.encounter.shichen_name", return_value="辰")
    @patch("backend.systems.time_weather.shichen_phase", return_value="朝")
    @patch("backend.systems.encounter.MAPS", {"world": {"name": "江湖"}})
    @patch("backend.systems.core.npc_ids_for_player", return_value=[])
    def test_basic_context(self, mock_npcs, mock_phase, mock_sh, mock_night, mock_atm, mock_tile):
        p = make_player()
        p.rumors = []
        p.events = []
        p.reputation = {}
        p.inventory = {}
        result = _build_encounter_context(p)
        assert "世态" in result
        assert "江湖" in result

    @patch("backend.systems.encounter.tile_at", return_value=".")
    @patch("backend.systems.encounter.tile_atmosphere", return_value="荒野小径")
    @patch("backend.systems.encounter.is_night", return_value=True)
    @patch("backend.systems.encounter.shichen_name", return_value="子")
    @patch("backend.systems.time_weather.shichen_phase", return_value="夜")
    @patch("backend.systems.encounter.MAPS", {"world": {"name": "江湖"}})
    @patch("backend.systems.core.npc_ids_for_player", return_value=[])
    def test_night_context(self, mock_npcs, mock_phase, mock_sh, mock_night, mock_atm, mock_tile):
        p = make_player()
        p.rumors = []
        p.events = []
        p.reputation = {}
        p.inventory = {}
        result = _build_encounter_context(p)
        assert "夜" in result

    def test_context_with_npcs(self):
        p = make_player()
        p.rumors = []
        p.events = []
        p.reputation = {}
        p.inventory = {}
        with patch("backend.systems.encounter.tile_at", return_value="."), \
             patch("backend.systems.encounter.tile_atmosphere", return_value="荒野小径"), \
             patch("backend.systems.encounter.is_night", return_value=False), \
             patch("backend.systems.encounter.shichen_name", return_value="辰"), \
             patch("backend.systems.time_weather.shichen_phase", return_value="朝"), \
             patch("backend.systems.encounter.MAPS", {"world": {"name": "江湖"}}), \
             patch("backend.systems.core.npc_ids_for_player", return_value=["npc_a"]), \
             patch("backend.systems.encounter.NPCS", {"npc_a": {"name": "NPC甲", "short": "甲"}}):
            result = _build_encounter_context(p)
        assert "近处有人" in result

    @patch("backend.systems.encounter.tile_at", return_value=".")
    @patch("backend.systems.encounter.tile_atmosphere", return_value="荒野小径")
    @patch("backend.systems.encounter.is_night", return_value=False)
    @patch("backend.systems.encounter.shichen_name", return_value="辰")
    @patch("backend.systems.time_weather.shichen_phase", return_value="朝")
    @patch("backend.systems.encounter.MAPS", {"world": {"name": "江湖"}})
    @patch("backend.systems.core.npc_ids_for_player", return_value=[])
    def test_context_with_rumors(self, mock_npcs, mock_phase, mock_sh, mock_night, mock_atm, mock_tile):
        p = make_player()
        p.rumors = ["风闻甲", "风闻乙"]
        p.events = []
        p.reputation = {}
        p.inventory = {}
        result = _build_encounter_context(p)
        assert "最近风闻" in result

    @patch("backend.systems.encounter.tile_at", return_value=".")
    @patch("backend.systems.encounter.tile_atmosphere", return_value="荒野小径")
    @patch("backend.systems.encounter.is_night", return_value=False)
    @patch("backend.systems.encounter.shichen_name", return_value="辰")
    @patch("backend.systems.time_weather.shichen_phase", return_value="朝")
    @patch("backend.systems.encounter.MAPS", {"world": {"name": "江湖"}})
    @patch("backend.systems.core.npc_ids_for_player", return_value=[])
    def test_context_with_reputation(self, mock_npcs, mock_phase, mock_sh, mock_night, mock_atm, mock_tile):
        p = make_player()
        p.rumors = []
        p.events = []
        p.reputation = {"yamen": 5}
        p.inventory = {}
        with patch("backend.systems.encounter.FACTIONS", {"yamen": "衙门"}):
            result = _build_encounter_context(p)
        assert "声望" in result


class TestFallbackEncounter:
    @patch("backend.systems.encounter.is_night", return_value=False)
    @patch("backend.systems.encounter.tile_at", return_value=".")
    @patch("backend.systems.encounter.tile_atmosphere", return_value="荒野小径")
    @patch("backend.systems.encounter.MAPS", {"world": {"name": "江湖"}})
    def test_daytime_fallback(self, mock_atm, mock_tile, mock_night):
        p = make_player()
        result = _fallback_encounter(p)
        assert "scene" in result
        assert "scope" in result

    @patch("backend.systems.encounter.is_night", return_value=True)
    @patch("backend.systems.encounter.tile_at", return_value=".")
    @patch("backend.systems.encounter.tile_atmosphere", return_value="荒野小径")
    @patch("backend.systems.encounter.MAPS", {"world": {"name": "江湖"}})
    def test_night_fallback_has_extra_template(self, mock_atm, mock_tile, mock_night):
        p = make_player()
        result = _fallback_encounter(p)
        assert "scene" in result

    @patch("backend.systems.encounter.is_night", return_value=False)
    @patch("backend.systems.encounter.tile_at", return_value=".")
    @patch("backend.systems.encounter.tile_atmosphere", return_value="荒野小径")
    @patch("backend.systems.encounter.MAPS", {"world": {"name": "江湖"}})
    def test_fallback_returns_dict(self, mock_atm, mock_tile, mock_night):
        p = make_player()
        result = _fallback_encounter(p)
        assert isinstance(result, dict)
        assert "scene" in result
        assert "hint" in result
        assert "scope" in result


class TestApplyEncounter:
    @patch("backend.agents.game_state.get_or_init_mind")
    @patch("backend.systems.core.push_rumor")
    @patch("backend.systems.reputation.push_event")
    @patch("backend.systems.encounter.is_night", return_value=False)
    @patch("backend.systems.encounter.shichen_name", return_value="辰")
    @patch("backend.systems.encounter.MAPS", {"world": {"name": "江湖"}})
    @patch("backend.systems.encounter.NPCS", {})
    @patch("backend.systems.encounter.NPC_FACTION", {})
    @patch("backend.systems.encounter.FACTIONS", {})
    def test_apply_encounter_pushes_event(self, mock_sh, mock_night, mock_push, mock_rumor, mock_mind):
        p = make_player()
        p.world_tick = 10
        encounter = {"scene": "远处有人影", "hint": "可以打听", "scope": "near"}
        apply_encounter(p, encounter)
        mock_push.assert_called_once()
        assert p.last_dynamic_encounter_tick == 10

    @patch("backend.agents.game_state.get_or_init_mind")
    @patch("backend.systems.core.push_rumor")
    @patch("backend.systems.reputation.push_event")
    @patch("backend.systems.encounter.is_night", return_value=False)
    @patch("backend.systems.encounter.shichen_name", return_value="辰")
    @patch("backend.systems.encounter.MAPS", {"world": {"name": "江湖"}})
    @patch("backend.systems.encounter.NPCS", {})
    @patch("backend.systems.encounter.NPC_FACTION", {})
    @patch("backend.systems.encounter.FACTIONS", {})
    def test_apply_encounter_pushes_rumor_when_hint(self, mock_sh, mock_night, mock_push, mock_rumor, mock_mind):
        p = make_player()
        p.world_tick = 10
        encounter = {"scene": "远处有人影", "hint": "可以打听", "scope": "near"}
        apply_encounter(p, encounter)
        mock_rumor.assert_called_once()

    @patch("backend.agents.game_state.get_or_init_mind")
    @patch("backend.systems.core.push_rumor")
    @patch("backend.systems.reputation.push_event")
    @patch("backend.systems.encounter.is_night", return_value=False)
    @patch("backend.systems.encounter.shichen_name", return_value="辰")
    @patch("backend.systems.encounter.MAPS", {"world": {"name": "江湖"}})
    @patch("backend.systems.encounter.NPCS", {})
    @patch("backend.systems.encounter.NPC_FACTION", {})
    @patch("backend.systems.encounter.FACTIONS", {})
    def test_apply_encounter_no_rumor_without_hint(self, mock_sh, mock_night, mock_push, mock_rumor, mock_mind):
        p = make_player()
        p.world_tick = 10
        encounter = {"scene": "远处有人影", "hint": None, "scope": "near"}
        apply_encounter(p, encounter)
        mock_rumor.assert_not_called()

    @patch("backend.agents.game_state.get_or_init_mind")
    @patch("backend.systems.core.push_rumor")
    @patch("backend.systems.reputation.push_event")
    @patch("backend.systems.encounter.is_night", return_value=False)
    @patch("backend.systems.encounter.shichen_name", return_value="辰")
    @patch("backend.systems.encounter.MAPS", {"world": {"name": "江湖"}})
    @patch("backend.systems.encounter.NPCS", {})
    @patch("backend.systems.encounter.NPC_FACTION", {})
    @patch("backend.systems.encounter.FACTIONS", {})
    def test_apply_encounter_empty_scene_does_nothing(self, mock_sh, mock_night, mock_push, mock_rumor, mock_mind):
        p = make_player()
        encounter = {"scene": "", "hint": None, "scope": "near"}
        apply_encounter(p, encounter)
        mock_push.assert_not_called()

    @patch("backend.agents.game_state.get_or_init_mind")
    @patch("backend.systems.core.push_rumor")
    @patch("backend.systems.reputation.push_event")
    @patch("backend.systems.encounter.is_night", return_value=False)
    @patch("backend.systems.encounter.shichen_name", return_value="辰")
    @patch("backend.systems.encounter.MAPS", {"world": {"name": "江湖"}})
    @patch("backend.systems.encounter.NPCS", {"jiang": {"name": "风闻子", "short": "风闻", "cell": ("world",)}})
    @patch("backend.systems.encounter.NPC_FACTION", {})
    @patch("backend.systems.encounter.FACTIONS", {})
    def test_apply_encounter_injects_jiang_mind(self, mock_sh, mock_night, mock_push, mock_rumor, mock_mind):
        mock_mind_obj = MagicMock()
        mock_mind.return_value = mock_mind_obj
        p = make_player()
        p.world_tick = 10
        encounter = {"scene": "远处有人影", "hint": None, "scope": "near"}
        with patch("backend.memory.affective_memory_importance", return_value=7.0), \
             patch("backend.agents.brain.record_observation") as mock_brain_rec:
            apply_encounter(p, encounter)
            mock_brain_rec.assert_called()


class TestFormatEncounterPerceptionBlock:
    def test_no_perceptions(self):
        mind = MagicMock()
        mind.items = []
        result = format_encounter_perception_block(mind, "辰")
        assert result == ""

    def test_with_perception(self):
        import time as _time

        from backend.memory import Memory
        now = _time.time()
        m = Memory(
            id="test1",
            kind="observation",
            text="方才在江湖，我隐约察觉到一些动静：远处有人影",
            importance=5.0,
            created_day=1,
            created_shichen="辰",
            created_at=now,
            last_accessed=now,
        )
        mind = MagicMock()
        mind.items = [m]
        result = format_encounter_perception_block(mind, "辰")
        assert "隐约察觉" in result

    def test_non_observation_ignored(self):
        import time as _time

        from backend.memory import Memory
        now = _time.time()
        m = Memory(
            id="test2",
            kind="reflection",
            text="方才在江湖，我隐约察觉到一些动静：远处有人影",
            importance=5.0,
            created_day=1,
            created_shichen="辰",
            created_at=now,
            last_accessed=now,
        )
        mind = MagicMock()
        mind.items = [m]
        result = format_encounter_perception_block(mind, "辰")
        assert result == ""

    def test_old_perception_ignored(self):
        import time as _time

        from backend.memory import Memory
        old_time = _time.time() - 99999
        m = Memory(
            id="test3",
            kind="observation",
            text="方才在江湖，我隐约察觉到一些动静：远处有人影",
            importance=5.0,
            created_day=1,
            created_shichen="辰",
            created_at=old_time,
            last_accessed=old_time,
        )
        mind = MagicMock()
        mind.items = [m]
        result = format_encounter_perception_block(mind, "辰")
        assert result == ""


# ════════════════════════════════════════════════════════════════
#  npc_gossip — _gossip_key / _get_attitude / _get_relation_note / _prune_gossip_cache / _pick_recent_snippet / _generate_gossip_text / format_gossip_awareness_block
# ════════════════════════════════════════════════════════════════


class TestGossipKey:
    def test_sorted_order(self):
        assert _gossip_key("b", "a") == "a+b"

    def test_same_order(self):
        assert _gossip_key("a", "b") == "a+b"

    def test_identical(self):
        result = _gossip_key("x", "x")
        assert result == "x+x"

    def test_communicative(self):
        assert _gossip_key("npc_a", "npc_b") == _gossip_key("npc_b", "npc_a")


class TestGetAttitude:
    @patch("backend.systems.npc_gossip.NPC_RELATIONSHIPS", {
        "zhanggui": [{"target": "yaren", "attitude": "生意往来"}],
    })
    def test_found_attitude(self):
        att, mult = _get_attitude("zhanggui", "yaren")
        assert att == "生意往来"
        assert mult == 1.2

    @patch("backend.systems.npc_gossip.NPC_RELATIONSHIPS", {
        "zhanggui": [{"target": "yaren", "attitude": "挚交"}],
    })
    def test_best_friend_attitude(self):
        att, mult = _get_attitude("zhanggui", "yaren")
        assert att == "挚交"
        assert mult == 2.5

    @patch("backend.systems.npc_gossip.NPC_RELATIONSHIPS", {
        "zhanggui": [{"target": "yaren", "attitude": "势同水火"}],
    })
    def test_hostile_attitude(self):
        att, mult = _get_attitude("zhanggui", "yaren")
        assert att == "势同水火"
        assert mult == 0.1

    @patch("backend.systems.npc_gossip.NPC_RELATIONSHIPS", {
        "zhanggui": [],
    })
    def test_no_relationship(self):
        att, mult = _get_attitude("zhanggui", "unknown")
        assert att == "面熟"
        assert mult == 0.4

    @patch("backend.systems.npc_gossip.NPC_RELATIONSHIPS", {})
    def test_no_entry(self):
        att, mult = _get_attitude("nonexistent", "unknown")
        assert att == "面熟"


class TestGetRelationNote:
    @patch("backend.systems.npc_gossip.NPC_RELATIONSHIPS", {
        "zhanggui": [{"target": "yaren", "attitude": "生意往来", "note": "给牙人抽过水"}],
    })
    def test_found_note(self):
        assert _get_relation_note("zhanggui", "yaren") == "给牙人抽过水"

    @patch("backend.systems.npc_gossip.NPC_RELATIONSHIPS", {
        "zhanggui": [{"target": "yaren", "attitude": "生意往来"}],
    })
    def test_no_note_field(self):
        assert _get_relation_note("zhanggui", "yaren") == ""

    @patch("backend.systems.npc_gossip.NPC_RELATIONSHIPS", {})
    def test_no_relationship(self):
        assert _get_relation_note("zhanggui", "unknown") == ""


class TestPruneGossipCache:
    def test_no_prune_under_limit(self):
        from backend.systems import npc_gossip
        npc_gossip._last_gossip.clear()
        for i in range(10):
            npc_gossip._last_gossip[f"key_{i}"] = float(i)
        _prune_gossip_cache()
        assert len(npc_gossip._last_gossip) == 10
        npc_gossip._last_gossip.clear()

    def test_prune_over_limit(self):
        from backend.systems import npc_gossip
        npc_gossip._last_gossip.clear()
        for i in range(300):
            npc_gossip._last_gossip[f"key_{i}"] = float(i)
        _prune_gossip_cache()
        assert len(npc_gossip._last_gossip) <= 256
        npc_gossip._last_gossip.clear()

    def test_prune_keeps_recent(self):
        from backend.systems import npc_gossip
        npc_gossip._last_gossip.clear()
        for i in range(300):
            npc_gossip._last_gossip[f"key_{i}"] = float(i)
        _prune_gossip_cache()
        assert "key_299" in npc_gossip._last_gossip
        npc_gossip._last_gossip.clear()


class TestPickRecentSnippet:
    def test_empty_mind(self):
        mind = MagicMock()
        mind.recent_observations.return_value = []
        result = _pick_recent_snippet(mind)
        assert result == ""

    def test_with_observations(self):
        mind = MagicMock()
        m1 = MagicMock()
        m1.text = "看到了一些事情"
        mind.recent_observations.return_value = [m1]
        result = _pick_recent_snippet(mind)
        assert "看到了一些事情" in result

    def test_with_about_keyword(self):
        mind = MagicMock()
        m1 = MagicMock()
        m1.text = "普通观察"
        m2 = MagicMock()
        m2.text = "关于逃犯的消息"
        mind.recent_observations.return_value = [m1, m2]
        result = _pick_recent_snippet(mind, about="逃犯")
        assert "逃犯" in result

    def test_snippet_truncated(self):
        mind = MagicMock()
        m1 = MagicMock()
        m1.text = "X" * 200
        mind.recent_observations.return_value = [m1]
        result = _pick_recent_snippet(mind)
        assert len(result) <= 60


class TestGenerateGossipText:
    @patch("backend.systems.npc_gossip._get_relation_note", return_value="")
    @patch("backend.systems.npc_gossip._get_attitude", return_value=("交好", 2.0))
    @patch("backend.systems.npc_gossip._pick_recent_snippet", return_value="")
    @patch("backend.systems.npc_gossip.NPCS", {"npc_a": {"name": "甲"}, "npc_b": {"name": "乙"}})
    def test_basic_gossip(self, mock_snippet, mock_att, mock_note):
        mind_a = MagicMock()
        mind_b = MagicMock()
        obs_a, obs_b = _generate_gossip_text("npc_a", "npc_b", mind_a, mind_b)
        assert "甲" in obs_a or "乙" in obs_a
        assert "乙" in obs_b or "甲" in obs_b

    @patch("backend.systems.npc_gossip._get_relation_note", return_value="旧账未清")
    @patch("backend.systems.npc_gossip._get_attitude", return_value=("旧交", 1.8))
    @patch("backend.systems.npc_gossip._pick_recent_snippet", return_value="最近听说的事")
    @patch("backend.systems.npc_gossip.NPCS", {"npc_a": {"name": "甲"}, "npc_b": {"name": "乙"}})
    @patch("backend.systems.npc_gossip.random.random", return_value=0.0)
    def test_gossip_with_snippet_and_note(self, mock_rand, mock_snippet, mock_att, mock_note):
        mind_a = MagicMock()
        mind_b = MagicMock()
        obs_a, obs_b = _generate_gossip_text("npc_a", "npc_b", mind_a, mind_b)
        assert "闲聊" in obs_a
        assert "闲聊" in obs_b

    @patch("backend.systems.npc_gossip._get_relation_note", return_value="")
    @patch("backend.systems.npc_gossip._get_attitude", return_value=("互不招惹", 0.3))
    @patch("backend.systems.npc_gossip._pick_recent_snippet", return_value="")
    @patch("backend.systems.npc_gossip.NPCS", {"npc_a": {"name": "甲"}, "npc_b": {"name": "乙"}})
    def test_gossip_no_snippet(self, mock_snippet, mock_att, mock_note):
        mind_a = MagicMock()
        mind_b = MagicMock()
        obs_a, obs_b = _generate_gossip_text("npc_a", "npc_b", mind_a, mind_b)
        assert "闲聊" in obs_a


class TestFormatGossipAwarenessBlock:
    def test_no_gossip(self):
        mind = MagicMock()
        mind.recent_observations.return_value = []
        result = format_gossip_awareness_block(mind, "npc_a")
        assert result == ""

    def test_with_gossip(self):
        import time as _time

        from backend.memory import Memory
        now = _time.time()
        m = Memory(
            id="g1",
            kind="observation",
            text="与NPC乙闲聊，乙提到：最近有动静",
            importance=5.0,
            created_day=1,
            created_shichen="辰",
            created_at=now,
            last_accessed=now,
        )
        mind = MagicMock()
        mind.recent_observations.return_value = [m]
        result = format_gossip_awareness_block(mind, "npc_a")
        assert "闲话" in result
        assert "闲聊" in result

    def test_old_gossip_ignored(self):
        import time as _time

        from backend.memory import Memory
        old_time = _time.time() - 99999
        m = Memory(
            id="g2",
            kind="observation",
            text="与NPC乙闲聊，乙提到：最近有动静",
            importance=5.0,
            created_day=1,
            created_shichen="辰",
            created_at=old_time,
            last_accessed=old_time,
        )
        mind = MagicMock()
        mind.recent_observations.return_value = [m]
        result = format_gossip_awareness_block(mind, "npc_a")
        assert result == ""

    def test_non_gossip_observation_ignored(self):
        import time as _time

        from backend.memory import Memory
        now = _time.time()
        m = Memory(
            id="g3",
            kind="observation",
            text="路过市口，看到有人摆摊",
            importance=5.0,
            created_day=1,
            created_shichen="辰",
            created_at=now,
            last_accessed=now,
        )
        mind = MagicMock()
        mind.recent_observations.return_value = [m]
        result = format_gossip_awareness_block(mind, "npc_a")
        assert result == ""


# ════════════════════════════════════════════════════════════════
#  models/npc — format_npc_character_sheet
# ════════════════════════════════════════════════════════════════


class TestFormatNpcCharacterSheet:
    def test_empty_character(self):
        npc = {}
        result = format_npc_character_sheet(npc)
        assert result == ""

    def test_none_character(self):
        npc = {"character": None}
        result = format_npc_character_sheet(npc)
        assert result == ""

    def test_non_dict_character(self):
        npc = {"character": "not a dict"}
        result = format_npc_character_sheet(npc)
        assert result == ""

    def test_basic_character(self):
        npc = {"character": {"性格": "沉稳", "外貌": "高大"}}
        result = format_npc_character_sheet(npc)
        assert "人物底稿" in result
        assert "性格" in result
        assert "沉稳" in result
        assert "外貌" in result

    def test_voice_style(self):
        npc = {"character": {"声口": "文言腔调，喜用典故"}}
        result = format_npc_character_sheet(npc)
        assert "说话风格" in result
        assert "必须遵守" in result
        assert "文言腔调" in result

    def test_voice_with_other_fields(self):
        npc = {"character": {"声口": "粗犷直率", "性格": "豪爽"}}
        result = format_npc_character_sheet(npc)
        assert "说话风格" in result
        assert "性格" in result
        assert "豪爽" in result

    def test_empty_string_values_skipped(self):
        npc = {"character": {"性格": "沉稳", "备注": "   "}}
        result = format_npc_character_sheet(npc)
        assert "性格" in result
        assert "备注" not in result

    def test_empty_voice_skipped(self):
        npc = {"character": {"声口": "  ", "性格": "沉稳"}}
        result = format_npc_character_sheet(npc)
        assert "说话风格" not in result
        assert "性格" in result
