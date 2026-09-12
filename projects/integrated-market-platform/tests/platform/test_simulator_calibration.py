"""Paper simulator calibration contract and metric tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.paper.calibration import (  # noqa: E402
    CalibrationDivergenceClass,
    ThresholdStatus,
    assess_futures_comparator_suitability,
    compute_calibration_metrics,
    default_unset_threshold_config,
    validate_comparator_binding,
    validate_threshold_config,
)
from market_platform_foundation.paper.calibration.metrics import FillObservation  # noqa: E402


class SimulatorCalibrationTests(unittest.TestCase):
    def test_default_threshold_config_is_blocking(self) -> None:
        config = default_unset_threshold_config(campaign_slug="FTEP-V1-001")
        self.assertTrue(config.execution_claims_blocked)
        payload = config.to_dict()
        restored = validate_threshold_config(payload)
        self.assertEqual(restored.schema_version, config.schema_version)

    def test_set_threshold_requires_value(self) -> None:
        payload = default_unset_threshold_config().to_dict()
        payload["thresholds"]["fill_no_fill_disagreement_rate_max"] = {
            "status": "SET",
            "value": 0.05,
            "unit": "rate",
        }
        restored = validate_threshold_config(payload)
        field = restored.thresholds["fill_no_fill_disagreement_rate_max"]
        self.assertEqual(field.status, ThresholdStatus.SET)
        self.assertEqual(field.value, 0.05)

    def test_compute_metrics_from_fixture_pairs(self) -> None:
        imp = [
            FillObservation(
                order_id="o1",
                filled=True,
                fill_price=100.0,
                ack_time_ns=1_000,
                realized_pnl_minor=50,
                position_qty=1,
            ),
            FillObservation(
                order_id="o2",
                filled=False,
                divergence_reason="PASSIVE_NO_FILL",
            ),
        ]
        comp = [
            FillObservation(
                order_id="o1",
                filled=True,
                fill_price=100.1,
                ack_time_ns=1_500,
                realized_pnl_minor=40,
                position_qty=1,
            ),
            FillObservation(order_id="o2", filled=False),
        ]
        metrics = compute_calibration_metrics(
            imp_fills=imp,
            comparator_fills=comp,
            reference_prices={"o1": 100.0},
        )
        self.assertEqual(metrics.pair_count, 2)
        self.assertEqual(metrics.fill_disagreement_rate, 0.0)
        self.assertAlmostEqual(metrics.mean_slippage_bps or 0.0, 10.0, places=3)
        self.assertEqual(metrics.pnl_delta_minor, 10)
        self.assertIn(CalibrationDivergenceClass.WITHIN_TOLERANCE, metrics.divergence_classes)

    def test_comparator_binding_rejects_market_truth(self) -> None:
        with self.assertRaises(Exception):
            validate_comparator_binding(
                {
                    "comparator_id": "tradier",
                    "environment": "sandbox",
                    "account_mode": "paper",
                    "limitations": ["equity_only"],
                    "is_market_truth": True,
                }
            )

    def test_futures_suitability_reads_wave_a_audit(self) -> None:
        result = assess_futures_comparator_suitability(
            broker="internal_simulation",
            repository_root=ROOT,
        )
        self.assertEqual(result.calibration_comparator_role, "PRIMARY_FOR_FTEP_SKELETON")
        self.assertTrue(result.advisory_only)
        self.assertTrue(result.not_market_truth)


if __name__ == "__main__":
    unittest.main()
