"""Honesty projector: never fabricate FRESH/ENTITLED from env flags."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.opportunity.data_quality import (
    project_opportunity_data_quality,
)


class OpportunityDataQualityTests(unittest.TestCase):
    def test_recorded_artifacts_stay_unavailable_under_live_env(self) -> None:
        quality = project_opportunity_data_quality(source="RECORDED_ARTIFACTS", live_observational_env=True)
        self.assertEqual(quality["freshness"], "UNAVAILABLE")
        self.assertEqual(quality["source"], "RECORDED_ARTIFACTS")

    def test_live_observational_is_unavailable(self) -> None:
        quality = project_opportunity_data_quality(source="LIVE_OBSERVATIONAL")
        self.assertEqual(quality["status"], "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
