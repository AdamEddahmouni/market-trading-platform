"""Deterministic BUILD 13 hypothesis test fixtures (test-only adapters)."""

from __future__ import annotations

from dataclasses import dataclass

from market_platform_foundation.intelligence.contracts import (
    ContractKind,
    ContractReference,
    EvidenceApplicability,
    EvidenceV1,
    ExpertDomain,
    IntelligenceScope,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.council import (
    BlackboardPhase,
    CouncilPolicy,
    EvidenceProvenanceResolver,
    EvidenceRelationAnalyzer,
    publish_blackboard_snapshot,
)
from market_platform_foundation.intelligence.council.comparison import DEFAULT_COMPARISON_REGISTRY
from market_platform_foundation.intelligence.hypotheses.adapters import (
    HypothesisEvidenceAdapterRegistry,
    MicrostructureShortSqueezeEvidenceAdapter,
    usable_evidence,
)
from market_platform_foundation.intelligence.hypotheses.contributions import ContributionStance, HypothesisContribution
from market_platform_foundation.intelligence.hypotheses.factors import ShortSqueezeFactor
from market_platform_foundation.intelligence.hypotheses.short_squeeze import ShortSqueezeHypothesisEngine
from market_platform_foundation.intelligence.hypotheses.types import HypothesisEvaluationContext
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from tests.intelligence.council_fixtures import completed_outcome, put_signals_for_refs, synthetic_evidence, T


def _ref(kind: ContractKind, record_id: str) -> ContractReference:
    return ContractReference(kind=kind.value, id=record_id)


def microstructure_order_flow_evidence(
    *,
    evidence_id: str,
    transition: str,
    signal_id: str = "SIG-M1",
    snapshot_id: str = "snap-hyp-1",
    instrument_id: str = "INST-1",
) -> EvidenceV1:
    return EvidenceV1(
        evidence_id=evidence_id,
        schema_version="1",
        snapshot_id=snapshot_id,
        expert_id="microstructure-specialist",
        scope=IntelligenceScope(instrument_ids=(instrument_id,)),
        applicability=EvidenceApplicability.APPLICABLE,
        quality=QualitySummary(state=QualityState.GOOD),
        assessment={
            "evidence_kind": "ORDER_FLOW_TRANSITION",
            "semantic_event_type": "ORDER_FLOW_REVERSAL",
            "transition": transition,
            "pressure_direction": "BULLISH" if transition == "NEGATIVE_TO_POSITIVE" else "BEARISH",
        },
        source_signal_refs=(_ref(ContractKind.SIGNAL, signal_id),),
        metadata={"expert_domain": ExpertDomain.MICROSTRUCTURE.value},
    )


def positioning_short_pressure_evidence(
    *,
    evidence_id: str,
    signal_id: str = "SIG-P1",
    snapshot_id: str = "snap-hyp-1",
    instrument_id: str = "INST-1",
) -> EvidenceV1:
    return EvidenceV1(
        evidence_id=evidence_id,
        schema_version="1",
        snapshot_id=snapshot_id,
        expert_id="positioning-borrow-specialist",
        scope=IntelligenceScope(instrument_ids=(instrument_id,)),
        applicability=EvidenceApplicability.APPLICABLE,
        quality=QualitySummary(state=QualityState.GOOD),
        assessment={
            "evidence_kind": "SHORT_INTEREST_PRESSURE",
            "pressure_level": "ELEVATED",
        },
        source_signal_refs=(_ref(ContractKind.SIGNAL, signal_id),),
        metadata={"expert_domain": ExpertDomain.POSITIONING_BORROW.value},
    )


@dataclass(frozen=True, slots=True)
class SyntheticPositioningBorrowAdapter:
    adapter_id: str = "synthetic-positioning-borrow-adapter"
    adapter_version: str = "test-1"
    expert_domain: ExpertDomain = ExpertDomain.POSITIONING_BORROW

    def adapt(self, evidence, *, source_signature, provenance_group_id=None, allow_degraded=True):
        if not usable_evidence(evidence, allow_degraded=allow_degraded):
            return ()
        assessment = evidence.assessment or {}
        if assessment.get("evidence_kind") != "SHORT_INTEREST_PRESSURE":
            return ()
        return (
            HypothesisContribution(
                evidence_ref=evidence.evidence_id,
                factor=ShortSqueezeFactor.SHORT_PRESSURE.value,
                stance=ContributionStance.SUPPORTS,
                expert_domain=self.expert_domain,
                quality=evidence.quality,
                source_signature_id=source_signature.signature_id,
                provenance_group_id=provenance_group_id,
            ),
        )


@dataclass(frozen=True, slots=True)
class SyntheticDerivativesAdapter:
    adapter_id: str = "synthetic-derivatives-adapter"
    adapter_version: str = "test-1"
    expert_domain: ExpertDomain = ExpertDomain.DERIVATIVES

    def adapt(self, evidence, *, source_signature, provenance_group_id=None, allow_degraded=True):
        if not usable_evidence(evidence, allow_degraded=allow_degraded):
            return ()
        assessment = evidence.assessment or {}
        if assessment.get("evidence_kind") != "GAMMA_ACCELERATION":
            return ()
        return (
            HypothesisContribution(
                evidence_ref=evidence.evidence_id,
                factor=ShortSqueezeFactor.DERIVATIVES_ACCELERATION.value,
                stance=ContributionStance.SUPPORTS,
                expert_domain=self.expert_domain,
                quality=evidence.quality,
                source_signature_id=source_signature.signature_id,
                provenance_group_id=provenance_group_id,
            ),
        )


@dataclass(frozen=True, slots=True)
class SyntheticRegimeAdapter:
    adapter_id: str = "synthetic-regime-adapter"
    adapter_version: str = "test-1"
    expert_domain: ExpertDomain = ExpertDomain.REGIME_CROSS_ASSET

    def adapt(self, evidence, *, source_signature, provenance_group_id=None, allow_degraded=True):
        if not usable_evidence(evidence, allow_degraded=allow_degraded):
            return ()
        assessment = evidence.assessment or {}
        if assessment.get("evidence_kind") != "RISK_ON_SUPPORT":
            return ()
        return (
            HypothesisContribution(
                evidence_ref=evidence.evidence_id,
                factor=ShortSqueezeFactor.REGIME_SUPPORT.value,
                stance=ContributionStance.SUPPORTS,
                expert_domain=self.expert_domain,
                quality=evidence.quality,
                source_signature_id=source_signature.signature_id,
                provenance_group_id=provenance_group_id,
            ),
        )


TEST_ADAPTER_REGISTRY = HypothesisEvidenceAdapterRegistry(
    adapters=(
        MicrostructureShortSqueezeEvidenceAdapter(),
        SyntheticPositioningBorrowAdapter(),
        SyntheticDerivativesAdapter(),
        SyntheticRegimeAdapter(),
    )
)


def analyze_blackboard(repo: InMemoryIntelligenceRepository, evidence_rows: tuple[EvidenceV1, ...]):
    ordered_rows = tuple(sorted(evidence_rows, key=lambda row: row.evidence_id))
    for row in ordered_rows:
        put_signals_for_refs(repo, row.source_signal_refs, snapshot_id=row.snapshot_id)
        repo.put_evidence(row)
    outcomes = tuple(
        completed_outcome(
            expert_domain=ExpertDomain(row.metadata["expert_domain"]),
            job_id=f"job-{row.metadata['expert_domain'].lower()}",
            evidence_ids=(row.evidence_id,),
        )
        for row in ordered_rows
    )
    blackboard = publish_blackboard_snapshot(
        council_id="COUNCIL-HYP",
        source_snapshot_id=evidence_rows[0].snapshot_id,
        evidence_refs=tuple(row.evidence_id for row in evidence_rows),
        participant_outcomes=outcomes,
        phase=BlackboardPhase.BLIND_PASS,
        revision=1,
        resolved_evidence={row.evidence_id: row for row in evidence_rows},
    )
    analyzer = EvidenceRelationAnalyzer(
        comparison_registry=DEFAULT_COMPARISON_REGISTRY,
        provenance_resolver=EvidenceProvenanceResolver(repo),
    )
    relation_report = analyzer.analyze(
        blackboard=blackboard,
        evidence_by_id={row.evidence_id: row for row in evidence_rows},
        policy=CouncilPolicy(),
    )
    return blackboard, relation_report


def evaluate_rows(
    evidence_rows: tuple[EvidenceV1, ...],
    *,
    adapter_registry=TEST_ADAPTER_REGISTRY,
):
    repo = InMemoryIntelligenceRepository()
    blackboard, relation_report = analyze_blackboard(repo, evidence_rows)
    engine = ShortSqueezeHypothesisEngine(adapter_registry=adapter_registry)
    return engine.evaluate(
        HypothesisEvaluationContext(
            blackboard=blackboard,
            relation_report=relation_report,
            evidence_by_id={row.evidence_id: row for row in evidence_rows},
            decision_time_ns=T,
        )
    )


__all__ = [
    "SyntheticDerivativesAdapter",
    "SyntheticPositioningBorrowAdapter",
    "SyntheticRegimeAdapter",
    "TEST_ADAPTER_REGISTRY",
    "analyze_blackboard",
    "evaluate_rows",
    "microstructure_order_flow_evidence",
    "positioning_short_pressure_evidence",
]
