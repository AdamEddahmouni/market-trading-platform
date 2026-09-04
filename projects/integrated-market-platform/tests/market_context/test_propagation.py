"""Tests for MC15 cross-entity propagation."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.market_context import ContextQualityFlag  # noqa: E402
from market_platform_foundation.cross_lane.evidence import EvidenceSignal  # noqa: E402
from market_platform_foundation.market_context.propagation import (  # noqa: E402
    EntityLink,
    EntityLinkType,
    DonorSignalRow,
    build_fixture_propagation_pipeline,
    build_propagation_cross_lane_evidence,
    load_entity_link_fixture,
    propagate_donor_signal,
    run_mc15_gate_validation,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.providers.projections import (  # noqa: E402
    build_workspace_market_context_payload,
)

PROPAGATION_FIXTURE = (
    ROOT / "tests" / "fixtures" / "market_context" / "boxl_nvda_propagation_slice.json"
)
EXPECTED_FIXTURE = (
    ROOT / "tests" / "fixtures" / "market_context" / "boxl_nvda_propagation_expected.json"
)
CUTOFF = "2026-07-23T00:00:00.000000000Z"
CUTOFF_NS = iso_to_epoch_ns(CUTOFF)
EARLY_CUTOFF_NS = iso_to_epoch_ns("2026-07-22T12:00:00.000000000Z")


class TestMC15CrossEntityPropagation(unittest.TestCase):
    def test_golden_workspace_propagation_block(self) -> None:
        expected = json.loads(EXPECTED_FIXTURE.read_text(encoding="utf-8"))
        payload = build_workspace_market_context_payload(
            "BOXL",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=CUTOFF_NS,
        )
        self.assertTrue(payload["cross_entity_propagation_available"])
        self.assertEqual(
            payload["cross_entity_propagation_count"],
            expected["cross_entity_propagation_count"],
        )
        self.assertEqual(
            payload["entity_link_count"],
            expected["entity_link_count"],
        )
        self.assertEqual(
            payload["cross_entity_propagation_summaries"],
            expected["propagation_summaries"],
        )

    def test_separate_propagated_fields_no_fused_score(self) -> None:
        payload = build_workspace_market_context_payload(
            "BOXL",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=CUTOFF_NS,
        )
        summaries = payload.get("cross_entity_propagation_summaries") or []
        self.assertTrue(summaries)
        for row in summaries:
            self.assertIn("propagated_catalyst_strength", row)
            self.assertIn("propagated_attention_level", row)
            self.assertIn("propagated_information_value", row)
            self.assertIn("propagated_diffusion_score", row)
            self.assertNotIn("news_score", row)
            self.assertNotIn("universal_score", row)
            self.assertIn(
                ContextQualityFlag.NO_UNIVERSAL_NEWS_SCORE.value,
                row.get("quality_flags", []),
            )

    def test_ambiguous_link_fail_closed(self) -> None:
        links, signals, target = load_entity_link_fixture(PROPAGATION_FIXTURE)
        summaries, _, _ = build_fixture_propagation_pipeline(
            links,
            signals,
            prediction_cutoff=CUTOFF_NS,
            entity_id=target,
        )
        link_ids = {item.link_id for item in summaries}
        self.assertNotIn("mc15-link-nvda-boxl-ambiguous", link_ids)

    def test_pit_excludes_future_donor_signals(self) -> None:
        links, signals, target = load_entity_link_fixture(PROPAGATION_FIXTURE)
        summaries, _, _ = build_fixture_propagation_pipeline(
            links,
            signals,
            prediction_cutoff=EARLY_CUTOFF_NS,
            entity_id=target,
        )
        event_ids = {item.source_event_id for item in summaries}
        self.assertNotIn("nvda-future-signal", event_ids)
        self.assertNotIn("nvda-guidance-cut", event_ids)

    def test_stale_link_excluded(self) -> None:
        links, signals, target = load_entity_link_fixture(PROPAGATION_FIXTURE)
        summaries, admitted, _ = build_fixture_propagation_pipeline(
            links,
            signals,
            prediction_cutoff=CUTOFF_NS,
            entity_id=target,
        )
        admitted_ids = {item.link_id for item in admitted}
        self.assertNotIn("mc15-link-nvda-boxl-stale", admitted_ids)
        self.assertTrue(all(item.link_id != "mc15-link-nvda-boxl-stale" for item in summaries))

    def test_direct_links_only_to_target_symbol(self) -> None:
        links, signals, target = load_entity_link_fixture(PROPAGATION_FIXTURE)
        summaries, _, _ = build_fixture_propagation_pipeline(
            links,
            signals,
            prediction_cutoff=CUTOFF_NS,
            entity_id=target,
        )
        self.assertTrue(all(item.target_entity_id == "BOXL" for item in summaries))
        self.assertTrue(all(item.source_entity_id == "NVDA" for item in summaries))

    def test_cross_lane_propagation_signals(self) -> None:
        links, signals, target = load_entity_link_fixture(PROPAGATION_FIXTURE)
        summaries, _, _ = build_fixture_propagation_pipeline(
            links,
            signals,
            prediction_cutoff=CUTOFF_NS,
            entity_id=target,
        )
        evidence = build_propagation_cross_lane_evidence(
            summaries,
            symbol=target,
            prediction_cutoff=CUTOFF_NS,
        )
        signals = {row["signal"] for row in evidence}
        self.assertIn(EvidenceSignal.PROPAGATED_CATALYST_ELEVATED.value, signals)
        self.assertIn(EvidenceSignal.PROPAGATED_ATTENTION_ELEVATED.value, signals)
        for row in evidence:
            self.assertTrue((row.get("metadata") or {}).get("research_only"))

    def test_unsupported_symbol_has_no_propagation(self) -> None:
        payload = build_workspace_market_context_payload(
            "NVDA",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=CUTOFF_NS,
        )
        self.assertFalse(payload.get("cross_entity_propagation_available", False))

    def test_missing_link_weight_fail_closed(self) -> None:
        link = EntityLink(
            link_id="missing-weight",
            source_entity_id="NVDA",
            target_entity_id="BOXL",
            link_type=EntityLinkType.SECTOR_PEER.value,
            link_weight=None,
            event_time="2026-07-01T00:00:00.000000000Z",
            available_time="2026-07-01T00:00:00.000000000Z",
        )
        signal = DonorSignalRow(
            entity_id="NVDA",
            event_id="nvda-earnings-beat",
            canonical_event_type="earnings_beat",
            catalyst_strength=0.85,
            attention_level=0.72,
            information_value=0.68,
            diffusion_score=0.55,
            event_time="2026-07-20T09:30:00.000000000Z",
            available_time="2026-07-20T10:00:00.000000000Z",
        )
        summary = propagate_donor_signal(
            link,
            signal,
            prediction_cutoff=CUTOFF_NS,
            target_entity_id="BOXL",
        )
        self.assertIsNone(summary)


class TestMC15GateValidation(unittest.TestCase):
    def test_unified_gate_validation_passes_on_admitted_fixtures(self) -> None:
        report = run_mc15_gate_validation()
        self.assertEqual(
            report.get("artifact_type"),
            "MC15_CROSS_ENTITY_PROPAGATION_GATE_VALIDATION_REPORT",
        )
        self.assertEqual(report.get("scope"), "fixture")
        self.assertTrue(report.get("research_only"))
        self.assertEqual(report.get("aggregate_status"), "PASS")
        for row in report.get("gate_summary", []):
            self.assertEqual(row.get("gate_status"), "PASS")

    def test_matches_golden_gate_summary(self) -> None:
        report = run_mc15_gate_validation()
        self.assertEqual(report.get("propagation_count"), 4)
        self.assertEqual(report.get("entity_link_count"), 3)
        self.assertEqual(report.get("ambiguous_link_count"), 1)


if __name__ == "__main__":
    unittest.main()
