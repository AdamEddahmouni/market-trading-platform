"""Evidence adapters mapping EvidenceV1 to hypothesis contributions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..contracts import EvidenceApplicability, EvidenceV1, ExpertDomain, QualityState
from ..council.models import ProvenanceGroup, SourceSignature
from .contributions import ContributionStance, HypothesisContribution
from .factors import ShortSqueezeFactor


class HypothesisEvidenceAdapter(Protocol):
    adapter_id: str
    adapter_version: str
    expert_domain: ExpertDomain

    def adapt(
        self,
        evidence: EvidenceV1,
        *,
        source_signature: SourceSignature,
        provenance_group_id: str | None = None,
        allow_degraded: bool = True,
    ) -> tuple[HypothesisContribution, ...]: ...


def expert_domain_for_evidence(evidence: EvidenceV1) -> ExpertDomain:
    domain = evidence.metadata.get("expert_domain")
    if domain:
        return ExpertDomain(str(domain))
    normalized = evidence.expert_id.lower().replace("-specialist", "").replace("-", "_").upper()
    for candidate in ExpertDomain:
        if candidate.value == normalized or candidate.value in evidence.expert_id.upper():
            return candidate
    return ExpertDomain.MICROSTRUCTURE


def usable_evidence(evidence: EvidenceV1, *, allow_degraded: bool) -> bool:
    if evidence.applicability != EvidenceApplicability.APPLICABLE:
        return False
    if evidence.quality.state == QualityState.INVALID:
        return False
    if evidence.quality.state == QualityState.DEGRADED and not allow_degraded:
        return False
    return True


@dataclass(frozen=True, slots=True)
class MicrostructureShortSqueezeEvidenceAdapter:
    """Production adapter for BUILD 11 microstructure evidence."""

    adapter_id: str = "microstructure-short-squeeze-adapter"
    adapter_version: str = "1"
    expert_domain: ExpertDomain = ExpertDomain.MICROSTRUCTURE

    def adapt(
        self,
        evidence: EvidenceV1,
        *,
        source_signature: SourceSignature,
        provenance_group_id: str | None = None,
        allow_degraded: bool = True,
    ) -> tuple[HypothesisContribution, ...]:
        if expert_domain_for_evidence(evidence) != self.expert_domain:
            return ()
        if not usable_evidence(evidence, allow_degraded=allow_degraded):
            return ()

        assessment = evidence.assessment or {}
        evidence_kind = str(assessment.get("evidence_kind") or "")
        base = {
            "evidence_ref": evidence.evidence_id,
            "expert_domain": self.expert_domain,
            "quality": evidence.quality,
            "source_signature_id": source_signature.signature_id,
            "provenance_group_id": provenance_group_id,
        }

        if evidence_kind == "ORDER_FLOW_TRANSITION":
            transition = str(assessment.get("transition") or "")
            if transition == "NEGATIVE_TO_POSITIVE":
                return (
                    HypothesisContribution(
                        **base,
                        factor=ShortSqueezeFactor.POSITIVE_DEMAND_ACTIVATION.value,
                        stance=ContributionStance.SUPPORTS,
                    ),
                )
            if transition == "POSITIVE_TO_NEGATIVE":
                return (
                    HypothesisContribution(
                        **base,
                        factor=ShortSqueezeFactor.NEGATIVE_DEMAND_PRESSURE.value,
                        stance=ContributionStance.OPPOSES,
                    ),
                    HypothesisContribution(
                        **base,
                        factor=ShortSqueezeFactor.POSITIVE_DEMAND_ACTIVATION.value,
                        stance=ContributionStance.OPPOSES,
                    ),
                )
            return ()

        if evidence_kind == "LIQUIDITY_STRESS":
            return (
                HypothesisContribution(
                    **base,
                    factor=ShortSqueezeFactor.LIQUIDITY_CONSTRAINT.value,
                    stance=ContributionStance.CONTEXT,
                ),
            )

        return ()


@dataclass(frozen=True, slots=True)
class HypothesisEvidenceAdapterRegistry:
    adapters: tuple[HypothesisEvidenceAdapter, ...]

    def adapt_all(
        self,
        evidence: EvidenceV1,
        *,
        source_signature: SourceSignature,
        provenance_group_id: str | None = None,
        allow_degraded: bool = True,
    ) -> tuple[HypothesisContribution, ...]:
        contributions: list[HypothesisContribution] = []
        for adapter in self.adapters:
            rows = adapter.adapt(
                evidence,
                source_signature=source_signature,
                provenance_group_id=provenance_group_id,
                allow_degraded=allow_degraded,
            )
            contributions.extend(rows)
        return tuple(sorted(contributions, key=lambda row: (row.evidence_ref, row.factor, row.stance.value)))


DEFAULT_PRODUCTION_ADAPTER_REGISTRY = HypothesisEvidenceAdapterRegistry(
    adapters=(MicrostructureShortSqueezeEvidenceAdapter(),)
)


def provenance_group_for_evidence(
    evidence_id: str,
    provenance_groups: tuple[ProvenanceGroup, ...],
) -> str | None:
    for group in provenance_groups:
        if evidence_id in group.evidence_ids:
            return group.group_id
    return None


__all__ = [
    "DEFAULT_PRODUCTION_ADAPTER_REGISTRY",
    "HypothesisEvidenceAdapter",
    "HypothesisEvidenceAdapterRegistry",
    "MicrostructureShortSqueezeEvidenceAdapter",
    "expert_domain_for_evidence",
    "provenance_group_for_evidence",
    "usable_evidence",
]
