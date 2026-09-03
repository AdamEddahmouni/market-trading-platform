"""Cboe daily market statistics parsing and ratio semantics."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cboe_options.contracts import (  # noqa: E402
    CoverageScope,
    OptionsFeatureLayer,
    OptionsStatisticFamily,
    ProductScope,
    RatioReconciliationStatus,
    market_statistic_to_dict,
)
from market_platform_foundation.cboe_options.daily import parse_daily_statistics_html  # noqa: E402
from market_platform_foundation.cboe_options.normalize import reconcile_ratio  # noqa: E402
from market_platform_foundation.cboe_options.quality import CboeOptionsQualityFlag  # noqa: E402

sys.path.insert(0, str(ROOT / "tests" / "cboe_options"))
from _helpers import INGESTED_TIME, RETRIEVED_TIME, daily_html, load_json, parse_daily_fixture


class CboeDailyParseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = load_json("daily_stats_embedded.json")
        self.capture = parse_daily_fixture()

    def test_parse_ratios_by_product_scope(self) -> None:
        ratio_products = {
            obs.product_scope
            for obs in self.capture.observations
            if obs.statistic_family == OptionsStatisticFamily.PUT_CALL_RATIO
        }
        self.assertIn(ProductScope.TOTAL, ratio_products)
        self.assertIn(ProductScope.INDEX, ratio_products)
        self.assertIn(ProductScope.EQUITY, ratio_products)
        self.assertIn(ProductScope.EXCHANGE_TRADED_PRODUCT, ratio_products)
        self.assertIn(ProductScope.VIX, ratio_products)
        self.assertIn(ProductScope.SPX_SPXW, ratio_products)

    def test_volume_and_open_interest_are_separate_families(self) -> None:
        families = {obs.statistic_family for obs in self.capture.observations}
        self.assertIn(OptionsStatisticFamily.OPTION_VOLUME, families)
        self.assertIn(OptionsStatisticFamily.OPEN_INTEREST, families)

    def test_total_volume_and_oi_metrics_are_distinct(self) -> None:
        total_rows = [
            obs
            for obs in self.capture.observations
            if obs.product_scope == ProductScope.TOTAL
            and obs.statistic_family in {
                OptionsStatisticFamily.OPTION_VOLUME,
                OptionsStatisticFamily.OPEN_INTEREST,
            }
        ]
        metrics = {obs.metric for obs in total_rows}
        self.assertIn("TOTAL_VOLUME", metrics)
        self.assertIn("TOTAL_OPEN_INTEREST", metrics)

    def test_coverage_scope_is_cboe_exchanges_not_consolidated_market(self) -> None:
        scopes = {obs.coverage_scope for obs in self.capture.observations}
        self.assertEqual(scopes, {CoverageScope.CBOE_EXCHANGES})

    def test_scope_flags_present_on_every_observation(self) -> None:
        for obs in self.capture.observations:
            self.assertTrue(obs.product_scope)
            self.assertTrue(obs.coverage_scope)
            self.assertTrue(obs.exchange_scope)

    def test_ratio_reconciliation_matches_within_rounding(self) -> None:
        total_ratio = next(
            obs
            for obs in self.capture.observations
            if obs.canonical_statistic_id == "TOTAL_PUT_CALL_RATIO"
        )
        total_volume = next(
            item
            for item in self.payload["volumeAndOpenInterest"]
            if item["name"] == "TOTAL VOLUME"
        )
        _derived, status = reconcile_ratio(
            call_value=total_volume["call"],
            put_value=total_volume["put"],
            source_ratio=total_ratio.source_ratio,
        )
        self.assertEqual(status, RatioReconciliationStatus.MATCH)
        self.assertAlmostEqual(total_ratio.source_ratio or 0.0, 0.95, places=2)

    def test_legitimate_zero_ratio_is_not_missing(self) -> None:
        zero_ratio = next(
            obs
            for obs in self.capture.observations
            if obs.statistic_family == OptionsStatisticFamily.PUT_CALL_RATIO
            and obs.source_ratio == 0.0
        )
        self.assertEqual(zero_ratio.source_ratio, 0.0)
        self.assertNotIn(CboeOptionsQualityFlag.MISSING_VALUE.value, zero_ratio.quality_flags)

    def test_undefined_ratio_when_call_denominator_zero(self) -> None:
        undefined = next(
            obs
            for obs in self.capture.observations
            if obs.statistic_family == OptionsStatisticFamily.PUT_CALL_RATIO
            and obs.ratio_reconciliation_status == RatioReconciliationStatus.UNDEFINED_DENOMINATOR
        )
        self.assertIsNone(undefined.source_ratio)
        self.assertIn(
            undefined.ratio_reconciliation_status,
            {
                RatioReconciliationStatus.UNDEFINED_DENOMINATOR,
                RatioReconciliationStatus.MISMATCH,
            },
        )
        self.assertTrue(
            CboeOptionsQualityFlag.UNDEFINED_RATIO.value in undefined.quality_flags
            or CboeOptionsQualityFlag.MISSING_VALUE.value in undefined.quality_flags
        )

    def test_no_directional_labels_on_observations(self) -> None:
        for obs in self.capture.observations:
            serialized = json.dumps(market_statistic_to_dict(obs)).upper()
            for forbidden in ("BEARISH", "BULLISH", "SMART_MONEY"):
                self.assertNotIn(forbidden, serialized)

    def test_html_parser_reads_trade_date_metadata(self) -> None:
        self.assertEqual(self.capture.trade_date, "2026-08-19")
        self.assertTrue(self.capture.last_updated)

    def test_derived_features_are_not_predictive(self) -> None:
        for obs in self.capture.observations:
            if obs.feature_layer == OptionsFeatureLayer.DETERMINISTIC_DERIVED:
                self.assertFalse(obs.predictive)

    def test_embedded_html_round_trip(self) -> None:
        capture = parse_daily_statistics_html(
            daily_html(self.payload),
            retrieved_time=RETRIEVED_TIME,
            ingested_time=INGESTED_TIME,
        )
        self.assertEqual(len(capture.observations), len(self.capture.observations))


if __name__ == "__main__":
    unittest.main()
