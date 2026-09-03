"""Tests for SHARED P4 opportunity evidence signals."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cross_lane.evidence import (  # noqa: E402
    EvidenceProvenanceClass,
    EvidenceSignal,
    LaneId,
    NormalizedLaneEvidence,
    validate_evidence_dag,
)


class OpportunityEvidenceTests(unittest.TestCase):
    def test_new_signals_exist(self) -> None:
        self.assertEqual(
            EvidenceSignal.CROSS_LANE_OPPORTUNITY_FUSED.value,
            "CROSS_LANE_OPPORTUNITY_FUSED",
        )
        self.assertEqual(
            EvidenceSignal.OPPORTUNITY_NO_ACTIONABLE_EDGE.value,
            "OPPORTUNITY_NO_ACTIONABLE_EDGE",
        )

    def test_cross_lane_output_dag_clean(self) -> None:
        items = [
            NormalizedLaneEvidence(
                lane=LaneId.OPTIONS,
                signal=EvidenceSignal.STRATEGY_OPPORTUNITY_RANKED,
                strength="MODERATE",
                available=True,
                source_ref="options:strategy",
                detail="lane ranked",
                provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
            ),
            NormalizedLaneEvidence(
                lane=LaneId.OPTIONS,
                signal=EvidenceSignal.CROSS_LANE_OPPORTUNITY_FUSED,
                strength="HIGH",
                available=True,
                source_ref="platform:opportunity_fusion",
                detail="fused opportunity",
                provenance_class=EvidenceProvenanceClass.CROSS_LANE_MODEL_OUTPUT,
            ),
        ]
        self.assertEqual(validate_evidence_dag(items), [])


if __name__ == "__main__":
    unittest.main()
