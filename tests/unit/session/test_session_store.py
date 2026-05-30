from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import asyncio
import unittest
from unittest.mock import patch

from backend.session.store import SessionStore

from conftest import make_player


def _run(coro):
    return asyncio.run(coro)


class TestGetOrCreate(unittest.TestCase):
    @patch("backend.systems.save_system.load_game", return_value=None)
    def test_creates_new_player(self, mock_load):
        store = SessionStore()
        p = _run(store.get_or_create("p1", "侠客甲", "男", False))
        self.assertEqual(p.player_id, "p1")
        self.assertEqual(p.display_name, "侠客甲")
        self.assertIn("p1", store.players)

    @patch("backend.systems.save_system.load_game", return_value=None)
    def test_returns_existing_player(self, mock_load):
        store = SessionStore()
        existing = make_player(player_id="p1")
        store.players["p1"] = existing
        p = _run(store.get_or_create("p1", "新名字", "女", True))
        self.assertIs(p, existing)

    @patch("backend.systems.save_system.load_game", return_value=None)
    def test_default_display_name_when_none(self, mock_load):
        store = SessionStore()
        p = _run(store.get_or_create("abc12345", None, "未言", False))
        self.assertIn("江湖客", p.display_name)

    @patch("backend.systems.save_system.load_game", return_value=None)
    def test_default_gender_when_invalid(self, mock_load):
        store = SessionStore()
        p = _run(store.get_or_create("p1", "测试", "invalid", False))
        self.assertEqual(p.gender, "未言")

    @patch("backend.systems.save_system.load_game", return_value=None)
    def test_fills_default_favor(self, mock_load):
        store = SessionStore()
        p = _run(store.get_or_create("p1", "测试", "男", False))
        self.assertIsInstance(p.favor, dict)

    @patch("backend.systems.save_system.load_game", return_value=None)
    def test_fills_default_rumors(self, mock_load):
        store = SessionStore()
        p = _run(store.get_or_create("p1", "测试", "男", False))
        self.assertIsInstance(p.rumors, list)

    @patch("backend.systems.save_system.load_game", return_value=None)
    def test_fills_default_vigor(self, mock_load):
        store = SessionStore()
        p = _run(store.get_or_create("p1", "测试", "男", False))
        self.assertGreater(p.vigor, 0)

    @patch("backend.systems.save_system.load_game", return_value=None)
    def test_fills_default_reputation(self, mock_load):
        store = SessionStore()
        p = _run(store.get_or_create("p1", "测试", "男", False))
        self.assertIsInstance(p.reputation, dict)


class TestRemovePlayer(unittest.TestCase):
    def test_remove_existing_player(self):
        store = SessionStore()
        p = make_player(player_id="p1")
        store.players["p1"] = p
        _run(store.remove_player("p1"))
        self.assertNotIn("p1", store.players)

    def test_remove_nonexistent_player_no_error(self):
        store = SessionStore()
        _run(store.remove_player("ghost"))
        self.assertEqual(len(store.players), 0)


class TestSetPlayer(unittest.TestCase):
    def test_set_player(self):
        store = SessionStore()
        p = make_player(player_id="p1")
        _run(store.set_player("p1", p))
        self.assertIn("p1", store.players)
        self.assertIs(store.players["p1"], p)

    def test_set_player_overwrites_existing(self):
        store = SessionStore()
        old = make_player(player_id="p1", display_name="旧名字")
        store.players["p1"] = old
        new = make_player(player_id="p1", display_name="新名字")
        _run(store.set_player("p1", new))
        self.assertEqual(store.players["p1"].display_name, "新名字")


class TestPopPlayer(unittest.TestCase):
    def test_pop_existing_player(self):
        store = SessionStore()
        p = make_player(player_id="p1")
        store.players["p1"] = p
        result = _run(store.pop_player("p1"))
        self.assertIs(result, p)
        self.assertNotIn("p1", store.players)

    def test_pop_nonexistent_player_returns_none(self):
        store = SessionStore()
        result = _run(store.pop_player("ghost"))
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
