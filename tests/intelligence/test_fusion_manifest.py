"""Fusion manifest tests (BUILD 14)."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.fusion import (
    ForecastFusionManifest,
    FusionPolicy,
    build_contributor_ref,
)
from tests.intelligence.fusion_fixtures import (
    default_horizon,
    default_target,
    production_contributor,
    sample_snapshot,
    synthetic_production_forecast,
)


class FusionManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot = sample_snapshot()
        self.target = default_target()
        self.horizon = default_horizon()
        self.policy = FusionPolicy()

    def _manifest(self, contributors):
        return ForecastFusionManifest.create(
            snapshot_id=self.snapshot.snapshot_id,
            target=self.target,
            horizon=self.horizon,
            decision_time_ns=self.snapshot.decision_time_ns,
            scope=self.snapshot.scope,
            contributors=contributors,
            fusion_policy=self.policy,
        )

    def test_manifest_identity_order_independent(self) -> None:
        f1 = synthetic_production_forecast(
            forecast_id="FCST-SYN-1",
            snapshot=self.snapshot,
            probability=0.7,
            signal_ids=("SIG-A",),
            forecast_family_key="family-a",
        )
        f2 = synthetic_production_forecast(
            forecast_id="FCST-SYN-2",
            snapshot=self.snapshot,
            probability=0.6,
            signal_ids=("SIG-B",),
            forecast_family_key="family-b",
        )
        manifest_a = self._manifest([production_contributor(f2), production_contributor(f1)])
        manifest_b = self._manifest([production_contributor(f1), production_contributor(f2)])
        self.assertEqual(manifest_a.fusion_input_id, manifest_b.fusion_input_id)

    def test_late_forecast_does_not_change_manifest(self) -> None:
        f1 = synthetic_production_forecast(
            forecast_id="FCST-SYN-1",
            snapshot=self.snapshot,
            probability=0.7,
            signal_ids=("SIG-A",),
            forecast_family_key="family-a",
        )
        f2 = synthetic_production_forecast(
            forecast_id="FCST-SYN-2",
            snapshot=self.snapshot,
            probability=0.6,
            signal_ids=("SIG-B",),
            forecast_family_key="family-b",
        )
        manifest = self._manifest([production_contributor(f1), production_contributor(f2)])
        _ = synthetic_production_forecast(
            forecast_id="FCST-SYN-3",
            snapshot=self.snapshot,
            probability=0.5,
            signal_ids=("SIG-C",),
            forecast_family_key="family-c",
        )
        self.assertEqual(len(manifest.contributors), 2)


if __name__ == "__main__":
    unittest.main()
