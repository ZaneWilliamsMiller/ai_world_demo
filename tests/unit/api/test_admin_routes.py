from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def _mock_settings():
    s = MagicMock()
    s.llm_api_key = "test-key"
    s.llm_base_url = "http://localhost"
    s.shutdown_secret = "secret"
    s.cors_allow_origins = "*"
    s.enable_test_routes = False
    s.auto_save_interval_s = 300.0
    return s


_SECRET = _mock_settings().shutdown_secret


def _mock_tracker():
    t = MagicMock()
    t.summary.return_value = {
        "total_calls": 10,
        "success_rate": 0.8,
        "avg_latency_ms": 120.5,
        "p50_latency_ms": 100.0,
        "p95_latency_ms": 250.0,
        "total_tokens_in": 5000,
        "total_tokens_out": 3000,
        "by_operation": {},
    }
    t.eval_summary.return_value = {
        "parse_success_rate": 0.9,
        "common_violations": [("missing_field", 3)],
        "by_npc": {"jiang": {"total": 5, "parse_failures": 1, "parse_failure_rate": 0.2}},
    }
    return t


def _mock_cb():
    cb = MagicMock()
    cb.stats = {
        "state": "closed",
        "total_requests": 100,
        "total_failures": 5,
        "rejected": 0,
        "recent_failures": 1,
        "last_failure_age_s": 30.0,
    }
    return cb


@patch("backend.api.admin_routes.settings", _mock_settings())
@patch("backend.api.routes.settings", _mock_settings())
@patch("backend.app.settings", _mock_settings())
@patch("backend.config.settings", _mock_settings())
class TestAdminAuth(unittest.TestCase):
    def test_no_secret_returns_403(self, *_):
        from backend.app import app
        client = TestClient(app)
        resp = client.get("/api/admin/metrics")
        self.assertEqual(resp.status_code, 403)

    def test_wrong_secret_returns_403(self, *_):
        from backend.app import app
        client = TestClient(app)
        resp = client.get("/api/admin/metrics", headers={"X-Admin-Secret": "wrong"})
        self.assertEqual(resp.status_code, 403)

    def test_correct_secret_returns_200(self, *_):
        from backend.app import app
        client = TestClient(app)
        tracker = _mock_tracker()
        cb = _mock_cb()
        with patch("backend.observability.tracker.get_tracker", return_value=tracker), \
             patch("backend.llm.circuit_breaker.get_circuit_breaker", return_value=cb):
            resp = client.get("/api/admin/metrics", headers={"X-Admin-Secret": _SECRET})
            self.assertEqual(resp.status_code, 200)


@patch("backend.api.admin_routes.settings", _mock_settings())
@patch("backend.api.routes.settings", _mock_settings())
@patch("backend.app.settings", _mock_settings())
@patch("backend.config.settings", _mock_settings())
class TestMetricsEndpoint(unittest.TestCase):
    def test_returns_summary_structure(self, *_):
        from backend.app import app
        client = TestClient(app)
        tracker = _mock_tracker()
        cb = _mock_cb()
        with patch("backend.observability.tracker.get_tracker", return_value=tracker), \
             patch("backend.llm.circuit_breaker.get_circuit_breaker", return_value=cb):
            resp = client.get("/api/admin/metrics", headers={"X-Admin-Secret": _SECRET})
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("total_calls", data)
            self.assertIn("success_rate", data)
            self.assertIn("avg_latency_ms", data)
            self.assertIn("circuit_breaker", data)


@patch("backend.api.admin_routes.settings", _mock_settings())
@patch("backend.api.routes.settings", _mock_settings())
@patch("backend.app.settings", _mock_settings())
@patch("backend.config.settings", _mock_settings())
class TestCircuitBreakerEndpoint(unittest.TestCase):
    def test_returns_cb_structure(self, *_):
        from backend.app import app
        client = TestClient(app)
        cb = _mock_cb()
        with patch("backend.llm.circuit_breaker.get_circuit_breaker", return_value=cb):
            resp = client.get("/api/admin/circuit_breaker", headers={"X-Admin-Secret": _SECRET})
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("state", data)
            self.assertIn("total_requests", data)
            self.assertIn("total_failures", data)


@patch("backend.api.admin_routes.settings", _mock_settings())
@patch("backend.api.routes.settings", _mock_settings())
@patch("backend.app.settings", _mock_settings())
@patch("backend.config.settings", _mock_settings())
class TestPlayersEndpoint(unittest.TestCase):
    @patch("backend.session.store.room")
    def test_returns_player_list(self, mock_room, *_):
        from backend.app import app
        p = MagicMock()
        p.display_name = "测试侠客"
        p.map_id = "world"
        p.px = 25
        p.py = 28
        p.dead = False
        p.ended = False
        mock_room.players = {"test_player": p}
        client = TestClient(app)
        resp = client.get("/api/admin/players", headers={"X-Admin-Secret": _SECRET})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("players", data)
        self.assertEqual(len(data["players"]), 1)
        player = data["players"][0]
        self.assertEqual(player["player_id"], "test_player")
        self.assertEqual(player["display_name"], "测试侠客")


