"""Scope validation for research-artifact attach."""

from __future__ import annotations

import unittest

from market_platform_foundation.canonical import load_json_strict
from market_platform_foundation.intelligence.contracts import (
    ContractReference,
    IntelligenceScope,
    OpportunitySide,
    OpportunityV1,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.ingest.research_artifact_scope import (
    research_artifact_instrument_ids,
    validate_research_artifact_opportunity_scope,
)
from pathlib import Path

_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "research"
    / "edge_stats_golden_artifact.json"
)


class ResearchArtifactScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.artifact = load_json_strict(_FIXTURE)
        self.opportunity = OpportunityV1(
            opportunity_id="opp-scope-1",
            schema_version="1",
            scope=IntelligenceScope(instrument_ids=("BIYA",), context_id="regular"),
            created_at_ns=1,
            quality=QualitySummary(state=QualityState.GOOD),
            side=OpportunitySide.LONG,
            expected_return=0.1,
            expected_net_edge=0.05,
            reason_summary="scope test",
            lineage_refs=(ContractReference(kind="forecast", id="fc-1"),),
        )

    def test_extracts_instrument_from_edge_stats_query(self) -> None:
        self.assertEqual(research_artifact_instrument_ids(self.artifact), ("BIYA",))

    def test_validate_accepts_matching_scope(self) -> None:
        validate_research_artifact_opportunity_scope(self.opportunity, self.artifact)

    def test_validate_rejects_mismatch(self) -> None:
        other = OpportunityV1(
            opportunity_id="opp-scope-2",
            schema_version="1",
            scope=IntelligenceScope(instrument_ids=("NVDA",), context_id="regular"),
            created_at_ns=1,
            quality=QualitySummary(state=QualityState.GOOD),
            side=OpportunitySide.LONG,
            expected_return=0.1,
            expected_net_edge=0.05,
            reason_summary="scope test",
            lineage_refs=(ContractReference(kind="forecast", id="fc-2"),),
        )
        with self.assertRaisesRegex(ValueError, "SCOPE_MISMATCH"):
            validate_research_artifact_opportunity_scope(other, self.artifact)


if __name__ == "__main__":
    unittest.main()
