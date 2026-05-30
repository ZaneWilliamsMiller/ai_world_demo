"""API Schema 契约测试——验证响应模型定义的完整性。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import unittest

from backend.api.schema import (
    DangerSense,
    HealthResponse,
    InitResponse,
    MoveResponse,
    PlayerPublic,
    StateResponse,
    TalkResponse,
)


class TestSchemaCompleteness(unittest.TestCase):
    def test_player_public_has_required_fields(self):
        fields = PlayerPublic.model_fields
        for field in [
            "map_id", "px", "py", "coins", "gender", "dead", "vigor", "spirit",
            "inventory", "reputation", "favor", "flags", "bounties",
            "world_day", "world_shichen", "weather",
        ]:
            self.assertIn(field, fields, f"PlayerPublic missing field: {field}")

    def test_init_response_has_required_fields(self):
        fields = InitResponse.model_fields
        for field in [
            "player", "npcs_here", "danger_sense", "maps", "npc_catalog",
            "factions", "map_locations", "events", "rumors",
        ]:
            self.assertIn(field, fields, f"InitResponse missing field: {field}")

    def test_player_public_instantiable_with_defaults(self):
        p = PlayerPublic()
        self.assertEqual(p.map_id, "world")
        self.assertEqual(p.vigor, 0)

    def test_danger_sense_model(self):
        ds = DangerSense(alert="前方有危险", scan="感知到动静")
        self.assertEqual(ds.alert, "前方有危险")
        self.assertEqual(ds.scan, "感知到动静")

    def test_all_routes_have_response_model(self):
        from backend.app import app
        missing = []
        for route in app.routes:
            if not hasattr(route, "methods"):
                continue
            if not hasattr(route, "response_model"):
                continue
            if route.path and ("stream" in route.path or "/stream" in route.path):
                continue
            if route.path and route.path == "/api/shutdown":
                continue
            if route.path and not route.path.startswith("/api/"):
                continue
            if route.response_model is None:
                missing.append(f"{route.methods} {route.path}")
        self.assertEqual(
            missing, [],
            f"以下端点缺少 response_model: {missing}",
        )

    def test_move_response_structure(self):
        fields = MoveResponse.model_fields
        for field in [
            "player", "npcs_here", "danger_sense", "path", "forced_encounter",
            "trap_state", "delta", "injuries", "atmosphere",
        ]:
            self.assertIn(field, fields, f"MoveResponse missing field: {field}")

    def test_talk_response_structure(self):
        fields = TalkResponse.model_fields
        for field in [
            "visible_text", "reply", "delta", "player", "npcs_here", "atmosphere",
        ]:
            self.assertIn(field, fields, f"TalkResponse missing field: {field}")

    def test_response_model_matches_routes(self):
        from backend.api.schema import (
            FinaleResponse,
            InitResponse,
            JournalResponse,
            MoveResponse,
            TalkResponse,
        )
        from backend.app import app
        expected = {
            "/api/health": HealthResponse,
            "/api/hello": InitResponse,
            "/api/move": MoveResponse,
            "/api/state/{player_id}": StateResponse,
            "/api/journal/{player_id}": JournalResponse,
            "/api/npc/talk": TalkResponse,
            "/api/finale": FinaleResponse,
        }
        route_map = {}
        for route in app.routes:
            if hasattr(route, "path") and hasattr(route, "response_model") and route.response_model:
                route_map[route.path] = route.response_model
        for path, expected_model in expected.items():
            self.assertIn(path, route_map, f"路由 {path} 未在 app.routes 中找到")
            self.assertEqual(
                route_map[path], expected_model,
                f"路由 {path} 的 response_model 应为 {expected_model.__name__}，实际为 {route_map[path].__name__}",
            )


if __name__ == "__main__":
    unittest.main()
