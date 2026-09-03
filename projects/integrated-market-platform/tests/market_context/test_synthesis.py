"""Tests for MC16 multi-document LLM synthesis."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.market_context import ContextQualityFlag  # noqa: E402
from market_platform_foundation.cross_lane.evidence import EvidenceSignal  # noqa: E402
from market_platform_foundation.market_context.entity_resolution import (  # noqa: E402
    build_symbol_mapping_registry,
    load_context_document_records,
)
from market_platform_foundation.market_context.extraction import (  # noqa: E402
    build_fixture_extraction_pipeline,
    load_llm_extraction_fixture,
)
from market_platform_foundation.market_context.synthesis import (  # noqa: E402
    build_fixture_synthesis_pipeline,
    build_synthesis_cross_lane_evidence,
    load_synthesis_fixture,
    run_mc16_gate_validation,
    GATE_PREDICTION_CUTOFF,
    GATE_REVISION_CUTOFF,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.providers.projections import (  # noqa: E402
    build_workspace_market_context_payload,
)

SYNTHESIS_FIXTURE = (
    ROOT / "tests" / "fixtures" / "market_context" / "boxl_multidoc_synthesis_slice.json"
)
EXPECTED_FIXTURE = (
    ROOT / "tests" / "fixtures" / "market_context" / "boxl_multidoc_synthesis_expected.json"
)
RAW_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_raw_documents_slice.json"
LLM_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_llm_extraction_slice.json"
CUTOFF = GATE_PREDICTION_CUTOFF
CUTOFF_NS = iso_to_epoch_ns(CUTOFF)
REVISION_CUTOFF_NS = iso_to_epoch_ns(GATE_REVISION_CUTOFF)


class TestMC16MultiDocumentSynthesis(unittest.TestCase):
    def test_golden_workspace_synthesis_block(self) -> None:
        expected = json.loads(EXPECTED_FIXTURE.read_text(encoding="utf-8"))
        payload = build_workspace_market_context_payload(
            "BOXL",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=CUTOFF_NS,
        )
        self.assertTrue(payload["multi_document_synthesis_available"])
        self.assertEqual(
            payload["multi_document_synthesis_count"],
            expected["multi_document_synthesis_count"],
        )
        self.assertEqual(
            payload["multi_document_synthesis_summaries"],
            expected["synthesis_summaries"],
        )

    def test_separate_synthesis_fields_no_fused_score(self) -> None:
        payload = build_workspace_market_context_payload(
            "BOXL",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=CUTOFF_NS,
        )
        summaries = payload.get("multi_document_synthesis_summaries") or []
        self.assertTrue(summaries)
        for row in summaries:
            self.assertIn("theme_agreement_score", row)
            self.assertIn("contradiction_detected", row)
            self.assertIn("consolidated_channels", row)
            self.assertNotIn("news_score", row)
            self.assertNotIn("universal_score", row)
            self.assertIn(
                ContextQualityFlag.NO_UNIVERSAL_NEWS_SCORE.value,
                row.get("quality_flags", []),
            )

    def test_single_member_cluster_produces_no_row(self) -> None:
        records = load_context_document_records(
            RAW_FIXTURE,
            symbol_mappings=build_symbol_mapping_registry("BOXL"),
        )
        llm_labels = load_llm_extraction_fixture(LLM_FIXTURE)
        synthesis_fixture = load_synthesis_fixture(SYNTHESIS_FIXTURE)
        _, events, _ = build_fixture_extraction_pipeline(
            records,
            prediction_cutoff=CUTOFF_NS,
            llm_labels=llm_labels,
        )
        summaries, _ = build_fixture_synthesis_pipeline(
            events,
            records,
            llm_labels,
            synthesis_fixture,
            prediction_cutoff=CUTOFF_NS,
            entity_id="BOXL",
        )
        cluster_ids = {item.cluster_id for item in summaries}
        offering_event = next(
            event for event in events if event.canonical_event_type == "offering_risk"
        )
        self.assertNotIn(offering_event.event_id, cluster_ids)

    def test_pit_excludes_future_revision_document(self) -> None:
        payload = build_workspace_market_context_payload(
            "BOXL",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=CUTOFF_NS,
        )
        summaries = payload.get("multi_document_synthesis_summaries") or []
        earnings_row = next(
            row
            for row in summaries
            if row.get("cluster_id") == "df2e6ba5-46ab-5bb1-a867-745fe0a75c91"
        )
        self.assertNotIn("mc-doc-earnings-1-v2", earnings_row.get("supporting_document_ids", []))
        self.assertNotIn("mc-doc-earnings-1-v2", earnings_row.get("revision_superseded_ids", []))

    def test_revision_supersession_at_late_cutoff(self) -> None:
        records = load_context_document_records(
            RAW_FIXTURE,
            symbol_mappings=build_symbol_mapping_registry("BOXL"),
        )
        llm_labels = load_llm_extraction_fixture(LLM_FIXTURE)
        synthesis_fixture = load_synthesis_fixture(SYNTHESIS_FIXTURE)
        _, events, _ = build_fixture_extraction_pipeline(
            records,
            prediction_cutoff=REVISION_CUTOFF_NS,
            llm_labels=llm_labels,
        )
        summaries, _ = build_fixture_synthesis_pipeline(
            events,
            records,
            llm_labels,
            synthesis_fixture,
            prediction_cutoff=REVISION_CUTOFF_NS,
            entity_id="BOXL",
        )
        earnings = next(
            item
            for item in summaries
            if item.cluster_id == "df2e6ba5-46ab-5bb1-a867-745fe0a75c91"
        )
        self.assertIn("mc-doc-earnings-1", earnings.revision_superseded_ids)
        self.assertIn("mc-doc-earnings-1-v2", earnings.supporting_document_ids)
        self.assertIn(
            ContextQualityFlag.SYNTHESIS_REVISION_CONFLICT.value,
            earnings.quality_flags,
        )

    def test_adversarial_contradiction_cluster(self) -> None:
        records = load_context_document_records(
            RAW_FIXTURE,
            symbol_mappings=build_symbol_mapping_registry("BOXL"),
        )
        llm_labels = load_llm_extraction_fixture(LLM_FIXTURE)
        synthesis_fixture = load_synthesis_fixture(SYNTHESIS_FIXTURE)
        _, events, _ = build_fixture_extraction_pipeline(
            records,
            prediction_cutoff=CUTOFF_NS,
            llm_labels=llm_labels,
        )
        summaries, _ = build_fixture_synthesis_pipeline(
            events,
            records,
            llm_labels,
            synthesis_fixture,
            prediction_cutoff=CUTOFF_NS,
            entity_id="BOXL",
            include_adversarial_clusters=True,
        )
        adversarial = next(
            item for item in summaries if item.cluster_id == "mc16-adversarial-contradiction"
        )
        self.assertTrue(adversarial.contradiction_detected)
        self.assertIn(
            ContextQualityFlag.SYNTHESIS_CONTRADICTION_PRESENT.value,
            adversarial.quality_flags,
        )

    def test_cross_lane_synthesis_signals(self) -> None:
        records = load_context_document_records(
            RAW_FIXTURE,
            symbol_mappings=build_symbol_mapping_registry("BOXL"),
        )
        llm_labels = load_llm_extraction_fixture(LLM_FIXTURE)
        synthesis_fixture = load_synthesis_fixture(SYNTHESIS_FIXTURE)
        _, events, _ = build_fixture_extraction_pipeline(
            records,
            prediction_cutoff=CUTOFF_NS,
            llm_labels=llm_labels,
        )
        summaries, _ = build_fixture_synthesis_pipeline(
            events,
            records,
            llm_labels,
            synthesis_fixture,
            prediction_cutoff=CUTOFF_NS,
            entity_id="BOXL",
        )
        evidence = build_synthesis_cross_lane_evidence(
            summaries,
            symbol="BOXL",
            prediction_cutoff=CUTOFF_NS,
        )
        signals = {row["signal"] for row in evidence}
        self.assertIn(EvidenceSignal.SYNTHESIS_THEME_ELEVATED.value, signals)
        for row in evidence:
            self.assertTrue((row.get("metadata") or {}).get("research_only"))

        adversarial_summaries, _ = build_fixture_synthesis_pipeline(
            events,
            records,
            llm_labels,
            synthesis_fixture,
            prediction_cutoff=CUTOFF_NS,
            entity_id="BOXL",
            include_adversarial_clusters=True,
        )
        adversarial_evidence = build_synthesis_cross_lane_evidence(
            adversarial_summaries,
            symbol="BOXL",
            prediction_cutoff=CUTOFF_NS,
        )
        adversarial_signals = {row["signal"] for row in adversarial_evidence}
        self.assertIn(EvidenceSignal.SYNTHESIS_CONTRADICTION_DETECTED.value, adversarial_signals)

    def test_unsupported_symbol_has_no_synthesis(self) -> None:
        payload = build_workspace_market_context_payload(
            "NVDA",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=CUTOFF_NS,
        )
        self.assertFalse(payload.get("multi_document_synthesis_available", False))


class TestMC16GateValidation(unittest.TestCase):
    def test_unified_gate_validation_passes_on_admitted_fixtures(self) -> None:
        report = run_mc16_gate_validation()
        self.assertEqual(
            report.get("artifact_type"),
            "MC16_MULTI_DOCUMENT_SYNTHESIS_GATE_VALIDATION_REPORT",
        )
        self.assertEqual(report.get("scope"), "fixture")
        self.assertTrue(report.get("research_only"))
        self.assertEqual(report.get("aggregate_status"), "PASS")
        for row in report.get("gate_summary", []):
            self.assertEqual(row.get("gate_status"), "PASS")

    def test_matches_golden_gate_summary(self) -> None:
        report = run_mc16_gate_validation()
        self.assertEqual(report.get("synthesis_count"), 3)


if __name__ == "__main__":
    unittest.main()
