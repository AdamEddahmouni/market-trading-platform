"""Golden fixtures for Market Trackers congressional PTR adapter preparation."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from market_platform_foundation.market_trackers.congressional_disclosure import (
    EVENT_TYPE,
    UPSTREAM_PIN,
    build_adapter_prep_bundle,
    characterize_record,
    event_v1_mapping_contract,
    validate_market_trackers_row,
)

_FIXTURE_DIR = (
    Path(__file__).resolve().parents[1] / "fixtures" / "market_trackers" / "congressional_disclosure"
)
_PLATFORM_RECEIVED_NS = 1_725_100_800_000_000_000


def _load(name: str) -> dict:
    return json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))


class MarketTrackersCongressionalDisclosureAdapterPrepTests(unittest.TestCase):
    def test_upstream_pin_documents_schema(self) -> None:
        self.assertEqual(UPSTREAM_PIN.dataset_id, "congress-trades")
        self.assertEqual(UPSTREAM_PIN.export_dir, "congress/trades")
        self.assertIn("Senate eFD", UPSTREAM_PIN.primary_source_authority)

    def test_characterization_lists_core_fields(self) -> None:
        spec = characterize_record()
        self.assertIn("transactedAt", spec.required_fields)
        self.assertIn("amountRange", spec.nested_objects)

    def test_malformed_row_fails_validation(self) -> None:
        row = _load("malformed_missing_provenance.json")
        outcome = validate_market_trackers_row(row)
        self.assertFalse(outcome.ok)
        self.assertTrue(any("provenance" in err for err in outcome.errors))

    def test_senate_purchase_golden_bundle(self) -> None:
        row = _load("senate_stock_purchase.json")
        bundle = build_adapter_prep_bundle(row, platform_received_time_ns=_PLATFORM_RECEIVED_NS)
        self.assertTrue(bundle.validation.ok)
        self.assertIsNotNone(bundle.receipt)
        self.assertIsNotNone(bundle.pit)
        self.assertIsNotNone(bundle.event_map)
        self.assertIsNotNone(bundle.evidence)

        assert bundle.pit is not None
        self.assertEqual(bundle.pit.economic_event_date, "2025-01-28")
        self.assertEqual(bundle.pit.filing_date, "2025-02-10")
        self.assertIn("PUBLIC_KNOWLEDGE_NOT_TRANSACTION_DATE", bundle.pit.pit_flags)

        assert bundle.event_map is not None
        self.assertEqual(bundle.event_map.event_type, EVENT_TYPE)
        self.assertEqual(bundle.event_map.publisher_id, "senate.efd")
        self.assertTrue(bundle.event_map.instrument_qualified_id.startswith("xa01.provisional:"))

        contract = event_v1_mapping_contract(row)
        self.assertEqual(contract["event_type"], EVENT_TYPE)
        self.assertNotIn("execution_side", contract["payload_core"])

        assert bundle.evidence is not None
        self.assertEqual(bundle.evidence.disclosed_side, "buy")
        self.assertIn("PTR_NOT_AUTO_DIRECTIONAL", bundle.evidence.uncertainty_flags)
        self.assertIn("DISCLOSED_SIDE_NOT_EXECUTION_SIDE", bundle.evidence.uncertainty_flags)

    def test_open_ended_range_and_null_ticker(self) -> None:
        row = _load("open_ended_amount_range.json")
        bundle = build_adapter_prep_bundle(row, platform_received_time_ns=_PLATFORM_RECEIVED_NS)
        self.assertTrue(bundle.validation.ok)
        assert bundle.event_map is not None
        self.assertIsNone(bundle.event_map.instrument_qualified_id)
        self.assertIn("INSTRUMENT_UNRESOLVED_TICKER_NULL", bundle.event_map.identity_flags)
        assert bundle.evidence is not None
        self.assertIn("OPEN_ENDED_AMOUNT_RANGE", bundle.evidence.uncertainty_flags)

    def test_receipt_quality_flags(self) -> None:
        row = _load("house_stock_sale.json")
        bundle = build_adapter_prep_bundle(row, platform_received_time_ns=_PLATFORM_RECEIVED_NS)
        assert bundle.receipt is not None
        self.assertIn("REPLACEABLE_AGGREGATOR", bundle.receipt.quality_flags)
        self.assertIn("NOT_TRADE_RECOMMENDATION", bundle.receipt.quality_flags)
        assert bundle.event_map is not None
        self.assertEqual(bundle.event_map.publisher_id, "house.clerk")

    def test_step_failure_fail_closed_no_partial_admit(self) -> None:
        row = _load("senate_stock_purchase.json")
        row = dict(row)
        row["docId"] = ""
        bundle = build_adapter_prep_bundle(row, platform_received_time_ns=_PLATFORM_RECEIVED_NS)
        self.assertTrue(bundle.errors)
        self.assertIsNone(bundle.event_map)
        self.assertIsNone(bundle.evidence)
        self.assertIsNone(bundle.receipt)
        self.assertIsNone(bundle.pit)


if __name__ == "__main__":
    unittest.main()