@patch("backend.api.admin_routes.settings", _mock_settings())
@patch("backend.api.routes.settings", _mock_settings())
@patch("backend.app.settings", _mock_settings())
@patch("backend.config.settings", _mock_settings())
class TestNpcStatesEndpoint(unittest.TestCase):
    @patch("backend.session.store.room")
    def test_returns_npc_states(self, mock_room, *_):
        from backend.app import app
        p = MagicMock()
        p.npc_positions = {"jiang": ("world", 10, 20)}
        p.npc_states = {"jiang": "idle"}
        mind = MagicMock()
        mind.daily_plan = "巡逻集市"
        p.minds = {"jiang": mind}
        mock_room.players = {"test_player": p}
        client = TestClient(app)
        resp = client.get("/api/admin/npc_states", headers={"X-Admin-Secret": _SECRET})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("test_player", data)
        self.assertIn("jiang", data["test_player"])
        npc = data["test_player"]["jiang"]
        self.assertIn("pos", npc)
        self.assertIn("state", npc)
        self.assertIn("plan_summary", npc)


@patch("backend.api.admin_routes.settings", _mock_settings())
@patch("backend.api.routes.settings", _mock_settings())
@patch("backend.app.settings", _mock_settings())
@patch("backend.config.settings", _mock_settings())
class TestEvalEndpoint(unittest.TestCase):
    def test_returns_eval_structure(self, *_):
        from backend.app import app
        client = TestClient(app)
        tracker = _mock_tracker()
        with patch("backend.observability.tracker.get_tracker", return_value=tracker):
            resp = client.get("/api/admin/eval", headers={"X-Admin-Secret": _SECRET})
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("parse_success_rate", data)
            self.assertIn("common_violations", data)
            self.assertIn("by_npc", data)



@patch("backend.api.admin_routes.settings", _mock_settings())
@patch("backend.api.routes.settings", _mock_settings())
@patch("backend.app.settings", _mock_settings())
@patch("backend.config.settings", _mock_settings())
class TestMetricsTokenCounts(unittest.TestCase):
    def test_metrics_includes_token_counts(self, *_):
        from backend.app import app
        client = TestClient(app)
        tracker = _mock_tracker()
        cb = _mock_cb()
        with patch("backend.observability.tracker.get_tracker", return_value=tracker), \
             patch("backend.llm.circuit_breaker.get_circuit_breaker", return_value=cb):
            resp = client.get("/api/admin/metrics", headers={"X-Admin-Secret": _SECRET})
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("total_tokens_in", data)
            self.assertIn("total_tokens_out", data)


@patch("backend.api.admin_routes.settings", _mock_settings())
@patch("backend.api.routes.settings", _mock_settings())
@patch("backend.app.settings", _mock_settings())
@patch("backend.config.settings", _mock_settings())
class TestPlayersEmptyList(unittest.TestCase):
    @patch("backend.session.store.room")
    def test_empty_returns_empty_list(self, mock_room, *_):
        from backend.app import app
        mock_room.players = {}
        client = TestClient(app)
        resp = client.get("/api/admin/players", headers={"X-Admin-Secret": _SECRET})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("players", data)
        self.assertEqual(len(data["players"]), 0)


@patch("backend.api.admin_routes.settings", _mock_settings())
@patch("backend.api.routes.settings", _mock_settings())
@patch("backend.app.settings", _mock_settings())
@patch("backend.config.settings", _mock_settings())
class TestNpcStatesEmpty(unittest.TestCase):
    @patch("backend.session.store.room")
    def test_empty_returns_empty_dict(self, mock_room, *_):
        from backend.app import app
        mock_room.players = {}
        client = TestClient(app)
        resp = client.get("/api/admin/npc_states", headers={"X-Admin-Secret": _SECRET})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data, {})


@patch("backend.api.admin_routes.settings", _mock_settings())
@patch("backend.api.routes.settings", _mock_settings())
@patch("backend.app.settings", _mock_settings())
@patch("backend.config.settings", _mock_settings())
class TestEvalEmpty(unittest.TestCase):
    def test_empty_returns_zeros(self, *_):
        from backend.app import app
        tracker = MagicMock()
        tracker.eval_summary.return_value = {
            "parse_success_rate": 0.0,
            "common_violations": [],
            "by_npc": {},
        }
        client = TestClient(app)
        with patch("backend.observability.tracker.get_tracker", return_value=tracker):
            resp = client.get("/api/admin/eval", headers={"X-Admin-Secret": _SECRET})
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["parse_success_rate"], 0.0)
            self.assertEqual(data["common_violations"], [])
            self.assertEqual(data["by_npc"], {})


@patch("backend.api.admin_routes.settings", _mock_settings())
@patch("backend.api.routes.settings", _mock_settings())
@patch("backend.app.settings", _mock_settings())
@patch("backend.config.settings", _mock_settings())
class TestCircuitBreakerOpenState(unittest.TestCase):
    def test_open_state(self, *_):
        from backend.app import app
        cb = MagicMock()
        cb.stats = {
            "state": "open",
            "total_requests": 100,
            "total_failures": 15,
            "rejected": 8,
            "recent_failures": 5,
            "last_failure_age_s": 5.0,
        }
        client = TestClient(app)
        with patch("backend.llm.circuit_breaker.get_circuit_breaker", return_value=cb):
            resp = client.get("/api/admin/circuit_breaker", headers={"X-Admin-Secret": _SECRET})
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["state"], "open")
            self.assertEqual(data["rejected"], 8)


if __name__ == "__main__":
    unittest.main()
