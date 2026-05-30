"""统一区域配置：消除 economy.py / encounter.py 中的硬编码坐标。"""
from __future__ import annotations

from typing import Any

# ════════════════════════════════════════════════════════════════════
#  经济区域 — 供 zone_price_mod 使用
#  每个区域定义为 (map_id, x_min, x_max, y_min, y_max) 的列表
#  附带价格倍率与说明
# ════════════════════════════════════════════════════════════════════
ECONOMY_ZONES: dict[str, dict[str, Any]] = {
    "town": {
        "label": "城区",
        "ranges": [
            ("world", 10, 50, 25, 45),
        ],
        "price_mod": 1.00,
        "price_hint": "县城市口，价稳",
    },
    "wild": {
        "label": "荒野",
        "ranges": [
            ("world", 5, 24, 21, 32),
        ],
        "price_mod": 1.25,
        "price_hint": "荒野难得，货价偏高",
    },
    "ferry": {
        "label": "渡口",
        "ranges": [
            ("world", 5, 45, 42, 55),
        ],
        "price_mod": 1.08,
        "price_hint": "渡口客多，坐地起价",
    },
    "temple": {
        "label": "卧佛寺",
        "ranges": [
            ("world", 40, 65, 10, 25),
        ],
        "price_mod": 0.80,
        "price_hint": "佛寺随缘施价",
    },
    "mill": {
        "label": "碾坊",
        "ranges": [
            ("world", 50, 70, 65, 82),
        ],
        "price_mod": 0.85,
        "price_hint": "碾坊自产自销，粮食贱",
    },
    "toll": {
        "label": "厘卡哨",
        "ranges": [
            ("world", 5, 45, 56, 72),
        ],
        "price_mod": 1.35,
        "price_hint": "卡吏抽头，往来皆贵",
    },
}

# ════════════════════════════════════════════════════════════════════
#  安全区 — 供 _is_wild 使用（非安全区 = 野外）
# ════════════════════════════════════════════════════════════════════
SAFE_ZONES: dict[str, dict[str, Any]] = {
    "county": {
        "label": "县城",
        "ranges": [
            ("world", 10, 50, 25, 45),
        ],
    },
    "temple": {
        "label": "寺庙",
        "ranges": [
            ("world", 40, 65, 10, 25),
        ],
    },
    "garrison": {
        "label": "关塞",
        "ranges": [
            ("world", 60, 90, 4, 14),
        ],
    },
    "ferry": {
        "label": "渡口",
        "ranges": [
            ("world", 5, 45, 42, 55),
        ],
    },
    "post": {
        "label": "驿站",
        "ranges": [
            ("world", 5, 45, 56, 75),
        ],
    },
    "checkpoint": {
        "label": "关卡",
        "ranges": [
            ("world", 5, 45, 56, 72),
        ],
    },
    "guild": {
        "label": "行会",
        "ranges": [
            ("world", 80, 120, 15, 35),
        ],
    },
}


def get_economy_zone(map_id: str, x: int, y: int) -> str:
    """返回坐标所属的经济区域类型，默认 'default'。"""
    for zone_id, zone in ECONOMY_ZONES.items():
        for mid, x0, x1, y0, y1 in zone["ranges"]:
            if mid == map_id and x0 <= x <= x1 and y0 <= y <= y1:
                return zone_id
    return "default"


def zone_price_mod(player_or_px: Any, py: int | None = None) -> tuple[float, str]:
    """根据玩家位置判断地区价格倍率。支持传入 PlayerState 或 (px, py) 坐标。"""
    if hasattr(player_or_px, 'px'):
        map_id = getattr(player_or_px, 'map_id', 'world')
        px = player_or_px.px
        py_ = player_or_px.py
    else:
        map_id = 'world'
        px = int(player_or_px)
        py_ = int(py or 0)
    zone_id = get_economy_zone(map_id, px, py_)
    if zone_id != "default":
        zone = ECONOMY_ZONES[zone_id]
        return (float(zone["price_mod"]), str(zone["price_hint"]))
    return (1.00, "市口平价")


def is_safe_zone(map_id: str, x: int, y: int) -> bool:
    """判断坐标是否在安全区内。"""
    for zone in SAFE_ZONES.values():
        for mid, x0, x1, y0, y1 in zone["ranges"]:
            if mid == map_id and x0 <= x <= x1 and y0 <= y <= y1:
                return True
    return False
