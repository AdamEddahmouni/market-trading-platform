"""Tests for futures leverage stress engine (F8)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.futures_quality import (
    FuturesQualityFlag,
    quality_blocks_leverage_stress,
)
from market_platform_foundation.futures.leverage_stress import (
    compute_margin_percentile,
    compute_stress_score,
    leverage_stress_payload,
    stress_regime_from_score,
    StressRegime,
)
from market_platform_foundation.futures.positioning import CrowdingRegime
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns
from market_platform_foundation.providers.adapters.fixture_futures_margin import (
    FixtureFuturesMarginProvider,
)
from market_platform_foundation.donor_bridge.cross_lane_adapter import build_cross_lane_snapshot_from_futures


class LeverageStressEngineTests(unittest.TestCase):
    def test_quality_blocks_leverage_stress(self) -> None:
        self.assertTrue(
            quality_blocks_leverage_stress((FuturesQualityFlag.MARGIN_STALE.value,))
        )

    def test_compute_margin_percentile(self) -> None:
        history = [Decimal("13500"), Decimal("13950"), Decimal("16200")]
        self.assertEqual(compute_margin_percentile(Decimal("16200"), history), 1.0)

    def test_stress_regime_thresholds(self) -> None:
        self.assertEqual(stress_regime_from_score(0.75), StressRegime.HIGH)
        self.assertEqual(stress_regime_from_score(0.50), StressRegime.MODERATE)
        self.assertEqual(stress_regime_from_score(0.20), StressRegime.LOW)

    def test_compute_stress_score_with_crowding(self) -> None:
        score = compute_stress_score(
            margin_percentile=1.0,
            margin_change_pct=8.0,
            crowding_regime=CrowdingRegime.CROWDED_LONG.value,
            fragility_score=0.03,
            effective_leverage=18.5,
        )
        assert score is not None
        self.assertGreaterEqual(score, 0.65)

    def test_es_leverage_stress_golden_fixture_regression(self) -> None:
        expected_path = ROOT / "tests" / "fixtures" / "futures" / "es_leverage_stress_expected.json"
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        cutoff = iso_to_epoch_ns(str(expected["cutoff"]))

        provider = FixtureFuturesMarginProvider()
        result = provider.fetch_margin("ES", as_of_time_ns=cutoff)
        payload = leverage_stress_payload(
            result,
            instrument_family="ES",
            decision_time=cutoff,
            crowding_regime=CrowdingRegime.CROWDED_LONG.value,
            lead_price=6001.375,
            fragility_score=0.029268,
        )

        exp = expected["expected"]
        self.assertTrue(payload.get("futures_leverage_stress_available"))
        self.assertEqual(payload.get("stress_regime"), exp["stress_regime"])
        self.assertEqual(payload.get("long_liquidation_risk"), exp["long_liquidation_risk"])

        snapshot = payload.get("leverage_stress_snapshot")
        self.assertIsInstance(snapshot, dict)
        assert isinstance(snapshot, dict)
        exp_snapshot = exp["leverage_stress_snapshot"]
        for key, value in exp_snapshot.items():
            self.assertEqual(snapshot.get(key), value, msg=key)

    def test_cross_lane_emits_long_liquidation_risk(self) -> None:
        futures_payload = {
            "available": True,
            "snapshot_count": 1,
            "futures_leverage_stress_available": True,
            "leverage_stress_snapshot": {
                "long_liquidation_risk": True,
                "short_liquidation_risk": False,
                "stress_regime": "HIGH",
            },
        }
        _, evidence = build_cross_lane_snapshot_from_futures(futures_payload)
        signals = [row.get("signal") for row in evidence]
        self.assertIn("FUTURES_LONG_LIQUIDATION_RISK", signals)


if __name__ == "__main__":
    unittest.main()
