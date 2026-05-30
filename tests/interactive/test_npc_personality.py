from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.interactive.conftest import InteractiveClient, ResponseEvaluator


class TestNpcPersonality(unittest.TestCase):
    client: InteractiveClient

    @classmethod
    def setUpClass(cls):
        cls.client = InteractiveClient()

    @classmethod
    def tearDownClass(cls):
        cls.client.teardown()

    def _talk(self, npc_id: str, message: str):
        self.client.setup(npc_id)
        try:
            return self.client.talk(npc_id, message)
        finally:
            self.client.teardown()

    def _assert_not_fallback(self, text: str, npc_id: str):
        if ResponseEvaluator.is_fallback(text):
            self.skipTest(f"LLM返回fallback响应，跳过: {text[:50]}")

    def test_zhanggui_voice(self):
        r = self._talk("zhanggui", "住店多少钱")
        self.assertTrue(r.get("success"), f"请求失败: {r.get('error', '')}")
        text = r.get("visible_text", "")
        self._assert_not_fallback(text, "zhanggui")
        self.assertTrue(
            ResponseEvaluator.check_voice("zhanggui", text),
            f"掌柜声口不符: {text[:100]}"
        )

    def test_yaren_shrewd(self):
        r = self._talk("yaren", "这批货什么价")
        self.assertTrue(r.get("success"), f"请求失败: {r.get('error', '')}")
        text = r.get("visible_text", "")
        self._assert_not_fallback(text, "yaren")
        self.assertTrue(
            ResponseEvaluator.check_voice("yaren", text),
            f"牙人声口不符: {text[:100]}"
        )

    def test_bullya_bureaucratic(self):
        r = self._talk("bullya", "我要告状")
        self.assertTrue(r.get("success"), f"请求失败: {r.get('error', '')}")
        text = r.get("visible_text", "")
        self._assert_not_fallback(text, "bullya")
        self.assertTrue(
            ResponseEvaluator.check_voice("bullya", text),
            f"皂隶声口不符: {text[:100]}"
        )

    def test_biaotout_concise(self):
        r = self._talk("biaotou", "能托镖吗")
        self.assertTrue(r.get("success"), f"请求失败: {r.get('error', '')}")
        text = r.get("visible_text", "")
        self._assert_not_fallback(text, "biaotou")
        self.assertTrue(
            ResponseEvaluator.check_voice("biaotou", text),
            f"镖头声口不符: {text[:100]}"
        )

    def test_seng_gentle(self):
        r = self._talk("seng", "大师求签")
        self.assertTrue(r.get("success"), f"请求失败: {r.get('error', '')}")
        text = r.get("visible_text", "")
        self._assert_not_fallback(text, "seng")
        self.assertTrue(
            ResponseEvaluator.check_voice("seng", text),
            f"知客僧声口不符: {text[:100]}"
        )

    def test_jiang_knowledgeable(self):
        r = self._talk("jiang", "最近有什么消息")
        self.assertTrue(r.get("success"), f"请求失败: {r.get('error', '')}")
        text = r.get("visible_text", "")
        self._assert_not_fallback(text, "jiang")
        self.assertTrue(
            ResponseEvaluator.check_voice("jiang", text),
            f"风闻子声口不符: {text[:100]}"
        )


if __name__ == "__main__":
    unittest.main()
