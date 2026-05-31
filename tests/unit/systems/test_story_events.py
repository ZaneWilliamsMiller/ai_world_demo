import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from conftest import make_player

from backend.data.npcs_data import NPCS
from backend.systems.story_events import (
    _fallback_story_events,
    format_bounty_context_for_prompt,
    format_story_events_for_prompt,
    generate_story_events,
    write_story_events_to_memory,
)


class TestFallbackStoryEvents:
    def test_returns_correct_count(self):
        p = make_player()
        events = _fallback_story_events(p, count=3)
        assert len(events) == 3

    def test_event_structure(self):
        p = make_player()
        events = _fallback_story_events(p, count=2)
        for evt in events:
            assert "id" in evt
            assert "title" in evt
            assert "desc" in evt
            assert "severity" in evt
            assert "involved_npcs" in evt
            assert "location" in evt
            assert "faction" in evt
            assert "bounty_hint" in evt

    def test_involved_npcs_valid(self):
        p = make_player()
        events = _fallback_story_events(p, count=5)
        valid_ids = set(NPCS.keys())
        for evt in events:
            for npc_id in evt.get("involved_npcs", []):
                assert npc_id in valid_ids, f"NPC '{npc_id}' not in NPCS"

    def test_severity_valid(self):
        p = make_player()
        events = _fallback_story_events(p, count=5)
        valid = {"minor", "moderate", "major"}
        for evt in events:
            assert evt["severity"] in valid, f"severity '{evt['severity']}' not valid"

    def test_bounty_hint_type_valid(self):
        p = make_player()
        events = _fallback_story_events(p, count=5)
        valid = {"缉拿", "押送", "打探", "寻回"}
        for evt in events:
            btype = evt["bounty_hint"]["type"]
            assert btype in valid, f"bounty_hint.type '{btype}' not valid"


class TestWriteStoryEventsToMemory:
    @patch("backend.systems.story_events.mem.record_observation", create=True)
    @patch("backend.systems.story_events.get_or_init_mind")
    def test_writes_to_involved_npc_memory(self, mock_get_mind, mock_record):
        p = make_player()
        mock_mind = MagicMock()
        mock_get_mind.return_value = mock_mind

        events = [{
            "id": "evt_0001_0",
            "title": "测试事件",
            "desc": "测试描述",
            "severity": "minor",
            "involved_npcs": ["zhanggui", "yaren"],
            "location": "市口",
            "faction": "yamen",
            "bounty_hint": {"type": "打探", "target_npc": "zhanggui", "target_item": "", "location": "市口"},
        }]
        write_story_events_to_memory(p, events)

        involved_npc_ids = set()
        for call_args in mock_get_mind.call_args_list:
            npc_arg = call_args[0][1]
            if npc_arg != "jiang":
                involved_npc_ids.add(npc_arg)
        assert "zhanggui" in involved_npc_ids or "yaren" in involved_npc_ids

    @patch("backend.systems.story_events.mem.record_observation", create=True)
    @patch("backend.systems.story_events.get_or_init_mind")
    def test_jiang_receives_all_events(self, mock_get_mind, mock_record):
        p = make_player()
        mock_mind = MagicMock()
        mock_get_mind.return_value = mock_mind

        events = [
            {
                "id": "evt_0001_0",
                "title": "事件一",
                "desc": "描述一",
                "severity": "minor",
                "involved_npcs": ["zhanggui"],
                "location": "市口",
                "faction": "yamen",
                "bounty_hint": {"type": "打探", "target_npc": "zhanggui", "target_item": "", "location": "市口"},
            },
            {
                "id": "evt_0002_1",
                "title": "事件二",
                "desc": "描述二",
                "severity": "major",
                "involved_npcs": ["yaren"],
                "location": "牙行",
                "faction": "biaoju",
                "bounty_hint": {"type": "缉拿", "target_npc": "yaren", "target_item": "", "location": "牙行"},
            },
        ]
        write_story_events_to_memory(p, events)

        jiang_mind_call_count = sum(
            1 for ca in mock_get_mind.call_args_list if ca[0][1] == "jiang"
        )
        assert jiang_mind_call_count == len(events)

    @patch("backend.systems.story_events.mem.record_observation", create=True)
    @patch("backend.systems.story_events.get_or_init_mind")
    def test_importance_matches_severity(self, mock_get_mind, mock_record):
        p = make_player()
        mock_mind = MagicMock()
        mock_get_mind.return_value = mock_mind

        events = [
            {
                "id": "evt_0001_0",
                "title": "大事件",
                "desc": "大描述",
                "severity": "major",
                "involved_npcs": ["zhanggui"],
                "location": "市口",
                "faction": "yamen",
                "bounty_hint": {"type": "缉拿", "target_npc": "zhanggui", "target_item": "", "location": "市口"},
            },
            {
                "id": "evt_0002_1",
                "title": "小事件",
                "desc": "小描述",
                "severity": "minor",
                "involved_npcs": ["yaren"],
                "location": "牙行",
                "faction": "biaoju",
                "bounty_hint": {"type": "打探", "target_npc": "yaren", "target_item": "", "location": "牙行"},
            },
        ]
        write_story_events_to_memory(p, events)

        major_importances = []
        non_major_importances = []
        for call_args in mock_record.call_args_list:
            kw = call_args[1]
            imp = kw.get("importance")
            if imp is not None:
                text = call_args[0][0] if call_args[0] else ""
                if "大描述" in text:
                    major_importances.append(imp)
                elif "小描述" in text:
                    non_major_importances.append(imp)

        if major_importances and non_major_importances:
            assert max(major_importances) > max(non_major_importances)


