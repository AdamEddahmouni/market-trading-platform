"""Mandatory semantic regression tests for Cboe options statistics."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cboe_options.aggregate import build_options_aggregate_context  # noqa: E402
from market_platform_foundation.cboe_options.contracts import (  # noqa: E402
    CboeExchangeCode,
    CoverageScope,
    ExchangeGroupCode,
    MarketScope,
    OptionsStatisticFamily,
    aggregate_context_to_dict,
    contract_snapshot_to_dict,
    market_statistic_to_dict,
)
from market_platform_foundation.cboe_options.market_volume import parse_market_volume_csv  # noqa: E402
from market_platform_foundation.cboe_options.quality import (  # noqa: E402
    CboeOptionsQualityFlag,
    default_activity_flags,
    quality_blocks_statistic,
)
from market_platform_foundation.cboe_options.store import CboeOptionsStore  # noqa: E402
from market_platform_foundation.cboe_options.symbol_data import parse_symbol_data_csv  # noqa: E402
from market_platform_foundation.contracts.options import OptionContract  # noqa: E402

sys.path.insert(0, str(ROOT / "tests" / "cboe_options"))
from _helpers import INGESTED_TIME, RETRIEVED_TIME, load_json, load_text, parse_daily_fixture


class CboeRequiredSemanticsTests(unittest.TestCase):
    def test_scope_exchange_symbol_volume_not_market_wide(self) -> None:
        capture = parse_symbol_data_csv(
            load_text("symbol_data_cone.csv"),
            exchange=CboeExchangeCode.C1,
            retrieved_time=RETRIEVED_TIME,
            ingested_time=INGESTED_TIME,
        )
        for snap in capture.snapshots:
            self.assertEqual(snap.coverage_scope, CoverageScope.EXCHANGE_SPECIFIC)
            self.assertNotEqual(snap.coverage_scope, CoverageScope.US_OPTIONS_MARKET)

    def test_publisher_venue_separation_for_market_share_row(self) -> None:
        delay_meta = load_json("market_volume_delayed.json")
        capture = parse_market_volume_csv(
            load_text("market_volume.csv"),
            retrieved_time=RETRIEVED_TIME,
            ingested_time=INGESTED_TIME,
            source_data_as_of_time=delay_meta["sourceDataAsOfTime"],
        )
        nasdaq = next(
            obs
            for obs in capture.observations
            if obs.reported_exchange_group == ExchangeGroupCode.NASDAQ_GROUP
        )
        self.assertEqual(nasdaq.publisher, "CBOE")
        self.assertEqual(nasdaq.reported_exchange_group, ExchangeGroupCode.NASDAQ_GROUP)
        self.assertEqual(nasdaq.market_scope, MarketScope.US_OPTIONS_MARKET)

    def test_put_call_direction_prohibition(self) -> None:
        capture = parse_daily_fixture()
        serialized = json.dumps(
            [market_statistic_to_dict(obs) for obs in capture.observations],
        ).upper()
        self.assertNotIn("BEARISH", serialized)
        self.assertNotIn("BULLISH", serialized)
        for obs in capture.observations:
            if obs.statistic_family == OptionsStatisticFamily.PUT_CALL_RATIO:
                self.assertIn(CboeOptionsQualityFlag.DIRECTION_UNKNOWN.value, obs.quality_flags)

    def test_volume_and_open_interest_remain_distinct(self) -> None:
        capture = parse_daily_fixture()
        volume_metrics = {
            obs.metric
            for obs in capture.observations
            if obs.statistic_family == OptionsStatisticFamily.OPTION_VOLUME
        }
        oi_metrics = {
            obs.metric
            for obs in capture.observations
            if obs.statistic_family == OptionsStatisticFamily.OPEN_INTEREST
        }
        self.assertTrue(volume_metrics.isdisjoint(oi_metrics))
        self.assertTrue(any("VOLUME" in metric for metric in volume_metrics))
        self.assertTrue(any("OPEN_INTEREST" in metric for metric in oi_metrics))

    def test_symbol_quotes_not_nbbo(self) -> None:
        capture = parse_symbol_data_csv(
            load_text("symbol_data_cone.csv"),
            exchange=CboeExchangeCode.C1,
            retrieved_time=RETRIEVED_TIME,
            ingested_time=INGESTED_TIME,
        )
        payload = json.dumps(
            [contract_snapshot_to_dict(snap) for snap in capture.snapshots],
        ).upper()
        self.assertNotIn("NBBO", payload)

    def test_delay_policy_blocks_real_time_use(self) -> None:
        delay_meta = load_json("market_volume_delayed.json")
        capture = parse_market_volume_csv(
            load_text("market_volume.csv"),
            retrieved_time=RETRIEVED_TIME,
            ingested_time=INGESTED_TIME,
            source_data_as_of_time=delay_meta["sourceDataAsOfTime"],
        )
        self.assertFalse(delay_meta.get("isRealTime", True))
        self.assertTrue(
            any(CboeOptionsQualityFlag.DELAYED_DATA.value in obs.quality_flags for obs in capture.observations)
        )

    def test_missing_statistic_is_unknown_not_zero(self) -> None:
        store = CboeOptionsStore()
        result = store.statistic_as_of(
            canonical_statistic_id="NONEXISTENT_STATISTIC",
            trade_date="2026-08-19",
            decision_time="2026-08-19T18:00:00-05:00",
        )
        self.assertIsNone(result)

    def test_legitimate_zero_ratio_remains_zero(self) -> None:
        capture = parse_daily_fixture()
        zero = next(
            obs
            for obs in capture.observations
            if obs.statistic_family == OptionsStatisticFamily.PUT_CALL_RATIO
            and obs.source_ratio == 0.0
        )
        self.assertEqual(zero.source_ratio, 0.0)
        self.assertFalse(quality_blocks_statistic(zero.quality_flags))

    def test_options_chain_coexists_with_aggregate_context_stub(self) -> None:
        store = CboeOptionsStore()
        store.add_statistics(parse_daily_fixture().observations)
        context = build_options_aggregate_context(store, as_of_time="2026-08-19T18:00:00-05:00")
        chain_contract = OptionContract(
            underlying_id="SPY",
            option_id="SPY250919C00600000",
            call_put="call",
            strike=600,
            expiration="2025-09-19",
            dte=30,
            provider="fixture_chain",
        )
        self.assertGreater(len(context.put_call_activity), 0)
        self.assertIsNotNone(chain_contract.option_id)
        self.assertNotEqual(context.provenance_ref, "fixture_chain")
        self.assertIn(CboeOptionsQualityFlag.DIRECTION_UNKNOWN.value, default_activity_flags())


if __name__ == "__main__":
    unittest.main()
