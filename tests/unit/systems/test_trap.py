# pyright: reportCallIssue=false,reportOptionalSubscript=false,reportArgumentType=false
"""离线单元测试 — trap 模块（险局/脱困/体力心气）"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from conftest import make_player


class TestClampInt:
    def test_below_lo(self):
        from backend.systems.trap import _clamp_int
        assert _clamp_int(-5, 0, 10) == 0

    def test_above_hi(self):
        from backend.systems.trap import _clamp_int
        assert _clamp_int(15, 0, 10) == 10

    def test_within_range(self):
        from backend.systems.trap import _clamp_int
        assert _clamp_int(5, 0, 10) == 5

    def test_equal_lo(self):
        from backend.systems.trap import _clamp_int
        assert _clamp_int(0, 0, 10) == 0

    def test_equal_hi(self):
        from backend.systems.trap import _clamp_int
        assert _clamp_int(10, 0, 10) == 10

    def test_negative_range(self):
        from backend.systems.trap import _clamp_int
        assert _clamp_int(-10, -5, -1) == -5

    def test_same_lo_hi(self):
        from backend.systems.trap import _clamp_int
        assert _clamp_int(99, 7, 7) == 7


class TestResetTrapState:
    def test_resets_move_locked(self):
        from backend.systems.trap import _reset_trap_state
        p = make_player()
        p.move_locked = True
        _reset_trap_state(p)
        assert p.move_locked is False

    def test_resets_lock_npc_id(self):
        from backend.systems.trap import _reset_trap_state
        p = make_player()
        p.move_lock_npc_id = "boss"
        _reset_trap_state(p)
        assert p.move_lock_npc_id is None

    def test_resets_trap_reason(self):
        from backend.systems.trap import _reset_trap_state
        p = make_player()
        p.trap_reason = "被困"
        _reset_trap_state(p)
        assert p.trap_reason is None

    def test_resets_trap_attempts(self):
        from backend.systems.trap import _reset_trap_state
        p = make_player()
        p.trap_attempts = 5
        _reset_trap_state(p)
        assert p.trap_attempts == 0

    def test_idempotent(self):
        from backend.systems.trap import _reset_trap_state
        p = make_player()
        _reset_trap_state(p)
        _reset_trap_state(p)
        assert p.move_locked is False
        assert p.trap_attempts == 0


class TestVigorStatusBlock:
    def test_phase_jinkujie_low_vigor(self):
        from backend.systems.trap import vigor_status_block
        p = make_player(vigor=5, vigor_max=100, spirit=80, spirit_max=100)
        result = vigor_status_block(p)
        assert "近枯竭" in result

    def test_phase_jiruo(self):
        from backend.systems.trap import vigor_status_block
        p = make_player(vigor=20, vigor_max=100, spirit=80, spirit_max=100)
        result = vigor_status_block(p)
        assert "极弱" in result

    def test_phase_jiandi(self):
        from backend.systems.trap import vigor_status_block
        p = make_player(vigor=45, vigor_max=100, spirit=80, spirit_max=100)
        result = vigor_status_block(p)
        assert "见底" in result

    def test_phase_shangke(self):
        from backend.systems.trap import vigor_status_block
        p = make_player(vigor=70, vigor_max=100, spirit=80, spirit_max=100)
        result = vigor_status_block(p)
        assert "尚可" in result

    def test_phase_shangzu(self):
        from backend.systems.trap import vigor_status_block
        p = make_player(vigor=90, vigor_max=100, spirit=80, spirit_max=100)
        result = vigor_status_block(p)
        assert "尚足" in result

    def test_spirit_phase_jinkujie(self):
        from backend.systems.trap import vigor_status_block
        p = make_player(vigor=80, vigor_max=100, spirit=5, spirit_max=100)
        result = vigor_status_block(p)
        assert "近枯竭" in result

    def test_spirit_phase_jiruo(self):
        from backend.systems.trap import vigor_status_block
        p = make_player(vigor=80, vigor_max=100, spirit=25, spirit_max=100)
        result = vigor_status_block(p)
        assert "极弱" in result

    def test_contains_vigor_fraction(self):
        from backend.systems.trap import vigor_status_block
        p = make_player(vigor=80, vigor_max=100, spirit=70, spirit_max=100)
        result = vigor_status_block(p)
        assert "80/100" in result

    def test_contains_spirit_fraction(self):
        from backend.systems.trap import vigor_status_block
        p = make_player(vigor=80, vigor_max=100, spirit=70, spirit_max=100)
        result = vigor_status_block(p)
        assert "70/100" in result

    def test_vigor_one_eighth_boundary(self):
        from backend.systems.trap import vigor_status_block
        p = make_player(vigor=12, vigor_max=100, spirit=80, spirit_max=100)
        result = vigor_status_block(p)
        assert "近枯竭" in result

    def test_vigor_just_above_one_eighth(self):
        from backend.systems.trap import vigor_status_block
        p = make_player(vigor=13, vigor_max=100, spirit=80, spirit_max=100)
        result = vigor_status_block(p)
        assert "极弱" in result


class TestTileHazardReason:
    @patch("backend.systems.trap.tile_at", return_value="&")
    def test_bush_tile(self, _mock):
        from backend.systems.trap import tile_hazard_reason
        p = make_player()
        result = tile_hazard_reason(p)
        assert result is not None
        assert "草莽" in result

    @patch("backend.systems.trap.tile_at", return_value="I")
    def test_inn_tile(self, _mock):
        from backend.systems.trap import tile_hazard_reason
        p = make_player()
        result = tile_hazard_reason(p)
        assert result is not None
        assert "门闩" in result

    @patch("backend.systems.trap.tile_at", return_value="~")
    def test_water_tile(self, _mock):
        from backend.systems.trap import tile_hazard_reason
        p = make_player()
        result = tile_hazard_reason(p)
        assert result is not None
        assert "浊流" in result

    @patch("backend.systems.trap.tile_at", return_value=".")
    def test_plain_tile_returns_none(self, _mock):
        from backend.systems.trap import tile_hazard_reason
        p = make_player()
        result = tile_hazard_reason(p)
        assert result is None

    @patch("backend.systems.trap.tile_at", return_value="T")
    def test_town_tile_returns_none(self, _mock):
        from backend.systems.trap import tile_hazard_reason
        p = make_player()
        result = tile_hazard_reason(p)
        assert result is None

    @patch("backend.systems.trap.tile_at", return_value=None)
    def test_none_tile_returns_none(self, _mock):
        from backend.systems.trap import tile_hazard_reason
        p = make_player()
        result = tile_hazard_reason(p)
        assert result is None


class TestTryClearMoveLockNotLocked:
    def test_returns_none_when_not_move_locked(self):
        from backend.systems.trap import try_clear_move_lock
        p = make_player()
        p.move_locked = False
        result = try_clear_move_lock(p, "逃跑", "jiang")
        assert result is None


class TestTryClearMoveLockEncounterPrefix:
    def test_returns_none_for_jiyu_prefix(self):
        from backend.systems.trap import try_clear_move_lock
        p = make_player()
        p.move_locked = True
        result = try_clear_move_lock(p, "[际遇]某事", "jiang")
        assert result is None


class TestTryClearMoveLockNpcMismatch:
    def test_returns_none_for_wrong_npc(self):
        from backend.systems.trap import try_clear_move_lock
        p = make_player()
        p.move_locked = True
        p.move_lock_npc_id = "boss"
        result = try_clear_move_lock(p, "逃跑", "other_npc")
        assert result is None

    def test_allows_matching_npc(self):
        from backend.systems.trap import try_clear_move_lock
        p = make_player()
        p.move_locked = True
        p.move_lock_npc_id = "boss"
        p.vigor = 80
        p.spirit = 80
        p.life_burn_ticks = 0
        result = try_clear_move_lock(p, "逃跑", "boss", llm_outcome="success")
        assert result is not None
        assert result["outcome"] == "escaped"

    def test_allows_empty_npc_id(self):
        from backend.systems.trap import try_clear_move_lock
        p = make_player()
        p.move_locked = True
        p.move_lock_npc_id = "boss"
        p.vigor = 80
        p.spirit = 80
        p.life_burn_ticks = 0
        result = try_clear_move_lock(p, "逃跑", "", llm_outcome="success")
        assert result is not None
        assert result["outcome"] == "escaped"


class TestTryClearMoveLockLifeBurn:
    def test_life_burn_with_vigor_escapes(self):
        from backend.systems.trap import try_clear_move_lock
        p = make_player()
        p.move_locked = True
        p.move_lock_npc_id = "jiang"
        p.life_burn_ticks = 3
        p.life_burn_max = 6
        p.vigor = 10
        result = try_clear_move_lock(p, "进食", "jiang")
        assert result["outcome"] == "escaped"
        assert "生命燃烧止息" in result["reason"]
        assert p.life_burn_ticks == 0
        assert p.life_burn_max == 0
        assert p.move_locked is False

    def test_life_burn_zero_vigor_struggling(self):
        from backend.systems.trap import try_clear_move_lock
        p = make_player()
        p.move_locked = True
        p.move_lock_npc_id = "jiang"
        p.life_burn_ticks = 3
        p.life_burn_max = 6
        p.vigor = 0
        result = try_clear_move_lock(p, "挣扎", "jiang")
        assert result["outcome"] == "struggling"
        assert "尽快进食" in result["reason"]

    def test_life_burn_increments_trap_attempts(self):
        from backend.systems.trap import try_clear_move_lock
        p = make_player()
        p.move_locked = True
        p.move_lock_npc_id = "jiang"
        p.life_burn_ticks = 3
        p.vigor = 0
        p.trap_attempts = 0
        try_clear_move_lock(p, "挣扎", "jiang")
        assert p.trap_attempts == 1


class TestTryClearMoveLockCollapse:
    @patch("backend.systems.trap.maybe_collapse_from_attrs")
    def test_collapse_returned_when_attrs_zero(self, mock_collapse):
        from backend.systems.trap import try_clear_move_lock
        p = make_player()
        p.move_locked = True
        p.move_lock_npc_id = "jiang"
        p.life_burn_ticks = 0
        p.vigor = 0
        p.spirit = 0
        mock_collapse.return_value = {"outcome": "dead", "reason": "气力心神俱断"}
        result = try_clear_move_lock(p, "挣扎", "jiang")
        assert result["outcome"] == "dead"

    @patch("backend.systems.trap.maybe_collapse_from_attrs")
    def test_collapse_burning_returned(self, mock_collapse):
        from backend.systems.trap import try_clear_move_lock
        p = make_player()
        p.move_locked = True
        p.move_lock_npc_id = "jiang"
        p.life_burn_ticks = 0
        p.vigor = 0
        p.spirit = 50
        mock_collapse.return_value = {"outcome": "burning", "reason": "体力枯竭"}
        result = try_clear_move_lock(p, "挣扎", "jiang")
        assert result["outcome"] == "burning"


class TestTryClearMoveLockEnslaved:
    def test_llm_enslaved_sets_enslaved(self):
        from backend.systems.trap import try_clear_move_lock
        p = make_player()
        p.move_locked = True
        p.move_lock_npc_id = "jiang"
        p.life_burn_ticks = 0
        p.vigor = 80
        p.spirit = 80
        result = try_clear_move_lock(p, "投降", "jiang", llm_enslaved="被俘为奴")
        assert result["outcome"] == "enslaved"
        assert p.enslaved is True
        assert p.enslaved_reason == "被俘为奴"
        assert p.ended is True
        assert p.ending_label == "囚徒残年"
        assert p.move_locked is False

    def test_llm_enslaved_empty_string_default_reason(self):
        from backend.systems.trap import try_clear_move_lock
        p = make_player()
        p.move_locked = True
        p.move_lock_npc_id = "jiang"
        p.life_burn_ticks = 0
        p.vigor = 80
        p.spirit = 80
        result = try_clear_move_lock(p, "投降", "jiang", llm_enslaved="   ")
        assert result["outcome"] == "enslaved"
        assert p.enslaved_reason == "失了自由身。"

    def test_llm_enslaved_truncates_long_reason(self):
        from backend.systems.trap import try_clear_move_lock
        p = make_player()
        p.move_locked = True
        p.move_lock_npc_id = "jiang"
        p.life_burn_ticks = 0
        p.vigor = 80
        p.spirit = 80
        long_reason = "被" * 100
        result = try_clear_move_lock(p, "投降", "jiang", llm_enslaved=long_reason)
        assert len(p.enslaved_reason) <= 80


class TestTryClearMoveLockSuccess:
    def test_llm_outcome_success_escapes(self):
        from backend.systems.trap import try_clear_move_lock
        p = make_player()
        p.move_locked = True
        p.move_lock_npc_id = "jiang"
        p.life_burn_ticks = 0
        p.vigor = 80
        p.spirit = 80
        result = try_clear_move_lock(p, "逃脱", "jiang", llm_outcome="success")
        assert result["outcome"] == "escaped"
        assert "脱身" in result["reason"]
        assert p.move_locked is False
        assert p.trap_attempts == 0


class TestTryClearMoveLockFail:
    def test_fail_under_max_attempts_struggling(self):
        from backend.systems.trap import try_clear_move_lock
        p = make_player()
        p.move_locked = True
        p.move_lock_npc_id = "jiang"
        p.life_burn_ticks = 0
        p.vigor = 80
        p.spirit = 80
        p.trap_attempts = 0
        result = try_clear_move_lock(p, "挣扎", "jiang", llm_outcome="fail")
        assert result["outcome"] == "struggling"
        assert "险局未解" in result["reason"]
        assert p.trap_attempts == 1

    def test_fail_at_max_attempts_enslaved(self):
        from backend.systems.constants import MAX_TRAP_ATTEMPTS
        from backend.systems.trap import try_clear_move_lock
        p = make_player()
        p.move_locked = True
        p.move_lock_npc_id = "jiang"
        p.life_burn_ticks = 0
        p.vigor = 80
        p.spirit = 80
        p.trap_attempts = MAX_TRAP_ATTEMPTS - 1
        result = try_clear_move_lock(p, "挣扎", "jiang", llm_outcome="fail")
        assert result["outcome"] == "enslaved"
        assert p.enslaved is True
        assert p.ended is True
        assert p.ending_label == "囚徒残年"
        assert p.move_locked is False

    def test_fail_attempts_increments(self):
        from backend.systems.trap import try_clear_move_lock
        p = make_player()
        p.move_locked = True
        p.move_lock_npc_id = "jiang"
        p.life_burn_ticks = 0
        p.vigor = 80
        p.spirit = 80
        p.trap_attempts = 0
        try_clear_move_lock(p, "挣扎", "jiang", llm_outcome="fail")
        assert p.trap_attempts == 1
        try_clear_move_lock(p, "挣扎", "jiang", llm_outcome="fail")
        assert p.trap_attempts == 2


class TestTryClearMoveLockProgress:
    def test_progress_outcome_struggling(self):
        from backend.systems.trap import try_clear_move_lock
        p = make_player()
        p.move_locked = True
        p.move_lock_npc_id = "jiang"
        p.life_burn_ticks = 0
        p.vigor = 80
        p.spirit = 80
        result = try_clear_move_lock(p, "反击", "jiang", llm_outcome="progress")
        assert result["outcome"] == "struggling"
        assert "暂占上风" in result["reason"]

    def test_progress_stays_locked(self):
        from backend.systems.trap import try_clear_move_lock
        p = make_player()
        p.move_locked = True
        p.move_lock_npc_id = "jiang"
        p.life_burn_ticks = 0
        p.vigor = 80
        p.spirit = 80
        try_clear_move_lock(p, "反击", "jiang", llm_outcome="progress")
        assert p.move_locked is True


class TestTryClearMoveLockDefault:
    def test_no_llm_outcome_defaults_struggling(self):
        from backend.systems.trap import try_clear_move_lock
        p = make_player()
        p.move_locked = True
        p.move_lock_npc_id = "jiang"
        p.life_burn_ticks = 0
        p.vigor = 80
        p.spirit = 80
        result = try_clear_move_lock(p, "观望", "jiang")
        assert result["outcome"] == "struggling"
        assert "险局未解" in result["reason"]

    def test_default_increments_attempts(self):
        from backend.systems.trap import try_clear_move_lock
        p = make_player()
        p.move_locked = True
        p.move_lock_npc_id = "jiang"
        p.life_burn_ticks = 0
        p.vigor = 80
        p.spirit = 80
        p.trap_attempts = 0
        try_clear_move_lock(p, "观望", "jiang")
        assert p.trap_attempts == 1


class TestEnterTrapState:
    def test_sets_move_locked(self):
        from backend.systems.trap import enter_trap_state
        p = make_player()
        enter_trap_state(p, "被围")
        assert p.move_locked is True

    def test_sets_trap_reason(self):
        from backend.systems.trap import enter_trap_state
        p = make_player()
        enter_trap_state(p, "被围困住")
        assert p.trap_reason == "被围困住"

    def test_default_npc_id(self):
        from backend.systems.trap import enter_trap_state
        p = make_player()
        enter_trap_state(p, "被围")
        assert p.move_lock_npc_id == "jiang"

    def test_custom_npc_id(self):
        from backend.systems.trap import enter_trap_state
        p = make_player()
        enter_trap_state(p, "被围", lock_npc_id="boss")
        assert p.move_lock_npc_id == "boss"

    def test_resets_trap_attempts(self):
        from backend.systems.trap import enter_trap_state
        p = make_player()
        p.trap_attempts = 5
        enter_trap_state(p, "被围")
        assert p.trap_attempts == 0

    def test_empty_reason_gets_default(self):
        from backend.systems.trap import enter_trap_state
        p = make_player()
        enter_trap_state(p, "")
        assert p.trap_reason == "骤入险局"

    def test_none_reason_gets_default(self):
        from backend.systems.trap import enter_trap_state
        p = make_player()
        enter_trap_state(p, None)
        assert p.trap_reason == "骤入险局"

    def test_long_reason_truncated(self):
        from backend.systems.trap import enter_trap_state
        p = make_player()
        enter_trap_state(p, "被" * 100)
        assert len(p.trap_reason) <= 80


class TestMaybeCollapseFromAttrs:
    def test_both_zero_dead(self):
        from backend.systems.trap import maybe_collapse_from_attrs
        p = make_player()
        p.vigor = 0
        p.spirit = 0
        result = maybe_collapse_from_attrs(p)
        assert result is not None
        assert result["outcome"] == "dead"
        assert p.dead is True

    def test_vigor_zero_spirit_positive_starts_burn(self):
        from backend.systems.constants import LIFE_BURN_TICKS
        from backend.systems.trap import maybe_collapse_from_attrs
        p = make_player()
        p.vigor = 0
        p.spirit = 50
        p.life_burn_ticks = 0
        result = maybe_collapse_from_attrs(p)
        assert result["outcome"] == "burning"
        assert p.life_burn_ticks == LIFE_BURN_TICKS
        assert p.move_locked is True

    def test_vigor_zero_already_burning(self):
        from backend.systems.trap import maybe_collapse_from_attrs
        p = make_player()
        p.vigor = 0
        p.spirit = 50
        p.life_burn_ticks = 3
        result = maybe_collapse_from_attrs(p)
        assert result["outcome"] == "burning"
        assert "燃烧中" in result["reason"]

    def test_spirit_zero_dead(self):
        from backend.systems.trap import maybe_collapse_from_attrs
        p = make_player()
        p.vigor = 50
        p.spirit = 0
        result = maybe_collapse_from_attrs(p)
        assert result["outcome"] == "dead"
        assert p.dead is True

    def test_both_positive_returns_none(self):
        from backend.systems.trap import maybe_collapse_from_attrs
        p = make_player()
        p.vigor = 50
        p.spirit = 50
        result = maybe_collapse_from_attrs(p)
        assert result is None
