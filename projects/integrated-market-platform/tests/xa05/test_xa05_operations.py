"""XA-05 operations tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.xa05.operations import execute, reset_engine_for_tests
from market_platform_foundation.xa05.queries import compare_states

from tests.xa05.test_xa05_fixtures import build_engine, populate_repository


class Xa05OperationsTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_engine_for_tests()
        populate_repository()

    def test_status_ok(self) -> None:
        result = execute("XA05.OP.STATUS")
        self.assertEqual(result.outcome_code, "OK")
        self.assertEqual(result.capability_id, "XA05.OP.STATUS")
        self.assertEqual(result.verification["persistence_mode"], "EPHEMERAL_RECONSTRUCTABLE")

    def test_construct_state_ok(self) -> None:
        result = execute(
            "XA05.OP.CONSTRUCT_STATE",
            {
                "decision_time": "2026-08-20T00:00:00Z",
                "construction_time": "2026-08-20T00:00:00Z",
            },
        )
        self.assertEqual(result.outcome_code, "OK")
        self.assertIn("state_id", result.verification)

    def test_compare_states_reports_changes(self) -> None:
        engine = build_engine()
        earlier = engine.construct_state(
            decision_time="2020-02-01T00:00:00Z",
            construction_time="2020-02-01T00:00:00Z",
        )
        later = engine.construct_state(
            decision_time="2026-08-20T00:00:00Z",
            construction_time="2026-08-20T00:00:00Z",
        )
        payload = compare_states(earlier, later)
        self.assertTrue(payload["semantic_fingerprint_changed"])


if __name__ == "__main__":
    unittest.main()
