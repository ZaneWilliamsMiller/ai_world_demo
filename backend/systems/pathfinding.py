from typing import Any
from backend.data.maps_data import MAPS

# ──── 地貌 / 移动 cost ────
# cost 越大走得越慢（折算时辰更多）；不写在表里默认 1。
# 所有地形默认可踏入（不再拦截），险地 cost 高且有受伤概率。
TILE_COST: dict[str, int] = {
    "#": 99,    # 墙（极难通行，高 cost 模拟不可通行）
    "^": 99,    # 悬崖（鬼见愁，极高 cost，模拟不可通行）
    "=": 2,     # 河道主脉（可涉水过河）
    "~": 4,     # 险水/支流（可勉强涉水，慢且险）
    "!": 8,     # 裂隙/深渊（极度危险，极高 cost）
    "@": 5,     # 废墟（危险，高 cost）
    ";": 3,     # 泥地
    "m": 4,     # 山岭
    "/": 2,     # 山道
    "F": 2,     # 林子
    "&": 2,     # 草丛（伏击点；外观同林）
    ",": 1,     # 草地
    ".": 1,     # 土路
    "T": 1,     # 客栈
    "M": 1,     # 市集
    "Y": 1,     # 衙
    "B": 1,     # 桥
    "I": 1,     # 黑店（外观同客栈）
}

TILE_ELEVATION: dict[str, int] = {
    "#": 99,
    "^": 9,
    "=": 1,
    "~": 1,
    "!": 99,   # 裂隙——视作不可攀越
    "@": 5,     # 废墟——中度高低差
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

# 危险地形：踏入有概率受伤/触发际遇
DANGEROUS: frozenset[str] = frozenset({"~", "!", "@", "^"})

# 受伤概率：地形 → 基础概率 (0.0~1.0)
DANGER_INJURY_CHANCE: dict[str, float] = {
    "~": 0.25,   # 险水：25% 概率受伤/触发水祟
    "!": 0.50,   # 裂隙：50% 概率坠落受伤
    "@": 0.20,   # 废墟：20% 概率被埋/触发伏击
    "^": 0.35,   # 悬崖：35% 概率坠落（可强行翻越）
}

MAX_ELEVATION_STEP = 2

IMPASSABLE: frozenset[str] = frozenset()   # 不再设不可通行；靠 cost 和 injury 模拟

def grid_size(rows: list[str]) -> tuple[int, int]:
    h = len(rows)
    w = len(rows[0]) if h else 0
    return w, h

def walkable(ch: str) -> bool:
    """所有地形默认可踏入；墙和悬崖仅 cost 极高。"""
    return True

def tile_cost(ch: str) -> int:
    return int(TILE_COST.get(ch, 1))

def tile_elevation(ch: str) -> int:
    return int(TILE_ELEVATION.get(ch, 2))

def is_dangerous(ch: str) -> bool:
    return ch in DANGEROUS

def danger_injury_chance(ch: str) -> float:
    return DANGER_INJURY_CHANCE.get(ch, 0.0)

def can_step_between(a: str, b: str, allow_steep: bool = False) -> bool:
    """允许所有地形通行；allow_steep 放宽 elevation 限制。"""
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
    """大地图无界门；保留接口以防上游调用。"""
    return None

def find_path(
    map_id: str,
    sx: int,
    sy: int,
    tx: int,
    ty: int,
    allow_steep: bool = False,
) -> list[tuple[int, int]] | None:
    """Dijkstra：按地貌 cost 找最便宜可行路径（支持所有地形）。"""
    rows = MAPS[map_id]["rows"]
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
    """累计行走 cost（含起点本身的 cost）。"""
    rows = MAPS[map_id]["rows"]
    total = 0
    for x, y in path:
        try:
            total += tile_cost(rows[y][x])
        except IndexError:
            continue
    return total

def cost_to_ticks(cost: int) -> int:
    """把行走 cost 折算成时辰推进数。"""
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
    """
    检查踏入地形 ch 是否受伤。
    返回 (injured: bool, reason: str|None)。
    """
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
