"""MEASURED labels must match non-zero timestamp presence."""

from __future__ import annotations

import unittest

from market_platform_foundation.hot_path_telemetry.exercise import (
    assert_timestamp_exercise_honest,
    derive_timestamp_exercise,
)


class HotPathExerciseHonestyTests(unittest.TestCase):
    def test_measured_requires_present_count(self) -> None:
        presence = {
            "source_event_at": {"present_count": 0, "missing_count": 2},
            "provider_received_at": {"present_count": 1, "missing_count": 0},
            "imp_received_at": {"present_count": 1, "missing_count": 0},
            "normalized_at": {"present_count": 1, "missing_count": 0},
            "router_dispatched_at": {"present_count": 0, "missing_count": 0},
            "detected_at": {"present_count": 0, "missing_count": 0},
            "opportunity_created_at": {"present_count": 0, "missing_count": 0},
            "operator_surfaced_at": {"present_count": 0, "missing_count": 0},
        }
        exercise = derive_timestamp_exercise(presence)
        self.assertEqual(exercise["source_event_at"], "NOT_EXERCISED")
        self.assertEqual(exercise["provider_received_at"], "MEASURED")
        self.assertEqual(exercise["opportunity_created_at"], "NOT_EXERCISED")
        assert_timestamp_exercise_honest(exercise, presence)

    def test_mismatch_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "HOT_PATH_TELEMETRY_EXERCISE_MISMATCH"):
            assert_timestamp_exercise_honest(
                {"source_event_at": "MEASURED"},
                {"source_event_at": {"present_count": 0, "missing_count": 1}},
            )


if __name__ == "__main__":
    unittest.main()
