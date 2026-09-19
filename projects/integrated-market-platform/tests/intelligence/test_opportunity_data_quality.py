"""Honesty projector for operator data_quality."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.opportunity.data_quality import (
    project_opportunity_data_quality,
)


class OpportunityDataQualityTests(unittest.TestCase):
    def test_recorded_artifacts_do_not_claim_fresh_or_entitled(self) -> None:
        quality = project_opportunity_data_quality(
            source="RECORDED_ARTIFACTS",
            live_observational_env=True,
        )
        self.assertEqual(quality["freshness"], "UNAVAILABLE")
        self.assertEqual(quality["entitlement"], "UNAVAILABLE")
        self.assertEqual(quality["source"], "RECORDED_ARTIFACTS")
        self.assertEqual(quality["operator_surface_flag"], "OK")
        self.assertNotIn("quote", quality)

    def test_live_observational_source_is_unavailable(self) -> None:
        live = project_opportunity_data_quality(source="LIVE_OBSERVATIONAL")
        self.assertEqual(live["status"], "UNAVAILABLE")
        self.assertEqual(live["reason_codes"], ["LIVE_OBSERVATIONAL_NOT_ENGINE_QUALITY"])

    def test_replay_does_not_set_fresh_from_adapter_presence(self) -> None:
        quality = project_opportunity_data_quality(source="REPLAY")
        self.assertEqual(quality["freshness"], "UNAVAILABLE")
        self.assertEqual(quality["entitlement"], "UNAVAILABLE")
        self.assertEqual(quality["operator_surface_flag"], "OK")

    def test_stale_or_degraded_sets_operator_surface_flag(self) -> None:
        degraded = project_opportunity_data_quality(
            source="UNKNOWN",
            quality_decision={"action": "DEGRADE", "freshness": "STALE"},
        )
        self.assertEqual(degraded["status"], "DEGRADED")
        self.assertEqual(degraded["operator_surface_flag"], "STALE_OR_DEGRADED")


if __name__ == "__main__":
    unittest.main()
