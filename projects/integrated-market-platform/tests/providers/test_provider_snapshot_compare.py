"""Fixture-backed tests for frozen provider snapshot comparison."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from market_platform_foundation.providers.snapshot_compare import (
    FrozenCompareError,
    FrozenCompareSnapshot,
    FrozenObservationRow,
    FrozenProviderArm,
    compare_frozen_provider_snapshot,
    frozen_compare_snapshot_from_dict,
    summarize_missingness,
)

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "providers" / "frozen_compare_sample.json"


class ProviderSnapshotCompareTests(unittest.TestCase):
    def test_fixture_compare_missingness_disagreement_latency(self) -> None:
        payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
        snapshot = frozen_compare_snapshot_from_dict(payload)
        report = compare_frozen_provider_snapshot(snapshot, reference_provider_id="alpha")
        self.assertEqual(report.reference_provider_id, "alpha")
        self.assertEqual(len(report.arms), 1)
        arm = report.arms[0]
        self.assertEqual(arm.candidate_provider_id, "beta")
        self.assertEqual(arm.missing_in_candidate, ("MSFT",))
        self.assertEqual(arm.missing_in_reference, ())
        self.assertEqual(len(arm.value_disagreements), 1)
        self.assertEqual(arm.value_disagreements[0]["instrument_key"], "AAPL")
        self.assertEqual(len(arm.latency_deltas_ns), 1)
        self.assertEqual(arm.latency_deltas_ns[0]["delta_ns"], 500_000)

    def test_summarize_missingness(self) -> None:
        snapshot = FrozenCompareSnapshot(
            schema_version="1.0.0",
            logical_id="providers.frozen_observation_compare",
            observed_at="2026-09-11T00:00:00Z",
            capability_id="quote",
            arms=(
                FrozenProviderArm(
                    "ref",
                    (
                        FrozenObservationRow("A", 1.0),
                        FrozenObservationRow("B", 2.0),
                    ),
                ),
                FrozenProviderArm("cand", (FrozenObservationRow("A", 1.0),)),
            ),
        )
        report = compare_frozen_provider_snapshot(snapshot, reference_provider_id="ref")
        self.assertEqual(summarize_missingness(report), {"cand": 1})

    def test_single_arm_fails_validation(self) -> None:
        snapshot = FrozenCompareSnapshot(
            schema_version="1.0.0",
            logical_id="providers.frozen_observation_compare",
            observed_at="2026-09-11T00:00:00Z",
            capability_id="quote",
            arms=(FrozenProviderArm("only", ()),),
        )
        with self.assertRaises(FrozenCompareError):
            compare_frozen_provider_snapshot(snapshot)


if __name__ == "__main__":
    unittest.main()
