"""Tests for MC16 → MC7/MC8 synthesis enrichment."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.market_context import (  # noqa: E402
    ContextQualityFlag,
    ModelVersionRef,
)
from market_platform_foundation.market_context.impact_components import (  # noqa: E402
    ImpactComponentSummary,
)
from market_platform_foundation.market_context.synthesis import (  # noqa: E402
    MultiDocumentSynthesisSummary,
)
from market_platform_foundation.market_context.synthesis_enrichment import (  # noqa: E402
    apply_synthesis_enrichment_to_catalyst,
    apply_synthesis_enrichment_to_impact,
    index_synthesis_by_cluster_id,
    run_mc16_mc78_enrichment_gate_validation,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.providers.projections import (  # noqa: E402
    build_workspace_market_context_payload,
)

EXPECTED_FIXTURE = (
    ROOT / "tests" / "fixtures" / "market_context" / "boxl_synthesis_enrichment_expected.json"
)
CATALYST_EXPECTED = ROOT / "tests" / "fixtures" / "market_context" / "boxl_catalyst_expected.json"
IMPACT_EXPECTED = (
    ROOT / "tests" / "fixtures" / "market_context" / "boxl_impact_components_expected.json"
)
CUTOFF_NS = iso_to_epoch_ns("2026-07-23T00:00:00.000000000Z")
EARLY_CUTOFF_NS = iso_to_epoch_ns("2026-07-16T00:00:00.000000000Z")

_MODEL_VERSION = ModelVersionRef(
    model_id="fixture-llm-synthesis-v1",
    model_version="1.0.0",
    prompt_version="mc16_synthesis_prompt_v1",
    schema_version="mc16_synthesis_schema_v1",
    feature_version="market_context_synthesis_v1",
)


class TestSynthesisEnrichment(unittest.TestCase):
    def test_golden_workspace_enrichment_blocks(self) -> None:
        expected = json.loads(EXPECTED_FIXTURE.read_text(encoding="utf-8"))
        payload = build_workspace_market_context_payload(
            "BOXL",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=CUTOFF_NS,
        )
        impact_by_event = {
            item["event_id"]: item
            for item in payload.get("impact_component_summaries") or []
        }
        catalyst_by_event = {
            item["event_id"]: item for item in payload.get("catalyst_summaries") or []
        }
        for row in expected["enriched_events"]:
            event_id = row["event_id"]
            self.assertEqual(
                impact_by_event[event_id]["synthesis_enrichment"],
                row["synthesis_enrichment"],
            )
            self.assertEqual(
                catalyst_by_event[event_id]["synthesis_enrichment"],
                row["synthesis_enrichment"],
            )

    def test_golden_catalyst_and_impact_fixtures(self) -> None:
        catalyst_expected = json.loads(CATALYST_EXPECTED.read_text(encoding="utf-8"))
        impact_expected = json.loads(IMPACT_EXPECTED.read_text(encoding="utf-8"))
        payload = build_workspace_market_context_payload(
            "BOXL",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=CUTOFF_NS,
        )
        self.assertEqual(payload["catalyst_summaries"], catalyst_expected["catalyst_summaries"])
        impact_by_event = {
            item["event_id"]: item
            for item in payload.get("impact_component_summaries") or []
        }
        for expected_row in impact_expected["impact_component_summaries"]:
            actual = impact_by_event[expected_row["event_id"]]
            self.assertEqual(actual["quality_flags"], expected_row["quality_flags"])
            if "synthesis_enrichment" in expected_row:
                self.assertEqual(
                    actual.get("synthesis_enrichment"),
                    expected_row["synthesis_enrichment"],
                )

    def test_score_invariance(self) -> None:
        expected = json.loads(EXPECTED_FIXTURE.read_text(encoding="utf-8"))
        payload = build_workspace_market_context_payload(
            "BOXL",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=CUTOFF_NS,
        )
        impact_by_event = {
            item["event_id"]: item
            for item in payload.get("impact_component_summaries") or []
        }
        catalyst_by_event = {
            item["event_id"]: item for item in payload.get("catalyst_summaries") or []
        }
        for row in expected["score_invariance_impact"]:
            actual = impact_by_event[row["event_id"]]
            for key in ("novelty_score", "materiality_score", "source_credibility", "surprise_score"):
                self.assertEqual(actual[key], row[key])
        for row in expected["score_invariance_catalyst"]:
            actual = catalyst_by_event[row["event_id"]]
            for key in (
                "catalyst_strength",
                "novelty_score",
                "materiality_score",
                "credibility_score",
                "gate_ok",
            ):
                self.assertEqual(actual[key], row[key])

    def test_pit_excludes_future_synthesis(self) -> None:
        payload = build_workspace_market_context_payload(
            "BOXL",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=EARLY_CUTOFF_NS,
        )
        enriched = [
            item
            for item in payload.get("impact_component_summaries") or []
            if item.get("synthesis_enrichment") is not None
        ]
        self.assertEqual(len(enriched), 1)
        self.assertEqual(enriched[0]["event_id"], "df2e6ba5-46ab-5bb1-a867-745fe0a75c91")

    def test_contradiction_fail_closed(self) -> None:
        impact = ImpactComponentSummary(
            event_id="df2e6ba5-46ab-5bb1-a867-745fe0a75c91",
            canonical_event_type="earnings_beat",
            entity_id="BOXL",
            novelty_score=0.5,
            duplicate_probability=0.5,
            incremental_information_score=0.5,
            materiality_score=0.9,
            materiality_basis="event_type:earnings_beat",
            source_credibility=0.65,
            corroboration_state="UNVERIFIED",
            official_source_found=False,
            surprise_score=None,
            event_time="2026-07-15T14:30:00.000000000Z",
            available_time="2026-07-15T14:45:00.000000000Z",
            publication_state="PUBLISHED",
            quality_flags=("EVENT_DUPLICATE",),
            impact_available=True,
        )
        synthesis = MultiDocumentSynthesisSummary(
            synthesis_id="test-synthesis-id",
            cluster_id=impact.event_id,
            entity_id="BOXL",
            thematic_summary="conflict",
            theme_agreement_score=0.4,
            contradiction_detected=True,
            consolidated_channels=(),
            supporting_document_ids=(),
            contradicting_document_ids=("mc-doc-earnings-1",),
            revision_superseded_ids=(),
            synthesis_confidence=0.42,
            model_version=_MODEL_VERSION,
            quality_flags=("SYNTHESIS_CONTRADICTION_PRESENT",),
            available_time="2026-07-15T14:45:00.000000000Z",
            publication_state="PUBLISHED",
        )
        enriched = apply_synthesis_enrichment_to_impact(
            [impact],
            index_synthesis_by_cluster_id([synthesis]),
            CUTOFF_NS,
        )[0]
        self.assertIn(
            ContextQualityFlag.CATALYST_SYNTHESIS_CONTRADICTION.value,
            enriched.quality_flags,
        )
        self.assertNotIn(
            ContextQualityFlag.SYNTHESIS_THEME_CORROBORATED.value,
            enriched.quality_flags,
        )

    def test_no_universal_news_score(self) -> None:
        payload = build_workspace_market_context_payload(
            "BOXL",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=CUTOFF_NS,
        )
        forbidden = ("universal_news_score", "context_score", "fused_news_score")
        self.assertFalse(any(key in payload for key in forbidden))

    def test_enrichment_gate_validation_passes(self) -> None:
        report = run_mc16_mc78_enrichment_gate_validation()
        self.assertEqual(report["aggregate_status"], "PASS")
        self.assertEqual(report["enriched_impact_count"], 3)


if __name__ == "__main__":
    unittest.main()
