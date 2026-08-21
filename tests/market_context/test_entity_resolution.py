"""Tests for MC2 entity resolution."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.market_context import (  # noqa: E402
    ContextQualityFlag,
    EntityClaim,
    entity_id_from_symbol,
)
from market_platform_foundation.market_context.entity_resolution import (  # noqa: E402
    build_symbol_mapping_registry,
    load_context_document_records,
    resolve_entity_from_claims,
)

RAW_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_raw_documents_slice.json"
AMBIGUOUS_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_entity_ambiguous_slice.json"


class TestMC2EntityResolution(unittest.TestCase):
    def test_entity_id_from_symbol_is_deterministic(self) -> None:
        first = entity_id_from_symbol("BOXL")
        second = entity_id_from_symbol("BOXL")
        self.assertEqual(first, second)
        self.assertNotEqual(first, entity_id_from_symbol("NVDA"))

    def test_missing_symbol_fails_closed(self) -> None:
        resolution = resolve_entity_from_claims(())
        self.assertIsNone(resolution.entity_id)
        self.assertIn(ContextQualityFlag.ENTITY_RESOLUTION_FAILED.value, resolution.quality_flags)

    def test_conflicting_claims_mark_ambiguous(self) -> None:
        resolution = resolve_entity_from_claims(
            (
                EntityClaim(symbol="BOXL", issuer_name="BOXL International Inc"),
                EntityClaim(symbol="BOX", issuer_name="Box Inc"),
            )
        )
        self.assertTrue(resolution.ambiguous)
        self.assertIsNone(resolution.entity_id)
        self.assertIn(ContextQualityFlag.ENTITY_AMBIGUOUS.value, resolution.quality_flags)
        self.assertEqual(len(resolution.candidate_entity_ids), 2)

    def test_fixture_documents_resolve_entity_ids(self) -> None:
        records = load_context_document_records(
            RAW_FIXTURE,
            symbol_mappings=build_symbol_mapping_registry("BOXL"),
        )
        self.assertEqual(len(records), 9)
        for record in records:
            self.assertIsNotNone(record.entity_resolution.entity_id)
            self.assertEqual(record.document.associated_entity_ids[0], record.entity_resolution.entity_id)
            self.assertEqual(record.document.associated_symbols, ("BOXL",))

    def test_ambiguous_fixture_marks_cluster_uncertain_inputs(self) -> None:
        records = load_context_document_records(AMBIGUOUS_FIXTURE)
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertTrue(record.entity_resolution.ambiguous)
        self.assertIn(ContextQualityFlag.ENTITY_AMBIGUOUS.value, record.document.quality_flags)

    def test_pit_fields_preserved_on_resolution(self) -> None:
        records = load_context_document_records(RAW_FIXTURE)
        record = records[0]
        self.assertLessEqual(record.document.event_time, record.document.available_time)


if __name__ == "__main__":
    unittest.main()
