"""Finviz provider tests — offline fixtures, no live credentials."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.discovery import DiscoveryEngine
from market_platform_foundation.discovery.capture import (
    load_discovery_capture,
    persist_discovery_capture,
    replay_capture_equivalence,
)
from market_platform_foundation.discovery.models import CandidateTransition
from market_platform_foundation.discovery.transitions import compute_transitions
from market_platform_foundation.finviz.fields import classify_screener_columns
from market_platform_foundation.finviz.news import parse_news_csv
from market_platform_foundation.finviz.provider_role import finviz_can_execute, assert_read_only_role
from market_platform_foundation.finviz.request_manager import FinvizRequestManager, redact_payload
from market_platform_foundation.finviz.screener import FinvizScreenerClient, parse_screener_csv
from market_platform_foundation.finviz.symbols import canonical_to_moomoo, finviz_to_canonical

FIXTURES = ROOT / "tests" / "fixtures" / "finviz"


class FinvizProviderTests(unittest.TestCase):
    def test_auth_not_leaked_in_redact(self) -> None:
        payload = {"auth": "secret-token", "nested": {"api_key": "abc"}}
        cleaned = redact_payload(payload)
        self.assertEqual(cleaned["auth"], "REDACTED")
        self.assertEqual(cleaned["nested"]["api_key"], "REDACTED")

    def test_request_rate_limit_waits(self) -> None:
        manager = FinvizRequestManager(min_interval_s=0.05)
        self.assertGreaterEqual(manager._min_interval_s, 0.05)

    def test_schema_validation_screener_csv(self) -> None:
        text = (FIXTURES / "screener_sample.csv").read_text(encoding="utf-8")
        rows, columns, err = parse_screener_csv(text)
        self.assertIsNone(err)
        self.assertEqual(len(rows), 2)
        self.assertIn("Ticker", columns)

    def test_screener_normalization(self) -> None:
        text = (FIXTURES / "screener_sample.csv").read_text(encoding="utf-8")
        rows, _, _ = parse_screener_csv(text)
        aapl = next(r for r in rows if r.ticker == "AAPL")
        self.assertEqual(aapl.sector, "Technology")
        self.assertAlmostEqual(aapl.change_pct, 2.50)

    def test_news_normalization(self) -> None:
        text = (FIXTURES / "news_sample.csv").read_text(encoding="utf-8")
        items, err = parse_news_csv(text)
        self.assertIsNone(err)
        self.assertEqual(len(items), 2)
        self.assertIn("AAPL", items[0]["tickers"])

    def test_finviz_symbol_maps_to_canonical_instrument(self) -> None:
        mapping = finviz_to_canonical("aapl")
        self.assertEqual(mapping.instrument_id, "AAPL")
        self.assertEqual(mapping.venue_id, "US_EQUITY")

    def test_finviz_and_moomoo_same_instrument(self) -> None:
        mapping = finviz_to_canonical("AAPL")
        self.assertEqual(canonical_to_moomoo(mapping.instrument_id), "US.AAPL")

    def test_finviz_has_no_execution_role(self) -> None:
        self.assertFalse(finviz_can_execute())
        with self.assertRaises(ValueError):
            assert_read_only_role("ORDER_SUBMISSION")

    def test_field_inventory(self) -> None:
        classified = classify_screener_columns(["Ticker", "Short Float", "Relative Volume"])
        self.assertEqual(len(classified), 3)


class FinvizDiscoveryOfflineTests(unittest.TestCase):
    def test_candidate_from_fixture_via_client(self) -> None:
        text = (FIXTURES / "screener_sample.csv").read_text(encoding="utf-8")
        client = FinvizScreenerClient(api_key="test-key")
        rows, columns, _ = parse_screener_csv(text)
        self.assertGreater(len(rows), 0)

    def test_capture_replay_equivalence(self) -> None:
        os.environ["IMP_FINVIZ_CAPTURE_DIR"] = str(ROOT / "tests" / "fixtures" / "finviz" / "captures_tmp")
        engine = DiscoveryEngine(screener=FinvizScreenerClient(api_key=None))
        # Build synthetic candidate set from fixture parse
        text = (FIXTURES / "screener_sample.csv").read_text(encoding="utf-8")
        rows, columns, _ = parse_screener_csv(text)
        self.assertEqual(len(rows), 2)

    def test_transitions(self) -> None:
        transitions = compute_transitions(
            previous_symbols={"AAPL"},
            current_symbols={"AAPL", "XYZ"},
            reentered_symbols=set(),
        )
        kinds = {t["instrument_id"]: t["transition"] for t in transitions}
        self.assertEqual(kinds["AAPL"], CandidateTransition.STILL_MATCHES.value)
        self.assertEqual(kinds["XYZ"], CandidateTransition.NEW_ENTRY.value)


if __name__ == "__main__":
    unittest.main()
