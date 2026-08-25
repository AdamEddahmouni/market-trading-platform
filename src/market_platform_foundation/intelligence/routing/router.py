"""Capability-aware deterministic SmartRouter (BUILD 09)."""

from __future__ import annotations

from ..contracts import (
    ComponentLineage,
    ContractKind,
    ContractReference,
    DetectionSeverity,
    DetectionV1,
    QualityState,
    QualitySummary,
    RouteAction,
    RoutingDecisionV1,
    RoutingPriority,
)
from ..quality import DecisionAction, IntelligenceCapability, QualityDecision
from .identity import derive_routing_decision_id
from .policy import RoutingPolicyV1

_PRIORITY_ORDER = (
    RoutingPriority.LOW,
    RoutingPriority.NORMAL,
    RoutingPriority.HIGH,
    RoutingPriority.CRITICAL,
)


def _priority(base: RoutingPriority, severity: DetectionSeverity, *, promote: bool) -> RoutingPriority:
    if not promote or severity not in {DetectionSeverity.HIGH, DetectionSeverity.CRITICAL}:
        return base
    index = min(_PRIORITY_ORDER.index(base) + 1, len(_PRIORITY_ORDER) - 1)
    return _PRIORITY_ORDER[index]


class SmartRouter:
    """Converts semantic detections to logical domain intents only."""

    def __init__(self, policy: RoutingPolicyV1 | None = None) -> None:
        self.policy = policy or RoutingPolicyV1()

    def route(self, detection: DetectionV1, *, quality_decision: QualityDecision) -> RoutingDecisionV1:
        if quality_decision.assessment.decision_time_ns != detection.detected_at_ns:
            raise ValueError("ROUTING_QUALITY_DECISION_TIME_MISMATCH")
        template = self.policy.template_for(detection.semantic_event_type)
        required = tuple(cap.value for cap in template.required_capabilities)
        optional = tuple(cap.value for cap in template.optional_capabilities)
        satisfied = {cap for cap in quality_decision.satisfied_requirements}
        degraded = {cap for cap in quality_decision.degraded_requirements}
        required_missing = set(template.required_capabilities) - satisfied - degraded
        optional_missing = set(template.optional_capabilities) - satisfied - degraded
        reasons = {f"{detection.semantic_event_type.value}_DETECTED"}
        route_action = RouteAction.ROUTE

        if quality_decision.action in {DecisionAction.ABSTAIN, DecisionAction.FAIL_CLOSED}:
            route_action = RouteAction.ABSTAIN
            reasons.add(f"BUILD_04_{quality_decision.action.value}")
        elif quality_decision.action == DecisionAction.DEGRADE and not self.policy.allow_degraded:
            route_action = RouteAction.ABSTAIN
            reasons.add("DEGRADED_ROUTING_REJECTED")
        elif required_missing:
            route_action = RouteAction.SUPPRESS
            reasons.add("REQUIRED_CAPABILITY_MISSING")
        else:
            reasons.add("REQUIRED_CAPABILITIES_AVAILABLE")
            if quality_decision.action == DecisionAction.DEGRADE or degraded:
                reasons.add("DEGRADED_INPUT_ALLOWED")
            if optional_missing:
                reasons.add("OPTIONAL_CAPABILITY_MISSING")

        degraded_route = bool(
            quality_decision.action == DecisionAction.DEGRADE
            or degraded
            or optional_missing
            or detection.quality.state in {QualityState.DEGRADED, QualityState.UNKNOWN}
        )
        if route_action == RouteAction.ROUTE:
            quality = QualitySummary(
                state=QualityState.DEGRADED if degraded_route else QualityState.GOOD,
                flags=detection.quality.flags,
            )
            deadline = detection.detected_at_ns + template.deadline_offset_ns
            expires = detection.detected_at_ns + template.ttl_ns
            ttl = template.ttl_ns
        else:
            quality = QualitySummary(
                state=QualityState.INVALID if quality_decision.action == DecisionAction.FAIL_CLOSED else QualityState.DEGRADED,
                flags=detection.quality.flags,
            )
            deadline = expires = ttl = None

        routing_context = {
            "quality_action": quality_decision.action.value,
            "satisfied": sorted(cap.value for cap in satisfied),
            "degraded": sorted(cap.value for cap in degraded),
            "required_missing": sorted(cap.value for cap in required_missing),
            "optional_missing": sorted(cap.value for cap in optional_missing),
        }
        route_id = derive_routing_decision_id(
            detection_id=detection.detection_id,
            router_policy_identity=self.policy.identity,
            expert_domain=template.expert_domain.value,
            required_capabilities=required,
            routing_context=routing_context,
        )
        return RoutingDecisionV1(
            routing_decision_id=route_id,
            schema_version="1",
            detection_ref=ContractReference(kind=ContractKind.DETECTION.value, id=detection.detection_id),
            decision_time_ns=detection.detected_at_ns,
            expert_domain=template.expert_domain,
            route_action=route_action,
            priority=_priority(template.base_priority, detection.severity, promote=self.policy.severity_promotions),
            reason_codes=tuple(reasons),
            required_capabilities=required,
            optional_capabilities=optional,
            deadline_time_ns=deadline,
            expires_at_ns=expires,
            ttl_ns=ttl,
            quality=quality,
            router_lineage=ComponentLineage(component_id="smart-router", component_version="1"),
            metadata={
                "routing_policy_id": self.policy.policy_id,
                "routing_policy_version": self.policy.policy_version,
                "routing_policy_identity": self.policy.identity,
                "route_is_scheduled_job": False,
            },
        )

    def route_all(
        self,
        detections: tuple[DetectionV1, ...] | list[DetectionV1],
        *,
        quality_decision: QualityDecision,
    ) -> tuple[RoutingDecisionV1, ...]:
        unique: dict[str, DetectionV1] = {}
        for row in detections:
            existing = unique.get(row.detection_id)
            if existing is not None and existing != row:
                raise ValueError(f"ROUTING_DETECTION_ID_CONFLICT:{row.detection_id}")
            unique[row.detection_id] = row
        routed = [self.route(unique[key], quality_decision=quality_decision) for key in sorted(unique)]
        return tuple(
            sorted(
                routed,
                key=lambda row: (row.expert_domain.value, row.detection_ref.id, row.routing_decision_id),
            )
        )


__all__ = ["SmartRouter"]
