"""Focused tests for opportunity decision provenance / thesis / invalidation."""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.discovery.models import DiscoveryCandidate  # noqa: E402
from market_platform_foundation.intelligence.contracts import (  # noqa: E402
    ContractReference,
    IntelligenceScope,
    OpportunitySide,
    OpportunityV1,
    QualityState,
    QualitySummary,
    StrategyConditionResult,
    StrategyMatch,
    StrategyMatchDisposition,
)
from market_platform_foundation.intelligence.opportunity.decision_provenance import (  # noqa: E402
    DECISION_PROVENANCE_METADATA_KEY,
    DECISION_PROVENANCE_SCHEMA_VERSION,
    ActionabilityStatus,
    EvidenceHonesty,
    LineageStatus,
    OriginKind,
    attach_decision_provenance,
    audit_opportunity_state_change,
    build_decision_provenance_from_strategy_match,
    decision_provenance_from_dict,
    decision_provenance_to_dict,
    evaluate_actionability,
    extract_decision_provenance,
    route_discovery_candidate_to_oe,
)
from market_platform_foundation.intelligence.opportunity.types import (  # noqa: E402
    AssessmentAction,
    AssessmentReasonCode,
    EconomicValueStatus,
    OpportunityAssessmentV1,
)
from market_platform_foundation.intelligence.evaluation.types import ProbabilityView  # noqa: E402
from market_platform_foundation.intelligence.quality.models import AvailabilityState  # noqa: E402


DECISION_NS = 1_700_000_000_000_000_000
SCOPE = IntelligenceScope(instrument_ids=("NVDA",), context_id="regular")
QUALITY = QualitySummary(state=QualityState.GOOD)


def _match() -> StrategyMatch:
    return StrategyMatch(
        match_id="match-prov-1",
        strategy_id="momentum-5m",
        strategy_identity_hash="STRATEGY-HASH-1",
        schema_version="1",
        scope=SCOPE,
        decision_time_ns=DECISION_NS,
        disposition=StrategyMatchDisposition.MATCHED,
        capability_state=AvailabilityState.AVAILABLE,
        quality=QUALITY,
        source_snapshot_ref=ContractReference(kind="snapshot", id="snap-1"),
        source_evidence_refs=(ContractReference(kind="evidence", id="ev-obs-1"),),
        source_signal_refs=(ContractReference(kind="signal", id="sig-1"),),
        condition_results=(
            StrategyConditionResult(
                condition_id="trend",
                matched=True,
                observed_value=0.8,
                expected_value=0.5,
                reason="trend threshold",
            ),
        ),
        context={"mode": "PAPER", "account_id": "paper-1", "strategy_family": "momentum"},
        source_forecast_refs=(ContractReference(kind="forecast", id="fc-1"),),
        valid_from_ns=DECISION_NS - 60_000_000_000,
        expires_at_ns=DECISION_NS + 300_000_000_000,
        lineage_refs=(ContractReference(kind="run", id="run-1"),),
    )


def _opportunity() -> OpportunityV1:
    return OpportunityV1(
        opportunity_id="opp-prov-1",
        schema_version="1",
        scope=SCOPE,
        created_at_ns=DECISION_NS,
        quality=QUALITY,
        side=OpportunitySide.LONG,
        valid_until_ns=DECISION_NS + 300_000_000_000,
        source_forecast_refs=(ContractReference(kind="forecast", id="fc-1"),),
        source_hypothesis_refs=(ContractReference(kind="hypothesis", id="hyp-1"),),
        reason_summary="Momentum continuation after trend threshold",
        lineage_refs=(ContractReference(kind="strategy_match", id="match-prov-1"),),
        metadata={
            "strategy_family": "momentum",
            "strategy_version": "1.0.0",
            "mechanism": "trend_continuation",
        },
    )


def _assessment(*, action: AssessmentAction = AssessmentAction.EMIT) -> OpportunityAssessmentV1:
    return OpportunityAssessmentV1(
        assessment_id="assess-1",
        schema_version="1",
        forecast_id="fc-1",
        champion_assignment_id="champ-1",
        opportunity_policy_id="pol-1",
        opportunity_decision_time_ns=DECISION_NS,
        forecast_decision_time_ns=DECISION_NS - 1_000_000_000,
        probability_view=ProbabilityView.OPERATIONAL,
        probability=0.7,
        reference_probability=0.5,
        probability_edge=0.2,
        side="LONG",
        quality_action=None,
        uncertainty_entropy=0.2,
        spread_bps=10.0,
        economic_value_status=EconomicValueStatus.AVAILABLE,
        assessment_action=action,
        reason_codes=(AssessmentReasonCode.OPPORTUNITY_EMITTED,),
        opportunity_id="opp-prov-1",
        expires_at_ns=DECISION_NS + 300_000_000_000,
    )


