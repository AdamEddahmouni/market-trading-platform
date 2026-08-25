"""Deterministic BUILD 12 council test fixtures."""

from __future__ import annotations

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
    CouncilParticipant,
    DeliberationContext,
    ParticipantOutcome,
)
from market_platform_foundation.intelligence.specialists.models import SpecialistExecutionStatus
from tests.intelligence.routing_fixtures import T


def _ref(kind: ContractKind, record_id: str) -> ContractReference:
    return ContractReference(kind=kind.value, id=record_id)


def synthetic_evidence(
    *,
    evidence_id: str,
    snapshot_id: str = "snap-council-1",
    expert_domain: ExpertDomain,
    evidence_kind: str,
    claim: str,
    polarity: str,
    signal_refs: tuple[ContractReference, ...] = (),
    event_refs: tuple[ContractReference, ...] = (),
    quality: QualityState = QualityState.GOOD,
    instrument_id: str = "INST-1",
) -> EvidenceV1:
    return EvidenceV1(
        evidence_id=evidence_id,
        schema_version="1",
        snapshot_id=snapshot_id,
        expert_id=f"{expert_domain.value.lower()}-specialist",
        scope=IntelligenceScope(instrument_ids=(instrument_id,)),
        applicability=EvidenceApplicability.APPLICABLE,
        quality=QualitySummary(state=quality),
        assessment={
            "evidence_kind": evidence_kind,
            "claim": claim,
            "polarity": polarity,
        },
        directional_score=0.5,
        support_strength=0.5,
        source_signal_refs=signal_refs,
        source_event_refs=event_refs,
        metadata={"expert_domain": expert_domain.value},
    )


def put_signals_for_refs(repo, refs: tuple[ContractReference, ...], *, snapshot_id: str = "snap-1") -> None:
    from tests.intelligence.routing_fixtures import signal, snapshot as make_snapshot

    snap = make_snapshot(snapshot_id)
    repo.put_snapshot(snap)
    for ref in refs:
        if ref.kind != ContractKind.SIGNAL.value:
            continue
        if repo.get_signal(ref.id) is None:
            repo.put_signal(signal(snap, ref.id, "net_signed_share", 0.1))


def council_participant(
    *,
    expert_domain: ExpertDomain,
    job_id: str,
) -> CouncilParticipant:
    return CouncilParticipant(
        expert_domain=expert_domain,
        job_id=job_id,
        job_ref=_ref(ContractKind.INFERENCE_JOB, job_id),
    )


def completed_outcome(
    *,
    expert_domain: ExpertDomain,
    job_id: str,
    evidence_ids: tuple[str, ...],
) -> ParticipantOutcome:
    return ParticipantOutcome(
        expert_domain=expert_domain,
        job_id=job_id,
        status=SpecialistExecutionStatus.COMPLETED,
        evidence_refs=evidence_ids,
    )


class SyntheticDeliberatingSpecialist:
    expert_domain = ExpertDomain.DERIVATIVES
    component_id = "synthetic-derivatives-specialist"
    component_version = "test-1"

    def analyze(self, context) -> object:
        raise NotImplementedError("test-only second pass specialist")

    def deliberate(self, context: DeliberationContext):
        from market_platform_foundation.intelligence.specialists.models import SpecialistResult

        blind_id = context.own_blind_evidence[0].evidence_id if context.own_blind_evidence else "EVID-blind"
        evidence = synthetic_evidence(
            evidence_id=f"{blind_id}-delib",
            expert_domain=self.expert_domain,
            evidence_kind="SYNTHETIC_CLAIM",
            claim="directional_pressure",
            polarity="NEUTRAL",
            signal_refs=context.own_blind_evidence[0].source_signal_refs if context.own_blind_evidence else (),
        )
        return SpecialistResult(
            status=SpecialistExecutionStatus.COMPLETED,
            evidence=(evidence,),
        )


__all__ = [
    "SyntheticDeliberatingSpecialist",
    "T",
    "completed_outcome",
    "council_participant",
    "put_signals_for_refs",
    "synthetic_evidence",
]
