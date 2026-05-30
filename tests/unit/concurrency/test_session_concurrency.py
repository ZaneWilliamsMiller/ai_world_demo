from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.session.store import SessionStore


class TestSessionConcurrency:

    @patch("backend.systems.save_system.load_game", return_value=None)
    async def test_concurrent_get_or_create_same_player_id(self, mock_load):
        store = SessionStore()
        player_id = "concurrent_player"
        n = 50

        results = await asyncio.gather(
            *[store.get_or_create(player_id, "侠客", "男", False) for _ in range(n)]
        )

        assert len(results) == n
        for r in results:
            assert r is results[0]
        assert len(store.players) == 1
        assert player_id in store.players

    @patch("backend.systems.save_system.load_game", return_value=None)
    async def test_concurrent_get_or_create_different_player_ids(self, mock_load):
        store = SessionStore()
        n = 50

        results = await asyncio.gather(
            *[store.get_or_create(f"player_{i}", f"侠客{i}", "男", False) for i in range(n)]
        )

        assert len(store.players) == n
        for i, r in enumerate(results):
            assert r.player_id == f"player_{i}"

    @patch("backend.systems.save_system.load_game", return_value=None)
    async def test_no_duplicate_players_under_contention(self, mock_load):
        store = SessionStore()
        player_id = "shared_id"
        n = 100

        await asyncio.gather(
            *[store.get_or_create(player_id, "侠客", "男", False) for _ in range(n)]
        )

        assert len(store.players) == 1

    @patch("backend.systems.save_system.load_game", return_value=None)
    async def test_get_or_create_returns_same_instance(self, mock_load):
        store = SessionStore()
        player_id = "instance_test"

        p1 = await store.get_or_create(player_id, "侠客", "男", False)
        p2 = await store.get_or_create(player_id, "另一个名字", "女", True)

        assert p1 is p2
        assert p1.display_name == "侠客"

    @patch("backend.systems.save_system.load_game", return_value=None)
    async def test_concurrent_get_or_create_and_remove(self, mock_load):
        store = SessionStore()
        player_id = "mixed_op"

        await store.get_or_create(player_id, "侠客", "男", False)
        assert player_id in store.players

        await store.remove_player(player_id)
        assert player_id not in store.players

        p = await store.get_or_create(player_id, "新侠客", "女", True)
        assert p.player_id == player_id
