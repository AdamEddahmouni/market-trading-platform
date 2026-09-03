from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.market_data.allocator import SubscriptionAllocator, SubscriptionRequest
from market_platform_foundation.market_data.book_features import compute_book_features, diff_book_liquidity
from market_platform_foundation.market_data.lifecycle import ObservationLifecycle, next_lifecycle_state
from market_platform_foundation.market_data.normalization import (
    classified_trade_from_ticker,
    l1_from_quote,
    levels_from_order_book,
    live_envelope_from_capture,
    replay_envelope_from_capture,
)
from market_platform_foundation.market_data.quality import assess_book, assess_quote, assess_ticker
from market_platform_foundation.market_data.replay import characterize_records, replay_captured_path
from market_platform_foundation.market_data.squeeze_allocation import allocate_squeeze_hot_set
from market_platform_foundation.order_flow.contracts import AggressorSide, AggressorSource
from market_platform_foundation.providers.adapters.captured_equity_quote import CapturedEquityQuoteProvider
from market_platform_foundation.contracts.temporal import check_tc002


FIXTURE = ROOT / "tests/fixtures/market_data/moomoo/captured-aapl.jsonl"


class MarketDataNormalizationTests(unittest.TestCase):
    def test_provider_ticker_direction_is_not_ground_truth(self) -> None:
        trade = classified_trade_from_ticker({"ticker_direction": "BUY", "price": 10, "volume": 4, "sequence": 1})
        self.assertEqual(trade.aggressor_side, AggressorSide.BUY)
        self.assertEqual(trade.aggressor_source, AggressorSource.PROVIDER_NATIVE)
        self.assertEqual(trade.classification_method, "provider.ticker_direction")
        unknown = classified_trade_from_ticker({"ticker_direction": "NEUTRAL", "price": 10, "volume": 4, "sequence": 2})
        self.assertEqual(unknown.aggressor_source, AggressorSource.UNKNOWN)

    def test_l1_and_book_features(self) -> None:
        quote = l1_from_quote({"bid_price": 10.0, "ask_price": 10.2, "bid_vol": 5, "ask_vol": 15})
        self.assertIsNotNone(quote)
        assert quote is not None
        self.assertGreater(quote.spread, 0)
        bids, asks = levels_from_order_book(
            {"Bid": [[10.0, 5, 1, {}], [9.9, 8, 1, {}]], "Ask": [[10.2, 15, 1, {}], [10.3, 20, 1, {}]]}
        )
        features = compute_book_features(bids, asks)
        self.assertIsNotNone(features)
        assert features is not None
        self.assertEqual(features.bid_depth_1, 5)
        delta = diff_book_liquidity(bids, [{"price": 10.0, "size": 8}], last_trade_size=2)
        self.assertGreaterEqual(delta["new_liquidity"], 0)

    def test_quality_flags_reuse_canonical_taxonomy(self) -> None:
        self.assertIn("CROSSED_BOOK", assess_quote({"bid_price": 11, "ask_price": 10, "bid_vol": 1, "ask_vol": 1}))
        self.assertIn("AGGRESSOR_UNKNOWN", assess_ticker({"ticker_direction": "N/A", "volume": 1, "price": 1}))
        self.assertIn("SEQUENCE_GAP", assess_ticker({"sequence": 5, "volume": 1, "price": 1, "ticker_direction": "BUY"}, prior_sequence=1))
        flags = assess_book({"Bid": [[10, 1, 0, {}]], "Ask": [[10.1, 1, 0, {}]]})
        self.assertIn("MBO_UNAVAILABLE", flags)

    def test_live_and_replay_envelopes_preserve_pit_clocks(self) -> None:
        record = {
            "provider": "moomoo",
            "provider_symbol": "US.AAPL",
            "instrument_id": "AAPL",
            "capability": "US_EQUITY_L1",
            "sequence": 9,
            "schema_version": "v1",
            "clocks": {
                "event_time_ns": 100,
                "provider_time_ns": 110,
                "received_time_ns": 200,
                "ingested_time_ns": 250,
                "available_time_ns": 200,
            },
            "raw_payload": {"last_price": 1},
        }
        live = live_envelope_from_capture(record)
        replay = replay_envelope_from_capture(record)
        self.assertEqual(live["live_received_time"], 200)
        self.assertIsNone(live["historical_ingested_time"])
        self.assertIsNone(replay["live_received_time"])
        self.assertEqual(replay["historical_ingested_time"], 250)
        self.assertEqual(replay["available_time"], 200)
        self.assertEqual(check_tc002([live], "live")[0], "PASS")
        self.assertEqual(check_tc002([replay], "historical")[0], "PASS")

    def test_admission_requires_authorization(self) -> None:
        with self.assertRaises(ValueError):
            next_lifecycle_state(
                ObservationLifecycle.QUALITY_CHARACTERIZED,
                ObservationLifecycle.ADMITTED,
                admission_authorized=False,
            )
        self.assertEqual(
            next_lifecycle_state(
                ObservationLifecycle.QUALITY_CHARACTERIZED,
                ObservationLifecycle.ADMITTED,
                admission_authorized=True,
            ),
            ObservationLifecycle.ADMITTED,
        )

    def test_quota_allocator_and_squeeze_priority(self) -> None:
        allocator = SubscriptionAllocator(max_slots=2)
        first = allocator.allocate(
            [
                SubscriptionRequest("AAPL", "US_EQUITY_DEPTH", 1),
                SubscriptionRequest("NVDA", "US_EQUITY_DEPTH", 1),
                SubscriptionRequest("SPY", "US_EQUITY_DEPTH", 1),
            ]
        )
        self.assertEqual(len(first.accepted), 2)
        self.assertIn("QUOTA_EXHAUSTED", first.reason_codes)
        hot = allocate_squeeze_hot_set(
            SubscriptionAllocator(max_slots=1),
            [
                {"instrument_id": "BIYA", "state": "IGNITION_WATCH"},
                {"instrument_id": "NVDA", "state": "LIVE_CONFIRMATION"},
            ],
        )
        self.assertEqual(hot.accepted, ("NVDA",))

    def test_captured_fixture_replays_without_opend(self) -> None:
        state = replay_captured_path(FIXTURE)
        self.assertGreaterEqual(state.visible_events[-1]["available_time"] if state.visible_events else 0, 1000)
        self.assertTrue(state.decisions)
        self.assertEqual(state.decisions[-1]["status"], "PASS")
        provider = CapturedEquityQuoteProvider(capture_path=FIXTURE)
        result = provider.fetch_quote("AAPL")
        self.assertEqual(result.status, "available")
        self.assertTrue(result.events)
        self.assertIsNone(result.events[0]["live_received_time"])
        characterized = characterize_records(
            [
                {
                    "capability": "US_EQUITY_TICKS",
                    "raw_payload": {"ticker_direction": "SELL", "volume": 2, "price": 1, "sequence": 3},
                }
            ]
        )
        self.assertEqual(characterized["trade_count"], 1)


if __name__ == "__main__":
    unittest.main()
