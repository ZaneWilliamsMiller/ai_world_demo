from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.interactive.conftest import InteractiveClient, ResponseEvaluator


class TestEmotionalResponse(unittest.TestCase):
    client: InteractiveClient

    @classmethod
    def setUpClass(cls):
        cls.client = InteractiveClient()

    @classmethod
    def tearDownClass(cls):
        cls.client.teardown()

    def test_polite_favor_up(self):
        self.client.setup("zhanggui")
        try:
            r = self.client.talk("zhanggui", "多谢掌柜，有劳了")
            self.assertTrue(r.get("success"), f"请求失败: {r.get('error', '')}")
            self.assertTrue(
                ResponseEvaluator.check_favor_direction(r, expected_positive=True),
                f"礼貌对话好感应上升: favor_delta={r.get('delta', {}).get('favor', 0)}"
            )
        finally:
            self.client.teardown()

    def test_insult_favor_down(self):
        self.client.setup("bullya")
        try:
            r = self.client.talk("bullya", "滚开")
            self.assertTrue(r.get("success"), f"请求失败: {r.get('error', '')}")
            self.assertTrue(
                ResponseEvaluator.check_favor_direction(r, expected_positive=False),
                f"冒犯后好感应下降: favor_delta={r.get('delta', {}).get('favor', 0)}"
            )
        finally:
            self.client.teardown()

    def test_distress_response(self):
        self.client.setup("seng")
        try:
            r = self.client.talk("seng", "大师我走投无路")
            self.assertTrue(r.get("success"), f"请求失败: {r.get('error', '')}")
            self.assertTrue(
                ResponseEvaluator.check_nonempty_reply(r),
                "求助应得到非空回复"
            )
            text = r.get("visible_text", "")
            caring_words = ["施主", "贫僧", "佛", "善", "缘", "慈悲", "宽心", "莫急"]
            has_caring = any(w in text for w in caring_words)
            self.assertTrue(
                has_caring,
                f"知客僧应有关怀语: {text[:200]}"
            )
        finally:
            self.client.teardown()

    def test_trade_coin_change(self):
        self.client.setup("zhanggui")
        try:
            r = self.client.talk("zhanggui", "住店，来间上房")
            self.assertTrue(r.get("success"), f"请求失败: {r.get('error', '')}")
            self.assertTrue(
                ResponseEvaluator.check_nonempty_reply(r),
                "交易应得到非空回复"
            )
        finally:
            self.client.teardown()


if __name__ == "__main__":
    unittest.main()
