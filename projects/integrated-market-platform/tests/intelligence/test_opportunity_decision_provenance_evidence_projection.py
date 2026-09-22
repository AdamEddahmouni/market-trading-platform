"""Evidence projection carries decision provenance with operator-honest classification."""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.contracts import (  # noqa: E402
    ContractReference,
    IntelligenceScope,
    OpportunitySide,
    OpportunityV1,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.opportunity.decision_provenance import (  # noqa: E402
    DECISION_PROVENANCE_METADATA_KEY,
    DECISION_PROVENANCE_SCHEMA_VERSION,
    ActionabilityAudit,
    ActionabilityStatus,
    EvidenceHonesty,
    FreshnessWindowRef,
    LineageStatus,
    OpportunityDecisionProvenanceV1,
    OpportunityThesisStatement,
    OriginKind,
    attach_decision_provenance,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository  # noqa: E402
from market_platform_foundation.ui_api.opportunity_projections import (  # noqa: E402
    build_opportunity_evidence_payload,
)
from market_platform_foundation.ui_api.store import ReplayStore  # noqa: E402

from tests.ui1.test_ui_api import COLLECTION_ROOT  # noqa: E402

DECISION_NS = 1_700_000_000_000_000_000


def _minted_opportunity() -> OpportunityV1:
    # Mirror admitted-equity projection fixtures: no undeclared strategy_family claim
    # (unknown family metadata would deny admission and drop the row from ranking).
    return OpportunityV1(
        opportunity_id="opp-prov-ui-1",
        schema_version="1",
        scope=IntelligenceScope(instrument_ids=("US:AAPL",), context_id="regular"),
        created_at_ns=DECISION_NS,
        quality=QualitySummary(state=QualityState.GOOD),
        side=OpportunitySide.LONG,
        expected_return=0.1,
        expected_net_edge=0.05,
        reason_summary="Momentum continuation after unusual volume",
        lineage_refs=(ContractReference(kind="forecast", id="fc-1"),),
        metadata={
            "family_admission_status": "ADMITTED",
            "asset_class": "US_EQUITY",
        },
    )


def _provenance(opportunity_id: str) -> OpportunityDecisionProvenanceV1:
    return OpportunityDecisionProvenanceV1(
        schema_version=DECISION_PROVENANCE_SCHEMA_VERSION,
        origin_kind=OriginKind.STRATEGY_MATCH,
        origin_refs=(ContractReference(kind="strategy_match", id="match-prov-ui-1"),),
        actionability=ActionabilityAudit(
            status=ActionabilityStatus.ACTIONABLE,
            still_actionable_reasons=("LIFECYCLE_ELIGIBLE", "FRESHNESS_FRESH"),
            lineage_status=LineageStatus.PRESENT,
        ),
        opportunity_id=opportunity_id,
        strategy_id="momentum-5m",
        strategy_family="momentum",
        thesis=OpportunityThesisStatement(
            statement="Momentum continuation after unusual volume",
            honesty=EvidenceHonesty.DERIVED,
            mechanism="trend_continuation",
            invalidation_criteria=("TREND_BREAK", "SPREAD_TOO_WIDE"),
        ),
        freshness_window=FreshnessWindowRef(
            policy_name="strategy_match_default",
            status="FRESH",
            information_cutoff_ns=DECISION_NS,
            valid_until_ns=DECISION_NS + 300_000_000_000,
        ),
        ai_assisted_notes=("Model paraphrase of volume spike — not authority",),
        lineage_status=LineageStatus.PRESENT,
    )


class OpportunityDecisionProvenanceEvidenceProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ReplayStore(collection_root=COLLECTION_ROOT)
        self.store.load()
        self.repo = InMemoryIntelligenceRepository()
        self.store.strategy_repository = self.repo

    def test_evidence_payload_projects_provenance_fields_with_honest_classification(self) -> None:
        opportunity = attach_decision_provenance(_minted_opportunity(), _provenance("opp-prov-ui-1"))
        self.assertEqual(opportunity.metadata[DECISION_PROVENANCE_METADATA_KEY]["thesis"]["honesty"], "DERIVED")
        self.assertNotEqual(
            opportunity.metadata[DECISION_PROVENANCE_METADATA_KEY]["thesis"]["honesty"],
            "OBSERVED",
        )
        self.repo.put_opportunity(opportunity)

        evidence = build_opportunity_evidence_payload(self.store, opportunity.opportunity_id)
        body = evidence[DECISION_PROVENANCE_METADATA_KEY]
        self.assertIsInstance(body, dict)
        self.assertEqual(body["origin_kind"], "STRATEGY_MATCH")
        self.assertEqual(body["strategy_id"], "momentum-5m")
        thesis = body["thesis"]
        self.assertIsInstance(thesis, dict)
        self.assertIn("Momentum continuation", thesis["statement"])
        self.assertEqual(thesis["honesty"], "DERIVED")
        self.assertNotEqual(thesis["honesty"], "OBSERVED")
        self.assertEqual(set(thesis["invalidation_criteria"]), {"SPREAD_TOO_WIDE", "TREND_BREAK"})
        self.assertEqual(set(evidence["invalidation_criteria"]), {"SPREAD_TOO_WIDE", "TREND_BREAK"})
        freshness = body["freshness_window"]
        self.assertIsInstance(freshness, dict)
        self.assertIn("valid_until_ns", freshness)
        actionability = evidence["actionability_audit"]
        self.assertEqual(actionability["status"], body["actionability"]["status"])
        self.assertTrue(
            actionability.get("still_actionable_reasons")
            or actionability.get("no_longer_actionable_reasons")
        )
        self.assertEqual(
            body["ai_assisted_notes"],
            ["Model paraphrase of volume spike — not authority"],
        )
        self.assertNotIn("ai_assisted", str(thesis).lower())
        self.assertNotIn("rank_score", evidence)
        self.assertNotIn("universal_score", evidence)

        # Thesis honesty stays non-observed even if a bad payload tried OBSERVED —
        # the contract rejects OBSERVED at construction time.
        with self.assertRaises(ValueError):
            replace(
                _provenance("opp-prov-ui-1"),
                thesis=OpportunityThesisStatement(
                    statement="Must not be observed",
                    honesty=EvidenceHonesty.OBSERVED,
                ),
            )


if __name__ == "__main__":
    unittest.main()
