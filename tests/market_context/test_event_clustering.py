"""Tests for MC3 event clustering."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.market_context import (  # noqa: E402
    ContextQualityFlag,
    CorroborationState,
    information_event_to_dict,
)
from market_platform_foundation.market_context.entity_resolution import (  # noqa: E402
    build_symbol_mapping_registry,
    load_context_document_records,
)
from market_platform_foundation.market_context.event_clustering import (  # noqa: E402
    cluster_fixture_records,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402

RAW_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_raw_documents_slice.json"
SYNDICATION_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_syndication_slice.json"
AMBIGUOUS_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_entity_ambiguous_slice.json"
EXPECTED_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_cluster_expected.json"


class TestMC3EventClustering(unittest.TestCase):
    def test_boxl_fixture_clusters_to_five_events(self) -> None:
        records = load_context_document_records(
            RAW_FIXTURE,
            symbol_mappings=build_symbol_mapping_registry("BOXL"),
        )
        events = cluster_fixture_records(
            records,
            prediction_cutoff="2026-07-23T00:00:00.000000000Z",
        )
        self.assertEqual(len(events), 5)
        event_types = sorted(event.canonical_event_type for event in events)
        self.assertEqual(
            event_types,
            [
                "analyst_upgrade",
                "earnings_beat",
                "fda_clearance",
                "macro_headwind",
                "offering_risk",
            ],
        )

    def test_duplicate_headlines_flag_event_duplicate(self) -> None:
        records = load_context_document_records(RAW_FIXTURE)
        events = cluster_fixture_records(
            records,
            prediction_cutoff="2026-07-23T00:00:00.000000000Z",
        )
        earnings = next(event for event in events if event.canonical_event_type == "earnings_beat")
        self.assertEqual(earnings.document_count, 2)
        self.assertIn(ContextQualityFlag.EVENT_DUPLICATE.value, earnings.quality_flags)

    def test_syndication_independent_source_count(self) -> None:
        records = load_context_document_records(SYNDICATION_FIXTURE)
        events = cluster_fixture_records(
            records,
            prediction_cutoff="2026-07-23T00:00:00.000000000Z",
        )
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.document_count, 4)
        self.assertEqual(event.independent_source_count, 3)
        self.assertEqual(event.corroboration_state, CorroborationState.CORROBORATED)

    def test_pit_cutoff_excludes_future_documents(self) -> None:
        records = load_context_document_records(RAW_FIXTURE)
        early_cutoff = iso_to_epoch_ns("2026-07-20T00:00:00.000000000Z")
        events = cluster_fixture_records(records, prediction_cutoff=early_cutoff)
        event_types = {event.canonical_event_type for event in events}
        self.assertIn("earnings_beat", event_types)
        self.assertIn("fda_clearance", event_types)
        self.assertNotIn("analyst_upgrade", event_types)
        self.assertNotIn("offering_risk", event_types)
        self.assertNotIn("macro_headwind", event_types)

    def test_ambiguous_entity_marks_cluster_uncertain(self) -> None:
        records = load_context_document_records(AMBIGUOUS_FIXTURE)
        events = cluster_fixture_records(
            records,
            prediction_cutoff="2026-07-23T00:00:00.000000000Z",
        )
        self.assertEqual(len(events), 1)
        self.assertIn(ContextQualityFlag.EVENT_CLUSTER_UNCERTAIN.value, events[0].quality_flags)

    def test_cluster_available_time_is_max_document_available_time(self) -> None:
        records = load_context_document_records(RAW_FIXTURE)
        events = cluster_fixture_records(
            records,
            prediction_cutoff="2026-07-23T00:00:00.000000000Z",
        )
        earnings = next(event for event in events if event.canonical_event_type == "earnings_beat")
        self.assertEqual(earnings.available_time, "2026-07-15T14:45:00.000000000Z")
        self.assertEqual(earnings.event_time, "2026-07-15T14:30:00.000000000Z")

    def test_golden_expected_clusters(self) -> None:
        records = load_context_document_records(
            RAW_FIXTURE,
            symbol_mappings=build_symbol_mapping_registry("BOXL"),
        )
        events = cluster_fixture_records(
            records,
            prediction_cutoff="2026-07-23T00:00:00.000000000Z",
        )
        actual = [information_event_to_dict(event) for event in events]
        expected_payload = json.loads(EXPECTED_FIXTURE.read_text(encoding="utf-8"))
        expected = expected_payload["events"]
        self.assertEqual(len(actual), len(expected))
        for actual_event, expected_event in zip(actual, expected, strict=True):
            self.assertEqual(actual_event["canonical_event_type"], expected_event["canonical_event_type"])
            self.assertEqual(actual_event["document_count"], expected_event["document_count"])
            self.assertEqual(
                actual_event["independent_source_count"],
                expected_event["independent_source_count"],
            )
            self.assertEqual(actual_event["corroboration_state"], expected_event["corroboration_state"])
            self.assertEqual(actual_event["event_id"], expected_event["event_id"])


if __name__ == "__main__":
    unittest.main()
