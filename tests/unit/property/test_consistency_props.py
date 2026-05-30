from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.systems.consistency import clamp_player_state
from hypothesis import given, settings

from tests.unit.property.strategies import st_player_state


@settings(max_examples=50)
@given(st_player_state())
def test_clamp_vigor_in_range(p):
    clamp_player_state(p)
    assert 0 <= p.vigor <= p.vigor_max


@settings(max_examples=50)
@given(st_player_state())
def test_clamp_spirit_in_range(p):
    clamp_player_state(p)
    assert 0 <= p.spirit <= p.spirit_max


@settings(max_examples=50)
@given(st_player_state())
def test_clamp_coins_nonnegative(p):
    clamp_player_state(p)
    assert p.coins >= 0


@settings(max_examples=50)
@given(st_player_state())
def test_clamp_idempotent(p):
    clamp_player_state(p)
    v, s, c = p.vigor, p.spirit, p.coins
    fixes = clamp_player_state(p)
    assert p.vigor == v
    assert p.spirit == s
    assert p.coins == c
    assert fixes == []
