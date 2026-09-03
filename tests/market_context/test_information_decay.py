"""Tests for MC13 information decay / priced-in enrichment."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.market_context import (  # noqa: E402
    ContextQualityFlag,
    InformationDecayClass,
    MarketReactionEvidence,
    PublicationState,
    ReactionConfirmationState,
    market_reaction_evidence_to_dict,
)
from market_platform_foundation.market_context.attention import (  # noqa: E402
    build_fixture_attention_pipeline,
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
from market_platform_foundation.market_context.information_decay import (  # noqa: E402
    compute_decay_class,
    compute_priced_in_probability,
    compute_remaining_information_edge,
    enrich_reaction_summaries,
    load_decay_fixture,
)
from market_platform_foundation.market_context.reaction import (  # noqa: E402
    build_fixture_reaction_pipeline,
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
DECAY_SLICE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_decay_slice.json"
DECAY_EXPECTED = ROOT / "tests" / "fixtures" / "market_context" / "boxl_decay_expected.json"
REACTION_EXPECTED = ROOT / "tests" / "fixtures" / "market_context" / "boxl_reaction_expected.json"
CUTOFF = "2026-07-23T00:00:00.000000000Z"
CUTOFF_NS = iso_to_epoch_ns(CUTOFF)


def _full_pipeline():
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
    _, attention_summaries, _ = build_fixture_attention_pipeline(
        enriched_events,
        catalyst_summaries,
        prediction_cutoff=CUTOFF_NS,
        entity_id="BOXL",
    )
    reaction_fixture = load_reaction_fixture(REACTION_SLICE)
    _, reaction_summaries, _ = build_fixture_reaction_pipeline(
        catalyst_summaries,
        surprise_summaries,
        reaction_fixture,
        prediction_cutoff=CUTOFF_NS,
        entity_id="BOXL",
    )
    decay_fixture = load_decay_fixture(DECAY_SLICE)
    return (
        catalyst_summaries,
        attention_summaries,
        surprise_summaries,
        reaction_summaries,
        decay_fixture,
    )


class TestMC13InformationDecay(unittest.TestCase):
    def test_golden_workspace_decay_block(self) -> None:
        expected = json.loads(DECAY_EXPECTED.read_text(encoding="utf-8"))
        payload = build_workspace_market_context_payload(
            "BOXL",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=CUTOFF_NS,
        )
        self.assertTrue(payload["information_decay_available"])
        self.assertEqual(
            payload["information_decay_count"],
            expected["information_decay_count"],
        )
        self.assertEqual(
            payload["information_decay_summaries"],
            expected["information_decay_summaries"],
        )

    def test_golden_workspace_reaction_enriched(self) -> None:
        expected = json.loads(REACTION_EXPECTED.read_text(encoding="utf-8"))
        payload = build_workspace_market_context_payload(
            "BOXL",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=CUTOFF_NS,
        )
        self.assertEqual(payload["reaction_summaries"], expected["reaction_summaries"])
        self.assertEqual(
            payload["reaction_contradictions"],
            expected["reaction_contradictions"],
        )

    def test_mc12_leaves_mc13_fields_none_before_enrichment(self) -> None:
        _, _, _, reaction_summaries, _ = _full_pipeline()
        for item in reaction_summaries:
            self.assertIsNone(item.priced_in_probability)
            self.assertIsNone(item.remaining_information_edge)
            self.assertIsNone(item.information_decay_class)

    def test_event_type_decay_class_mapping(self) -> None:
        decay_class, defaulted = compute_decay_class("earnings_beat")
        self.assertEqual(decay_class, InformationDecayClass.HOURS)
        self.assertFalse(defaulted)

        decay_class, defaulted = compute_decay_class("offering_risk")
        self.assertEqual(decay_class, InformationDecayClass.MINUTES)
        self.assertFalse(defaulted)

        decay_class, defaulted = compute_decay_class("macro_headwind")
        self.assertEqual(decay_class, InformationDecayClass.DAYS)
        self.assertTrue(defaulted)

    def test_offering_risk_high_priced_in(self) -> None:
        catalyst, attention, surprise, reaction_summaries, decay_fixture = _full_pipeline()
        enriched = enrich_reaction_summaries(
            reaction_summaries,
            catalyst_by_event={item.event_id: item for item in catalyst},
            attention_by_event={item.event_id: item for item in attention},
            surprise_by_event={
                item.event_id: item for item in surprise if item.event_id is not None
            },
            decay_fixture=decay_fixture,
            prediction_cutoff=CUTOFF_NS,
        )
        offering = next(
            item for item in enriched if item.canonical_event_type == "offering_risk"
        )
        self.assertGreater(offering.priced_in_probability or 0.0, 0.5)
        self.assertEqual(offering.information_decay_class, InformationDecayClass.MINUTES.value)
        self.assertTrue(offering.reaction_mismatch)

    def test_partial_input_fail_closed(self) -> None:
        priced_in, partial = compute_priced_in_probability(
            pre_event_abnormal_return=None,
            diffusion_score=None,
            surprise_magnitude=None,
        )
        self.assertIsNone(priced_in)
        self.assertTrue(partial)

        remaining, partial = compute_remaining_information_edge(
            expected_impact=0.8,
            abnormal_return=None,
            priced_in_probability=0.4,
            diffusion_score=0.2,
        )
        self.assertIsNone(remaining)
        self.assertTrue(partial)

    def test_pit_cutoff_excludes_future_events(self) -> None:
        catalyst, attention, surprise, reaction_summaries, decay_fixture = _full_pipeline()
        early_cutoff = iso_to_epoch_ns("2026-07-15T14:00:00.000000000Z")
        enriched = enrich_reaction_summaries(
            reaction_summaries,
            catalyst_by_event={item.event_id: item for item in catalyst},
            attention_by_event={item.event_id: item for item in attention},
            surprise_by_event={
                item.event_id: item for item in surprise if item.event_id is not None
            },
            decay_fixture=decay_fixture,
            prediction_cutoff=early_cutoff,
        )
        for item in enriched:
            if iso_to_epoch_ns(item.available_time) > early_cutoff:
                self.assertIsNone(item.information_decay_class)
                self.assertIsNone(item.priced_in_probability)

    def test_contract_round_trip_information_decay_class(self) -> None:
        evidence = MarketReactionEvidence(
            entity_id="BOXL",
            event_id="evt-1",
            semantic_direction="BULLISH",
            predicted_economic_direction="BULLISH",
            observed_market_direction="BULLISH",
            reaction_mismatch=False,
            confirmation_state=ReactionConfirmationState.CONFIRMED,
            abnormal_return=0.02,
            volume_multiple=1.5,
            priced_in_probability=0.4,
            remaining_information_edge=0.08,
            information_decay_class=InformationDecayClass.HOURS,
            horizon="1D",
            event_time="2026-07-15T14:30:00.000000000Z",
            available_time="2026-07-15T14:45:00.000000000Z",
            publication_state=PublicationState.PUBLISHED,
            quality_flags=(
                ContextQualityFlag.INFORMATION_DECAY_EXPERIMENTAL.value,
            ),
        )
        payload = market_reaction_evidence_to_dict(evidence)
        self.assertEqual(payload["information_decay_class"], "HOURS")
        self.assertEqual(payload["priced_in_probability"], 0.4)
        self.assertIn("INFORMATION_DECAY_EXPERIMENTAL", payload["quality_flags"])


if __name__ == "__main__":
    unittest.main()
