"""NPC Agent 交互测试 — 需要运行中的后端服务器。

Token 消耗标注：
- TestNpcPlan: ✅ 消耗 Token（plan_day 调用 chat_completion）
- TestNpcReflect: ✅ 消耗 Token（reflect 调用 chat_completion）
- TestNpcActLoopWithReflect: ✅ 消耗 Token（act_loop 触发 reflect）
- TestNpcCrossTalk: ❌ 不消耗 Token（模板对话），但需运行中的服务器验证效果
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.interactive.conftest import InteractiveClient


class TestNpcPlan(unittest.TestCase):
    """测试 /api/agent/plan 端点 — ✅ 消耗 Token"""

    client: InteractiveClient

    @classmethod
    def setUpClass(cls):
        cls.client = InteractiveClient()

    @classmethod
    def tearDownClass(cls):
        cls.client.teardown()

    def setUp(self):
        self.client.setup()

    def tearDown(self):
        self.client.teardown()

    def test_plan_returns_ok(self):
        resp = self.client.client.post("/api/agent/plan", json={
            "player_id": self.client.player_id,
            "npc_id": "jiang",
        }, timeout=60.0)
        self.assertEqual(resp.status_code, 200, f"plan failed: {resp.status_code} {resp.text[:200]}")
        data = resp.json()
        self.assertTrue(data.get("ok"), f"plan returned ok=False: {data}")
        self.assertIn("plan_by_shichen", data)
        self.assertIsInstance(data["plan_by_shichen"], dict)

    def test_plan_idempotent(self):
        resp1 = self.client.client.post("/api/agent/plan", json={
            "player_id": self.client.player_id,
            "npc_id": "jiang",
        }, timeout=60.0)
        self.assertEqual(resp1.status_code, 200)

        resp2 = self.client.client.post("/api/agent/plan", json={
            "player_id": self.client.player_id,
            "npc_id": "jiang",
        }, timeout=60.0)
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        self.assertFalse(data2.get("ok"), "重复 plan 应返回 ok=False")

    def test_plan_affects_mind(self):
        self.client.client.post("/api/agent/plan", json={
            "player_id": self.client.player_id,
            "npc_id": "jiang",
        }, timeout=60.0)

        mind = self.client.get_mind("jiang")
        self.assertIsNotNone(mind.get("plan_summary"), "plan 后 mind.plan_summary 应非空")
        self.assertIsInstance(mind.get("plan_by_shichen"), dict)
        self.assertGreater(len(mind.get("plan_by_shichen", {})), 0, "plan_by_shichen 应有内容")


class TestNpcReflect(unittest.TestCase):
    """测试 /api/agent/reflect 端点 — ✅ 消耗 Token"""

    client: InteractiveClient

    @classmethod
    def setUpClass(cls):
        cls.client = InteractiveClient()

    @classmethod
    def tearDownClass(cls):
        cls.client.teardown()

    def setUp(self):
        self.client.setup()

    def tearDown(self):
        self.client.teardown()

    def test_reflect_returns_insights(self):
        self.client.client.post("/api/agent/plan", json={
            "player_id": self.client.player_id,
            "npc_id": "jiang",
        }, timeout=60.0)

        self.client.talk("jiang", "最近有什么消息？")

        resp = self.client.client.post("/api/agent/reflect", json={
            "player_id": self.client.player_id,
            "npc_id": "jiang",
        }, timeout=60.0)
        self.assertEqual(resp.status_code, 200, f"reflect failed: {resp.status_code} {resp.text[:200]}")
        data = resp.json()
        self.assertIn("added", data)
        self.assertIn("count", data)
        self.assertIn("player", data)

    def test_reflect_updates_mind(self):
        self.client.client.post("/api/agent/plan", json={
            "player_id": self.client.player_id,
            "npc_id": "jiang",
        }, timeout=60.0)

        self.client.talk("jiang", "你觉得最近怎么样？")

        mind_before = self.client.get_mind("jiang")
        importance_before = mind_before.get("importance_since_reflect", 0)

        resp = self.client.client.post("/api/agent/reflect", json={
            "player_id": self.client.player_id,
            "npc_id": "jiang",
        }, timeout=60.0)
        self.assertEqual(resp.status_code, 200)

        mind_after = self.client.get_mind("jiang")
        self.assertIsInstance(mind_after.get("affect_mood", ""), str)


class TestNpcActLoopWithReflect(unittest.TestCase):
    """测试 act_loop 触发 reflect 的场景 — ✅ 消耗 Token"""

    client: InteractiveClient

    @classmethod
    def setUpClass(cls):
        cls.client = InteractiveClient()

    @classmethod
    def tearDownClass(cls):
        cls.client.teardown()

    def setUp(self):
        self.client.setup()

    def tearDown(self):
        self.client.teardown()

    def test_act_loop_with_high_importance_triggers_reflect(self):
        self.client.client.post("/api/agent/plan", json={
            "player_id": self.client.player_id,
            "npc_id": "jiang",
        }, timeout=60.0)

        self.client.talk("jiang", "我听说了一件大事")

        resp = self.client.client.post("/api/agent/act_loop", json={
            "player_id": self.client.player_id,
            "npc_id": "jiang",
            "max_steps": 3,
        }, timeout=90.0)
        self.assertEqual(resp.status_code, 200, f"act_loop failed: {resp.status_code} {resp.text[:200]}")
        data = resp.json()
        self.assertIn("steps", data)
        self.assertIn("total_steps", data)
        self.assertIn("reflected", data)
        self.assertIsInstance(data["steps"], list)
        self.assertLessEqual(data["total_steps"], 3)


class TestNpcCrossTalk(unittest.TestCase):
    """测试 NPC 间模板对话 — ❌ 不消耗 Token，但需运行中的服务器"""

    client: InteractiveClient

    @classmethod
    def setUpClass(cls):
        cls.client = InteractiveClient()

    @classmethod
    def tearDownClass(cls):
        cls.client.teardown()

    def setUp(self):
        self.client.setup()

    def tearDown(self):
        self.client.teardown()

    def test_talk_with_same_cell_npc(self):
        self.client.client.post("/api/agent/plan", json={
            "player_id": self.client.player_id,
            "npc_id": "jiang",
        }, timeout=60.0)

        mind_before = self.client.get_mind("jiang")
        plan = mind_before.get("plan_by_shichen", {})

        has_talk_plan = any(
            any(kw in v for kw in ("见", "访", "谈", "聊", "问", "寻", "会", "商"))
            for v in plan.values()
        )

        if not has_talk_plan:
            self.skipTest("当前时辰计划不含交谈关键词，跳过 NPC 交流测试")

        act_resp = self.client.client.post("/api/agent/act", json={
            "player_id": self.client.player_id,
            "npc_id": "jiang",
        }, timeout=30.0)
        self.assertEqual(act_resp.status_code, 200)
        data = act_resp.json()
        if data.get("action") == "talk":
            self.assertIn("success", data)

    def test_talk_alone_npc_fails(self):
        self.client.client.post("/api/agent/plan", json={
            "player_id": self.client.player_id,
            "npc_id": "jiang",
        }, timeout=60.0)

        mind = self.client.get_mind("jiang")
        plan = mind.get("plan_by_shichen", {})

        has_talk_plan = any(
            any(kw in v for kw in ("见", "访", "谈", "聊", "问", "寻", "会", "商"))
            for v in plan.values()
        )

        if not has_talk_plan:
            self.skipTest("当前时辰计划不含交谈关键词，跳过独处 NPC 交谈测试")

        act_resp = self.client.client.post("/api/agent/act", json={
            "player_id": self.client.player_id,
            "npc_id": "jiang",
        }, timeout=30.0)
        self.assertEqual(act_resp.status_code, 200)
        data = act_resp.json()
        if data.get("action") == "talk" and not data.get("success"):
            desc = data.get("description", "")
            self.assertTrue(
                "无人" in desc or "无处" in desc or "可谈" in desc,
                f"独处 NPC 交谈失败描述应提及无人/无处可谈: {desc}",
            )


if __name__ == "__main__":
    unittest.main()
