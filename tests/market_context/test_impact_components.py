"""Tests for MC7 novelty / materiality / credibility impact components."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.market_context import ContextQualityFlag  # noqa: E402
from market_platform_foundation.market_context.entity_resolution import (  # noqa: E402
    build_symbol_mapping_registry,
    load_context_document_records,
)
from market_platform_foundation.market_context.event_clustering import cluster_fixture_records  # noqa: E402
from market_platform_foundation.market_context.extraction import (  # noqa: E402
    build_fixture_extraction_pipeline,
    load_llm_extraction_fixture,
    load_structured_metrics_fixture,
)
from market_platform_foundation.market_context.impact_components import (  # noqa: E402
    build_fixture_impact_pipeline,
    build_impact_cross_lane_evidence,
    compute_novelty_evidence,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.providers.projections import (  # noqa: E402
    build_workspace_market_context_payload,
)

RAW_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_raw_documents_slice.json"
SYNDICATION_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_syndication_slice.json"
AMBIGUOUS_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_entity_ambiguous_slice.json"
LLM_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_llm_extraction_slice.json"
STRUCTURED_FIXTURE = (
    ROOT / "tests" / "fixtures" / "market_context" / "boxl_structured_metrics_slice.json"
)
EXPECTED_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_impact_components_expected.json"
CUTOFF = "2026-07-23T00:00:00.000000000Z"
CUTOFF_NS = iso_to_epoch_ns(CUTOFF)


def _impact_pipeline_for_fixture(fixture_path: Path, *, cutoff_ns: int = CUTOFF_NS):
    records = load_context_document_records(
        fixture_path,
        symbol_mappings=build_symbol_mapping_registry("BOXL"),
    )
    llm_labels = load_llm_extraction_fixture(LLM_FIXTURE) if LLM_FIXTURE.is_file() else {}
    structured_metrics = (
        load_structured_metrics_fixture(STRUCTURED_FIXTURE)
        if STRUCTURED_FIXTURE.is_file()
        else {}
    )
    _, enriched_events, _ = build_fixture_extraction_pipeline(
        records,
        prediction_cutoff=cutoff_ns,
        llm_labels=llm_labels,
        structured_metrics=structured_metrics,
    )
    return build_fixture_impact_pipeline(
        records,
        enriched_events,
        prediction_cutoff=cutoff_ns,
    )


class TestMC7ImpactPipeline(unittest.TestCase):
    def test_golden_workspace_impact_block(self) -> None:
        expected = json.loads(EXPECTED_FIXTURE.read_text(encoding="utf-8"))
        payload = build_workspace_market_context_payload(
            "BOXL",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=CUTOFF_NS,
        )
        self.assertTrue(payload["impact_components_available"])
        self.assertEqual(
            len(payload["impact_component_summaries"]),
            expected["impact_summary_count"],
        )
        self.assertEqual(len(payload["novelty_evidence"]), expected["novelty_count"])
        self.assertEqual(len(payload["materiality_evidence"]), expected["materiality_count"])
        self.assertEqual(len(payload["credibility_evidence"]), expected["credibility_count"])

        by_event = {item["event_id"]: item for item in payload["impact_component_summaries"]}
        for expected_row in expected["impact_component_summaries"]:
            actual = by_event[expected_row["event_id"]]
            self.assertEqual(actual["canonical_event_type"], expected_row["canonical_event_type"])
            self.assertEqual(actual["novelty_score"], expected_row["novelty_score"])
            self.assertEqual(actual["materiality_score"], expected_row["materiality_score"])
            self.assertEqual(actual["source_credibility"], expected_row["source_credibility"])
            self.assertEqual(actual["official_source_found"], expected_row["official_source_found"])
            self.assertEqual(actual["quality_flags"], expected_row["quality_flags"])

    def test_syndication_slice_higher_novelty_than_duplicate_pair(self) -> None:
        raw_novelty, _, _, raw_summaries = _impact_pipeline_for_fixture(RAW_FIXTURE)
        syn_novelty, _, _, syn_summaries = _impact_pipeline_for_fixture(SYNDICATION_FIXTURE)

        raw_fda = next(item for item in raw_summaries if item.canonical_event_type == "fda_clearance")
        syn_fda = next(item for item in syn_summaries if item.canonical_event_type == "fda_clearance")

        self.assertIsNotNone(raw_fda.novelty_score)
        self.assertIsNotNone(syn_fda.novelty_score)
        self.assertGreater(syn_fda.novelty_score, raw_fda.novelty_score)
        self.assertGreater(syn_fda.duplicate_probability or 0.0, 0.0)
        self.assertEqual(len(raw_novelty), len(raw_summaries))
        self.assertEqual(len(syn_novelty), 1)

    def test_official_fda_source_elevated_credibility(self) -> None:
        _, _, credibility_rows, summaries = _impact_pipeline_for_fixture(RAW_FIXTURE)
        fda = next(item for item in summaries if item.canonical_event_type == "fda_clearance")
        fda_cred = next(item for item in credibility_rows if item.event_id == fda.event_id)

        self.assertTrue(fda.official_source_found)
        self.assertTrue(fda_cred.official_source_found)
        self.assertGreaterEqual(fda.source_credibility or 0.0, 0.75)

    def test_pit_excludes_future_clusters(self) -> None:
        early_cutoff = iso_to_epoch_ns("2026-07-16T00:00:00.000000000Z")
        novelty_rows, _, _, summaries = _impact_pipeline_for_fixture(
            RAW_FIXTURE,
            cutoff_ns=early_cutoff,
        )
        types = {item.canonical_event_type for item in summaries}
        self.assertIn("earnings_beat", types)
        self.assertNotIn("fda_clearance", types)
        self.assertEqual(len(novelty_rows), len(summaries))

    def test_ambiguous_cluster_flags_novelty_uncertain(self) -> None:
        records = load_context_document_records(
            AMBIGUOUS_FIXTURE,
            symbol_mappings=build_symbol_mapping_registry("BOXL"),
        )
        events = cluster_fixture_records(records, prediction_cutoff=CUTOFF_NS)
        records_by_id = {record.document.document_id: record for record in records}
        uncertain = next(
            event
            for event in events
            if ContextQualityFlag.EVENT_CLUSTER_UNCERTAIN.value in event.quality_flags
        )
        member_records = [
            records_by_id[document_id]
            for document_id in uncertain.document_ids
            if document_id in records_by_id
        ]
        novelty = compute_novelty_evidence(uncertain, member_records)
        self.assertIn(ContextQualityFlag.NOVELTY_UNCERTAIN.value, novelty.quality_flags)

    def test_cross_lane_metadata_exposes_components(self) -> None:
        _, _, _, summaries = _impact_pipeline_for_fixture(RAW_FIXTURE)
        evidence = build_impact_cross_lane_evidence(
            summaries,
            symbol="BOXL",
            prediction_cutoff=CUTOFF_NS,
        )
        self.assertTrue(evidence)
        impact_rows = [
            row
            for row in evidence
            if row.get("metadata", {}).get("scoring_method") == "impact_components_v1"
        ]
        self.assertTrue(impact_rows)
        metadata = impact_rows[0]["metadata"]
        self.assertIn("novelty_score", metadata)
        self.assertIn("materiality_score", metadata)
        self.assertIn("source_credibility", metadata)
        self.assertIn("materiality_basis", metadata)

    def test_non_boxl_symbol_fail_closed(self) -> None:
        payload = build_workspace_market_context_payload(
            "NVDA",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=CUTOFF_NS,
        )
        self.assertFalse(payload["available"])
        self.assertFalse(payload.get("impact_components_available", True))


if __name__ == "__main__":
    unittest.main()
