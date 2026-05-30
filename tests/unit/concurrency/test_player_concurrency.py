from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.models.player import PlayerState

from conftest import make_player


async def _apply_delta(p: PlayerState, vigor_delta: int = 0, spirit_delta: int = 0, coins_delta: int = 0) -> None:
    async with p.lock:
        p.vigor += vigor_delta
        p.spirit += spirit_delta
        p.coins += coins_delta


class TestPlayerConcurrency:

    async def test_concurrent_vigor_spirit_delta(self):
        p = make_player(vigor=100, spirit=100)
        initial_vigor = p.vigor
        initial_spirit = p.spirit
        n = 100

        coros = [_apply_delta(p, vigor_delta=1, spirit_delta=-1) for _ in range(n)]
        await asyncio.gather(*coros)

        assert p.vigor == initial_vigor + n
        assert p.spirit == initial_spirit - n

    async def test_concurrent_coins_delta(self):
        p = make_player(coins=0)
        n = 100

        coros = [_apply_delta(p, coins_delta=1) for _ in range(n)]
        await asyncio.gather(*coros)

        assert p.coins == n

    async def test_concurrent_mixed_deltas(self):
        p = make_player(vigor=50, spirit=50, coins=50)
        n = 100

        coros = [_apply_delta(p, vigor_delta=1, spirit_delta=-1, coins_delta=2) for _ in range(n)]
        await asyncio.gather(*coros)

        assert p.vigor == 50 + n
        assert p.spirit == 50 - n
        assert p.coins == 50 + 2 * n

    async def test_concurrent_zero_delta_no_change(self):
        p = make_player(vigor=80, spirit=70)
        n = 50

        coros = [_apply_delta(p) for _ in range(n)]
        await asyncio.gather(*coros)

        assert p.vigor == 80
        assert p.spirit == 70

    async def test_lock_prevents_lost_updates(self):
        p = make_player(vigor=0)
        n = 200

        coros = [_apply_delta(p, vigor_delta=1) for _ in range(n)]
        await asyncio.gather(*coros)

        assert p.vigor == n
