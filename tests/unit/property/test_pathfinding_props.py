from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.data.maps_data import MAPS
from backend.systems.pathfinding import find_path, is_passable
from hypothesis import given, settings

from tests.unit.property.strategies import st_position

MAP_ID = "world"
ROWS = MAPS[MAP_ID]["rows"]
MAP_H = len(ROWS)
MAP_W = len(ROWS[0]) if MAP_H else 0


def _is_passable(x: int, y: int) -> bool:
    ch = ROWS[y][x]
    return is_passable(ch)


@settings(max_examples=50, deadline=None)
@given(st_position(), st_position())
def test_path_length_at_least_manhattan(start, end):
    sx, sy = start
    tx, ty = end
    if not (_is_passable(sx, sy) and _is_passable(tx, ty)):
        return
    path = find_path(MAP_ID, sx, sy, tx, ty)
    if path is None:
        return
    manhattan = abs(sx - tx) + abs(sy - ty)
    assert len(path) >= manhattan + 1


@settings(max_examples=50, deadline=None)
@given(st_position(), st_position())
def test_path_no_impassable_tiles(start, end):
    sx, sy = start
    tx, ty = end
    if not (_is_passable(sx, sy) and _is_passable(tx, ty)):
        return
    path = find_path(MAP_ID, sx, sy, tx, ty, allow_steep=True)
    if path is None:
        return
    for x, y in path:
        ch = ROWS[y][x]
        assert is_passable(ch)


@settings(max_examples=50, deadline=None)
@given(st_position())
def test_same_start_end_path_length(pos):
    x, y = pos
    if not _is_passable(x, y):
        return
    path = find_path(MAP_ID, x, y, x, y)
    if path is not None:
        assert len(path) <= 1
