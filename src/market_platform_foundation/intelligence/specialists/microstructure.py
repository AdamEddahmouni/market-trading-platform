"""Deterministic CPU-native microstructure specialist (BUILD 11)."""

from __future__ import annotations

from typing import Any

from ..contracts import (
    ComponentLineage,
    ContractKind,
    ContractReference,
    DetectionSeverity,
    EvidenceApplicability,
    EvidenceV1,
    ExpertDomain,
    QualityState,
    QualitySummary,
    SemanticEventType,
    SignalV1,
)
from .context import SpecialistExecutionContext
from .identity import derive_microstructure_evidence_id
from .models import (
    SpecialistDiagnostic,
    SpecialistDiagnosticCode,
    SpecialistExecutionStatus,
    SpecialistResult,
)
from .policy import DEFAULT_MICROSTRUCTURE_SPECIALIST_POLICY, MicrostructureSpecialistPolicyV1
from .protocol import Specialist


_SEVERITY_STRENGTH = {
    DetectionSeverity.LOW: 0.25,
    DetectionSeverity.MEDIUM: 0.5,
    DetectionSeverity.HIGH: 0.75,
    DetectionSeverity.CRITICAL: 1.0,
}


def _ref(kind: ContractKind, record_id: str) -> ContractReference:
    return ContractReference(kind=kind.value, id=record_id)


def _signal_by_id(signals: tuple[SignalV1, ...]) -> dict[str, SignalV1]:
    return {row.signal_id: row for row in signals}


def _merge_quality(*summaries: QualitySummary) -> QualitySummary:
    states = [row.state for row in summaries]
    flags: set[str] = set()
    for row in summaries:
        flags.update(row.flags)
    if QualityState.INVALID in states:
        state = QualityState.INVALID
    elif QualityState.DEGRADED in states or QualityState.UNKNOWN in states:
        state = QualityState.DEGRADED
    else:
        state = QualityState.GOOD
    return QualitySummary(state=state, flags=tuple(sorted(flags)))


def _support_strength(severity: DetectionSeverity) -> float:
    return _SEVERITY_STRENGTH[severity]


def _directional_score(*, transition: str, magnitude: float) -> float:
    bounded = min(1.0, max(0.0, magnitude / 2.0))
    if transition in {"NEGATIVE_TO_POSITIVE", "NORMAL_TO_STRESSED"}:
        return bounded
    return max(0.0, 1.0 - bounded)


