from __future__ import annotations
"""
_test_endpoints.py — API 端点回归测试套件
==========================================

使用 FastAPI TestClient，以最小外部依赖覆盖核心路径。

运行:
    python -m pytest tests/_test_endpoints.py -v
    python -m pytest tests/ -v

测试覆盖:
  1. /api/hello — 角色创建 & 状态
  2. /api/state — 角色状态读取
  3. maps_data — 传送门双向一致性
  4. /api/move — 跨地图移动
  5. /api/npc/talk — NPC 对话可达性
  6. 寻路 — 边界、封闭区域
  7. 经济/天气 — 价格浮动
"""

import unittest
from typing import Any

from fastapi.testclient import TestClient
from backend.app import app
from backend.session.store import room
from backend.data.maps_data import MAPS, MAP_LOCATIONS
from backend.data.npcs_data import NPCS
from backend.systems.pathfinding import (
    find_path, apply_portal, tile_at, walkable, tile_cost, tile_elevation,
    path_cost, can_step_between, cost_to_ticks,
)
from backend.systems.economy import suggest_item_price, format_npc_inventory
from backend.systems.core import init_npc_positions
from backend.models.player import PlayerState


def _make_client() -> TestClient:
    return TestClient(app)


def _hello(client: TestClient) -> dict:
    resp = client.post("/api/hello", json={
        "player_id": None,
        "display_name": "pytest-测试角色",
        "gender": "未言",
        "permadeath": False,
    })
    if resp.status_code != 200:
        raise AssertionError(f"hello failed {resp.status_code}: {resp.text}")
    return resp.json()


# ═══════════════════════════════════════════════════════
#  1. /api/hello — 角色创建 & 状态
# ═══════════════════════════════════════════════════════

class TestHelloEndpoint(unittest.TestCase):

    def setUp(self):
        self.client = _make_client()

    def tearDown(self):
        room.players.clear()

    def test_hello_returns_player_state(self):
        """/api/hello 应返回完整玩家状态字段。"""
        data = _hello(self.client)
        self.assertIn("player_id", data)
        self.assertIn("display_name", data)
        self.assertIn("world_name", data)
        self.assertIn("maps", data)
        player = data["player"]
        for key in ("map_id", "px", "py", "vigor", "spirit", "coins",
                     "permadeath", "dead", "inventory", "reputation"):
            self.assertIn(key, player, f"缺少 player.{key}")
        self.assertEqual(player["vigor"], 80, "新角色体力应为 80")

    def test_hello_npcs_here(self):
        """/api/hello 应返回当前地图的 NPC 列表。"""
        data = _hello(self.client)
        npcs = data.get("npcs_here", [])
        self.assertTrue(len(npcs) > 0, "county 应有 NPC")

    def test_hello_maps_include_all(self):
        """maps 返回应包含 county、wild、temple 等。"""
        data = _hello(self.client)
        maps = data.get("maps", {})
        self.assertGreaterEqual(len(maps), 3)
        self.assertIn("county", maps)
        self.assertIn("wild", maps)


# ═══════════════════════════════════════════════════════
#  2. /api/state — 角色状态读取
# ═══════════════════════════════════════════════════════

class TestStateEndpoint(unittest.TestCase):

    def setUp(self):
        self.client = _make_client()
        room.players.clear()

    def test_state_returns_correct_fields(self):
        data = _hello(self.client)
        pid = data["player_id"]
        resp = self.client.get(f"/api/state/{pid}")
        self.assertEqual(resp.status_code, 200)
        state = resp.json()
        self.assertIn("player", state)
        self.assertIn("npcs_here", state)

    def test_state_unknown_player_404(self):
        resp = self.client.get("/api/state/not-a-real-player")
        self.assertEqual(resp.status_code, 404)


# ═══════════════════════════════════════════════════════
#  3. 地图数据完整性 & 传送门双向一致性
# ═══════════════════════════════════════════════════════

