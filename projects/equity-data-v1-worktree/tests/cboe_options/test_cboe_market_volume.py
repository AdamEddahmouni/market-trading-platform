"""Cboe U.S. options market volume / market-share parsing."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cboe_options.contracts import (  # noqa: E402
    ExchangeGroupCode,
    MarketScope,
    OptionsStatisticFamily,
)
from market_platform_foundation.cboe_options.market_volume import parse_market_volume_csv  # noqa: E402
from market_platform_foundation.cboe_options.quality import CboeOptionsQualityFlag  # noqa: E402

sys.path.insert(0, str(ROOT / "tests" / "cboe_options"))
from _helpers import INGESTED_TIME, RETRIEVED_TIME, load_json, load_text


class CboeMarketVolumeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.csv = load_text("market_volume.csv")
        self.delay_meta = load_json("market_volume_delayed.json")

    def _capture(self, csv_text: str | None = None):
        return parse_market_volume_csv(
            csv_text or self.csv,
            retrieved_time=RETRIEVED_TIME,
            ingested_time=INGESTED_TIME,
            trade_date="2026-08-19",
            source_data_as_of_time=self.delay_meta["sourceDataAsOfTime"],
        )

    def test_publisher_separate_from_reported_exchange_group(self) -> None:
        capture = self._capture()
        nasdaq = next(
            obs
            for obs in capture.observations
            if obs.reported_exchange_group == ExchangeGroupCode.NASDAQ_GROUP
            and obs.statistic_family == OptionsStatisticFamily.MATCHED_VOLUME
        )
        self.assertEqual(nasdaq.publisher, "CBOE")
        self.assertEqual(nasdaq.market_scope, MarketScope.US_OPTIONS_MARKET)
        self.assertNotEqual(nasdaq.publisher, nasdaq.reported_exchange_group.value)

    def test_all_exchange_groups_present(self) -> None:
        capture = self._capture()
        groups = {
            obs.reported_exchange_group
            for obs in capture.observations
            if obs.statistic_family == OptionsStatisticFamily.MATCHED_VOLUME
            and obs.reported_exchange_group != ExchangeGroupCode.ALL_MARKET
        }
        self.assertEqual(
            groups,
            {
                ExchangeGroupCode.CBOE_GROUP,
                ExchangeGroupCode.NASDAQ_GROUP,
                ExchangeGroupCode.NYSE_GROUP,
                ExchangeGroupCode.MIAX_GROUP,
                ExchangeGroupCode.BOX,
                ExchangeGroupCode.MEMX,
            },
        )

    def test_market_share_preserved_from_source(self) -> None:
        capture = self._capture()
        cboe_share = next(
            obs
            for obs in capture.observations
            if obs.reported_exchange_group == ExchangeGroupCode.CBOE_GROUP
            and obs.statistic_family == OptionsStatisticFamily.MARKET_SHARE
        )
        self.assertAlmostEqual(cboe_share.source_value or 0.0, 32.5, places=1)

    def test_delay_policy_prevents_real_time_classification(self) -> None:
        capture = self._capture()
        for obs in capture.observations:
            self.assertIn(CboeOptionsQualityFlag.DELAYED_DATA.value, obs.quality_flags)
            self.assertTrue(obs.source_delay_policy)
        self.assertFalse(self.delay_meta.get("isRealTime", True))

    def test_total_reconciliation_flags_mismatch_without_forcing_equality(self) -> None:
        tampered = self.csv.replace("11549800", "11000000")
        capture = self._capture(tampered)
        flagged = [
            obs
            for obs in capture.observations
            if CboeOptionsQualityFlag.TOTAL_RECONCILIATION_MISMATCH.value in obs.quality_flags
        ]
        self.assertGreater(len(flagged), 0)

    def test_total_reconciliation_passes_on_fixture(self) -> None:
        capture = self._capture()
        flagged = [
            obs
            for obs in capture.observations
            if CboeOptionsQualityFlag.TOTAL_RECONCILIATION_MISMATCH.value in obs.quality_flags
        ]
        self.assertEqual(flagged, [])


if __name__ == "__main__":
    unittest.main()
