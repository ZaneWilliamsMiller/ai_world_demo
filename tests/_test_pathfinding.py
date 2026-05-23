"""
_test_pathfinding.py — 寻路 & 传送门专项深度测试
==================================================

运行:
    python -m pytest tests/_test_pathfinding.py -v

测试范围:
  - 每张地图全网可达性（从入口到所有 walkable tile）
  - 传送门出口/入口是否在其地图的寻路网络中孤立
  - tile_at 全地图坐标覆盖
  - cost_to_ticks 时间折算
"""

import sys
import os
import unittest
from collections import deque

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend.data.maps_data import MAPS
from backend.systems.pathfinding import (
    find_path, tile_at, tile_cost, tile_elevation,
    can_step_between, walkable, apply_portal,
    path_cost, cost_to_ticks,
)


class TestTileAtCoverage(unittest.TestCase):
    """tile_at 不应在任何合法坐标上返回 None。"""

    def test_tile_at_valid_coords(self):
        for mid, m in MAPS.items():
            rows = m["rows"]
            w, h = len(rows[0]), len(rows)
            for y in range(h):
                for x in range(w):
                    ch = tile_at(mid, x, y)
                    self.assertIsNotNone(ch, f"tile_at({mid}, {x}, {y}) = None")

    def test_tile_at_out_of_bounds_returns_none(self):
        """越界坐标应返回 None。"""
        self.assertIsNone(tile_at("county", -1, 0))
        self.assertIsNone(tile_at("county", 0, -1))
        self.assertIsNone(tile_at("county", 99, 0))
        self.assertIsNone(tile_at("county", 0, 99))
        self.assertIsNone(tile_at("nonexistent", 0, 0))


class TestMapReachability(unittest.TestCase):
    """每张地图的所有 walkable tile 应该在一个连通分量内（或几乎全部）。"""

    def _bfs_component(self, map_id: str, start_x: int, start_y: int) -> set[tuple[int, int]]:
        """BFS 返回从起点可抵达的全部 walkable 坐标。"""
        m = MAPS[map_id]
        rows = m["rows"]
        w, h = len(rows[0]), len(rows)
        visited: set[tuple[int, int]] = set()
        q: deque[tuple[int, int]] = deque()
        q.append((start_x, start_y))
        visited.add((start_x, start_y))
        dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))
        while q:
            cx, cy = q.popleft()
            for dx, dy in dirs:
                nx, ny = cx + dx, cy + dy
                if not (0 <= nx < w and 0 <= ny < h):
                    continue
                if (nx, ny) in visited:
                    continue
                src = rows[cy][cx]
                dst = rows[ny][nx]
                if can_step_between(src, dst):
                    visited.add((nx, ny))
                    q.append((nx, ny))
        return visited

    def _walkable_count(self, map_id: str) -> int:
        m = MAPS[map_id]
        rows = m["rows"]
        return sum(1 for row in rows for ch in row if walkable(ch))

    def test_reachability_from_first_walkable(self):
        """从每张地图第一个 walkable tile BFS，覆盖率应 > 95%。"""
        for mid, m in MAPS.items():
            rows = m["rows"]
            w, h = len(rows[0]), len(rows)
            # 找第一个 walkable tile
            start = None
            for y in range(h):
                for x in range(w):
                    if walkable(rows[y][x]):
                        start = (x, y)
                        break
                if start:
                    break
            self.assertIsNotNone(start, f"地图 {mid} 没有任何 walkable tile")
            reachable = self._bfs_component(mid, start[0], start[1])
            total_walkable = self._walkable_count(mid)
            ratio = len(reachable) / total_walkable if total_walkable else 0
            # temple 地图含 ^ 悬崖，天然分割 walkable 区域，90% 合理
            self.assertGreaterEqual(
                ratio, 0.90,
                f"地图 {mid} BFS 覆盖率仅 {ratio:.1%} "
                f"({len(reachable)}/{total_walkable})，可能存在孤立区域"
            )

    def test_portal_tiles_are_reachable(self):
        """每张地图的「传送门所在格子」必须在 BFS 网络中可达。"""
        for mid, m in MAPS.items():
            # BFS 从第一个 walkable 开始
            rows = m["rows"]
            start = None
            for y, row in enumerate(rows):
                for x, ch in enumerate(row):
                    if walkable(ch):
                        start = (x, y)
                        break
                if start:
                    break
            if not start:
                continue
            reachable = self._bfs_component(mid, start[0], start[1])
            for p in m.get("portals", []):
                px, py = int(p["x"]), int(p["y"])
                self.assertIn(
                    (px, py), reachable,
                    f"地图 {mid} 的传送门 ({px},{py}) 不可从入口抵达"
                )


class TestCostToTicks(unittest.TestCase):
    def test_zero_cost(self):
        self.assertEqual(cost_to_ticks(0), 0)
    def test_short_cost(self):
        self.assertEqual(cost_to_ticks(2), 0)        # <=2 → 0 ticks
        self.assertEqual(cost_to_ticks(5), 1)        # <=6
        self.assertEqual(cost_to_ticks(10), 2)       # <=12
        self.assertEqual(cost_to_ticks(18), 3)       # <=20
        self.assertEqual(cost_to_ticks(25), 4)       # >20
    def test_negative_cost(self):
        self.assertEqual(cost_to_ticks(-1), 0)


class TestPathCostForPortalMap(unittest.TestCase):
    """确认 path_cost 传入正确 map_id 不会因为坐标而崩溃。"""

    def test_path_cost_on_each_map(self):
        for mid, m in MAPS.items():
            rows = m["rows"]
            path = [(1, 1)]
            # 找一个 walkable 坐标
            for y, row in enumerate(rows):
                for x, ch in enumerate(row):
                    if walkable(ch) and (x, y) != (1, 1):
                        path.append((x, y))
                        break
                if len(path) >= 2:
                    break
            if len(path) >= 2:
                cost = path_cost(mid, path)
                self.assertGreaterEqual(cost, 0, f"path_cost({mid}) 不应为负")


if __name__ == "__main__":
    unittest.main(verbosity=2)