# pyright: reportCallIssue=false
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.models.llm_schema import NpcResponseSchema, RepDelta, StateUpdate
from backend.models.npc import format_npc_character_sheet
from pydantic import ValidationError


class TestNpcResponseSchema(unittest.TestCase):
    def test_defaults(self):
        s = NpcResponseSchema(visible_text="你好")
        self.assertEqual(s.visible_text, "你好")
        self.assertEqual(s.favor_delta, 0)
        self.assertEqual(s.coin_delta, 0)
        self.assertEqual(s.items_gain, [])
        self.assertEqual(s.items_lose, [])
        self.assertIsNone(s.rep_delta)
        self.assertEqual(s.events, [])
        self.assertIsNone(s.permadeath)
        self.assertIsNone(s.state_update)
        self.assertEqual(s.vigor_delta, 0)
        self.assertEqual(s.spirit_delta, 0)

    def test_favor_delta_range(self):
        NpcResponseSchema(visible_text="hi", favor_delta=3)
        NpcResponseSchema(visible_text="hi", favor_delta=-3)
        with self.assertRaises(ValidationError):
            NpcResponseSchema(visible_text="hi", favor_delta=4)
        with self.assertRaises(ValidationError):
            NpcResponseSchema(visible_text="hi", favor_delta=-4)

    def test_coin_delta_range(self):
        NpcResponseSchema(visible_text="hi", coin_delta=200)
        NpcResponseSchema(visible_text="hi", coin_delta=-200)
        with self.assertRaises(ValidationError):
            NpcResponseSchema(visible_text="hi", coin_delta=201)
        with self.assertRaises(ValidationError):
            NpcResponseSchema(visible_text="hi", coin_delta=-201)

    def test_visible_text_required(self):
        with self.assertRaises(ValidationError):
            NpcResponseSchema()


class TestStateUpdate(unittest.TestCase):
    def test_valid_range(self):
        s = StateUpdate(order=3, truth=-3, hope=0, chaos=1)
        self.assertEqual(s.order, 3)
        self.assertEqual(s.truth, -3)

    def test_out_of_range(self):
        with self.assertRaises(ValidationError):
            StateUpdate(order=4)
        with self.assertRaises(ValidationError):
            StateUpdate(truth=-4)
        with self.assertRaises(ValidationError):
            StateUpdate(hope=4)
        with self.assertRaises(ValidationError):
            StateUpdate(chaos=-4)


class TestRepDelta(unittest.TestCase):
    def test_valid_range(self):
        r = RepDelta(yamen=2, biaoju=-2, caobang=0, shuyuan=1, lulin=-1)
        self.assertEqual(r.yamen, 2)
        self.assertEqual(r.biaoju, -2)

    def test_out_of_range(self):
        with self.assertRaises(ValidationError):
            RepDelta(yamen=3)
        with self.assertRaises(ValidationError):
            RepDelta(biaoju=-3)
        with self.assertRaises(ValidationError):
            RepDelta(caobang=3)
        with self.assertRaises(ValidationError):
            RepDelta(shuyuan=-3)
        with self.assertRaises(ValidationError):
            RepDelta(lulin=3)


class TestFormatNpcCharacterSheet(unittest.TestCase):
    def test_with_voice(self):
        npc = {"character": {"声口": "文绉绉，爱引经据典", "性格": "沉稳"}}
        result = format_npc_character_sheet(npc)
        self.assertIn("说话风格", result)
        self.assertIn("文绉绉", result)
        self.assertIn("性格", result)
        self.assertIn("沉稳", result)

    def test_without_voice(self):
        npc = {"character": {"性格": "豪爽", "外貌": "高大"}}
        result = format_npc_character_sheet(npc)
        self.assertNotIn("说话风格", result)
        self.assertIn("性格", result)
        self.assertIn("外貌", result)

    def test_empty_character(self):
        npc = {"character": {}}
        result = format_npc_character_sheet(npc)
        self.assertEqual(result, "")

    def test_character_not_dict(self):
        npc = {"character": "not a dict"}
        result = format_npc_character_sheet(npc)
        self.assertEqual(result, "")

    def test_no_character_key(self):
        npc = {}
        result = format_npc_character_sheet(npc)
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
