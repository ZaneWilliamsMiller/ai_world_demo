from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.systems.consistency import clamp_player_state
from backend.systems.economy import apply_coin_delta
from backend.systems.trap import apply_spirit_delta, apply_vigor_delta
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.unit.property.strategies import st_player_state


@settings(max_examples=50)
@given(st_player_state(), st.integers(-200, 200))
def test_vigor_in_range_after_delta(p, delta):
    apply_vigor_delta(p, delta)
    assert 0 <= p.vigor <= p.vigor_max


@settings(max_examples=50)
@given(st_player_state(), st.integers(-200, 200))
def test_spirit_in_range_after_delta(p, delta):
    apply_spirit_delta(p, delta)
    assert 0 <= p.spirit <= p.spirit_max


@settings(max_examples=50)
@given(st_player_state(), st.integers(-99999, 99999))
def test_coins_nonnegative_after_any_delta(p, delta):
    apply_coin_delta(p, delta)
    assert p.coins >= 0


@settings(max_examples=50)
@given(st_player_state())
def test_clamp_fixes_all_violations(p):
    clamp_player_state(p)
    assert 0 <= p.vigor <= p.vigor_max
    assert 0 <= p.spirit <= p.spirit_max
    assert p.coins >= 0
