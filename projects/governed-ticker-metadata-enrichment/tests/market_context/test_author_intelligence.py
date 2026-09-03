"""Tests for MC14 social / author intelligence."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.market_context import (  # noqa: E402
    AccuracyEvidence,
    AuthorEvidence,
    AuthorIdentity,
    ContextQualityFlag,
    InfluenceEvidence,
    PublicationState,
    accuracy_evidence_to_dict,
    author_evidence_to_dict,
    author_id_from_handle,
    influence_evidence_to_dict,
)
from market_platform_foundation.cross_lane.evidence import EvidenceSignal  # noqa: E402
from market_platform_foundation.market_context.author_intelligence import (  # noqa: E402
    build_author_intelligence_cross_lane_evidence,
    build_fixture_author_intelligence_pipeline,
    compute_accuracy_score,
    compute_influence_score,
    load_social_author_fixture,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.providers.projections import (  # noqa: E402
    build_workspace_market_context_payload,
)

SOCIAL_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_social_author_slice.json"
EXPECTED_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_social_author_expected.json"
CUTOFF = "2026-07-23T00:00:00.000000000Z"
CUTOFF_NS = iso_to_epoch_ns(CUTOFF)
EARLY_CUTOFF_NS = iso_to_epoch_ns("2026-07-21T15:30:00.000000000Z")


class TestMC14AuthorIntelligence(unittest.TestCase):
    def test_golden_workspace_author_block(self) -> None:
        expected = json.loads(EXPECTED_FIXTURE.read_text(encoding="utf-8"))
        payload = build_workspace_market_context_payload(
            "BOXL",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=CUTOFF_NS,
        )
        self.assertTrue(payload["author_intelligence_available"])
        self.assertEqual(
            payload["author_intelligence_count"],
            expected["author_intelligence_count"],
        )
        self.assertEqual(
            payload["author_intelligence_summaries"],
            expected["author_intelligence_summaries"],
        )

    def test_influence_not_equal_to_accuracy(self) -> None:
        rows = load_social_author_fixture(SOCIAL_FIXTURE)
        _, summaries, _ = build_fixture_author_intelligence_pipeline(
            rows,
            prediction_cutoff=CUTOFF_NS,
            entity_id="BOXL",
        )
        viral = next(item for item in summaries if item.handle == "boxl_hype")
        specialist = next(item for item in summaries if item.handle == "boxl_specialist")
        self.assertEqual(viral.influence_score, 1.0)
        self.assertEqual(viral.accuracy_score, 0.0)
        self.assertLess(specialist.influence_score or 0.0, 0.02)
        self.assertEqual(specialist.accuracy_score, 1.0)
        self.assertIn(ContextQualityFlag.INFLUENCE_NOT_ACCURACY.value, viral.quality_flags)

    def test_pending_outcome_fail_closed(self) -> None:
        rows = load_social_author_fixture(SOCIAL_FIXTURE)
        _, summaries, _ = build_fixture_author_intelligence_pipeline(
            rows,
            prediction_cutoff=CUTOFF_NS,
            entity_id="BOXL",
        )
        pending = next(item for item in summaries if item.handle == "boxl_pending")
        self.assertIsNotNone(pending.influence_score)
        self.assertIsNone(pending.accuracy_score)
        self.assertIn(
            ContextQualityFlag.AUTHOR_ACCURACY_UNVALIDATED.value,
            pending.quality_flags,
        )

    def test_pit_excludes_future_social_posts(self) -> None:
        rows = load_social_author_fixture(SOCIAL_FIXTURE)
        _, summaries, _ = build_fixture_author_intelligence_pipeline(
            rows,
            prediction_cutoff=EARLY_CUTOFF_NS,
            entity_id="BOXL",
        )
        handles = {item.handle for item in summaries}
        self.assertEqual(handles, {"boxl_hype"})
        viral = summaries[0]
        self.assertIsNone(viral.accuracy_score)

    def test_missing_social_metrics_fail_closed(self) -> None:
        score, missing = compute_influence_score(None, None)
        self.assertIsNone(score)
        self.assertTrue(missing)

    def test_accuracy_requires_ex_post_outcome(self) -> None:
        score, unvalidated = compute_accuracy_score(
            1.0,
            outcome_available_time="2026-07-21T15:00:00.000000000Z",
            post_available_time="2026-07-21T15:01:00.000000000Z",
            prediction_cutoff=CUTOFF_NS,
        )
        self.assertIsNone(score)
        self.assertTrue(unvalidated)

    def test_cross_lane_influence_and_accuracy_signals(self) -> None:
        rows = load_social_author_fixture(SOCIAL_FIXTURE)
        _, summaries, _ = build_fixture_author_intelligence_pipeline(
            rows,
            prediction_cutoff=CUTOFF_NS,
            entity_id="BOXL",
        )
        evidence = build_author_intelligence_cross_lane_evidence(
            summaries,
            symbol="BOXL",
            prediction_cutoff=CUTOFF_NS,
        )
        signals = {row["signal"] for row in evidence}
        self.assertIn(EvidenceSignal.SOCIAL_INFLUENCE_ELEVATED.value, signals)
        self.assertIn(EvidenceSignal.AUTHOR_ACCURACY_LOW.value, signals)
        for row in evidence:
            self.assertTrue((row.get("metadata") or {}).get("research_only"))

    def test_unsupported_symbol_has_no_author_intelligence(self) -> None:
        payload = build_workspace_market_context_payload(
            "NVDA",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=CUTOFF_NS,
        )
        self.assertFalse(payload.get("author_intelligence_available", False))

    def test_contract_round_trip_author_evidence(self) -> None:
        author_id = author_id_from_handle("boxl_hype")
        identity = AuthorIdentity(
            author_id=author_id,
            handle="boxl_hype",
            platform="fixture_social",
            available_time="2026-07-21T15:01:00.000000000Z",
            event_time="2026-07-21T15:00:00.000000000Z",
        )
        influence = InfluenceEvidence(
            author_id=author_id,
            entity_id="BOXL",
            influence_score=1.0,
            follower_count=250000,
            repost_count=8000,
            event_time=identity.event_time,
            available_time=identity.available_time,
            publication_state=PublicationState.PUBLISHED,
        )
        accuracy = AccuracyEvidence(
            author_id=author_id,
            entity_id="BOXL",
            accuracy_score=0.0,
            labeled_correct=0.0,
            outcome_available_time="2026-07-22T16:00:00.000000000Z",
            event_time=identity.event_time,
            available_time=identity.available_time,
            publication_state=PublicationState.PUBLISHED,
        )
        evidence = AuthorEvidence(
            author=identity,
            influence=influence,
            accuracy=accuracy,
            document_id="mc-social-viral-wrong",
            event_time=identity.event_time,
            available_time=identity.available_time,
            publication_state=PublicationState.PUBLISHED,
        )
        payload = author_evidence_to_dict(evidence)
        self.assertEqual(payload["influence"]["influence_score"], 1.0)
        self.assertEqual(payload["accuracy"]["accuracy_score"], 0.0)
        self.assertEqual(influence_evidence_to_dict(influence)["influence_score"], 1.0)
        self.assertEqual(accuracy_evidence_to_dict(accuracy)["accuracy_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
