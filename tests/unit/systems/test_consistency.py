from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from conftest import make_player
from backend.systems.consistency import clamp_player_state, validate_player_state
from backend.systems.constants import INITIAL_PX, INITIAL_PY


class TestValidatePlayerState:
    def test_healthy_state_no_violations(self):
        p = make_player()
        assert validate_player_state(p) == []

    def test_vigor_exceeds_max(self):
        p = make_player(vigor=120, vigor_max=100)
        assert validate_player_state(p) == ["体力超过上限"]

    def test_spirit_exceeds_max(self):
        p = make_player(spirit=110, spirit_max=100)
        assert validate_player_state(p) == ["心气超过上限"]

    def test_coins_negative(self):
        p = make_player(coins=-10)
        assert validate_player_state(p) == ["制钱为负"]

    def test_position_out_of_bounds(self):
        p = make_player(px=999, py=999)
        assert validate_player_state(p) == ["位置越界"]

    def test_unconscious_and_locked(self):
        p = make_player()
        p.unconscious_ticks = 3
        p.move_locked = True
        assert validate_player_state(p) == ["昏迷中不应被锁定"]

    def test_dead_with_vigor(self):
        p = make_player(vigor=50)
        p.dead = True
        assert validate_player_state(p) == ["已故但体力非零"]

    def test_ended_without_label(self):
        p = make_player()
        p.ended = True
        p.ending_label = None
        assert validate_player_state(p) == ["已收束但无结局标签"]

    def test_multiple_violations(self):
        p = make_player(vigor=120, vigor_max=100, coins=-10)
        p.dead = True
        violations = validate_player_state(p)
        assert len(violations) == 3
        assert "体力超过上限" in violations
        assert "制钱为负" in violations
        assert "已故但体力非零" in violations


class TestClampPlayerState:
    def test_clamp_vigor(self):
        p = make_player(vigor=120, vigor_max=100)
        fixes = clamp_player_state(p)
        assert p.vigor == 100
        assert "体力超过上限" in fixes

    def test_clamp_spirit(self):
        p = make_player(spirit=110, spirit_max=100)
        fixes = clamp_player_state(p)
        assert p.spirit == 100
        assert "心气超过上限" in fixes

    def test_clamp_coins(self):
        p = make_player(coins=-10)
        fixes = clamp_player_state(p)
        assert p.coins == 0
        assert "制钱为负" in fixes

    def test_clamp_position(self):
        p = make_player(px=999, py=999)
        fixes = clamp_player_state(p)
        assert p.px == INITIAL_PX
        assert p.py == INITIAL_PY
        assert "位置越界" in fixes

    def test_unlock_move_locked(self):
        p = make_player()
        p.unconscious_ticks = 3
        p.move_locked = True
        fixes = clamp_player_state(p)
        assert p.move_locked is False
        assert "昏迷中不应被锁定" in fixes

    def test_dead_vigor_to_zero(self):
        p = make_player(vigor=50)
        p.dead = True
        fixes = clamp_player_state(p)
        assert p.vigor == 0
        assert "已故但体力非零" in fixes

    def test_set_default_ending_label(self):
        p = make_player()
        p.ended = True
        p.ending_label = None
        fixes = clamp_player_state(p)
        assert p.ending_label == "未知结局"
        assert "已收束但无结局标签" in fixes

    def test_healthy_state_no_changes(self):
        p = make_player()
        orig_vigor = p.vigor
        orig_spirit = p.spirit
        orig_coins = p.coins
        orig_px = p.px
        orig_py = p.py
        fixes = clamp_player_state(p)
        assert fixes == []
        assert p.vigor == orig_vigor
        assert p.spirit == orig_spirit
        assert p.coins == orig_coins
        assert p.px == orig_px
        assert p.py == orig_py
