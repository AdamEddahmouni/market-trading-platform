"""EventV1 normalization for Market Trackers SEC insider rows (Lane B)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.normalization import (  # noqa: E402
    IngestionMode,
    NormalizationContext,
    get_normalizer,
)
from market_platform_foundation.intelligence.normalization.errors import (  # noqa: E402
    NormalizationErrorCode,
)
from market_platform_foundation.intelligence.normalization.providers.market_trackers_sec_insider import (  # noqa: E402
    normalize_sec_insider_row,
)
from market_platform_foundation.market_trackers.sec_insider.reconcile import (  # noqa: E402
    reconcile_sec_insider_clocks,
)

_MT_FIXTURES = ROOT / "tests" / "fixtures" / "market_trackers" / "sec_insider"
_EDGAR_FIXTURES = ROOT / "tests" / "fixtures" / "sec_edgar"
_PLATFORM_RECEIVED_NS = 1_725_100_800_000_000_000


def _load_mt(name: str) -> dict:
    return json.loads((_MT_FIXTURES / name).read_text(encoding="utf-8"))


def _load_edgar(name: str) -> dict:
    return json.loads((_EDGAR_FIXTURES / name).read_text(encoding="utf-8"))


class MarketTrackersSecInsiderEventV1Tests(unittest.TestCase):
    def test_registry_exposes_normalizer_for_lane_a(self) -> None:
        fn = get_normalizer("market_trackers.sec_insider")
        self.assertIsNotNone(fn)
        self.assertIs(fn, normalize_sec_insider_row)

    def test_form4_golden_event_v1_five_clocks(self) -> None:
        row = _load_mt("form4_open_market_purchase.json")
        edgar = _load_edgar("insider_form4_nvda_submission.json")
        ctx = NormalizationContext(
            received_time_ns=_PLATFORM_RECEIVED_NS,
            ingestion_mode=IngestionMode.FIXTURE,
        )
        result = normalize_sec_insider_row(row, context=ctx, edgar_primary=edgar)
        self.assertTrue(result.ok, result.diagnostics)
        assert result.event is not None
        clocks = result.event.payload["clocks"]
        self.assertIsNotNone(clocks["economic_event_time_ns"])
        self.assertGreater(clocks["filing_publication_time_ns"], 0)
        self.assertGreater(clocks["sec_acceptance_time_ns"], 0)
        self.assertGreater(clocks["aggregator_retrieved_time_ns"], 0)
        self.assertEqual(clocks["platform_received_time_ns"], _PLATFORM_RECEIVED_NS)
        self.assertGreater(result.event.available_time_ns, clocks["economic_event_time_ns"])
        self.assertNotEqual(result.event.available_time_ns, clocks["economic_event_time_ns"])
        self.assertIn("PRIMARY_SOURCE_EDGAR_WINS", result.event.payload["reconcile_flags"])

    def test_transaction_date_is_not_available_time(self) -> None:
        row = _load_mt("form4_open_market_purchase.json")
        clocks = reconcile_sec_insider_clocks(row, platform_received_time_ns=_PLATFORM_RECEIVED_NS)
        economic = clocks.economic_event_time_ns
        assert economic is not None
        self.assertNotEqual(clocks.available_time_ns, economic)

    def test_edgar_primary_overrides_aggregator_filing_date(self) -> None:
        row = _load_mt("form4_open_market_purchase.json")
        row = dict(row)
        row["filedAt"] = "2025-01-16"
        edgar = _load_edgar("insider_form4_nvda_submission.json")
        clocks = reconcile_sec_insider_clocks(row, platform_received_time_ns=_PLATFORM_RECEIVED_NS, edgar_primary=edgar)
        self.assertIn("AGGREGATOR_FILING_DATE_OVERRIDDEN_BY_EDGAR", clocks.reconcile_flags)
        self.assertEqual(clocks.primary_filing_date, "2025-01-17")
        self.assertEqual(clocks.aggregator_filing_date, "2025-01-16")

    def test_null_ticker_fail_closed(self) -> None:
        row = _load_mt("form4_null_ticker.json")
        ctx = NormalizationContext(
            received_time_ns=_PLATFORM_RECEIVED_NS,
            ingestion_mode=IngestionMode.FIXTURE,
        )
        result = normalize_sec_insider_row(row, context=ctx)
        self.assertIsNone(result.event)
        self.assertTrue(result.diagnostics)
        self.assertEqual(result.diagnostics[0].code, NormalizationErrorCode.INVALID_INSTRUMENT)

    def test_invalid_ticker_fail_closed(self) -> None:
        row = _load_mt("form4_open_market_purchase.json")
        row = dict(row)
        row["ticker"] = "!!!"
        ctx = NormalizationContext(
            received_time_ns=_PLATFORM_RECEIVED_NS,
            ingestion_mode=IngestionMode.FIXTURE,
        )
        result = normalize_sec_insider_row(row, context=ctx)
        self.assertIsNone(result.event)
        self.assertEqual(result.diagnostics[0].code, NormalizationErrorCode.INVALID_INSTRUMENT)


if __name__ == "__main__":
    unittest.main()