class OpportunityDecisionProvenanceTests(unittest.TestCase):
    def test_strategy_match_build_preserves_origin_thesis_invalidation_and_evidence(self) -> None:
        provenance = build_decision_provenance_from_strategy_match(
            match=_match(),
            opportunity=_opportunity(),
            assessment=_assessment(),
            invalidation_criteria=("TREND_BREAK", "SPREAD_TOO_WIDE"),
            as_of_ns=DECISION_NS + 1_000_000_000,
        )

        self.assertEqual(provenance.schema_version, DECISION_PROVENANCE_SCHEMA_VERSION)
        self.assertEqual(provenance.origin_kind, OriginKind.STRATEGY_MATCH)
        self.assertEqual(provenance.opportunity_id, "opp-prov-1")
        self.assertEqual(provenance.strategy_id, "momentum-5m")
        self.assertEqual(provenance.strategy_family, "momentum")
        self.assertEqual(provenance.strategy_version, "1.0.0")
        self.assertEqual(provenance.lineage_status, LineageStatus.PRESENT)
        self.assertIsNotNone(provenance.thesis)
        assert provenance.thesis is not None
        self.assertIn("Momentum continuation", provenance.thesis.statement)
        self.assertEqual(provenance.thesis.mechanism, "trend_continuation")
        self.assertEqual(provenance.thesis.honesty, EvidenceHonesty.DERIVED)
        self.assertEqual(provenance.thesis.hypothesis_id, "hyp-1")
        self.assertEqual(provenance.thesis.invalidation_criteria, ("SPREAD_TOO_WIDE", "TREND_BREAK"))
        evidence_ids = {binding.evidence_id for binding in provenance.evidence_bindings}
        self.assertIn("ev-obs-1", evidence_ids)
        self.assertIn("sig-1", evidence_ids)
        self.assertIn("fc-1", evidence_ids)
        self.assertIn("hyp-1", evidence_ids)
        obs = next(b for b in provenance.evidence_bindings if b.evidence_id == "ev-obs-1")
        self.assertEqual(obs.honesty, EvidenceHonesty.OBSERVED)
        derived = next(b for b in provenance.evidence_bindings if b.evidence_id == "fc-1")
        self.assertEqual(derived.honesty, EvidenceHonesty.DERIVED)
        self.assertIsNotNone(provenance.freshness_window)
        assert provenance.freshness_window is not None
        self.assertEqual(provenance.freshness_window.valid_until_ns, DECISION_NS + 300_000_000_000)
        self.assertEqual(provenance.actionability.status, ActionabilityStatus.ACTIONABLE)
        self.assertTrue(provenance.actionability.still_actionable_reasons)
        self.assertEqual(provenance.ai_assisted_notes, ())

    def test_missing_lineage_distinct_from_mismatch(self) -> None:
        opportunity = replace(_opportunity(), lineage_refs=())
        missing = build_decision_provenance_from_strategy_match(
            match=_match(),
            opportunity=opportunity,
            assessment=_assessment(),
            as_of_ns=DECISION_NS,
        )
        self.assertEqual(missing.lineage_status, LineageStatus.MISSING)

        mismatched = replace(
            _opportunity(),
            lineage_refs=(ContractReference(kind="strategy_match", id="other-match"),),
        )
        mismatch = build_decision_provenance_from_strategy_match(
            match=_match(),
            opportunity=mismatched,
            assessment=_assessment(),
            as_of_ns=DECISION_NS,
        )
        self.assertEqual(mismatch.lineage_status, LineageStatus.MISMATCH)

    def test_discover_route_is_investigate_only_and_does_not_mint_opportunity(self) -> None:
        candidate = DiscoveryCandidate(
            instrument_id="BIYA",
            provider_symbol="BIYA",
            screen_id="finviz-unusual-volume",
            screen_version="1",
            discovered_at="2026-09-21T12:00:00Z",
            available_time_ns=DECISION_NS,
            matched_reasons=["volume_spike"],
            metrics={"rel_volume": 4.2},
            inspection_priority=1,
            quality="GOOD",
            provenance={"provider": "finviz", "capture_id": "cap-1"},
            rank=1,
            transition="NEW_ENTRY",
        )
        routed = route_discovery_candidate_to_oe(candidate)
        self.assertEqual(routed.origin_kind, OriginKind.DISCOVER_SCREEN)
        self.assertIsNone(routed.opportunity_id)
        self.assertEqual(routed.actionability.status, ActionabilityStatus.NOT_ACTIONABLE)
        self.assertIn("DISCOVER_INVESTIGATE_ONLY", routed.actionability.no_longer_actionable_reasons)
        self.assertTrue(any(ref.kind == "discovery_screen" for ref in routed.origin_refs))
        self.assertTrue(any(b.evidence_id == "cap-1" for b in routed.evidence_bindings))
        self.assertIsNone(extract_decision_provenance({"metadata": {}}))

    def test_actionability_explains_still_and_no_longer(self) -> None:
        provenance = build_decision_provenance_from_strategy_match(
            match=_match(),
            opportunity=_opportunity(),
            assessment=_assessment(),
            invalidation_criteria=("TREND_BREAK",),
            as_of_ns=DECISION_NS,
        )
        still = evaluate_actionability(
            provenance,
            as_of_ns=DECISION_NS + 1_000_000_000,
            lifecycle_state="ELIGIBLE",
            freshness_status="FRESH",
            assessment_action=AssessmentAction.EMIT,
        )
        self.assertEqual(still.status, ActionabilityStatus.ACTIONABLE)
        self.assertTrue(still.still_actionable_reasons)
        self.assertEqual(still.no_longer_actionable_reasons, ())

        stale = evaluate_actionability(
            provenance,
            as_of_ns=DECISION_NS + 1_000_000_000,
            lifecycle_state="ELIGIBLE",
            freshness_status="STALE",
            assessment_action=AssessmentAction.EMIT,
        )
        self.assertEqual(stale.status, ActionabilityStatus.NOT_ACTIONABLE)
        self.assertIn("FRESHNESS_STALE", stale.no_longer_actionable_reasons)

        expired = evaluate_actionability(
            provenance,
            as_of_ns=DECISION_NS + 400_000_000_000,
            lifecycle_state="EXPIRED",
            freshness_status="FRESH",
            assessment_action=AssessmentAction.EMIT,
        )
        self.assertEqual(expired.status, ActionabilityStatus.NOT_ACTIONABLE)
        self.assertTrue(
            {"VALIDITY_WINDOW_EXPIRED", "LIFECYCLE_EXPIRED"} & set(expired.no_longer_actionable_reasons)
        )

    def test_state_change_audit_is_deterministic_and_keeps_ai_non_authoritative(self) -> None:
        prior = build_decision_provenance_from_strategy_match(
            match=_match(),
            opportunity=_opportunity(),
            assessment=_assessment(),
            as_of_ns=DECISION_NS,
        )
        next_actionability = evaluate_actionability(
            prior,
            as_of_ns=DECISION_NS + 10_000_000_000,
            lifecycle_state="INELIGIBLE",
            freshness_status="STALE",
            assessment_action=AssessmentAction.SUPPRESS,
            evidence_changed_ids=("ev-obs-1",),
        )
        audited = audit_opportunity_state_change(
            prior,
            to_lifecycle_state="INELIGIBLE",
            actionability=next_actionability,
            changed_at_ns=DECISION_NS + 10_000_000_000,
            ai_assisted_notes=("model suggested suppress",),
        )
        self.assertEqual(audited.actionability.status, ActionabilityStatus.NOT_ACTIONABLE)
        self.assertEqual(len(audited.state_changes), 1)
        change = audited.state_changes[0]
        self.assertEqual(change.to_state, "INELIGIBLE")
        self.assertEqual(change.authority_class, "DETERMINISTIC")
        self.assertIn("ev-obs-1", change.evidence_changed_ids)
        self.assertEqual(audited.ai_assisted_notes, ("model suggested suppress",))
        self.assertNotIn("model suggested suppress", change.reason_codes)

    def test_attach_round_trip_and_metadata_key(self) -> None:
        provenance = build_decision_provenance_from_strategy_match(
            match=_match(),
            opportunity=_opportunity(),
            assessment=_assessment(),
            as_of_ns=DECISION_NS,
        )
        attached = attach_decision_provenance(_opportunity(), provenance)
        self.assertIn(DECISION_PROVENANCE_METADATA_KEY, attached.metadata)
        extracted = extract_decision_provenance(attached)
        self.assertIsNotNone(extracted)
        assert extracted is not None
        self.assertEqual(decision_provenance_to_dict(extracted), decision_provenance_to_dict(provenance))
        restored = decision_provenance_from_dict(decision_provenance_to_dict(provenance))
        self.assertEqual(restored, provenance)


if __name__ == "__main__":
    unittest.main()
