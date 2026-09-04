"""P3.3 discovery engine tests."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.discovery import DiscoveryEngine, get_screen
from market_platform_foundation.discovery.capture import persist_discovery_capture, replay_capture_equivalence
from market_platform_foundation.discovery.models import CandidateSet, DiscoveryCandidate
from market_platform_foundation.finviz.screener import FinvizScreenerRow, parse_screener_csv
from market_platform_foundation.ui_api.discovery_projections import promote_to_live_analysis

FIXTURES = ROOT / "tests" / "fixtures" / "finviz"


class DiscoveryP33Tests(unittest.TestCase):
    def test_versioned_screen(self) -> None:
        screen = get_screen("SHORT_SQUEEZE_DISCOVERY")
        self.assertIsNotNone(screen)
        assert screen is not None
        self.assertEqual(screen.version, "1.0.0")
        self.assertIn("short", screen.filters)

    def test_candidate_contains_match_reasons(self) -> None:
        text = (FIXTURES / "screener_sample.csv").read_text(encoding="utf-8")
        rows, _, _ = parse_screener_csv(text)
        row = rows[0]
        screen = get_screen("SHORT_SQUEEZE_DISCOVERY")
        assert screen is not None
        from market_platform_foundation.discovery.engine import _match_reasons

        reasons = _match_reasons(row, screen)
        self.assertTrue(reasons)

    def test_candidate_not_trade_signal(self) -> None:
        candidate = DiscoveryCandidate(
            instrument_id="AAPL",
            provider_symbol="AAPL",
            screen_id="TEST",
            screen_version="1",
            discovered_at="2026-08-22T00:00:00Z",
            available_time_ns=1,
            matched_reasons=["RVOL 2.0"],
            metrics={},
            inspection_priority=10,
            quality="PASS",
            provenance={},
        )
        payload = candidate.to_dict()
        self.assertEqual(payload["candidate_role"], "INVESTIGATE")
        self.assertNotIn("buy_score", payload)

    def test_discovery_never_creates_order_intent(self) -> None:
        result = promote_to_live_analysis("AAPL")
        self.assertFalse(result["order_intent_created"])
        self.assertFalse(result["paper_order_created"])
        self.assertFalse(result["broker_order_created"])

    def test_capture_persist_and_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["IMP_FINVIZ_CAPTURE_DIR"] = tmp
            candidate = DiscoveryCandidate(
                instrument_id="XYZ",
                provider_symbol="XYZ",
                screen_id="SHORT_SQUEEZE_DISCOVERY",
                screen_version="1.0.0",
                discovered_at="2026-08-22T12:00:00Z",
                available_time_ns=1000,
                matched_reasons=["RVOL 3.40"],
                metrics={"rel_volume": 3.4},
                inspection_priority=50,
                quality="PASS",
                provenance={"provider": "FINVIZ_ELITE"},
                rank=1,
            )
            candidate_set = CandidateSet(
                run_id="run-test",
                screen_id="SHORT_SQUEEZE_DISCOVERY",
                screen_version="1.0.0",
                screen_definition={"screen_id": "SHORT_SQUEEZE_DISCOVERY"},
                requested_at="2026-08-22T12:00:00Z",
                received_at="2026-08-22T12:00:01Z",
                available_time_ns=1000,
                provider="FINVIZ_ELITE",
                schema_version="discovery.screen/1.0.0",
                candidate_count=1,
                candidates=[candidate],
                quality="PASS",
            )
            path = persist_discovery_capture(candidate_set)
            replayed = __import__("json").loads(path.read_text(encoding="utf-8"))
            equiv = replay_capture_equivalence(candidate_set, replayed)
            self.assertTrue(equiv["equivalent"])

    def test_run_screen_with_mock_export(self) -> None:
        text = (FIXTURES / "screener_sample.csv").read_text(encoding="utf-8")
        rows, columns, _ = parse_screener_csv(text)

        class StubClient:
            configured = True

            def fetch_export(self, **kwargs):
                return {
                    "success": True,
                    "rows": rows,
                    "columns": list(columns),
                    "received_at": "2026-08-22T12:00:00Z",
                    "available_time_ns": 2000,
                    "raw_response_hash": "abc",
                }

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["IMP_FINVIZ_CAPTURE_DIR"] = tmp
            engine = DiscoveryEngine(screener=StubClient())
            result = engine.run_screen("SHORT_SQUEEZE_DISCOVERY", persist=True)
            self.assertGreater(result.candidate_count, 0)
            for c in result.candidates:
                self.assertEqual(c.to_dict()["candidate_role"], "INVESTIGATE")


if __name__ == "__main__":
    unittest.main()
