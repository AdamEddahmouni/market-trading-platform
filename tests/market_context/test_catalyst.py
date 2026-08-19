"""Tests for MC8 catalyst fusion and short-thesis invalidation."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.market_context import ContextQualityFlag  # noqa: E402
from market_platform_foundation.market_context.catalyst import (  # noqa: E402
    CATALYST_STRENGTH_THRESHOLD,
    THESIS_INVALIDATION_THRESHOLD,
    build_catalyst_cross_lane_evidence,
    build_fixture_catalyst_pipeline,
    compute_catalyst_strength,
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
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.providers.projections import (  # noqa: E402
    build_workspace_catalyst_payload,
    build_workspace_market_context_payload,
)

RAW_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_raw_documents_slice.json"
LLM_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_llm_extraction_slice.json"
STRUCTURED_FIXTURE = (
    ROOT / "tests" / "fixtures" / "market_context" / "boxl_structured_metrics_slice.json"
)
EXPECTATIONS_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_expectations_slice.json"
EXPECTED_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_catalyst_expected.json"
CUTOFF = "2026-07-23T00:00:00.000000000Z"
CUTOFF_NS = iso_to_epoch_ns(CUTOFF)
EARLY_CUTOFF_NS = iso_to_epoch_ns("2026-07-16T00:00:00.000000000Z")


def _catalyst_pipeline(*, cutoff_ns: int = CUTOFF_NS):
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
    return build_fixture_catalyst_pipeline(
        impact_summaries,
        prediction_cutoff=cutoff_ns,
        entity_id="BOXL",
    )


class TestMC8CatalystPipeline(unittest.TestCase):
    def test_golden_workspace_catalyst_block(self) -> None:
        expected = json.loads(EXPECTED_FIXTURE.read_text(encoding="utf-8"))
        payload = build_workspace_market_context_payload(
            "BOXL",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=CUTOFF_NS,
        )
        self.assertTrue(payload["catalyst_available"])
        self.assertEqual(payload["catalyst_count"], expected["catalyst_count"])
        self.assertEqual(payload["catalyst_summaries"], expected["catalyst_summaries"])
        thesis = payload.get("thesis_invalidation_evidence") or {}
        self.assertEqual(
            thesis.get("invalidation_strength"),
            expected["thesis_invalidation_strength"],
        )

    def test_fail_closed_when_components_missing(self) -> None:
        strength, flags = compute_catalyst_strength(
            novelty_score=None,
            materiality_score=0.8,
            credibility_score=0.7,
            surprise_score=0.5,
        )
        self.assertIsNone(strength)
        self.assertIn(ContextQualityFlag.CATALYST_COMPONENTS_INCOMPLETE.value, flags)

    def test_pit_excludes_future_clusters(self) -> None:
        _, summaries, thesis, _ = _catalyst_pipeline(cutoff_ns=EARLY_CUTOFF_NS)
        self.assertLess(len(summaries), 5)
        self.assertIsNotNone(thesis)
        self.assertLess(thesis.invalidation_strength or 0.0, 0.75)

    def test_cross_lane_catalyst_and_thesis_signals(self) -> None:
        _, summaries, thesis, _ = _catalyst_pipeline()
        evidence = build_catalyst_cross_lane_evidence(
            summaries,
            thesis,
            symbol="BOXL",
            prediction_cutoff=CUTOFF_NS,
        )
        signals = {row["signal"] for row in evidence}
        self.assertIn("CATALYST_STRENGTH", signals)
        self.assertIn("SHORT_THESIS_INVALIDATION", signals)
        catalyst_rows = [row for row in evidence if row["signal"] == "CATALYST_STRENGTH"]
        self.assertTrue(
            all(
                (row.get("metadata") or {}).get("catalyst_strength", 0)
                >= CATALYST_STRENGTH_THRESHOLD
                for row in catalyst_rows
            )
        )
        thesis_rows = [row for row in evidence if row["signal"] == "SHORT_THESIS_INVALIDATION"]
        self.assertTrue(
            all(
                (row.get("metadata") or {}).get("invalidation_strength", 0)
                >= THESIS_INVALIDATION_THRESHOLD
                for row in thesis_rows
            )
        )

    def test_catalyst_payload_uses_mc8_pipeline_for_boxl(self) -> None:
        payload = build_workspace_catalyst_payload(
            "BOXL",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=CUTOFF_NS,
        )
        self.assertTrue(payload["available"])
        self.assertEqual(payload.get("source"), "mc8_fixture_pipeline")
        self.assertEqual(payload.get("provider_id"), "market_context.catalyst")
        self.assertTrue(payload.get("catalysts"))
        self.assertIsNotNone(payload.get("thesis_invalidation_evidence"))


if __name__ == "__main__":
    unittest.main()
