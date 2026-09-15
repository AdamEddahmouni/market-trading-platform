"""Item 9 prospective receipt → comparator bridge (no orders)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.paper.calibration.bar_ohlcv_prospective_comparator_bridge import (  # noqa: E402
    REASON_NOT_PROSPECTIVE_RECEIPT,
    build_comparator_bridge_from_receipt,
    validate_prospective_receipt_for_comparator,
)
from market_platform_foundation.paper.calibration.bar_ohlcv_prospective_proof import (  # noqa: E402
    PROOF_MODE_RETROSPECTIVE,
    run_prospective_proof,
)
from market_platform_foundation.paper.calibration.bar_ohlcv_sources import (  # noqa: E402
    normalize_moomoo_kline_row,
)

COLLECTION_ROOT = ROOT.parent


def _kline_row(time_key: str = "2023-11-14 10:30:00") -> dict[str, object]:
    return {
        "close": 10.2,
        "high": 10.5,
        "low": 9.5,
        "open": 10.0,
        "time_key": time_key,
        "volume": 50_000,
    }


class BarOhlcvProspectiveComparatorBridgeTests(unittest.TestCase):
    def _prospective_receipt(self) -> dict[str, object]:
        rows = (_kline_row(time_key="2023-11-14 10:29:00"), _kline_row())
        first = normalize_moomoo_kline_row(
            rows[0],
            instrument_id="AAPL",
            fetched_at_ns=9_999_999_999_999_999_999,
        )
        second = normalize_moomoo_kline_row(
            rows[1],
            instrument_id="AAPL",
            fetched_at_ns=9_999_999_999_999_999_999,
        )
        assert first is not None and second is not None
        outcome = run_prospective_proof(
            instrument_id="AAPL",
            collection_root=COLLECTION_ROOT,
            env={},
            signal_time_ns=int(first["event_time"]),
            signal_established_at_ns=int(first["event_time"]),
            observation_time_ns=int(second["available_time"]),
            kline_rows=rows,
            experiment_id="bridge-test-exp",
            runtime_git_sha="test-sha",
        )
        assert outcome["receipt"] is not None
        return outcome["receipt"]

    def test_receipt_includes_bar_id_and_first_post_signal_proof(self) -> None:
        receipt = self._prospective_receipt()
        self.assertTrue(receipt["first_post_signal_proof"]["ok"])
        self.assertIsNotNone(receipt.get("bar_id"))
        self.assertIn("simulator_output", receipt)
        self.assertEqual(receipt["item9_status"], "PARTIAL_NOT_CALIBRATED")

    def test_validate_rejects_transport_receipt(self) -> None:
        receipt = dict(self._prospective_receipt())
        receipt["proof_mode"] = PROOF_MODE_RETROSPECTIVE
        gate = validate_prospective_receipt_for_comparator(receipt)
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["reason_code"], REASON_NOT_PROSPECTIVE_RECEIPT)

    @mock.patch(
        "market_platform_foundation.paper.calibration.bar_ohlcv_prospective_comparator_bridge.run_bounded_bar_ohlcv_experiment",
    )
    def test_bridge_imp_leg_only_zero_pairs(self, dry_run: mock.Mock) -> None:
        from market_platform_foundation.paper.calibration.bar_ohlcv_experiment import (
            BarOhlcvExperimentResult,
            CLASSIFICATION_RUNNABLE,
        )

        dry_run.return_value = BarOhlcvExperimentResult(
            classification=CLASSIFICATION_RUNNABLE,
            signal_time_ns=1,
            observation_time_ns=2,
            bar_source_id="MOOMOO_OPEND_HISTORY_KLINE_1M",
            instrument_id="AAPL",
            bar_provenance={},
            first_post_signal_bar=None,
            simulator_version="test-sim",
            sim_order_state="FILLED",
            sim_reason_codes=(),
            sim_fill=None,
            comparator_harness_status="COMPARATOR_NOT_CONFIGURED",
            calibrated=False,
            orders_placed=False,
        )
        receipt = self._prospective_receipt()
        payload = build_comparator_bridge_from_receipt(
            receipt,
            env={},
            collection_root=COLLECTION_ROOT,
        )
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["matched_pair_count"], 0)
        self.assertFalse(payload["orders_placed"])
        self.assertFalse(payload["calibrated"])
        self.assertIsNone(payload["comparator_external_leg"])


if __name__ == "__main__":
    unittest.main()
