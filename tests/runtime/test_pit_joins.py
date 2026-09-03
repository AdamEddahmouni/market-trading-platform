"""Tests for centralized P0 PIT joins (O-23)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.reference import ReferenceKind  # noqa: E402
from market_platform_foundation.runtime.bitemporal_store import (  # noqa: E402
    BitemporalReferenceStore,
    load_reference_records,
)
from market_platform_foundation.runtime.pit_joins import (  # noqa: E402
    join_as_of,
    run_p0_bitemporal_gate_validation,
)

FIXTURE = ROOT / "tests" / "fixtures" / "platform" / "p0" / "p0_bitemporal_slice.json"

T_BEFORE = "2024-06-14T23:59:59.000000000Z"
T_AFTER = "2024-06-16T00:00:00.000000000Z"
MARKET = "2025-01-15T20:00:00.000000000Z"


class PitJoinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.store = BitemporalReferenceStore()
        for record in load_reference_records(payload["records"]):
            cls.store.append(record)

    def test_futures_spec_correction(self) -> None:
        before = join_as_of(self.store, ReferenceKind.FUTURES_SPEC, "ES", MARKET, T_BEFORE)
        after = join_as_of(self.store, ReferenceKind.FUTURES_SPEC, "ES", MARKET, T_AFTER)
        self.assertEqual(before["status"], "AVAILABLE")
        self.assertEqual(before["payload"]["spec_version"], "es_cme_v1")
        self.assertEqual(after["payload"]["spec_version"], "es_cme_v1_corrected")
        self.assertIn("LOOKAHEAD_REJECTED", before["quality_flags"])

    def test_earnings_calendar_revision(self) -> None:
        before = join_as_of(self.store, ReferenceKind.EARNINGS_CALENDAR, "NVDA", MARKET, T_BEFORE)
        after = join_as_of(self.store, ReferenceKind.EARNINGS_CALENDAR, "NVDA", MARKET, T_AFTER)
        self.assertEqual(before["payload"]["earnings_event_time"], "2026-08-26T20:00:00.000000000Z")
        self.assertEqual(after["payload"]["earnings_event_time"], "2026-08-27T20:00:00.000000000Z")

    def test_options_oi_restatement(self) -> None:
        before = join_as_of(self.store, ReferenceKind.OPTIONS_OI, "NVDA", MARKET, T_BEFORE)
        after = join_as_of(self.store, ReferenceKind.OPTIONS_OI, "NVDA", MARKET, T_AFTER)
        self.assertEqual(before["payload"]["open_interest"], 1000)
        self.assertEqual(after["payload"]["open_interest"], 1250)

    def test_dividend_restatement(self) -> None:
        before = join_as_of(self.store, ReferenceKind.DIVIDEND_ASSUMPTION, "NVDA", MARKET, T_BEFORE)
        after = join_as_of(self.store, ReferenceKind.DIVIDEND_ASSUMPTION, "NVDA", MARKET, T_AFTER)
        self.assertEqual(before["payload"]["dividend_yield"], "0.0100")
        self.assertEqual(after["payload"]["dividend_yield"], "0.0120")

    def test_symbol_mapping(self) -> None:
        result = join_as_of(self.store, ReferenceKind.SYMBOL_MAPPING, "ES", MARKET, T_AFTER)
        self.assertEqual(result["status"], "AVAILABLE")
        self.assertEqual(result["payload"]["venue_id"], "CME")

    def test_p0_s1_gate_pass(self) -> None:
        report = run_p0_bitemporal_gate_validation()
        self.assertEqual(report["aggregate_status"], "PASS")

    def test_missing_join_fail_closed(self) -> None:
        result = join_as_of(self.store, ReferenceKind.FUTURES_SPEC, "NQ", MARKET, T_AFTER)
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["payload"], {})
        self.assertIn("REFERENCE_UNAVAILABLE", result["quality_flags"])


if __name__ == "__main__":
    unittest.main()
