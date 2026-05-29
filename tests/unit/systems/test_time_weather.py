import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from conftest import make_player
from backend.systems.time_weather import shichen_name, is_night, shichen_phase, advance_clock


class TestShichenName(unittest.TestCase):
    def test_all_twelve_shichen(self):
        expected = ["子时", "丑时", "寅时", "卯时", "辰时", "巳时",
                    "午时", "未时", "申时", "酉时", "戌时", "亥时"]
        for i, name in enumerate(expected):
            self.assertEqual(shichen_name(i), name)

    def test_boundary_zero(self):
        self.assertEqual(shichen_name(0), "子时")

    def test_boundary_eleven(self):
        self.assertEqual(shichen_name(11), "亥时")

    def test_modulo_twelve(self):
        self.assertEqual(shichen_name(12), "子时")
        self.assertEqual(shichen_name(13), "丑时")
        self.assertEqual(shichen_name(24), "子时")
        self.assertEqual(shichen_name(25), "丑时")

    def test_negative_modulo(self):
        self.assertEqual(shichen_name(-1), "亥时")
        self.assertEqual(shichen_name(-2), "戌时")
        self.assertEqual(shichen_name(-12), "子时")
        self.assertEqual(shichen_name(-13), "亥时")


class TestIsNight(unittest.TestCase):
    def test_night_shichen(self):
        self.assertTrue(is_night(0))
        self.assertTrue(is_night(1))
        self.assertTrue(is_night(10))
        self.assertTrue(is_night(11))

    def test_day_shichen(self):
        for i in [2, 3, 4, 5, 6, 7, 8, 9]:
            self.assertFalse(is_night(i), f"is_night({i}) should be False")

    def test_modulo_night(self):
        self.assertTrue(is_night(12))
        self.assertTrue(is_night(13))
        self.assertTrue(is_night(22))
        self.assertTrue(is_night(23))

    def test_modulo_day(self):
        self.assertFalse(is_night(14))
        self.assertFalse(is_night(16))


class TestShichenPhase(unittest.TestCase):
    def test_deep_night(self):
        self.assertEqual(shichen_phase(0), "深夜")
        self.assertEqual(shichen_phase(1), "深夜")

    def test_dawn(self):
        self.assertEqual(shichen_phase(2), "凌晨")
        self.assertEqual(shichen_phase(3), "凌晨")

    def test_morning(self):
        self.assertEqual(shichen_phase(4), "上午")
        self.assertEqual(shichen_phase(5), "上午")

    def test_noon(self):
        self.assertEqual(shichen_phase(6), "正午")
        self.assertEqual(shichen_phase(7), "正午")

    def test_dusk(self):
        self.assertEqual(shichen_phase(8), "傍晚")
        self.assertEqual(shichen_phase(9), "傍晚")

    def test_night(self):
        self.assertEqual(shichen_phase(10), "夜里")
        self.assertEqual(shichen_phase(11), "夜里")

    def test_modulo_phase(self):
        self.assertEqual(shichen_phase(12), "深夜")
        self.assertEqual(shichen_phase(14), "凌晨")
        self.assertEqual(shichen_phase(18), "正午")
        self.assertEqual(shichen_phase(22), "夜里")


class TestAdvanceClock(unittest.TestCase):
    @patch("random.random", return_value=1.0)
    def test_advance_one_tick(self, _mock):
        p = make_player(world_shichen=4, world_tick=0, world_day=1)
        advance_clock(p, ticks=1)
        self.assertEqual(p.world_shichen, 5)
        self.assertEqual(p.world_tick, 1)
        self.assertEqual(p.world_day, 1)

    @patch("random.random", return_value=1.0)
    def test_advance_multiple_ticks(self, _mock):
        p = make_player(world_shichen=4, world_tick=0, world_day=1)
        advance_clock(p, ticks=3)
        self.assertEqual(p.world_shichen, 7)
        self.assertEqual(p.world_tick, 3)
        self.assertEqual(p.world_day, 1)

    def test_advance_zero_ticks(self):
        p = make_player(world_shichen=4, world_tick=0, world_day=1)
        advance_clock(p, ticks=0)
        self.assertEqual(p.world_shichen, 4)
        self.assertEqual(p.world_tick, 0)
        self.assertEqual(p.world_day, 1)

    def test_advance_negative_ticks(self):
        p = make_player(world_shichen=4, world_tick=0, world_day=1)
        advance_clock(p, ticks=-5)
        self.assertEqual(p.world_shichen, 4)
        self.assertEqual(p.world_tick, 0)
        self.assertEqual(p.world_day, 1)

    @patch("random.random", return_value=1.0)
    def test_shichen_overflow_increments_day(self, _mock):
        p = make_player(world_shichen=11, world_tick=0, world_day=1)
        advance_clock(p, ticks=1)
        self.assertEqual(p.world_shichen, 0)
        self.assertEqual(p.world_day, 2)

    @patch("random.random", return_value=1.0)
    def test_shichen_overflow_multiple_days(self, _mock):
        p = make_player(world_shichen=10, world_tick=0, world_day=1)
        advance_clock(p, ticks=3)
        self.assertEqual(p.world_shichen, 1)
        self.assertEqual(p.world_day, 2)

    @patch("random.random", return_value=1.0)
    def test_unconscious_ticks_decrement(self, _mock):
        p = make_player(world_shichen=4, world_tick=0, world_day=1,
                        unconscious_ticks=3, sleep_debt=0)
        del p.sleep_debt
        advance_clock(p, ticks=2)
        self.assertEqual(p.unconscious_ticks, 1)

    @patch("random.random", return_value=1.0)
    def test_sleep_debt_increases(self, _mock):
        p = make_player(world_shichen=4, world_tick=0, world_day=1,
                        spirit=80, spirit_max=100, sleep_debt=0)
        advance_clock(p, ticks=3)
        self.assertEqual(p.sleep_debt, 3)

    @patch("random.random", return_value=1.0)
    def test_ticks_capped_at_24(self, _mock):
        p = make_player(world_shichen=4, world_tick=0, world_day=1)
        advance_clock(p, ticks=100)
        self.assertLessEqual(p.world_tick, 24)


if __name__ == "__main__":
    unittest.main()