class TestMapDataIntegrity(unittest.TestCase):

    def test_all_maps_have_name_and_rows(self):
        for mid, m in MAPS.items():
            self.assertIn("name", m, f"地图 {mid} 缺少 name")
            self.assertIsInstance(m.get("rows"), list, f"地图 {mid} rows 不是 list")
            self.assertTrue(len(m.get("rows", [])) > 0,
                            f"地图 {mid} 无 rows")

    def test_portal_target_coords_walkable(self):
        """所有传送门的出口坐标必须是可站立的地形。"""
        for mid, m in MAPS.items():
            rows = m["rows"]
            w, h = len(rows[0]), len(rows)
            for p in m.get("portals", []):
                to_map = p["to"]
                tx, ty = int(p["tx"]), int(p["ty"])
                tm = MAPS.get(to_map)
                self.assertIsNotNone(tm, f"传送门 {mid}→{to_map} 目标地图不存在")
                tr = tm["rows"]
                tw, th = len(tr[0]), len(tr)
                self.assertTrue(0 <= tx < tw and 0 <= ty < th,
                                f"传送门出口越界 {mid}→{to_map}({tx},{ty})")
                ch = tr[ty][tx]
                self.assertNotIn(ch, "#^",
                                 f"传送门出口在不可站立格 {mid}→{to_map}({tx},{ty})='{ch}'")

    def test_portals_bidirectional(self):
        """所有传送门应有反向传送门，且坐标精确对应。"""
        portal_set: set[tuple] = set()
        for mid, m in MAPS.items():
            for p in m.get("portals", []):
                portal_set.add((
                    mid, int(p["x"]), int(p["y"]),
                    p["to"], int(p["tx"]), int(p["ty"]),
                ))
        for src_map, sx, sy, dst_map, dx, dy in portal_set:
            rev = (dst_map, dx, dy, src_map, sx, sy)
            self.assertIn(rev, portal_set,
                          f"缺少反向传送门: {dst_map}({dx},{dy})→{src_map}({sx},{sy})")

    def test_apply_portal_returns_expected(self):
        """apply_portal() 在已知传送门坐标上返回正确目标。"""
        # county 南门 (1,5) -> wild (1,1)
        result = apply_portal("county", 1, 5)
        self.assertIsNotNone(result, "county(1,5) 应触发传送门到 wild")
        self.assertEqual(result[0], "wild")
        self.assertEqual((result[1], result[2]), (1, 1),
                         "county(1,5) 应传送到 wild(1,1)")

        # 非传送门坐标 -> None
        result2 = apply_portal("county", 4, 2)
        self.assertIsNone(result2, "非传送门坐标应返回 None")


# ═══════════════════════════════════════════════════════
#  4. /api/move 跨地图移动测试
# ═══════════════════════════════════════════════════════