class MicrostructureSpecialist:
    """First real specialist — deterministic quantitative microstructure analysis."""

    expert_domain = ExpertDomain.MICROSTRUCTURE
    component_id = "microstructure-specialist"
    component_version = "1"

    def __init__(self, policy: MicrostructureSpecialistPolicyV1 | None = None) -> None:
        self.policy = policy or DEFAULT_MICROSTRUCTURE_SPECIALIST_POLICY

    def analyze(self, context: SpecialistExecutionContext) -> SpecialistResult:
        if context.job.expert_domain != ExpertDomain.MICROSTRUCTURE:
            return SpecialistResult(
                status=SpecialistExecutionStatus.FAILED,
                diagnostics=(
                    SpecialistDiagnostic(
                        SpecialistDiagnosticCode.UNSUPPORTED_DOMAIN,
                        "job expert domain is not MICROSTRUCTURE",
                        {"expert_domain": context.job.expert_domain.value},
                    ),
                ),
            )

        event_type = context.detection.semantic_event_type
        if event_type not in self.policy.supported_semantic_event_types:
            return SpecialistResult(
                status=SpecialistExecutionStatus.FAILED,
                diagnostics=(
                    SpecialistDiagnostic(
                        SpecialistDiagnosticCode.UNSUPPORTED_SEMANTIC_EVENT,
                        "semantic event not supported by microstructure specialist",
                        {"semantic_event_type": event_type.value},
                    ),
                ),
            )

        if event_type == SemanticEventType.ORDER_FLOW_REVERSAL:
            return self._analyze_order_flow(context)
        if event_type == SemanticEventType.LIQUIDITY_EVENT:
            return self._analyze_liquidity(context)

        return SpecialistResult(
            status=SpecialistExecutionStatus.FAILED,
            diagnostics=(
                SpecialistDiagnostic(
                    SpecialistDiagnosticCode.UNSUPPORTED_SEMANTIC_EVENT,
                    "unsupported semantic event",
                    {"semantic_event_type": event_type.value},
                ),
            ),
        )

    def _analyze_order_flow(self, context: SpecialistExecutionContext) -> SpecialistResult:
        signals = context.signals
        if len(signals) != 2:
            return SpecialistResult(
                status=SpecialistExecutionStatus.FAILED,
                diagnostics=(
                    SpecialistDiagnostic(
                        SpecialistDiagnosticCode.MISSING_REQUIRED_SOURCE,
                        "order-flow reversal requires exactly two frozen NSS signals",
                        {"signal_count": len(signals)},
                    ),
                ),
            )

        for row in signals:
            if row.signal_type != "net_signed_share":
                return SpecialistResult(
                    status=SpecialistExecutionStatus.FAILED,
                    diagnostics=(
                        SpecialistDiagnostic(
                            SpecialistDiagnosticCode.WRONG_SIGNAL_TYPE,
                            "order-flow reversal requires net_signed_share signals",
                            {"signal_id": row.signal_id, "signal_type": row.signal_type},
                        ),
                    ),
                )
            if row.quality.state == QualityState.INVALID:
                return SpecialistResult(
                    status=SpecialistExecutionStatus.FAILED,
                    diagnostics=(
                        SpecialistDiagnostic(
                            SpecialistDiagnosticCode.QUALITY_REJECTED,
                            "required source signal quality invalid",
                            {"signal_id": row.signal_id},
                        ),
                    ),
                )

        ordered = tuple(sorted(signals, key=lambda row: (row.as_of_time_ns, row.signal_id)))
        previous, current = ordered[0], ordered[1]
        transition = context.detection.identity_context.get("transition")
        if transition not in {"NEGATIVE_TO_POSITIVE", "POSITIVE_TO_NEGATIVE"}:
            transition = "NEGATIVE_TO_POSITIVE" if current.value > previous.value else "POSITIVE_TO_NEGATIVE"

        delta = current.value - previous.value
        magnitude = abs(delta)
        evidence_kind = "ORDER_FLOW_TRANSITION"
        source_refs = tuple(_ref(ContractKind.SIGNAL, row.signal_id) for row in (previous, current))
        evidence_id = derive_microstructure_evidence_id(
            job=context.job,
            route=context.route,
            detection=context.detection,
            evidence_kind=evidence_kind,
            source_signal_refs=source_refs,
            specialist_component_id=self.component_id,
            specialist_component_version=self.component_version,
            specialist_policy_identity=self.policy.identity,
            evidence_identity_version=self.policy.evidence_identity_version,
        )

        assessment: dict[str, Any] = {
            "evidence_kind": evidence_kind,
            "semantic_event_type": SemanticEventType.ORDER_FLOW_REVERSAL.value,
            "transition": transition,
            "previous_nss": previous.value,
            "current_nss": current.value,
            "delta_nss": delta,
            "pressure_direction": "BULLISH" if transition == "NEGATIVE_TO_POSITIVE" else "BEARISH",
            "strength_semantics": "derived_from_detection_severity_not_probability",
        }
        explanation = (
            f"Net signed share shifted from {previous.value:.4f} to {current.value:.4f} "
            f"within the routed order-flow reversal context."
        )
        evidence_for = (
            ("OBSERVED_BULLISH_MICROSTRUCTURE_PRESSURE",)
            if transition == "NEGATIVE_TO_POSITIVE"
            else ("OBSERVED_BEARISH_MICROSTRUCTURE_PRESSURE",)
        )
        evidence = EvidenceV1(
            evidence_id=evidence_id,
            schema_version="1",
            snapshot_id=context.snapshot.snapshot_id,
            expert_id=self.component_id,
            scope=context.snapshot.scope,
            applicability=EvidenceApplicability.APPLICABLE,
            quality=_merge_quality(context.detection.quality, previous.quality, current.quality),
            assessment=assessment,
            directional_score=_directional_score(transition=transition, magnitude=magnitude),
            support_strength=_support_strength(context.detection.severity),
            evidence_for=evidence_for,
            source_signal_refs=source_refs,
            component_lineage=ComponentLineage(
                component_id=self.component_id,
                component_version=self.component_version,
            ),
            explanation=explanation,
            metadata={
                "specialist_policy_identity": self.policy.identity,
                "detection_id": context.detection.detection_id,
                "routing_decision_id": context.route.routing_decision_id,
                "job_id": context.job.job_id,
                "reason_codes": list(context.detection.reason_codes),
            },
        )
        return SpecialistResult(status=SpecialistExecutionStatus.COMPLETED, evidence=(evidence,))

    def _analyze_liquidity(self, context: SpecialistExecutionContext) -> SpecialistResult:
        signals = context.signals
        if len(signals) != 2:
            return SpecialistResult(
                status=SpecialistExecutionStatus.FAILED,
                diagnostics=(
                    SpecialistDiagnostic(
                        SpecialistDiagnosticCode.MISSING_REQUIRED_SOURCE,
                        "liquidity event requires exactly two frozen spread signals",
                        {"signal_count": len(signals)},
                    ),
                ),
            )

        for row in signals:
            if row.signal_type != "spread_bps":
                return SpecialistResult(
                    status=SpecialistExecutionStatus.FAILED,
                    diagnostics=(
                        SpecialistDiagnostic(
                            SpecialistDiagnosticCode.WRONG_SIGNAL_TYPE,
                            "liquidity event requires spread_bps signals",
                            {"signal_id": row.signal_id, "signal_type": row.signal_type},
                        ),
                    ),
                )
            if row.quality.state == QualityState.INVALID:
                return SpecialistResult(
                    status=SpecialistExecutionStatus.FAILED,
                    diagnostics=(
                        SpecialistDiagnostic(
                            SpecialistDiagnosticCode.QUALITY_REJECTED,
                            "required source signal quality invalid",
                            {"signal_id": row.signal_id},
                        ),
                    ),
                )

        ordered = tuple(sorted(signals, key=lambda row: (row.as_of_time_ns, row.signal_id)))
        previous, current = ordered[0], ordered[1]
        spread_delta = current.value - previous.value
        transition = context.detection.identity_context.get("transition", "NORMAL_TO_STRESSED")
        assessment: dict[str, Any] = {
            "evidence_kind": "LIQUIDITY_STRESS",
            "semantic_event_type": SemanticEventType.LIQUIDITY_EVENT.value,
            "transition": transition,
            "previous_spread_bps": previous.value,
            "current_spread_bps": current.value,
            "spread_delta_bps": spread_delta,
            "strength_semantics": "derived_from_detection_severity_not_probability",
        }
        if previous.value > 0:
            assessment["spread_ratio"] = current.value / previous.value

        evidence_kind = "LIQUIDITY_STRESS"
        source_refs = tuple(_ref(ContractKind.SIGNAL, row.signal_id) for row in (previous, current))
        evidence_id = derive_microstructure_evidence_id(
            job=context.job,
            route=context.route,
            detection=context.detection,
            evidence_kind=evidence_kind,
            source_signal_refs=source_refs,
            specialist_component_id=self.component_id,
            specialist_component_version=self.component_version,
            specialist_policy_identity=self.policy.identity,
            evidence_identity_version=self.policy.evidence_identity_version,
        )
        explanation = (
            f"Bid/ask spread moved from {previous.value:.2f} bps to {current.value:.2f} bps "
            f"within the routed liquidity-stress context."
        )
        evidence = EvidenceV1(
            evidence_id=evidence_id,
            schema_version="1",
            snapshot_id=context.snapshot.snapshot_id,
            expert_id=self.component_id,
            scope=context.snapshot.scope,
            applicability=EvidenceApplicability.APPLICABLE,
            quality=_merge_quality(context.detection.quality, previous.quality, current.quality),
            assessment=assessment,
            directional_score=_directional_score(transition=transition, magnitude=abs(spread_delta) / 100.0),
            support_strength=_support_strength(context.detection.severity),
            evidence_for=("OBSERVED_LIQUIDITY_STRESS",),
            source_signal_refs=source_refs,
            component_lineage=ComponentLineage(
                component_id=self.component_id,
                component_version=self.component_version,
            ),
            explanation=explanation,
            metadata={
                "specialist_policy_identity": self.policy.identity,
                "detection_id": context.detection.detection_id,
                "routing_decision_id": context.route.routing_decision_id,
                "job_id": context.job.job_id,
                "reason_codes": list(context.detection.reason_codes),
            },
        )
        return SpecialistResult(status=SpecialistExecutionStatus.COMPLETED, evidence=(evidence,))


__all__ = ["MicrostructureSpecialist"]
