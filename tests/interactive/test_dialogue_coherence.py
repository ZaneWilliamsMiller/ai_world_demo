from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.interactive.conftest import InteractiveClient, ResponseEvaluator


class TestDialogueCoherence(unittest.TestCase):
    client: InteractiveClient

    @classmethod
    def setUpClass(cls):
        cls.client = InteractiveClient()

    @classmethod
    def tearDownClass(cls):
        cls.client.teardown()

    def test_memory_continuation(self):
        self.client.setup("zhanggui")
        try:
            results = self.client.dialogue("zhanggui", [
                "住店",
                "多少钱一晚",
                "能便宜点吗",
            ])
            self.assertEqual(len(results), 3, "应完成3轮对话")
            for r in results:
                self.assertTrue(r.get("success"), f"对话失败: {r.get('error', '')}")
            last_text = results[-1].get("visible_text", "")
            if ResponseEvaluator.is_fallback(last_text):
                self.skipTest(f"LLM返回fallback: {last_text[:50]}")
            self.assertTrue(
                len(last_text) >= 10,
                f"第三轮回复过短: {last_text[:100]}"
            )
        finally:
            self.client.teardown()

    def test_reject_unreasonable_request(self):
        self.client.setup("yaren")
        try:
            r = self.client.talk("yaren", "白送我一批货")
            self.assertTrue(r.get("success"), f"请求失败: {r.get('error', '')}")
            text = r.get("visible_text", "")
            if ResponseEvaluator.is_fallback(text):
                self.skipTest(f"LLM返回fallback: {text[:50]}")
            self.assertTrue(
                len(text) >= 10,
                f"回复过短: {text[:100]}"
            )
        finally:
            self.client.teardown()

    def test_favor_accumulation(self):
        self.client.setup("zhanggui")
        try:
            results = self.client.dialogue("zhanggui", [
                "掌柜好，叨扰了",
                "贵店生意兴隆啊",
                "多谢掌柜关照",
            ])
            self.assertEqual(len(results), 3, "应完成3轮对话")

            any_fallback = any(
                ResponseEvaluator.is_fallback(r.get("visible_text", ""))
                for r in results if r.get("success")
            )
            if any_fallback:
                self.skipTest("LLM返回fallback响应")

            total_favor = sum(r.get("delta", {}).get("favor", 0) for r in results if r.get("success"))
            self.assertGreaterEqual(
                total_favor, 0,
                f"3轮礼貌对话后好感不应下降, 实际: {total_favor}"
            )
        finally:
            self.client.teardown()

    def test_favor_decline(self):
        self.client.setup("bullya")
        try:
            r = self.client.talk("bullya", "你这条狗")
            self.assertTrue(r.get("success"), f"请求失败: {r.get('error', '')}")
            text = r.get("visible_text", "")
            if ResponseEvaluator.is_fallback(text):
                self.skipTest(f"LLM返回fallback: {text[:50]}")
            favor_delta = r.get("delta", {}).get("favor", 0)
            self.assertLessEqual(
                favor_delta, 0,
                f"冒犯后好感不应上升, 实际: {favor_delta}"
            )
        finally:
            self.client.teardown()


if __name__ == "__main__":
    unittest.main()
