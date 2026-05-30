"""状态一致性检查与修复"""
from __future__ import annotations

from backend.data.maps_data import MAPS
from backend.models.player import PlayerState
from backend.systems.constants import INITIAL_PX, INITIAL_PY


def validate_player_state(p: PlayerState) -> list[str]:
    violations: list[str] = []
    if p.vigor > p.vigor_max:
        violations.append("体力超过上限")
    if p.spirit > p.spirit_max:
        violations.append("心气超过上限")
    if p.coins < 0:
        violations.append("制钱为负")
    map_data = MAPS.get(p.map_id)
    if map_data:
        rows = map_data.get("rows", [])
        max_y = len(rows) - 1
        max_x = max(len(r) for r in rows) - 1 if rows else 0
        if p.px < 0 or p.px > max_x or p.py < 0 or p.py > max_y:
            violations.append("位置越界")
    if p.unconscious_ticks > 0 and p.move_locked:
        violations.append("昏迷中不应被锁定")
    if p.dead and p.vigor > 0:
        violations.append("已故但体力非零")
    if p.ended and p.ending_label is None:
        violations.append("已收束但无结局标签")
    return violations


def clamp_player_state(p: PlayerState) -> list[str]:
    fixes: list[str] = []
    if p.vigor > p.vigor_max:
        p.vigor = p.vigor_max
        fixes.append("体力超过上限")
    if p.spirit > p.spirit_max:
        p.spirit = p.spirit_max
        fixes.append("心气超过上限")
    if p.coins < 0:
        p.coins = 0
        fixes.append("制钱为负")
    map_data = MAPS.get(p.map_id)
    if map_data:
        rows = map_data.get("rows", [])
        max_y = len(rows) - 1
        max_x = max(len(r) for r in rows) - 1 if rows else 0
        if p.px < 0 or p.px > max_x or p.py < 0 or p.py > max_y:
            p.px = INITIAL_PX
            p.py = INITIAL_PY
            fixes.append("位置越界")
    if p.unconscious_ticks > 0 and p.move_locked:
        p.move_locked = False
        fixes.append("昏迷中不应被锁定")
    if p.dead and p.vigor > 0:
        p.vigor = 0
        fixes.append("已故但体力非零")
    if p.ended and p.ending_label is None:
        p.ending_label = "未知结局"
        fixes.append("已收束但无结局标签")
    return fixes
