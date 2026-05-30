from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from conftest import make_player


def _mock_settings():
    s = MagicMock()
    s.llm_api_key = "test-key"
    s.llm_base_url = "http://localhost"
    s.shutdown_secret = "secret"
    s.cors_allow_origins = "*"
    s.enable_test_routes = False
    s.auto_save_interval_s = 300.0
    return s


@patch("backend.config.settings", _mock_settings())
@patch("backend.app.settings", _mock_settings())
@patch("backend.api.routes.settings", _mock_settings())
class TestHealthEndpoint(unittest.TestCase):
    def test_health_returns_200(self, *_):
        from backend.app import app
        client = TestClient(app)
        resp = client.get("/api/health")
        self.assertEqual(resp.status_code, 200)

    def test_health_status_ok(self, *_):
        from backend.app import app
        client = TestClient(app)
        resp = client.get("/api/health")
        data = resp.json()
        self.assertEqual(data["status"], "ok")


@patch("backend.config.settings", _mock_settings())
@patch("backend.app.settings", _mock_settings())
@patch("backend.api.routes.settings", _mock_settings())
class TestHelloEndpoint(unittest.TestCase):
    @patch("backend.api.player_routes.init_npc_inventories")
    @patch("backend.api.player_routes.init_npc_positions")
    @patch("backend.session.store.room")
    def test_hello_creates_player_returns_200(self, mock_room, mock_init_npc_pos, mock_init_npc_inv, *_):
        p = make_player()
        mock_room.get_or_create = AsyncMock(return_value=p)
        from backend.app import app
        client = TestClient(app)
        resp = client.post("/api/hello", json={"player_id": "test_player", "display_name": "测试侠客"})
        self.assertEqual(resp.status_code, 200)

    @patch("backend.api.player_routes.init_npc_inventories")
    @patch("backend.api.player_routes.init_npc_positions")
    @patch("backend.session.store.room")
    def test_hello_returns_player_id(self, mock_room, mock_init_npc_pos, mock_init_npc_inv, *_):
        p = make_player()
        mock_room.get_or_create = AsyncMock(return_value=p)
        from backend.app import app
        client = TestClient(app)
        resp = client.post("/api/hello", json={"player_id": "test_player", "display_name": "测试侠客"})
        data = resp.json()
        self.assertEqual(data["player_id"], "test_player")


@patch("backend.config.settings", _mock_settings())
@patch("backend.app.settings", _mock_settings())
@patch("backend.api.routes.settings", _mock_settings())
class TestStateEndpoint(unittest.TestCase):
    @patch("backend.session.store.room")
    def test_state_returns_player_state(self, mock_room, *_):
        p = make_player()
        mock_room.players = {"test_player": p}
        from backend.app import app
        client = TestClient(app)
        resp = client.get("/api/state/test_player")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["display_name"], "测试侠客")

    @patch("backend.session.store.room")
    def test_state_unknown_player_returns_404(self, mock_room, *_):
        mock_room.players = {}
        from backend.app import app
        client = TestClient(app)
        resp = client.get("/api/state/nonexistent")
        self.assertEqual(resp.status_code, 404)


@patch("backend.config.settings", _mock_settings())
@patch("backend.app.settings", _mock_settings())
@patch("backend.api.routes.settings", _mock_settings())
class TestSavesListEndpoint(unittest.TestCase):
    @patch("backend.api.save_routes.list_saves", return_value=["save1", "save2"])
    def test_saves_list_returns_200(self, mock_list_saves, *_):
        from backend.app import app
        client = TestClient(app)
        resp = client.get("/api/saves")
        self.assertEqual(resp.status_code, 200)

    @patch("backend.api.save_routes.list_saves", return_value=["save1", "save2"])
    def test_saves_list_returns_saves(self, mock_list_saves, *_):
        from backend.app import app
        client = TestClient(app)
        resp = client.get("/api/saves")
        data = resp.json()
        self.assertIn("saves", data)
        self.assertEqual(data["saves"], ["save1", "save2"])


@patch("backend.config.settings", _mock_settings())
@patch("backend.app.settings", _mock_settings())
@patch("backend.api.routes.settings", _mock_settings())
class TestMoveValidation(unittest.TestCase):
    @patch("backend.session.store.room")
    def test_move_invalid_player_id_returns_404(self, mock_room, *_):
        mock_room.players = {}
        from backend.app import app
        client = TestClient(app)
        resp = client.post("/api/move", json={"player_id": "nonexistent", "to_x": 10, "to_y": 10})
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
