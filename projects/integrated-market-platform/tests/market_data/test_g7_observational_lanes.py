"""G7 observational lane runtime wiring tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.market_data.lane_requirements import (  # noqa: E402
    ObservationalLane,
    evaluate_lane_readiness,
    lane_required_capabilities,
)
from market_platform_foundation.market_data.observational_lanes import (  # noqa: E402
    ObservationalLaneRuntime,
)
from market_platform_foundation.market_data.observational_state import (  # noqa: E402
    ObservationalStateStore,
)
from market_platform_foundation.order_flow.ofi import OFI_METHOD_MULTILEVEL_PRICE_ALIGNED  # noqa: E402
from market_platform_foundation.providers.runtime_capability import CAP_L2  # noqa: E402
from market_platform_foundation.xa01.enums import InstrumentKind  # noqa: E402


def _admitted_depth(payload: dict, symbol: str = "AAPL", received_ns: int = 1000) -> dict:
    return {
        "admission": {"display": "PASS"},
        "envelope": {
            "available_time": 950,
            "event_time": 900,
            "event_type": "DEPTH",
            "instrument_id": symbol,
        },
        "record": {
            "capability": "US_EQUITY_DEPTH",
            "clocks": {"received_time_ns": received_ns, "event_time_ns": received_ns - 100},
            "instrument_id": symbol,
            "provider": "ibkr.observational",
            "raw_payload": payload,
        },
    }


class ObservationalLaneRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ObservationalStateStore()
        self.lanes = ObservationalLaneRuntime(self.store)

    def test_canonical_quote_reaches_l1(self) -> None:
        self.store.apply_quote_update(
            instrument_id="AAPL",
            bid_price=100.0,
            ask_price=101.0,
            bid_size=10.0,
            ask_size=5.0,
            provider="ibkr.observational",
            event_time_ns=900,
            received_ns=1000,
        )
        payload = self.lanes.build_l1_payload("AAPL")
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertTrue(payload["available"])
        self.assertEqual(payload["provenance"]["provider"], "ibkr.observational")
        self.assertEqual(payload["provenance"]["source_time_ns"], 900)

    def test_invalid_book_suppresses_authoritative_ofi(self) -> None:
        self.store.apply_admitted(
            _admitted_depth({"bids": [], "asks": []}),
        )
        ofi = self.lanes.build_ofi_payload("AAPL")
        self.assertFalse(ofi["available"])
        self.assertEqual(ofi["reason"], "INVALID_BOOK")

    def test_stale_freshness_blocks_authoritative_ofi(self) -> None:
        p1 = {
            "bids": [{"price": 100.0, "size": 10.0}],
            "asks": [{"price": 101.0, "size": 5.0}],
        }
        p2 = {
            "bids": [{"price": 100.0, "size": 12.0}],
            "asks": [{"price": 101.0, "size": 5.0}],
        }
        self.store.apply_admitted(_admitted_depth(p1, received_ns=1000))
        self.lanes.build_ofi_payload("AAPL")
        self.store.apply_admitted(_admitted_depth(p2, received_ns=2000))
        book = self.store.book_for("AAPL")
        assert book is not None
        book["freshness_status"] = "STALE"
        self.store.books["AAPL"] = book
        ofi = self.lanes.build_ofi_payload("AAPL")
        self.assertFalse(ofi["available"])
        self.assertEqual(ofi["reason"], "STALE_BOOK")
        self.assertEqual(ofi["state"], "STALE")
        self.assertNotIn("ofi_value", ofi)

    def test_stale_freshness_blocks_book_features(self) -> None:
        payload = {
            "bids": [{"price": 100.0, "size": 10.0}],
            "asks": [{"price": 101.0, "size": 5.0}],
        }
        self.store.apply_admitted(_admitted_depth(payload))
        book = self.store.book_for("AAPL")
        assert book is not None
        book["freshness_status"] = "STALE"
        self.store.books["AAPL"] = book
        features = self.lanes.build_book_features_payload("AAPL")
        self.assertFalse(features["available"])
        self.assertEqual(features["reason"], "STALE_BOOK")
        self.assertEqual(features["state"], "STALE")

    def test_price_aligned_ofi_from_canonical_l2(self) -> None:
        p1 = {
            "bids": [{"price": 100.0, "size": 10.0}],
            "asks": [{"price": 101.0, "size": 5.0}],
        }
        p2 = {
            "bids": [{"price": 100.0, "size": 12.0}],
            "asks": [{"price": 101.0, "size": 5.0}],
        }
        self.store.apply_admitted(_admitted_depth(p1, received_ns=1000))
        self.lanes.build_ofi_payload("AAPL")
        self.store.apply_admitted(_admitted_depth(p2, received_ns=2000))
        ofi = self.lanes.build_ofi_payload("AAPL")
        self.assertTrue(ofi["available"])
        self.assertEqual(ofi["ofi_method"], OFI_METHOD_MULTILEVEL_PRICE_ALIGNED)
        self.assertEqual(ofi["sequence_status"], "NO_SEQUENCE")

    def test_book_features_from_canonical_depth(self) -> None:
        payload = {
            "bids": [{"price": 100.0, "size": 10.0}],
            "asks": [{"price": 101.0, "size": 5.0}],
        }
        self.store.apply_admitted(_admitted_depth(payload))
        features = self.lanes.build_book_features_payload("AAPL")
        self.assertTrue(features["available"])
        self.assertIsNotNone(features["book_features"])
        self.assertEqual(features["provenance"]["provider"], "ibkr.observational")

    def test_cvd_insufficient_classification_explicit(self) -> None:
        self.store.trades["AAPL"] = __import__("collections").deque(
            [
                {
                    "aggressor_side": "UNKNOWN",
                    "quantity": 100,
                    "event_time_ns": 900,
                    "provider": "moomoo",
                }
            ],
            maxlen=500,
        )
        cvd = self.lanes.build_cvd_payload("AAPL")
        self.assertFalse(cvd["available"])
        self.assertEqual(cvd["reason"], "INSUFFICIENT_TRADE_CLASSIFICATION")

    def test_cvd_session_semantics_unchanged(self) -> None:
        from collections import deque

        self.store.trades["AAPL"] = deque(
            [
                {
                    "aggressor_side": "BUY",
                    "aggressor_provenance": "PROVIDER_NATIVE",
                    "quantity": 100,
                    "event_time_ns": 900,
                    "available_time_ns": 950,
                    "provider": "ibkr",
                    "quality": "PASS",
                    "admission": "PASS",
                }
            ],
            maxlen=500,
        )
        cvd = self.lanes.build_cvd_payload("AAPL")
        self.assertTrue(cvd["available"])
        self.assertIn("session_cvd", cvd["cvd"])

    def test_generation_reset_clears_ofi_carry(self) -> None:
        p1 = {
            "bids": [{"price": 100.0, "size": 10.0}],
            "asks": [{"price": 101.0, "size": 5.0}],
        }
        self.store.apply_admitted(_admitted_depth(p1))
        self.lanes.build_ofi_payload("AAPL")
        self.lanes.reset_generation("AAPL")
        ofi = self.lanes.build_ofi_payload("AAPL")
        self.assertEqual(ofi["reason"], "AWAITING_SECOND_SNAPSHOT")

    def test_replay_deterministic_hash(self) -> None:
        payload = {
            "bids": [{"price": 100.0, "size": 10.0}],
            "asks": [{"price": 101.0, "size": 5.0}],
        }
        self.store.apply_admitted(_admitted_depth(payload))
        first = self.lanes.build_evidence_bundle("AAPL")
        second = self.lanes.build_evidence_bundle("AAPL")
        self.assertEqual(first["evidence_hash"], second["evidence_hash"])

    def test_option_contract_required(self) -> None:
        result = self.lanes.build_options_observation_payload(
            instrument_id="NVDA",
            instrument_kind=InstrumentKind.TRADABLE_SECURITY.value,
        )
        self.assertEqual(result["reason"], "OPTION_CONTRACT_REQUIRED")

    def test_future_family_rejected(self) -> None:
        result = self.lanes.build_futures_observation_payload(
            instrument_id="ES",
            instrument_kind=InstrumentKind.FUTURE_FAMILY.value,
            price=5000.0,
            multiplier=50.0,
        )
        self.assertEqual(result["reason"], "SPECIFIC_FUTURE_CONTRACT_REQUIRED")

    def test_future_multiplier_required(self) -> None:
        result = self.lanes.build_futures_observation_payload(
            instrument_id="ESZ5",
            instrument_kind=InstrumentKind.FUTURE_CONTRACT.value,
            price=5000.0,
            multiplier=None,
        )
        self.assertEqual(result["reason"], "MULTIPLIER_REQUIRED")

    def test_lane_requirements_ofi_needs_l2(self) -> None:
        caps = lane_required_capabilities(ObservationalLane.OFI)
        self.assertIn(CAP_L2, caps)

    def test_lane_readiness_evaluates(self) -> None:
        readiness = evaluate_lane_readiness(
            ObservationalLane.OFI,
            instrument_id="AAPL",
        )
        self.assertIsNotNone(readiness.state)


if __name__ == "__main__":
    unittest.main()
