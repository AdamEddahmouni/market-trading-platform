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
    def test_registry_default_path_is_aggregator_only(self) -> None:
        fn = get_normalizer("market_trackers.sec_insider")
        self.assertIsNotNone(fn)
        self.assertIs(fn, normalize_sec_insider_row)
        row = _load_mt("form4_open_market_purchase.json")
        ctx = NormalizationContext(
            received_time_ns=_PLATFORM_RECEIVED_NS,
            ingestion_mode=IngestionMode.FIXTURE,
        )
        result = fn(row, context=ctx)
        self.assertTrue(result.ok, result.diagnostics)
        assert result.event is not None
        flags = result.event.payload["reconcile_flags"]
        self.assertIn("SEC_PRIMARY_NOT_SUPPLIED_AGGREGATOR_FILING_ONLY", flags)
        self.assertIn("AGGREGATOR_FILING_PUBLICATION_ONLY", flags)
        self.assertNotIn("PRIMARY_SOURCE_EDGAR_WINS", flags)
        self.assertFalse(result.event.payload["clock_doctrine"]["edgar_primary_supplied"])
        self.assertEqual(
            result.event.payload["clock_doctrine"]["publication_authority"],
            "market_trackers.sec_insider",
        )

    def test_form4_golden_event_v1_five_clocks_with_edgar_primary(self) -> None:
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
        flags = result.event.payload["reconcile_flags"]
        self.assertIn("PRIMARY_SOURCE_EDGAR_WINS", flags)
        self.assertIn("SEC_ACCEPTANCE_FROM_PRIMARY", flags)
        self.assertNotIn("SEC_PRIMARY_NOT_SUPPLIED_AGGREGATOR_FILING_ONLY", flags)
        self.assertNotIn("AGGREGATOR_FILING_PUBLICATION_ONLY", flags)
        self.assertTrue(result.event.payload["clock_doctrine"]["edgar_primary_supplied"])
        self.assertEqual(result.event.payload["clock_doctrine"]["publication_authority"], "sec.edgar")

    def test_reconcile_flags_match_omitted_edgar_primary(self) -> None:
        row = _load_mt("form4_open_market_purchase.json")
        clocks = reconcile_sec_insider_clocks(row, platform_received_time_ns=_PLATFORM_RECEIVED_NS)
        self.assertIn("SEC_PRIMARY_NOT_SUPPLIED_AGGREGATOR_FILING_ONLY", clocks.reconcile_flags)
        self.assertIn("AGGREGATOR_FILING_PUBLICATION_ONLY", clocks.reconcile_flags)
        self.assertNotIn("PRIMARY_SOURCE_EDGAR_WINS", clocks.reconcile_flags)
        self.assertEqual(clocks.sec_acceptance_time_ns, 0)
        self.assertNotIn("sec_edgar", clocks.available_time_basis)

    def test_reconcile_flags_match_supplied_edgar_primary(self) -> None:
        row = _load_mt("form4_open_market_purchase.json")
        edgar = _load_edgar("insider_form4_nvda_submission.json")
        clocks = reconcile_sec_insider_clocks(
            row,
            platform_received_time_ns=_PLATFORM_RECEIVED_NS,
            edgar_primary=edgar,
        )
        self.assertIn("PRIMARY_SOURCE_EDGAR_WINS", clocks.reconcile_flags)
        self.assertIn("SEC_ACCEPTANCE_FROM_PRIMARY", clocks.reconcile_flags)
        self.assertNotIn("SEC_PRIMARY_NOT_SUPPLIED_AGGREGATOR_FILING_ONLY", clocks.reconcile_flags)
        self.assertGreater(clocks.sec_acceptance_time_ns, 0)
        self.assertGreaterEqual(clocks.available_time_ns, clocks.sec_acceptance_time_ns)

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
