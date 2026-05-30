from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


import unittest
from unittest.mock import patch

from backend.services.talk_service import _assemble_messages, build_graceful_fallback


class TestBuildGracefulFallback(unittest.TestCase):
    @patch("backend.services.talk_service.random.choice", return_value="（似乎神游天外，一时未能回话……）")
    def test_returns_dict_with_visible_text_and_parsed(self, mock_choice):
        result = build_graceful_fallback("npc1", "timeout")
        self.assertIn("visible_text", result)
        self.assertIn("parsed", result)
        self.assertEqual(result["visible_text"], "（似乎神游天外，一时未能回话……）")

    @patch("backend.services.talk_service.random.choice", return_value="（忽被旁人打断，未及应答）")
    def test_is_fallback_true(self, mock_choice):
        result = build_graceful_fallback("npc1", "error")
        self.assertTrue(result["is_fallback"])

    @patch("backend.services.talk_service.random.choice", return_value="（那人低头想着心事，半晌才回过神来）")
    def test_parsed_has_visible_text(self, mock_choice):
        result = build_graceful_fallback("npc1", "fail")
        self.assertEqual(result["parsed"].visible_text, "（那人低头想着心事，半晌才回过神来）")


class TestAssembleMessages(unittest.TestCase):
    @patch("backend.services.talk_service.cached_system", side_effect=lambda x: x)
    def test_empty_history(self, mock_cached):
        msgs = _assemble_messages("static", "dynamic", [], "你好", "地图「测试」格坐标 (1,2)")
        self.assertEqual(msgs[0]["role"], "system")
        self.assertEqual(msgs[0]["content"], "static")
        self.assertEqual(msgs[1]["role"], "user")
        self.assertEqual(msgs[1]["content"], "dynamic")
        last = msgs[-1]
        self.assertEqual(last["role"], "user")
        self.assertIn("你好", last["content"])

    @patch("backend.services.talk_service.cached_system", side_effect=lambda x: x)
    def test_with_history(self, mock_cached):
        hist: list[dict[str, str | int]] = [
            {"user": "你好", "assistant": "你好啊"},
            {"user": "天气如何", "assistant": "尚可"},
        ]
        msgs = _assemble_messages("static", "dynamic", hist, "再见", "地图「测试」格坐标 (1,2)")
        user_inputs = [m for m in msgs if m["role"] == "user"]
        assistant_msgs = [m for m in msgs if m["role"] == "assistant"]
        self.assertEqual(len(assistant_msgs), 2)
        self.assertEqual(assistant_msgs[0]["content"], "你好啊")
        self.assertIn("<user_input>你好</user_input>", user_inputs[1]["content"])

    @patch("backend.services.talk_service.cached_system", side_effect=lambda x: x)
    def test_with_dynamic_text(self, mock_cached):
        msgs = _assemble_messages("static", "dynamic content here", [], "你好", "地图「测试」格坐标 (1,2)")
        dyn_msg = msgs[1]
        self.assertEqual(dyn_msg["role"], "user")
        self.assertEqual(dyn_msg["content"], "dynamic content here")

    @patch("backend.services.talk_service.cached_system", side_effect=lambda x: x)
    def test_without_dynamic_text(self, mock_cached):
        msgs = _assemble_messages("static", "", [], "你好", "地图「测试」格坐标 (1,2)")
        user_msgs = [m for m in msgs if m["role"] == "user"]
        self.assertEqual(len(user_msgs), 1)
        self.assertIn("你好", user_msgs[0]["content"])

    @patch("backend.services.talk_service.cached_system", side_effect=lambda x: x)
    def test_with_location(self, mock_cached):
        loc = "地图「长安」格坐标 (10,20)；性别：男。"
        msgs = _assemble_messages("static", "", [], "你好", loc)
        last = msgs[-1]
        self.assertTrue(last["content"].startswith(loc))


if __name__ == "__main__":
    unittest.main()
