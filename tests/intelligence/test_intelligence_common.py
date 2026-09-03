"""Tests for intelligence contract shared primitives."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.contracts.common import (  # noqa: E402
    ContractReference,
    ForecastEstimate,
    QualityState,
    QualitySummary,
    TimeHorizonNs,
    contract_reference_to_dict,
    forecast_estimate_from_dict,
    normalize_unique_refs,
    round_trip_contract_dict,
    validate_id,
    validate_probability,
)


class IntelligenceCommonTests(unittest.TestCase):
    def test_valid_ids(self) -> None:
        validate_id("event-abc-123")
        ref = ContractReference(kind="signal", id="sig-1")
        payload = contract_reference_to_dict(ref)
        self.assertEqual(payload["schema_version"], "1")

    def test_invalid_ids_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_id("")
        with self.assertRaises(ValueError):
            validate_id("  leading")
        with self.assertRaises(ValueError):
            validate_id(" trailing ")

    def test_probability_bounds(self) -> None:
        validate_probability(0.0)
        validate_probability(1.0)
        with self.assertRaises(ValueError):
            validate_probability(-0.01)
        with self.assertRaises(ValueError):
            validate_probability(1.01)
        with self.assertRaises(ValueError):
            validate_probability(math.nan)
        with self.assertRaises(ValueError):
            validate_probability(math.inf)

    def test_quality_summary_round_trip(self) -> None:
        quality = QualitySummary(state=QualityState.DEGRADED, flags=("PARTIAL_DATA", "STALE_INFERENCE"))
        payload = {"state": quality.state.value, "flags": list(quality.flags)}
        restored = round_trip_contract_dict(payload)
        self.assertEqual(restored["flags"], ["PARTIAL_DATA", "STALE_INFERENCE"])

    def test_duplicate_refs_normalized(self) -> None:
        ref = ContractReference(kind="event", id="e1")
        normalized = normalize_unique_refs((ref, ref))
        self.assertEqual(len(normalized), 1)

    def test_horizon_negative_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TimeHorizonNs(duration_ns=-1)
        with self.assertRaises(ValueError):
            TimeHorizonNs(duration_ns=0)

    def test_forecast_estimate_rejects_non_finite(self) -> None:
        with self.assertRaises(ValueError):
            ForecastEstimate(estimate_kind="classification_probability", probability=math.nan)
        payload = forecast_estimate_from_dict(
            {"estimate_kind": "regression", "expected_value": 0.01}
        )
        self.assertEqual(payload.expected_value, 0.01)


if __name__ == "__main__":
    unittest.main()
