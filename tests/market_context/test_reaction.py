"""Tests for MC12 market reaction evidence."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.market_context import (  # noqa: E402
    ContextQualityFlag,
    ReactionConfirmationState,
)
from market_platform_foundation.market_context.catalyst import (  # noqa: E402
    build_fixture_catalyst_pipeline,
)
from market_platform_foundation.market_context.entity_resolution import (  # noqa: E402
    build_symbol_mapping_registry,
    load_context_document_records,
)
from market_platform_foundation.market_context.extraction import (  # noqa: E402
    build_fixture_extraction_pipeline,
    load_llm_extraction_fixture,
    load_structured_metrics_fixture,
)
from market_platform_foundation.market_context.expectations import (  # noqa: E402
    build_fixture_surprise_pipeline,
    load_expectations_fixture,
)
from market_platform_foundation.market_context.impact_components import (  # noqa: E402
    build_fixture_impact_pipeline,
)
from market_platform_foundation.market_context.reaction import (  # noqa: E402
    build_fixture_reaction_pipeline,
    build_reaction_cross_lane_evidence,
    load_reaction_fixture,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.providers.projections import (  # noqa: E402
    build_workspace_market_context_payload,
)

RAW_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_raw_documents_slice.json"
LLM_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_llm_extraction_slice.json"
STRUCTURED_FIXTURE = (
    ROOT / "tests" / "fixtures" / "market_context" / "boxl_structured_metrics_slice.json"
)
EXPECTATIONS_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_expectations_slice.json"
REACTION_SLICE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_reaction_slice.json"
EXPECTED_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_reaction_expected.json"
CUTOFF = "2026-07-23T00:00:00.000000000Z"
CUTOFF_NS = iso_to_epoch_ns(CUTOFF)


def _reaction_pipeline():
    records = load_context_document_records(
        RAW_FIXTURE,
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
        prediction_cutoff=CUTOFF_NS,
        llm_labels=llm_labels,
        structured_metrics=structured_metrics,
    )
    expectation_rows = (
        load_expectations_fixture(EXPECTATIONS_FIXTURE)
        if EXPECTATIONS_FIXTURE.is_file()
        else []
    )
    _, _, surprise_summaries, _ = build_fixture_surprise_pipeline(
        expectation_rows,
        prediction_cutoff=CUTOFF_NS,
    )
    _, _, _, impact_summaries = build_fixture_impact_pipeline(
        records,
        enriched_events,
        prediction_cutoff=CUTOFF_NS,
        surprise_summaries=surprise_summaries,
    )
    _, catalyst_summaries, _, _ = build_fixture_catalyst_pipeline(
        impact_summaries,
        prediction_cutoff=CUTOFF_NS,
        entity_id="BOXL",
    )
    reaction_fixture = load_reaction_fixture(REACTION_SLICE)
    return build_fixture_reaction_pipeline(
        catalyst_summaries,
        surprise_summaries,
        reaction_fixture,
        prediction_cutoff=CUTOFF_NS,
        entity_id="BOXL",
    )


class TestMC12ReactionPipeline(unittest.TestCase):
    def test_golden_workspace_reaction_block(self) -> None:
        expected = json.loads(EXPECTED_FIXTURE.read_text(encoding="utf-8"))
        payload = build_workspace_market_context_payload(
            "BOXL",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=CUTOFF_NS,
        )
        self.assertTrue(payload["reaction_available"])
        self.assertEqual(payload["reaction_count"], expected["reaction_count"])
        self.assertEqual(payload["reaction_summaries"], expected["reaction_summaries"])
        self.assertEqual(payload["reaction_contradictions"], expected["reaction_contradictions"])

    def test_offering_risk_contradicted(self) -> None:
        _, summaries, _ = _reaction_pipeline()
        offering = next(
            item for item in summaries if item.canonical_event_type == "offering_risk"
        )
        self.assertTrue(offering.reaction_mismatch)
        self.assertEqual(
            offering.confirmation_state,
            ReactionConfirmationState.CONTRADICTED.value,
        )

    def test_missing_fixture_fail_closed(self) -> None:
        _, summaries, _ = _reaction_pipeline()
        macro = next(
            item for item in summaries if item.canonical_event_type == "macro_headwind"
        )
        self.assertEqual(
            macro.confirmation_state,
            ReactionConfirmationState.INSUFFICIENT_DATA.value,
        )
        self.assertIn(
            ContextQualityFlag.MARKET_REACTION_DATA_MISSING.value,
            macro.quality_flags,
        )

    def test_cross_lane_reaction_signals(self) -> None:
        _, summaries, _ = _reaction_pipeline()
        evidence = build_reaction_cross_lane_evidence(
            summaries,
            symbol="BOXL",
            prediction_cutoff=CUTOFF_NS,
        )
        signals = {row["signal"] for row in evidence}
        self.assertIn("REACTION_CONFIRMED", signals)
        self.assertIn("REACTION_CONTRADICTED", signals)

    def test_priced_in_deferred(self) -> None:
        _, summaries, _ = _reaction_pipeline()
        for item in summaries:
            self.assertIsNone(item.priced_in_probability)
            self.assertIsNone(item.remaining_information_edge)

    def test_workspace_contradictions_exposed(self) -> None:
        payload = build_workspace_market_context_payload(
            "BOXL",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=CUTOFF_NS,
        )
        contradictions = payload.get("reaction_contradictions") or []
        self.assertEqual(len(contradictions), 1)
        self.assertTrue(contradictions[0]["reaction_mismatch"])


if __name__ == "__main__":
    unittest.main()
