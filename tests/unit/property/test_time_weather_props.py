from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from unittest.mock import patch

from backend.systems.time_weather import WEATHERS, advance_clock
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.unit.property.strategies import st_player_state


@settings(max_examples=50, deadline=None)
@given(st_player_state(), st.integers(1, 24))
def test_shichen_always_in_range(p, ticks):
    with patch("random.random", return_value=0.0), \
         patch("backend.agents.actor.execute_plan_step"), \
         patch("backend.agents.game_state.get_or_init_mind"):
        advance_clock(p, ticks)
    assert 0 <= p.world_shichen <= 11


@settings(max_examples=50, deadline=None)
@given(st_player_state(), st.integers(1, 24))
def test_weather_always_legal(p, ticks):
    with patch("random.random", return_value=0.0), \
         patch("random.choice", side_effect=lambda seq: seq[0]), \
         patch("backend.agents.actor.execute_plan_step"), \
         patch("backend.agents.game_state.get_or_init_mind"):
        advance_clock(p, ticks)
    assert p.weather in WEATHERS
