from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.market_data.live_admission import (
    ADMISSION_BLOCKED,
    ADMISSION_EXECUTION,
    LiveAdmissionEngine,
)

FIXTURE = ROOT / "tests/fixtures/market_data/moomoo/captured-aapl.jsonl"


class LiveAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = LiveAdmissionEngine()

    def _quote_record(self, **overrides: object) -> dict:
        base = {
            "capability": "US_EQUITY_L1",
            "clocks": {
                "event_time_ns": 1_000_000_000,
                "provider_time_ns": 1_000_000_000,
                "received_time_ns": 1_100_000_000,
            },
            "instrument_id": "AAPL",
            "provider": "moomoo",
            "provider_symbol": "US.AAPL",
            "raw_payload": {"ask_price": 190.2, "ask_vol": 200, "bid_price": 190.0, "bid_vol": 100, "last_price": 190.1},
            "sequence": 1,
        }
        base.update(overrides)
        return base

    def test_healthy_quote_admitted(self) -> None:
        result = self.engine.evaluate_record(self._quote_record(), wall_now_ns=1_200_000_000)
        self.assertEqual(result["admission"]["display"], "DISPLAY_ADMITTED")
        self.assertIsNotNone(result["envelope"])

    def test_crossed_book_blocked(self) -> None:
        record = self._quote_record(
            raw_payload={"ask_price": 10.0, "ask_vol": 1, "bid_price": 11.0, "bid_vol": 1, "last_price": 10.5}
        )
        result = self.engine.evaluate_record(record, wall_now_ns=1_200_000_000)
        self.assertEqual(result["consumer_eligibility"], "BLOCKED")

    def test_cached_first_push_blocks_execution(self) -> None:
        result = self.engine.evaluate_record(self._quote_record(), wall_now_ns=1_200_000_000, is_cached=True)
        self.assertEqual(result["admission"]["execution"], ADMISSION_BLOCKED)
        self.assertEqual(result["admission"]["display"], "DISPLAY_ADMITTED")

    def test_snapshot_first_push_blocks_execution(self) -> None:
        result = self.engine.evaluate_record(self._quote_record(), wall_now_ns=1_200_000_000, is_first_push=True)
        self.assertEqual(result["admission"]["execution"], ADMISSION_BLOCKED)
        self.assertEqual(result["admission"]["display"], "DISPLAY_ADMITTED")

    def test_provider_time_parser_uses_et(self) -> None:
        from market_platform_foundation.market_data.provider_time import parse_provider_datetime_ns

        parsed = parse_provider_datetime_ns("2026-08-21 16:13:22.551")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertGreater(parsed, 1_000_000_000_000_000_000)


    def test_provider_disconnect_blocks(self) -> None:
        self.engine.on_disconnect()
        result = self.engine.evaluate_record(self._quote_record(), wall_now_ns=1_200_000_000)
        self.assertEqual(result["consumer_eligibility"], "BLOCKED")

    def test_future_event_time_clock_drift(self) -> None:
        record = self._quote_record(
            clocks={
                "event_time_ns": 2_000_000_000,
                "provider_time_ns": 2_000_000_000,
                "received_time_ns": 1_100_000_000,
            }
        )
        result = self.engine.evaluate_record(record, wall_now_ns=2_100_000_000)
        self.assertEqual(result["consumer_eligibility"], "BLOCKED")

    def test_duplicate_sequence_warns(self) -> None:
        record = self._quote_record(sequence=5)
        self.engine.evaluate_record(record, wall_now_ns=1_200_000_000)
        dup = self._quote_record(sequence=5)
        result = self.engine.evaluate_record(dup, wall_now_ns=1_300_000_000)
        self.assertIn("DUPLICATE", [row.get("state") for row in result["observations"]])

    def test_fixture_capture_replay_admission(self) -> None:
        import json

        lines = FIXTURE.read_text(encoding="utf-8").strip().splitlines()
        admitted = 0
        for line in lines:
            record = json.loads(line)
            result = self.engine.evaluate_record(record, wall_now_ns=int(record["clocks"]["received_time_ns"]) + 1_000_000)
            if result.get("envelope"):
                admitted += 1
        self.assertEqual(admitted, 3)


if __name__ == "__main__":
    unittest.main()
