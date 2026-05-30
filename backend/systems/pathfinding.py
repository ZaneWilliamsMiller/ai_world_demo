from __future__ import annotations

from typing import Any

from backend.data.maps_data import MAPS

TILE_COST: dict[str, int] = {
    "#": 99,
    "^": 99,
    "=": 2,
    "~": 4,
    "!": 8,
    "@": 5,
    ";": 3,
    "m": 4,
    "/": 2,
    "F": 2,
    "&": 2,
    ",": 1,
    ".": 1,
    "T": 1,
    "M": 1,
    "Y": 1,
    "B": 1,
    "I": 1,
}

TILE_ELEVATION: dict[str, int] = {
    "#": 99,
    "^": 9,
    "=": 1,
    "~": 1,
    "!": 99,
    "@": 5,
    "m": 7,
    "/": 6,
    "F": 4,
    "&": 4,
    ";": 3,
    ",": 2,
    ".": 2,
    "T": 2,
    "M": 2,
    "Y": 2,
    "B": 2,
    "I": 2,
}

DANGEROUS: frozenset[str] = frozenset({"~", "!", "@", "^"})

DANGER_INJURY_CHANCE: dict[str, float] = {
    "~": 0.25,
    "!": 0.50,
    "@": 0.20,
    "^": 0.35,
}

MAX_ELEVATION_STEP = 2

_PATH_CACHE_MAX = 128
_path_cache: dict[tuple[str, int, int, int, int, bool], list[tuple[int, int]] | None] = {}


def invalidate_path_cache() -> None:
    _path_cache.clear()


def grid_size(rows: list[str]) -> tuple[int, int]:
    h = len(rows)
    w = len(rows[0]) if h else 0
    return w, h

IMPASSABLE: frozenset[str] = frozenset({"#", "!"})

def is_passable(ch: str) -> bool:
    return ch not in IMPASSABLE

def walkable(ch: str) -> bool:
    return is_passable(ch)

def tile_cost(ch: str) -> int:
    return int(TILE_COST.get(ch, 1))

def tile_elevation(ch: str) -> int:
    return int(TILE_ELEVATION.get(ch, 2))

def is_dangerous(ch: str) -> bool:
    return ch in DANGEROUS

def danger_injury_chance(ch: str) -> float:
    return DANGER_INJURY_CHANCE.get(ch, 0.0)

def can_step_between(a: str, b: str, allow_steep: bool = False) -> bool:
    if allow_steep:
        return True
    return abs(tile_elevation(a) - tile_elevation(b)) <= MAX_ELEVATION_STEP

def tile_at(map_id: str, x: int, y: int) -> str | None:
    m = MAPS.get(map_id)
    if not m:
        return None
    rows: list[str] = m["rows"]
    w, h = grid_size(rows)
    if not (0 <= x < w and 0 <= y < h):
        return None
    return rows[y][x]

def apply_portal(map_id: str, x: int, y: int) -> tuple[str, int, int] | None:
    return None

def find_path(
    map_id: str,
    sx: int,
    sy: int,
    tx: int,
    ty: int,
    allow_steep: bool = False,
) -> list[tuple[int, int]] | None:
    cache_key = (map_id, sx, sy, tx, ty, allow_steep)
    if cache_key in _path_cache:
        return _path_cache[cache_key]

    result = _dijkstra(map_id, sx, sy, tx, ty, allow_steep)

    if len(_path_cache) >= _PATH_CACHE_MAX:
        oldest = next(iter(_path_cache))
        del _path_cache[oldest]
    _path_cache[cache_key] = result
    return result


def _dijkstra(
    map_id: str,
    sx: int,
    sy: int,
    tx: int,
    ty: int,
    allow_steep: bool = False,
) -> list[tuple[int, int]] | None:
    rows = MAPS.get(map_id, {}).get("rows")
    if not rows:
        return None
    w, h = grid_size(rows)
    if not (0 <= tx < w and 0 <= ty < h and 0 <= sx < w and 0 <= sy < h):
        return None
    if sx == tx and sy == ty:
        return [(sx, sy)]

    import heapq

    dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))
    dist: dict[tuple[int, int], int] = {(sx, sy): 0}
    prev: dict[tuple[int, int], tuple[int, int] | None] = {(sx, sy): None}
    pq: list[tuple[int, int, int]] = [(0, sx, sy)]
    while pq:
        d, x, y = heapq.heappop(pq)
        if (x, y) == (tx, ty):
            break
        if d > dist.get((x, y), 1 << 30):
            continue
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < w and 0 <= ny < h):
                continue
            ch = rows[ny][nx]
            src = rows[y][x]
            if not can_step_between(src, ch, allow_steep=allow_steep):
                continue
            nd = d + tile_cost(ch)
            if nd < dist.get((nx, ny), 1 << 30):
                dist[(nx, ny)] = nd
                prev[(nx, ny)] = (x, y)
                heapq.heappush(pq, (nd, nx, ny))

    if (tx, ty) not in prev:
        return None
    path: list[tuple[int, int]] = []
    cur: tuple[int, int] | None = (tx, ty)
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    return path

def path_cost(map_id: str, path: list[tuple[int, int]]) -> int:
    rows = MAPS.get(map_id, {}).get("rows")
    if not rows:
        return 0
    total = 0
    for x, y in path:
        try:
            total += tile_cost(rows[y][x])
        except IndexError:
            continue
    return total

def cost_to_ticks(cost: int) -> int:
    if cost <= 2:
        return 0
    if cost <= 6:
        return 1
    if cost <= 12:
        return 2
    if cost <= 20:
        return 3
    return 4

def check_danger_and_injure(
    ch: str, rng: Any | None = None
) -> tuple[bool, str | None]:
    if not is_dangerous(ch):
        return False, None
    chance = danger_injury_chance(ch)
    if rng is None:
        import random
        rng = random
    if rng.random() < chance:
        reasons = {
            "~": "踏入险水，被暗流拽入深渊",
            "!": "踩空裂隙，坠入无底深渊",
            "@": "踏入废墟，瓦砾塌陷将你埋住",
            "^": "攀爬悬崖失手，险些坠落",
        }
        return True, reasons.get(ch, "遭遇险境，身受重伤")
    return False, None