class TestFormatStoryEventsForPrompt:
    def test_empty_events_returns_empty(self):
        p = make_player()
        p.story_events = []
        result = format_story_events_for_prompt(p, npc_id="zhanggui")
        assert result == ""

    def test_protagonist_marked(self):
        p = make_player()
        p.story_events = [
            {
                "title": "盗窃案",
                "desc": "有人在市口行窃",
                "severity": "minor",
                "involved_npcs": ["zhanggui"],
                "location": "市口",
                "faction": "yamen",
                "bounty_hint": {"type": "寻回", "target_npc": "yaren", "target_item": "密信", "location": "市口"},
            }
        ]
        result = format_story_events_for_prompt(p, npc_id="zhanggui")
        assert "你与此事有关" in result

    def test_bystander_marked(self):
        p = make_player()
        p.story_events = [
            {
                "title": "盗窃案",
                "desc": "有人在市口行窃",
                "severity": "minor",
                "involved_npcs": ["yaren"],
                "location": "市口",
                "faction": "yamen",
                "bounty_hint": {"type": "寻回", "target_npc": "yaren", "target_item": "密信", "location": "市口"},
            }
        ]
        result = format_story_events_for_prompt(p, npc_id="zhanggui")
        assert "你与此事有关" not in result
        assert "盗窃案" in result


class TestFormatBountyContextForPrompt:
    def test_empty_bounties_returns_empty(self):
        p = make_player()
        p.active_bounty = None
        result = format_bounty_context_for_prompt(p, npc_id="zhanggui")
        assert result == ""

    def test_wanted_npc_gets_alert(self):
        p = make_player()
        p.active_bounty = {
            "title": "缉拿沈掌柜",
            "desc": "沈掌柜通匪潜逃",
            "type": "缉拿",
            "requires": {"talk_to_npc": "zhanggui"},
        }
        result = format_bounty_context_for_prompt(p, npc_id="zhanggui")
        assert "通缉" in result


class TestGenerateStoryEvents:
    def test_llm_success(self):
        p = make_player()
        fake_json = json.dumps({
            "events": [
                {
                    "title": "夜窃案",
                    "desc": "昨夜有人行窃",
                    "severity": "minor",
                    "involved_npcs": ["zhanggui"],
                    "location": "市口",
                    "faction": "yamen",
                    "bounty_hint": {"type": "寻回", "target_npc": "zhanggui", "target_item": "密信", "location": "市口"},
                }
            ]
        })

        with patch("backend.llm.client.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = fake_json
            result = asyncio.run(generate_story_events(p, count=1))
        assert len(result) >= 1
        assert result[0]["title"] == "夜窃案"

    def test_llm_failure_falls_back(self):
        p = make_player()

        with patch("backend.llm.client.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = RuntimeError("LLM unavailable")
            result = asyncio.run(generate_story_events(p, count=3))
        assert len(result) == 3
        for evt in result:
            assert "id" in evt
            assert "title" in evt

    def test_llm_invalid_json_falls_back(self):
        p = make_player()

        with patch("backend.llm.client.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "this is not valid json {{{"
            result = asyncio.run(generate_story_events(p, count=3))
        assert len(result) == 3
        for evt in result:
            assert "id" in evt
            assert "title" in evt
