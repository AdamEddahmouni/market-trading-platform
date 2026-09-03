"""Task 7 — decision candidate synthesis tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns
from market_platform_foundation.research.decision_research.synthesis import (
    DecisionCandidate,
    build_decision_candidate,
)

# A cutoff inside the admitted fixture era (after every lane's available_time).
CUTOFF = iso_to_epoch_ns("2026-07-21T00:00:00Z")


def _lane(
    *,
    lane: str,
    direction: str,
    quality: str = "PASS",
    relevance: str = "HIGH",
    summary: str = "lane summary",
    freshness_label: str = "REPLAY",
    available_time: str | None = "2026-07-20T13:00:00Z",
    evidence_type: str = "LANE_EVIDENCE",
) -> dict:
    return {
        "instrument": "BIYA",
        "lane": lane,
        "evidence_type": evidence_type,
        "quality": quality,
        "relevance": relevance,
        "direction": direction,
        "confidence": "MEDIUM",
        "probability": None,
        "expected_value": None,
        "summary": summary,
        "freshness_label": freshness_label,
        "as_of": available_time,
        "available_time": available_time,
        "reason_codes": [],
        "sources": [f"src-{lane.lower()}"],
        "details": {},
        "explain_ref": f"explain:{lane.lower()}",
        "missing_evidence": [],
        "research_only": True,
    }


class AlignedCandidateTests(unittest.TestCase):
    def test_aligned_long(self) -> None:
        candidate = build_decision_candidate(
            "BIYA", CUTOFF, [_lane(lane="SHORT_SQUEEZE", direction="POSITIVE")]
        )
        self.assertEqual(candidate.evidence_mix, "ALIGNED")
        self.assertEqual(candidate.direction_hypothesis, "LONG")
        self.assertEqual(len(candidate.supporting_evidence), 1)
        self.assertEqual(
            candidate.supporting_evidence[0]["lane"], "SHORT_SQUEEZE"
        )
        self.assertEqual(candidate.supporting_evidence[0]["direction"], "POSITIVE")
        self.assertEqual(candidate.contradicting_evidence, [])

    def test_aligned_short(self) -> None:
        candidate = build_decision_candidate(
            "BIYA",
            CUTOFF,
            [
                _lane(lane="ORDER_FLOW", direction="NEGATIVE"),
                _lane(lane="CATALYST", direction="NEGATIVE"),
            ],
        )
        self.assertEqual(candidate.evidence_mix, "ALIGNED")
        self.assertEqual(candidate.direction_hypothesis, "SHORT")

    def test_neutral_aligned(self) -> None:
        candidate = build_decision_candidate(
            "BIYA", CUTOFF, [_lane(lane="MARKET_CONTEXT", direction="NEUTRAL")]
        )
        self.assertEqual(candidate.evidence_mix, "ALIGNED")
        self.assertEqual(candidate.direction_hypothesis, "NEUTRAL")

    def test_multiple_same_direction(self) -> None:
        candidate = build_decision_candidate(
            "BIYA",
            CUTOFF,
            [
                _lane(lane="SHORT_SQUEEZE", direction="POSITIVE"),
                _lane(lane="CATALYST", direction="POSITIVE"),
                _lane(lane="ORDER_FLOW", direction="POSITIVE"),
            ],
        )
        self.assertEqual(candidate.direction_hypothesis, "LONG")
        self.assertEqual(len(candidate.supporting_evidence), 3)


class ContradictionCandidateTests(unittest.TestCase):
    def test_bull_vs_bear_lanes_are_mixed(self) -> None:
        candidate = build_decision_candidate(
            "BIYA",
            CUTOFF,
            [
                _lane(lane="SHORT_SQUEEZE", direction="POSITIVE"),
                _lane(lane="ORDER_FLOW", direction="NEGATIVE"),
            ],
        )
        self.assertEqual(candidate.evidence_mix, "MIXED")
        self.assertEqual(candidate.direction_hypothesis, "NO_HYPOTHESIS")
        # the two sides are documented separately, never averaged
        self.assertEqual(len(candidate.supporting_evidence), 1)
        self.assertEqual(len(candidate.contradicting_evidence), 1)

    def test_lane_mixed_direction_is_contradiction(self) -> None:
        candidate = build_decision_candidate(
            "BIYA", CUTOFF, [_lane(lane="CATALYST", direction="MIXED")]
        )
        self.assertEqual(candidate.evidence_mix, "MIXED")
        self.assertEqual(candidate.direction_hypothesis, "NO_HYPOTHESIS")


class InsufficientCandidateTests(unittest.TestCase):
    def test_no_usable_lanes_is_insufficient(self) -> None:
        candidate = build_decision_candidate(
            "BIYA",
            CUTOFF,
            [
                _lane(lane="ORDER_FLOW", direction="UNKNOWN"),
                _lane(lane="OPTIONS", direction=None, quality="NOT_CONFIGURED"),
            ],
        )
        self.assertEqual(candidate.evidence_mix, "INSUFFICIENT")
        self.assertEqual(candidate.direction_hypothesis, "NO_HYPOTHESIS")
        self.assertEqual(candidate.supporting_evidence, [])

    def test_unavailable_lane_never_coerced(self) -> None:
        candidate = build_decision_candidate(
            "BIYA", CUTOFF, [_lane(lane="CATALYST", direction="POSITIVE", quality="UNAVAILABLE")]
        )
        # quality UNAVAILABLE -> not directional, no coercion to LONG
        self.assertEqual(candidate.evidence_mix, "INSUFFICIENT")
        self.assertEqual(candidate.direction_hypothesis, "NO_HYPOTHESIS")

    def test_pit_violating_lane_excluded_from_direction(self) -> None:
        candidate = build_decision_candidate(
            "BIYA",
            CUTOFF,
            [
                _lane(
                    lane="SHORT_SQUEEZE",
                    direction="POSITIVE",
                    available_time="2026-07-21T02:00:00Z",
                )
            ],
        )
        # available_time after cutoff -> not directional (PIT guard)
        self.assertEqual(candidate.evidence_mix, "INSUFFICIENT")
        self.assertEqual(candidate.direction_hypothesis, "NO_HYPOTHESIS")


class NoCompositeScoreTests(unittest.TestCase):
    def test_no_score_field_anywhere(self) -> None:
        candidate = build_decision_candidate(
            "BIYA",
            CUTOFF,
            [
                _lane(lane="SHORT_SQUEEZE", direction="POSITIVE"),
                _lane(lane="CATALYST", direction="POSITIVE"),
            ],
        )
        d = candidate.to_dict()
        self.assertNotIn("score", d)
        for piece in d["supporting_evidence"] + d["contradicting_evidence"]:
            self.assertNotIn("score", piece)
        self.assertNotIn("score", candidate.thesis.lower())

    def test_candidate_id_deterministic(self) -> None:
        a = build_decision_candidate(
            "BIYA", CUTOFF, [_lane(lane="SHORT_SQUEEZE", direction="POSITIVE")]
        )
        b = build_decision_candidate(
            "BIYA", CUTOFF, [_lane(lane="SHORT_SQUEEZE", direction="POSITIVE")]
        )
        self.assertEqual(a.candidate_id, b.candidate_id)
        self.assertTrue(a.candidate_id.startswith("CAND-"))

    def test_research_only_authority(self) -> None:
        candidate = build_decision_candidate(
            "BIYA", CUTOFF, [_lane(lane="SHORT_SQUEEZE", direction="POSITIVE")]
        )
        self.assertTrue(candidate.research_only)
        self.assertEqual(candidate.execution_authority, "NONE")


class Mc16EnrichmentTests(unittest.TestCase):
    MC16 = {
        "synthesis_id": "SYN-1",
        "cluster_id": "B1",
        "entity_id": "BIYA",
        "thematic_summary": "bullish on BIYA",
        "theme_agreement_score": 1.0,
        "contradiction_detected": False,
        "consolidated_channels": ["BIYA"],
        "synthesis_confidence": "MEDIUM",
        "model_version": "mc16-v1",
        "quality_flags": ["MULTI_DOCUMENT_SYNTHESIS_EXPERIMENTAL", "NO_UNIVERSAL_NEWS_SCORE"],
        "available_time": "2026-07-20T13:00:00Z",
        "publication_state": "GOLDEN",
        "scoring_method": "theme_agreement",
    }

    def test_flags_and_scores_propagate_without_overriding_direction(self) -> None:
        candidate = build_decision_candidate(
            "BIYA",
            CUTOFF,
            [_lane(lane="MARKET_CONTEXT", direction="POSITIVE")],
            mc16_summaries=[self.MC16],
        )
        self.assertEqual(candidate.direction_hypothesis, "LONG")
        piece = candidate.supporting_evidence[0]
        self.assertEqual(set(piece["quality_flags"]), {"MULTI_DOCUMENT_SYNTHESIS_EXPERIMENTAL", "NO_UNIVERSAL_NEWS_SCORE"})
        self.assertEqual(piece["synthesis_confidence"], "MEDIUM")
        self.assertEqual(piece["theme_agreement_score"], 1.0)

    def test_mc16_contradiction_enriches_to_mixed_without_erasing_lane_direction(self) -> None:
        mc16 = dict(self.MC16, contradiction_detected=True)
        candidate = build_decision_candidate(
            "BIYA",
            CUTOFF,
            [_lane(lane="MARKET_CONTEXT", direction="POSITIVE")],
            mc16_summaries=[mc16],
        )
        # MC16 contradiction enriches the mix -> MIXED/NO_HYPOTHESIS ...
        self.assertEqual(candidate.evidence_mix, "MIXED")
        self.assertEqual(candidate.direction_hypothesis, "NO_HYPOTHESIS")
        # ... but never rewrites the lane's own direction/scores.
        pieces = candidate.supporting_evidence + candidate.contradicting_evidence
        self.assertEqual(len(pieces), 1)
        self.assertEqual(pieces[0]["direction"], "POSITIVE")
        self.assertEqual(pieces[0]["theme_agreement_score"], 1.0)


if __name__ == "__main__":
    unittest.main()
