import asyncio
import pickle
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.data.factions import FACTIONS
from backend.models.player import PlayerState, _default_flags, _default_reputation

from conftest import make_player


class TestPlayerStateDefaults(unittest.TestCase):
    def test_required_fields(self):
        p = PlayerState(player_id="abc", display_name="张三")
        self.assertEqual(p.player_id, "abc")
        self.assertEqual(p.display_name, "张三")

    def test_optional_defaults(self):
        p = PlayerState(player_id="abc", display_name="张三")
        self.assertEqual(p.gender, "未言")
        self.assertFalse(p.permadeath)
        self.assertFalse(p.dead)
        self.assertIsNone(p.death_reason)
        self.assertEqual(p.map_id, "world")
        self.assertIsInstance(p.coins, int)
        self.assertIsInstance(p.px, int)
        self.assertIsInstance(p.py, int)

    def test_default_flags(self):
        flags = _default_flags()
        self.assertEqual(set(flags.keys()), {"order", "truth", "hope", "chaos"})

    def test_default_reputation(self):
        rep = _default_reputation()
        self.assertEqual(set(rep.keys()), set(FACTIONS.keys()))
        for v in rep.values():
            self.assertEqual(v, 0)

    def test_lock_is_asyncio_lock(self):
        p = PlayerState(player_id="abc", display_name="张三")
        self.assertIsInstance(p.lock, asyncio.Lock)


class TestPlayerStatePickle(unittest.TestCase):
    def test_getstate_removes_lock(self):
        p = PlayerState(player_id="abc", display_name="张三")
        state = p.__getstate__()
        self.assertNotIn("lock", state)

    def test_setstate_restores_lock(self):
        p = PlayerState(player_id="abc", display_name="张三")
        state = p.__getstate__()
        self.assertNotIn("lock", state)
        p2 = PlayerState(player_id="x", display_name="y")
        p2.__setstate__(state)
        self.assertIsInstance(p2.lock, asyncio.Lock)
        self.assertEqual(p2.player_id, "abc")
        self.assertEqual(p2.display_name, "张三")

    def test_pickle_roundtrip(self):
        p = make_player()
        data = pickle.dumps(p)
        p2 = pickle.loads(data)
        self.assertEqual(p2.player_id, p.player_id)
        self.assertEqual(p2.display_name, p.display_name)
        self.assertEqual(p2.map_id, p.map_id)
        self.assertEqual(p2.coins, p.coins)
        self.assertIsInstance(p2.lock, asyncio.Lock)


if __name__ == "__main__":
    unittest.main()
