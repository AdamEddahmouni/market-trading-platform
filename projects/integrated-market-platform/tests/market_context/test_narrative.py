"""Tests for MC10 narrative intelligence evidence."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.market_context import ContextQualityFlag  # noqa: E402
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
from market_platform_foundation.market_context.narrative import (  # noqa: E402
    NARRATIVE_ACCELERATION_THRESHOLD,
    NARRATIVE_VELOCITY_THRESHOLD,
    build_fixture_narrative_pipeline,
    build_narrative_cross_lane_evidence,
)
from market_platform_foundation.market_context.sentiment import (  # noqa: E402
    build_fixture_sentiment_pipeline,
    load_finbert_fixture_labels,
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
FINBERT_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_finbert_labels_slice.json"
EXPECTED_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_narrative_expected.json"
CUTOFF = "2026-07-23T00:00:00.000000000Z"
CUTOFF_NS = iso_to_epoch_ns(CUTOFF)
EARLY_CUTOFF_NS = iso_to_epoch_ns("2026-07-16T00:00:00.000000000Z")


def _narrative_pipeline(*, cutoff_ns: int = CUTOFF_NS):
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
        prediction_cutoff=cutoff_ns,
        llm_labels=llm_labels,
        structured_metrics=structured_metrics,
    )
    finbert_labels = load_finbert_fixture_labels(FINBERT_FIXTURE) if FINBERT_FIXTURE.is_file() else {}
    _, _, event_summaries = build_fixture_sentiment_pipeline(
        records,
        prediction_cutoff=cutoff_ns,
        finbert_labels=finbert_labels,
    )
    expectation_rows = (
        load_expectations_fixture(EXPECTATIONS_FIXTURE)
        if EXPECTATIONS_FIXTURE.is_file()
        else []
    )
    _, _, surprise_summaries, _ = build_fixture_surprise_pipeline(
        expectation_rows,
        prediction_cutoff=cutoff_ns,
    )
    _, _, _, impact_summaries = build_fixture_impact_pipeline(
        records,
        enriched_events,
        prediction_cutoff=cutoff_ns,
        surprise_summaries=surprise_summaries,
    )
    _, catalyst_summaries, _, _ = build_fixture_catalyst_pipeline(
        impact_summaries,
        prediction_cutoff=cutoff_ns,
        entity_id="BOXL",
    )
    return build_fixture_narrative_pipeline(
        catalyst_summaries,
        event_summaries,
        prediction_cutoff=cutoff_ns,
        entity_id="BOXL",
    )


class TestMC10NarrativePipeline(unittest.TestCase):
    def test_golden_workspace_narrative_block(self) -> None:
        expected = json.loads(EXPECTED_FIXTURE.read_text(encoding="utf-8"))
        payload = build_workspace_market_context_payload(
            "BOXL",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=CUTOFF_NS,
        )
        self.assertTrue(payload["narrative_available"])
        self.assertEqual(payload["narrative_count"], expected["narrative_count"])
        self.assertEqual(payload["narrative_summaries"], expected["narrative_summaries"])

    def test_thesis_graph_supporting_and_opposing_ids(self) -> None:
        _, summaries, _ = _narrative_pipeline()
        bullish = [item for item in summaries if item.thesis_lean == "BULLISH"]
        bearish = [item for item in summaries if item.thesis_lean == "BEARISH"]
        self.assertEqual(len(bullish), 3)
        self.assertEqual(len(bearish), 2)
        for item in bullish:
            self.assertTrue(item.supporting_event_ids)
        self.assertEqual(bullish[0].opposing_event_ids, ())
        for item in bearish:
            self.assertTrue(item.opposing_event_ids)
        self.assertTrue(summaries[-1].opposing_event_ids)

    def test_first_theme_snapshot_velocity_fail_closed(self) -> None:
        _, summaries, _ = _narrative_pipeline()
        self.assertIsNone(summaries[0].velocity)
        self.assertIn(
            ContextQualityFlag.NARRATIVE_HISTORY_INSUFFICIENT.value,
            summaries[0].quality_flags,
        )

    def test_pit_excludes_future_narratives(self) -> None:
        _, summaries, _ = _narrative_pipeline(cutoff_ns=EARLY_CUTOFF_NS)
        self.assertLess(len(summaries), 5)

    def test_cross_lane_narrative_shift(self) -> None:
        _, summaries, _ = _narrative_pipeline()
        evidence = build_narrative_cross_lane_evidence(
            summaries,
            symbol="BOXL",
            prediction_cutoff=CUTOFF_NS,
        )
        signals = {row["signal"] for row in evidence}
        self.assertIn("NARRATIVE_SHIFT", signals)
        for row in evidence:
            metadata = row.get("metadata") or {}
            velocity = metadata.get("velocity")
            acceleration = metadata.get("acceleration")
            self.assertTrue(
                (velocity is not None and abs(velocity) >= NARRATIVE_VELOCITY_THRESHOLD)
                or (
                    acceleration is not None
                    and abs(acceleration) >= NARRATIVE_ACCELERATION_THRESHOLD
                )
            )

    def test_prevalence_bounded(self) -> None:
        _, summaries, _ = _narrative_pipeline()
        for item in summaries:
            self.assertIsNotNone(item.prevalence)
            assert item.prevalence is not None
            self.assertGreater(item.prevalence, 0.0)
            self.assertLessEqual(item.prevalence, 1.0)


if __name__ == "__main__":
    unittest.main()
