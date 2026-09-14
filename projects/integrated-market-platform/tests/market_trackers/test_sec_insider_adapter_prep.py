"""Golden fixtures for Market Trackers SEC Forms 3/4/5 adapter preparation."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from market_platform_foundation.market_trackers.sec_insider import (
    UPSTREAM_PIN,
    build_adapter_prep_bundle,
    characterize_record,
    validate_market_trackers_row,
)

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "market_trackers" / "sec_insider"
_PLATFORM_RECEIVED_NS = 1_725_100_800_000_000_000  # fixed for deterministic golden bundles


def _load(name: str) -> dict:
    return json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))


class MarketTrackersSecInsiderAdapterPrepTests(unittest.TestCase):
    def test_upstream_pin_documents_schema_version(self) -> None:
        self.assertEqual(UPSTREAM_PIN.dataset_id, "insider-transactions")
        self.assertEqual(UPSTREAM_PIN.schema_version, 2)
        self.assertIn("sec edgar", UPSTREAM_PIN.primary_source_authority.lower())

    def test_characterization_lists_core_fields(self) -> None:
        spec = characterize_record()
        self.assertIn("accessionNumber", spec.required_fields)
        self.assertIn("transactedAt", spec.optional_nullable_fields)

    def test_malformed_row_fails_validation(self) -> None:
        row = _load("malformed_missing_provenance.json")
        outcome = validate_market_trackers_row(row)
        self.assertFalse(outcome.ok)
        self.assertTrue(any("provenance" in err for err in outcome.errors))

    def test_form4_purchase_golden_bundle(self) -> None:
        row = _load("form4_open_market_purchase.json")
        bundle = build_adapter_prep_bundle(row, platform_received_time_ns=_PLATFORM_RECEIVED_NS)
        self.assertTrue(bundle.validation.ok)
        self.assertIsNotNone(bundle.receipt)
        self.assertIsNotNone(bundle.pit)
        self.assertIsNotNone(bundle.event_map)
        self.assertIsNotNone(bundle.evidence)

        assert bundle.pit is not None
        self.assertEqual(bundle.pit.economic_event_date, "2025-01-15")
        self.assertEqual(bundle.pit.filing_date, "2025-01-17")
        self.assertIn("PUBLIC_KNOWLEDGE_NOT_TRANSACTION_DATE", bundle.pit.pit_flags)

        assert bundle.event_map is not None
        self.assertEqual(bundle.event_map.event_type, "INSIDER_OWNERSHIP_ROW")
        self.assertTrue(bundle.event_map.instrument_qualified_id.startswith("xa01.provisional:"))

        assert bundle.evidence is not None
        self.assertEqual(bundle.evidence.transaction_code, "P")
        self.assertIn("FORM4_NOT_AUTO_DIRECTIONAL", bundle.evidence.uncertainty_flags)
        self.assertNotIn("BULLISH", bundle.evidence.reason_codes)

    def test_form3_holding_null_transacted_at(self) -> None:
        row = _load("form3_initial_holding.json")
        bundle = build_adapter_prep_bundle(row, platform_received_time_ns=_PLATFORM_RECEIVED_NS)
        self.assertTrue(bundle.validation.ok)
        assert bundle.pit is not None
        self.assertIsNone(bundle.pit.economic_event_date)
        self.assertIn("FORM3_OR_HOLDING_ROW_NO_TRANSACTION_DATE", bundle.pit.pit_flags)

    def test_derivative_row_preserves_uncertainty(self) -> None:
        row = _load("form4_derivative_disposition.json")
        bundle = build_adapter_prep_bundle(row, platform_received_time_ns=_PLATFORM_RECEIVED_NS)
        assert bundle.evidence is not None
        self.assertIn("DERIVATIVE_TABLE_ROW", bundle.evidence.uncertainty_flags)

    def test_null_ticker_fails_closed_on_instrument(self) -> None:
        row = _load("form4_null_ticker.json")
        bundle = build_adapter_prep_bundle(row, platform_received_time_ns=_PLATFORM_RECEIVED_NS)
        assert bundle.event_map is not None
        self.assertIsNone(bundle.event_map.instrument_qualified_id)
        self.assertIn("INSTRUMENT_UNRESOLVED_TICKER_NULL", bundle.event_map.identity_flags)

    def test_receipt_links_primary_source(self) -> None:
        row = _load("form4_open_market_purchase.json")
        bundle = build_adapter_prep_bundle(row, platform_received_time_ns=_PLATFORM_RECEIVED_NS)
        assert bundle.receipt is not None
        self.assertTrue(bundle.receipt.primary_source_url.startswith("https://www.sec.gov/"))
        self.assertIn("NOT_TRADE_RECOMMENDATION", bundle.receipt.quality_flags)

    def test_step_failure_fail_closed_no_partial_admit(self) -> None:
        row = _load("form4_open_market_purchase.json")
        row = dict(row)
        row["accessionNumber"] = ""
        bundle = build_adapter_prep_bundle(row, platform_received_time_ns=_PLATFORM_RECEIVED_NS)
        self.assertTrue(bundle.errors)
        self.assertIsNone(bundle.event_map)
        self.assertIsNone(bundle.evidence)
        self.assertIsNone(bundle.receipt)
        self.assertIsNone(bundle.pit)


if __name__ == "__main__":
    unittest.main()
