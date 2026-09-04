"""Comparable evidence adapters for BUILD 12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..contracts import EvidenceApplicability, EvidenceV1, QualityState
from .models import ComparableEvidenceView
from .provenance import EvidenceProvenanceResolver, SourceSignature


class EvidenceComparisonAdapter(Protocol):
    comparison_adapter_version: str

    def to_comparable_view(
        self,
        evidence: EvidenceV1,
        *,
        source_signature: SourceSignature,
    ) -> ComparableEvidenceView: ...


def _scope_key(evidence: EvidenceV1) -> str:
    instruments = ",".join(sorted(evidence.scope.instrument_ids))
    context = evidence.scope.context_id or ""
    return f"{instruments}|{context}"


@dataclass(frozen=True, slots=True)
class MicrostructureComparisonAdapter:
    comparison_adapter_version: str = "microstructure-comparison-v1"

    def to_comparable_view(
        self,
        evidence: EvidenceV1,
        *,
        source_signature: SourceSignature,
    ) -> ComparableEvidenceView:
        assessment = evidence.assessment or {}
        evidence_kind = str(assessment.get("evidence_kind") or "")
        semantic_event = str(
            assessment.get("semantic_event")
            or evidence.metadata.get("semantic_event")
            or ""
        )
        scope_key = _scope_key(evidence)

        if not evidence_kind:
            return ComparableEvidenceView(
                evidence_id=evidence.evidence_id,
                expert_domain=_expert_domain(evidence),
                scope_key=scope_key,
                comparison_key="",
                polarity="UNKNOWN",
                quality_state=evidence.quality.state.value,
                strength=evidence.support_strength,
                source_signature_id=source_signature.signature_id,
                terminal_source_ids=source_signature.terminal_source_ids,
                evidence_kind=None,
                comparable=False,
            )

        if evidence_kind == "ORDER_FLOW_TRANSITION":
            polarity = str(assessment.get("pressure_direction") or "UNKNOWN")
            comparison_key = f"{scope_key}:{evidence_kind}:{semantic_event}"
            return ComparableEvidenceView(
                evidence_id=evidence.evidence_id,
                expert_domain=_expert_domain(evidence),
                scope_key=scope_key,
                comparison_key=comparison_key,
                polarity=polarity,
                quality_state=evidence.quality.state.value,
                strength=evidence.support_strength,
                source_signature_id=source_signature.signature_id,
                terminal_source_ids=source_signature.terminal_source_ids,
                evidence_kind=evidence_kind,
                comparable=True,
            )

        if evidence_kind == "LIQUIDITY_STRESS":
            comparison_key = f"{scope_key}:{evidence_kind}"
            return ComparableEvidenceView(
                evidence_id=evidence.evidence_id,
                expert_domain=_expert_domain(evidence),
                scope_key=scope_key,
                comparison_key=comparison_key,
                polarity="STRESSED",
                quality_state=evidence.quality.state.value,
                strength=evidence.support_strength,
                source_signature_id=source_signature.signature_id,
                terminal_source_ids=source_signature.terminal_source_ids,
                evidence_kind=evidence_kind,
                comparable=True,
            )

        return ComparableEvidenceView(
            evidence_id=evidence.evidence_id,
            expert_domain=_expert_domain(evidence),
            scope_key=scope_key,
            comparison_key="",
            polarity="UNKNOWN",
            quality_state=evidence.quality.state.value,
            strength=evidence.support_strength,
            source_signature_id=source_signature.signature_id,
            terminal_source_ids=source_signature.terminal_source_ids,
            evidence_kind=evidence_kind or None,
            comparable=False,
        )


def _expert_domain(evidence: EvidenceV1):
    from ..contracts import ExpertDomain

    domain = evidence.metadata.get("expert_domain")
    if domain:
        return ExpertDomain(str(domain))
    normalized = evidence.expert_id.lower().replace("-specialist", "").replace("-", "_").upper()
    for candidate in ExpertDomain:
        if candidate.value == normalized or candidate.value in evidence.expert_id.upper():
            return candidate
    return ExpertDomain.MICROSTRUCTURE


@dataclass(frozen=True, slots=True)
class SyntheticCouncilComparisonAdapter:
    """Deterministic adapter for synthetic test specialists."""

    comparison_adapter_version: str = "synthetic-council-comparison-v1"

    def to_comparable_view(
        self,
        evidence: EvidenceV1,
        *,
        source_signature: SourceSignature,
    ) -> ComparableEvidenceView:
        assessment = evidence.assessment or {}
        evidence_kind = str(assessment.get("evidence_kind") or "")
        claim = str(assessment.get("claim") or "")
        scope_key = _scope_key(evidence)
        polarity = str(assessment.get("polarity") or "UNKNOWN")
        if not evidence_kind or not claim:
            return ComparableEvidenceView(
                evidence_id=evidence.evidence_id,
                expert_domain=_expert_domain(evidence),
                scope_key=scope_key,
                comparison_key="",
                polarity=polarity,
                quality_state=evidence.quality.state.value,
                strength=evidence.support_strength,
                source_signature_id=source_signature.signature_id,
                terminal_source_ids=source_signature.terminal_source_ids,
                comparable=False,
            )
        comparison_key = f"{scope_key}:{evidence_kind}:{claim}"
        return ComparableEvidenceView(
            evidence_id=evidence.evidence_id,
            expert_domain=_expert_domain(evidence),
            scope_key=scope_key,
            comparison_key=comparison_key,
            polarity=polarity,
            quality_state=evidence.quality.state.value,
            strength=evidence.support_strength,
            source_signature_id=source_signature.signature_id,
            terminal_source_ids=source_signature.terminal_source_ids,
            evidence_kind=evidence_kind,
            comparable=True,
        )


@dataclass(frozen=True, slots=True)
class ComparisonAdapterRegistry:
    adapters: tuple[EvidenceComparisonAdapter, ...]

    def to_comparable_view(
        self,
        evidence: EvidenceV1,
        *,
        provenance_resolver: EvidenceProvenanceResolver,
    ) -> ComparableEvidenceView:
        source_signature = provenance_resolver.resolve_terminal_sources(evidence)
        selected: ComparableEvidenceView | None = None
        for adapter in self.adapters:
            view = adapter.to_comparable_view(evidence, source_signature=source_signature)
            if view.comparable:
                return view
            if selected is None and view.evidence_kind:
                selected = view
        if selected is not None:
            return selected
        return ComparableEvidenceView(
            evidence_id=evidence.evidence_id,
            expert_domain=_expert_domain(evidence),
            scope_key=_scope_key(evidence),
            comparison_key="",
            polarity="UNKNOWN",
            quality_state=evidence.quality.state.value,
            strength=evidence.support_strength,
            source_signature_id=source_signature.signature_id,
            terminal_source_ids=source_signature.terminal_source_ids,
            comparable=False,
        )


def evidence_operational(
    evidence: EvidenceV1,
    *,
    allow_degraded: bool,
) -> bool:
    if evidence.applicability != EvidenceApplicability.APPLICABLE:
        return False
    if evidence.quality.state == QualityState.INVALID:
        return False
    if evidence.quality.state == QualityState.DEGRADED and not allow_degraded:
        return False
    return True


DEFAULT_COMPARISON_REGISTRY = ComparisonAdapterRegistry(
    adapters=(
        MicrostructureComparisonAdapter(),
        SyntheticCouncilComparisonAdapter(),
    )
)


__all__ = [
    "ComparisonAdapterRegistry",
    "DEFAULT_COMPARISON_REGISTRY",
    "EvidenceComparisonAdapter",
    "MicrostructureComparisonAdapter",
    "SyntheticCouncilComparisonAdapter",
    "evidence_operational",
]
