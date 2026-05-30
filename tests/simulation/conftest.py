from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.data.maps_data import MAPS
from backend.models.player import PlayerState
from backend.systems.constants import (
    INITIAL_COINS,
    INITIAL_PX,
    INITIAL_PY,
    INITIAL_SPIRIT,
    INITIAL_SPIRIT_MAX,
    INITIAL_VIGOR,
    INITIAL_VIGOR_MAX,
)
from backend.systems.core import init_npc_positions
from backend.systems.economy import init_npc_inventories


def _make_player(**overrides):
    defaults = dict(
        player_id="sim_player",
        display_name="仿真侠客",
        gender="男",
        permadeath=False,
        map_id="world",
        px=INITIAL_PX,
        py=INITIAL_PY,
        coins=INITIAL_COINS,
        vigor=INITIAL_VIGOR,
        vigor_max=INITIAL_VIGOR_MAX,
        spirit=INITIAL_SPIRIT,
        spirit_max=INITIAL_SPIRIT_MAX,
        sleep_debt=0,
        world_day=1,
        world_shichen=4,
        world_tick=0,
        weather="薄阴",
    )
    defaults.update(overrides)
    return PlayerState(**defaults)


def _init_world(p: PlayerState) -> None:
    init_npc_positions(p)
    init_npc_inventories(p)
    if not getattr(p, "npc_states", None):
        p.npc_states = {}
    if not getattr(p, "minds", None):
        p.minds = {}


def _get_map_bounds(map_id: str = "world"):
    rows = MAPS.get(map_id, {}).get("rows", [])
    max_y = len(rows) - 1
    max_x = max(len(r) for r in rows) - 1 if rows else 0
    return max_x, max_y


@pytest.fixture
def game_world():
    with patch("backend.agents.actor.execute_plan_step") as mock_exec, \
         patch("backend.agents.game_state.get_or_init_mind") as mock_mind, \
         patch("random.random", return_value=1.0):
        mock_result = MagicMock()
        mock_result.action_type = MagicMock(value="idle")
        mock_result.description = "idle"
        mock_result.success = True
        mock_result.target_pos = None
        mock_result.raw_dialogue = None
        mock_exec.return_value = mock_result

        mock_mind_obj = MagicMock()
        mock_mind_obj.plan_by_shichen = {}
        mock_mind_obj.affect_valence = 0
        mock_mind_obj.affect_arousal = 5
        mock_mind_obj.affect_mood = "平静"
        mock_mind_obj.affect_cause = ""
        mock_mind_obj.mood_decay_tick = MagicMock()
        mock_mind.return_value = mock_mind_obj

        p = _make_player()
        _init_world(p)
        yield p


@pytest.fixture
def make_player():
    return _make_player


@pytest.fixture
def init_world():
    return _init_world


@pytest.fixture
def map_bounds():
    return _get_map_bounds