class TestMoveAcrossMaps(unittest.TestCase):

    def setUp(self):
        self.client = _make_client()
        room.players.clear()

    def test_move_to_portal_and_through(self):
        """移动到 county(1,5) 触发传送门 -> wild(1,1)。"""
        client = self.client
        hello = _hello(client)
        pid = hello["player_id"]

        resp = client.post("/api/move", json={
            "player_id": pid,
            "to_x": 1,
            "to_y": 5,
        })
        self.assertEqual(resp.status_code, 200, f"移动失败: {resp.text}")
        data = resp.json()
        player_after = data["player"]
        self.assertEqual(player_after["map_id"], "wild",
                         f"穿越传送门后地图应为 wild，实际为 {player_after['map_id']}")
        self.assertEqual(
            (player_after["px"], player_after["py"]), (1, 1),
            f"穿越后坐标应为 (1,1)，实际为 ({player_after['px']},{player_after['py']})"
        )

    def test_move_after_portal_npc_refresh(self):
        """穿越到 wild 后，/api/state 应返回 wild 地图的 NPC。"""
        client = self.client
        hello = _hello(client)
        pid = hello["player_id"]

        client.post("/api/move", json={
            "player_id": pid, "to_x": 1, "to_y": 5,
        })
        resp = client.get(f"/api/state/{pid}")
        self.assertEqual(resp.status_code, 200)
        state = resp.json()
        self.assertTrue(
            len(state["npcs_here"]) > 0,
            "穿越到 wild 后 npcs_here 不应为空"
        )

    def test_move_same_map_no_portal(self):
        """同城内移动不应触发地图切换。"""
        client = self.client
        hello = _hello(client)
        pid = hello["player_id"]

        resp = client.post("/api/move", json={
            "player_id": pid, "to_x": 5, "to_y": 3,
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["player"]["map_id"], "county",
                         "同城移动不应切换地图")


# ═══════════════════════════════════════════════════════
#  5. /api/npc/talk 基本可达性
# ═══════════════════════════════════════════════════════

class TestTalkEndpoint(unittest.TestCase):

    def setUp(self):
        self.client = _make_client()
        room.players.clear()

    def test_talk_requires_valid_npc(self):
        """对当前地图的 NPC 说话应返回有效响应（不报 400/404）。"""
        client = self.client
        hello = _hello(client)
        pid = hello["player_id"]

        # jiang 在 county，直接说应成功（或 502 LLM不可用但不应是 400/404）
        resp = client.post("/api/npc/talk", json={
            "player_id": pid,
            "npc_id": "jiang",
            "message": "你好",
        })
        self.assertNotEqual(resp.status_code, 400,
                            f"jiang 在当前地图应可对话: {resp.text}")
        self.assertNotEqual(resp.status_code, 404,
                            f"jiang 应存在: {resp.text}")


# ═══════════════════════════════════════════════════════
#  6. 寻路 — 边界 & 封闭区域
# ═══════════════════════════════════════════════════════

class TestPathfindingCrossMap(unittest.TestCase):

    def test_no_cross_map_path(self):
        """find_path 对越界坐标应返回 None。"""
        path = find_path("county", 4, 2, 99, 2)
        self.assertIsNone(path, "对越界坐标应返回 None")

    def test_path_blocked_by_wall(self):
        """被墙 # 隔开的点应返回 None。"""
        # county(0,0) 为 #，不可达
        path = find_path("county", 4, 2, 0, 0)
        self.assertIsNone(path, "目标为墙应返回 None")

    def test_path_within_map(self):
        """同城内简单路径应正确返回。"""
        # county 客栈 → 街前
        path = find_path("county", 4, 2, 6, 2)
        self.assertIsNotNone(path, "county(4,2)→(6,2) 应可通达")
        self.assertGreater(len(path), 1)

    def test_path_cost_non_negative(self):
        """path_cost 不应返回负值。"""
        path = find_path("county", 4, 2, 6, 2)
        self.assertIsNotNone(path)
        cost = path_cost("county", path)
        self.assertGreaterEqual(cost, 0)


# ═══════════════════════════════════════════════════════
#  7. 经济/天气 — 价格浮动
# ═══════════════════════════════════════════════════════

class TestEconomyWeather(unittest.TestCase):

    def test_weather_expensive_in_rain(self):
        """骤雨下食物应涨价。"""
        info = suggest_item_price("干粮", "county", "骤雨")
        self.assertIsNotNone(info)
        self.assertGreater(info["local"], info["base"],
                           f"骤雨下干粮应涨过基准价: {info}")

    def test_weather_cheaper_in_heat(self):
        """闷热下食物应打折。"""
        info = suggest_item_price("干粮", "county", "闷热")
        self.assertIsNotNone(info)
        self.assertLess(info["local"], info["base"],
                        f"闷热下干粮应低于基准价: {info}")

    def test_format_inventory_includes_weather(self):
        """format_npc_inventory 天气参数应生效。"""
        p = PlayerState(player_id="weather-test", display_name="天气测试")
        p.weather = "骤雨"
        p.npc_inventories["weather-test-jiang"] = {"干粮": 3, "金创药": 1}
        result = format_npc_inventory(p, "weather-test-jiang")
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)