"""Canonical L2 engine integration with the live observational book store (G5).

Proves the ObservationalStateStore book path routes full-book provider pushes
through the canonical incremental engine (snapshot ingestion compatibility
mode), that ``book_state_valid`` is derived truth rather than hard-coded
optimism (ARCH-009), and that empty pushes are truthfully reported invalid
instead of silently "valid".
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.market_data.observational_state import (  # noqa: E402
    ObservationalStateStore,
)


def depth_record(payload: dict[str, object], *, symbol: str = "AAPL") -> dict[str, object]:
    return {
        "capability": "US_EQUITY_DEPTH",
        "clocks": {
            "available_time_ns": 950,
            "event_time_ns": 900,
            "provider_time_ns": 900,
            "received_time_ns": 1000,
        },
        "instrument_id": symbol,
        "provider": "moomoo",
        "provider_symbol": f"US.{symbol}",
        "raw_payload": payload,
    }


def admitted(payload: dict[str, object], *, symbol: str = "AAPL") -> dict[str, object]:
    record = depth_record(payload, symbol=symbol)
    envelope = {
        "available_time": 950,
        "event_time": 900,
        "event_type": "DEPTH",
        "instrument_id": symbol,
    }
    return {
        "admission": {"display": "PASS"},
        "envelope": envelope,
        "record": record,
    }


class CanonicalBookStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ObservationalStateStore()

    def test_full_book_push_drives_canonical_engine(self) -> None:
        payload = {
            "bids": [
                {"price": 100.0, "size": 10.0},
                {"price": 99.0, "size": 5.0},
            ],
            "asks": [{"price": 101.0, "size": 7.0}],
        }
        self.assertTrue(self.store.apply_admitted(admitted(payload)))
        book = self.store.book_for("AAPL")
        self.assertIsNotNone(book)
        engine = self.store.book_engine_for("AAPL")
        self.assertIsNotNone(engine)
        assert engine is not None and book is not None
        # Derived truth and canonical meta fields are present.
        self.assertTrue(book["book_state_valid"])
        self.assertEqual(book["book_status"], "VALID")
        self.assertEqual(book["book_status_reason"], "NONE")
        self.assertEqual(book["sequence_status"], "NO_SEQUENCE")
        self.assertEqual(engine.best_bid_price, 100)
        self.assertEqual(engine.best_ask_price, 101)
        # Engine and projection rows agree.
        self.assertEqual(book["bids"][0]["price"], 100.0)
        self.assertEqual(book["asks"][0]["price"], 101.0)

    def test_second_full_book_push_replaces_old_levels(self) -> None:
        first = admitted(
            {
                "bids": [{"price": 100.0, "size": 10.0}],
                "asks": [{"price": 101.0, "size": 7.0}],
            }
        )
        self.store.apply_admitted(first)
        self.store.apply_admitted(
            admitted(
                {
                    "bids": [{"price": 50.0, "size": 3.0}],
                    "asks": [{"price": 51.0, "size": 3.0}],
                }
            )
        )
        engine = self.store.book_engine_for("AAPL")
        assert engine is not None
        # Full-book pushes enter via replace_from_snapshot: old levels cleared.
        self.assertEqual(engine.best_bid_price, 50)
        self.assertEqual(engine.best_ask_price, 51)
        self.assertTrue(engine.book_state_valid)

    def test_empty_push_is_derived_invalid_not_optimistic(self) -> None:
        first = admitted(
            {
                "bids": [{"price": 100.0, "size": 10.0}],
                "asks": [{"price": 101.0, "size": 7.0}],
            }
        )
        self.store.apply_admitted(first)
        self.store.apply_admitted(admitted({"bids": [], "asks": []}))
        book = self.store.book_for("AAPL")
        self.assertIsNotNone(book)
        assert book is not None
        # ARCH-009: no hard-coded book_state_valid=true on an empty book.
        self.assertFalse(book["book_state_valid"])
        self.assertEqual(book["book_status"], "INVALID")
        self.assertEqual(book["book_status_reason"], "RESET_PENDING")

    def test_multiple_instruments_have_independent_engines(self) -> None:
        self.store.apply_admitted(admitted({"bids": [{"price": 10.0, "size": 1.0}], "asks": []}))
        self.store.apply_admitted(
            admitted(
                {"bids": [{"price": 20.0, "size": 1.0}], "asks": [{"price": 21.0, "size": 1.0}]},
                symbol="MSFT",
            )
        )
        aapl = self.store.book_engine_for("AAPL")
        msft = self.store.book_engine_for("MSFT")
        assert aapl is not None and msft is not None
        self.assertNotEqual(aapl.state_hash(), msft.state_hash())
        self.assertNotEqual(aapl.instrument_id, msft.instrument_id)

    def test_clear_instrument_removes_engine(self) -> None:
        self.store.apply_admitted(
            admitted({"bids": [{"price": 100.0, "size": 1.0}], "asks": []})
        )
        self.assertIsNotNone(self.store.book_engine_for("AAPL"))
        self.store.clear_instrument("AAPL")
        self.assertIsNone(self.store.book_engine_for("AAPL"))
        self.assertIsNone(self.store.book_for("AAPL"))


if __name__ == "__main__":
    unittest.main()
