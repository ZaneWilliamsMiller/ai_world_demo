from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import unittest

from backend.llm.params import (
    COMPRESS_MAX_TOKENS,
    COMPRESS_TEMPERATURE,
    CROSS_REFLECT_MAX_TOKENS,
    CROSS_REFLECT_TEMPERATURE,
    ENCOUNTER_MAX_TOKENS,
    ENCOUNTER_TEMPERATURE,
    FINALE_MAX_TOKENS,
    FINALE_TEMPERATURE,
    PLAN_MAX_TOKENS,
    PLAN_TEMPERATURE,
    REFLECT_MAX_TOKENS,
    REFLECT_TEMPERATURE,
    TALK_FULL_MAX_TOKENS,
    TALK_LIGHT_MAX_TOKENS,
    TALK_TEMPERATURE,
)


class TestLlmParams(unittest.TestCase):
    def test_talk_temperature_type_and_range(self):
        self.assertIsInstance(TALK_TEMPERATURE, float)
        self.assertGreater(TALK_TEMPERATURE, 0.0)
        self.assertLessEqual(TALK_TEMPERATURE, 2.0)

    def test_talk_temperature_value(self):
        self.assertEqual(TALK_TEMPERATURE, 0.85)

    def test_talk_light_max_tokens_type_and_range(self):
        self.assertIsInstance(TALK_LIGHT_MAX_TOKENS, int)
        self.assertGreater(TALK_LIGHT_MAX_TOKENS, 0)

    def test_talk_light_max_tokens_value(self):
        self.assertEqual(TALK_LIGHT_MAX_TOKENS, 450)

    def test_talk_full_max_tokens_type_and_range(self):
        self.assertIsInstance(TALK_FULL_MAX_TOKENS, int)
        self.assertGreater(TALK_FULL_MAX_TOKENS, 0)

    def test_talk_full_max_tokens_value(self):
        self.assertEqual(TALK_FULL_MAX_TOKENS, 800)

    def test_reflect_temperature_type_and_range(self):
        self.assertIsInstance(REFLECT_TEMPERATURE, float)
        self.assertGreater(REFLECT_TEMPERATURE, 0.0)
        self.assertLessEqual(REFLECT_TEMPERATURE, 2.0)

    def test_reflect_temperature_value(self):
        self.assertEqual(REFLECT_TEMPERATURE, 0.7)

    def test_reflect_max_tokens_type_and_range(self):
        self.assertIsInstance(REFLECT_MAX_TOKENS, int)
        self.assertGreater(REFLECT_MAX_TOKENS, 0)

    def test_reflect_max_tokens_value(self):
        self.assertEqual(REFLECT_MAX_TOKENS, 400)

    def test_cross_reflect_temperature_type_and_range(self):
        self.assertIsInstance(CROSS_REFLECT_TEMPERATURE, float)
        self.assertGreater(CROSS_REFLECT_TEMPERATURE, 0.0)
        self.assertLessEqual(CROSS_REFLECT_TEMPERATURE, 2.0)

    def test_cross_reflect_max_tokens_type_and_range(self):
        self.assertIsInstance(CROSS_REFLECT_MAX_TOKENS, int)
        self.assertGreater(CROSS_REFLECT_MAX_TOKENS, 0)

    def test_plan_temperature_type_and_range(self):
        self.assertIsInstance(PLAN_TEMPERATURE, float)
        self.assertGreater(PLAN_TEMPERATURE, 0.0)
        self.assertLessEqual(PLAN_TEMPERATURE, 2.0)

    def test_plan_max_tokens_type_and_range(self):
        self.assertIsInstance(PLAN_MAX_TOKENS, int)
        self.assertGreater(PLAN_MAX_TOKENS, 0)

    def test_encounter_temperature_type_and_range(self):
        self.assertIsInstance(ENCOUNTER_TEMPERATURE, float)
        self.assertGreater(ENCOUNTER_TEMPERATURE, 0.0)
        self.assertLessEqual(ENCOUNTER_TEMPERATURE, 2.0)

    def test_encounter_max_tokens_type_and_range(self):
        self.assertIsInstance(ENCOUNTER_MAX_TOKENS, int)
        self.assertGreater(ENCOUNTER_MAX_TOKENS, 0)

    def test_compress_temperature_type_and_range(self):
        self.assertIsInstance(COMPRESS_TEMPERATURE, float)
        self.assertGreater(COMPRESS_TEMPERATURE, 0.0)
        self.assertLessEqual(COMPRESS_TEMPERATURE, 2.0)

    def test_compress_max_tokens_type_and_range(self):
        self.assertIsInstance(COMPRESS_MAX_TOKENS, int)
        self.assertGreater(COMPRESS_MAX_TOKENS, 0)

    def test_finale_temperature_type_and_range(self):
        self.assertIsInstance(FINALE_TEMPERATURE, float)
        self.assertGreater(FINALE_TEMPERATURE, 0.0)
        self.assertLessEqual(FINALE_TEMPERATURE, 2.0)

    def test_finale_max_tokens_type_and_range(self):
        self.assertIsInstance(FINALE_MAX_TOKENS, int)
        self.assertGreater(FINALE_MAX_TOKENS, 0)

    def test_all_temperatures_within_valid_range(self):
        temps = [
            TALK_TEMPERATURE, REFLECT_TEMPERATURE, CROSS_REFLECT_TEMPERATURE,
            PLAN_TEMPERATURE, ENCOUNTER_TEMPERATURE, COMPRESS_TEMPERATURE,
            FINALE_TEMPERATURE,
        ]
        for t in temps:
            self.assertGreater(t, 0.0)
            self.assertLessEqual(t, 2.0)

    def test_all_max_tokens_positive(self):
        tokens = [
            TALK_LIGHT_MAX_TOKENS, TALK_FULL_MAX_TOKENS, REFLECT_MAX_TOKENS,
            CROSS_REFLECT_MAX_TOKENS, PLAN_MAX_TOKENS, ENCOUNTER_MAX_TOKENS,
            COMPRESS_MAX_TOKENS, FINALE_MAX_TOKENS,
        ]
        for t in tokens:
            self.assertGreater(t, 0)

    def test_talk_full_greater_than_light(self):
        self.assertGreater(TALK_FULL_MAX_TOKENS, TALK_LIGHT_MAX_TOKENS)


if __name__ == "__main__":
    unittest.main()
