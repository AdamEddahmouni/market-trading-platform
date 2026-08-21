"""OptionsAggregateContext structure and non-signal guarantees."""

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
    aggregate_context_to_dict,
)
from market_platform_foundation.cboe_options.intraday import parse_intraday_statistics_html  # noqa: E402
from market_platform_foundation.cboe_options.market_volume import parse_market_volume_csv  # noqa: E402
from market_platform_foundation.cboe_options.store import CboeOptionsStore  # noqa: E402
from market_platform_foundation.cboe_options.symbol_data import parse_symbol_data_csv  # noqa: E402

sys.path.insert(0, str(ROOT / "tests" / "cboe_options"))
from _helpers import INGESTED_TIME, RETRIEVED_TIME, intraday_html, load_json, load_text, parse_daily_fixture


FORBIDDEN_SIGNAL_KEYS = {
    "score",
    "signal",
    "bearish",
    "bullish",
    "alpha",
    "expected_return",
    "trade_direction",
    "smart_money",
    "whale",
    "gex",
}


class CboeAggregateContextTests(unittest.TestCase):
    def setUp(self) -> None:
        store = CboeOptionsStore()
        store.add_statistics(parse_daily_fixture().observations)
        delay_meta = load_json("market_volume_delayed.json")
        store.add_statistics(
            parse_market_volume_csv(
                load_text("market_volume.csv"),
                retrieved_time=RETRIEVED_TIME,
                ingested_time=INGESTED_TIME,
                trade_date="2026-08-19",
                source_data_as_of_time=delay_meta["sourceDataAsOfTime"],
            ).observations
        )
        intraday_payload = load_json("intraday_exchange_stats.json")
        store.add_statistics(
            parse_intraday_statistics_html(
                intraday_html(intraday_payload),
                retrieved_time=RETRIEVED_TIME,
                ingested_time=INGESTED_TIME,
                trade_date=intraday_payload["tradeDate"],
            ).cumulative
        )
        store.add_snapshots(
            parse_symbol_data_csv(
                load_text("symbol_data_cone.csv"),
                exchange=CboeExchangeCode.C1,
                retrieved_time=RETRIEVED_TIME,
                ingested_time=INGESTED_TIME,
            ).snapshots
        )
        self.context = build_options_aggregate_context(store, as_of_time="2026-08-19T18:00:00-05:00")

    def test_context_has_required_blocks(self) -> None:
        self.assertGreater(len(self.context.put_call_activity), 0)
        self.assertGreater(len(self.context.volume_activity), 0)
        self.assertGreater(len(self.context.open_interest_context), 0)
        self.assertGreater(len(self.context.market_share), 0)
        self.assertGreater(len(self.context.exchange_intraday_activity), 0)
        self.assertGreater(len(self.context.contract_activity_snapshot), 0)
        self.assertIsInstance(self.context.quality_flags, tuple)
        self.assertIsInstance(self.context.staleness, dict)
        self.assertTrue(self.context.provenance_ref)

    def test_context_has_no_signal_fields(self) -> None:
        payload = aggregate_context_to_dict(self.context)
        serialized = json.dumps(payload).lower()
        for key in FORBIDDEN_SIGNAL_KEYS:
            self.assertNotIn(key, serialized)

    def test_context_blocks_are_structured_not_scalar_scores(self) -> None:
        payload = aggregate_context_to_dict(self.context)
        for block_name in (
            "put_call_activity",
            "volume_activity",
            "open_interest_context",
            "market_share",
            "exchange_intraday_activity",
            "contract_activity_snapshot",
        ):
            block = payload[block_name]
            self.assertIsInstance(block, list)


if __name__ == "__main__":
    unittest.main()
