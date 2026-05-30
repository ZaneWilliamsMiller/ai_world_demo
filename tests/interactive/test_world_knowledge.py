from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.interactive.conftest import InteractiveClient, ResponseEvaluator


class TestWorldKnowledge(unittest.TestCase):
    client: InteractiveClient

    @classmethod
    def setUpClass(cls):
        cls.client = InteractiveClient()

    @classmethod
    def tearDownClass(cls):
        cls.client.teardown()

    def test_geography_knowledge(self):
        self.client.setup("jiang")
        try:
            r = self.client.talk("jiang", "青石县有哪些地方")
            self.assertTrue(r.get("success"), f"请求失败: {r.get('error', '')}")
            text = r.get("visible_text", "")
            if ResponseEvaluator.is_fallback(text):
                self.skipTest(f"LLM返回fallback: {text[:50]}")
            self.assertTrue(
                ResponseEvaluator.check_world_locations(text, min_count=1),
                f"风闻子应提及地名: {text[:200]}"
            )
        finally:
            self.client.teardown()

    def test_faction_knowledge(self):
        self.client.setup("jiang")
        try:
            r = self.client.talk("jiang", "县里谁说了算")
            self.assertTrue(r.get("success"), f"请求失败: {r.get('error', '')}")
            text = r.get("visible_text", "")
            if ResponseEvaluator.is_fallback(text):
                self.skipTest(f"LLM返回fallback: {text[:50]}")
            self.assertTrue(
                ResponseEvaluator.check_faction_knowledge(text),
                f"风闻子应提及势力: {text[:200]}"
            )
        finally:
            self.client.teardown()

    def test_price_awareness(self):
        self.client.setup("zhanggui")
        try:
            r = self.client.talk("zhanggui", "住一晚多少文")
            self.assertTrue(r.get("success"), f"请求失败: {r.get('error', '')}")
            text = r.get("visible_text", "")
            if ResponseEvaluator.is_fallback(text):
                self.skipTest(f"LLM返回fallback: {text[:50]}")
            has_number = bool(re.search(r'\d+', text))
            self.assertTrue(
                has_number or "文" in text or "钱" in text or "银" in text or "两" in text,
                f"掌柜应提及价格: {text[:200]}"
            )
        finally:
            self.client.teardown()

    def test_self_identity(self):
        self.client.setup("zhanggui")
        try:
            r = self.client.talk("zhanggui", "你是做什么的")
            self.assertTrue(r.get("success"), f"请求失败: {r.get('error', '')}")
            text = r.get("visible_text", "")
            if ResponseEvaluator.is_fallback(text):
                self.skipTest(f"LLM返回fallback: {text[:50]}")
            self.assertTrue(
                ResponseEvaluator.check_self_identity("zhanggui", text),
                f"掌柜应自我介绍: {text[:200]}"
            )
        finally:
            self.client.teardown()


if __name__ == "__main__":
    unittest.main()
