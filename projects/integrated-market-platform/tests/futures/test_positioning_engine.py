"""Tests for futures COT / OI positioning engine (F4)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.futures import cot_point_in_time_valid
from market_platform_foundation.contracts.futures_quality import FuturesQualityFlag
from market_platform_foundation.futures.positioning import (
    CROWDED_LONG_THRESHOLD,
    CrowdingRegime,
    OiVelocityHypothesis,
    compute_net_percentile,
    compute_net_zscore,
    compute_oi_velocity,
    crowding_regime,
    filter_pit_reports,
    positioning_payload,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns
from market_platform_foundation.providers.adapters.fixture_futures_chain import FixtureFuturesChainProvider
from market_platform_foundation.providers.adapters.fixture_futures_positioning import (
    DEFAULT_COT_FIXTURE,
    FixtureFuturesPositioningProvider,
)
from market_platform_foundation.providers.contracts import ProviderResult
from market_platform_foundation.donor_bridge.cross_lane_adapter import build_cross_lane_snapshot_from_futures


class PositioningEngineTests(unittest.TestCase):
    def test_crowding_regime_thresholds(self) -> None:
        self.assertEqual(crowding_regime(CROWDED_LONG_THRESHOLD), CrowdingRegime.CROWDED_LONG)
        self.assertEqual(crowding_regime(0.19), CrowdingRegime.CROWDED_SHORT)
        self.assertEqual(crowding_regime(0.5), CrowdingRegime.NEUTRAL)

    def test_filter_pit_reports_excludes_future_publication(self) -> None:
        reports = [
            {
                "observation_time": "2025-05-27T00:00:00Z",
                "publication_time": "2025-05-30T17:30:00Z",
                "net": 75000,
            },
            {
                "observation_time": "2025-06-03T00:00:00Z",
                "publication_time": "2025-06-06T17:30:00Z",
                "net": 90000,
            },
        ]
        pit, flags = filter_pit_reports(reports, "2025-06-02T14:41:07.000000000Z")
        self.assertEqual(len(pit), 1)
        self.assertEqual(pit[0]["net"], 75000)
        self.assertNotIn(FuturesQualityFlag.COT_PUBLICATION_PENDING.value, flags)

    def test_filter_pit_reports_pending_flag(self) -> None:
        reports = [
            {
                "observation_time": "2025-05-27T00:00:00Z",
                "publication_time": "2025-06-06T17:30:00Z",
                "net": 75000,
            },
        ]
        _, flags = filter_pit_reports(reports, "2025-06-02T14:41:07.000000000Z")
        self.assertIn(FuturesQualityFlag.COT_PUBLICATION_PENDING.value, flags)

    def test_compute_net_percentile_and_zscore(self) -> None:
        history = [20000, 30000, 40000, 50000]
        self.assertEqual(compute_net_percentile(50000, history), 1.0)
        zscore = compute_net_zscore(50000, history)
        assert zscore is not None
        self.assertGreater(zscore, 0)

    def test_compute_oi_velocity_rising_with_price(self) -> None:
        chain = ProviderResult(
            status="available",
            events=(
                {
                    "open_interest": 200000,
                    "price": "6001.75",
                    "open_interest_history": [
                        {"open_interest": 195000, "price": 5998.5},
                        {"open_interest": 200000, "price": 6001.75},
                    ],
                },
            ),
        )
        obs = compute_oi_velocity(chain)
        self.assertEqual(obs.label, OiVelocityHypothesis.OI_RISING_WITH_PRICE.value)
        self.assertEqual(obs.front_oi_delta, 5000)

    def test_es_positioning_golden_fixture_regression(self) -> None:
        expected_path = ROOT / "tests" / "fixtures" / "futures" / "es_positioning_expected.json"
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        cutoff = iso_to_epoch_ns(str(expected["cutoff"]))
        positioning_result = FixtureFuturesPositioningProvider().fetch_positioning(
            expected["symbol"],
            as_of_time_ns=cutoff,
        )
        chain_result = FixtureFuturesChainProvider().fetch_chain(
            expected["symbol"],
            as_of_time_ns=cutoff,
        )
        payload = positioning_payload(
            positioning_result,
            chain_result,
            decision_time=cutoff,
        )
        exp = expected["expected"]
        self.assertEqual(payload["available"], exp["available"])
        self.assertEqual(payload["futures_positioning_available"], exp["futures_positioning_available"])
        self.assertEqual(payload["crowding_regime"], exp["crowding_regime"])
        snap = payload["positioning_snapshot"]
        exp_snap = exp["positioning_snapshot"]
        self.assertEqual(snap["net"], exp_snap["net"])
        self.assertEqual(snap["net_percentile"], exp_snap["net_percentile"])
        self.assertEqual(snap["net_zscore"], exp_snap["net_zscore"])
        self.assertEqual(snap["participant_category"], exp_snap["participant_category"])
        oi = payload["oi_velocity_hypothesis"]
        exp_oi = exp["oi_velocity_hypothesis"]
        self.assertEqual(oi["label"], exp_oi["label"])
        self.assertEqual(oi["front_oi_delta"], exp_oi["front_oi_delta"])
        self.assertEqual(oi["front_price_delta"], exp_oi["front_price_delta"])
        self.assertNotEqual(snap["net"], exp["lookahead_excluded_net"])

    def test_cross_lane_emits_crowded_long_from_cot(self) -> None:
        futures_payload = {
            "available": True,
            "snapshot_count": 1,
            "futures_positioning_available": True,
            "crowding_regime": "CROWDED_LONG",
            "positioning_snapshot": {
                "net": 75000,
                "net_percentile": 1.0,
                "participant_category": "managed_money",
            },
        }
        snapshot, evidence = build_cross_lane_snapshot_from_futures(futures_payload)
        assert snapshot is not None
        self.assertTrue(snapshot.get("futures_positioning_available"))
        signals = [row["signal"] for row in evidence]
        self.assertIn("FUTURES_POSITIONING_CROWDED_LONG", signals)

    def test_cot_fixture_lookahead_not_in_adapter_at_cutoff(self) -> None:
        cutoff = iso_to_epoch_ns("2025-06-02T14:41:07.000000000Z")
        result = FixtureFuturesPositioningProvider(fixture_path=DEFAULT_COT_FIXTURE).fetch_positioning(
            "ES",
            as_of_time_ns=cutoff,
        )
        self.assertEqual(result.status, "available")
        nets = [row.get("net") for row in result.events if isinstance(row, dict)]
        self.assertIn(75000, nets)
        self.assertNotIn(90000, nets)


if __name__ == "__main__":
    unittest.main()
