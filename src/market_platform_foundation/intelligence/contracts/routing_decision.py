"""RoutingDecisionV1 — BUILD 09 handoff contract for BUILD 10."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ComponentLineage,
    ContractKind,
    ContractReference,
    QualitySummary,
    component_lineage_from_dict,
    component_lineage_to_dict,
    contract_reference_from_dict,
    contract_reference_to_dict,
    dataclass_field_names,
    quality_summary_from_dict,
    quality_summary_to_dict,
    reject_unknown_keys,
    validate_id,
    validate_schema_version,
    validate_timestamp_ns,
)


class ExpertDomain(StrEnum):
    MICROSTRUCTURE = "MICROSTRUCTURE"
    DERIVATIVES = "DERIVATIVES"
    POSITIONING_BORROW = "POSITIONING_BORROW"
    CORPORATE_FUNDAMENTAL = "CORPORATE_FUNDAMENTAL"
    INSIDER_OWNERSHIP = "INSIDER_OWNERSHIP"
    NARRATIVE_SENTIMENT = "NARRATIVE_SENTIMENT"
    MACRO_POLICY = "MACRO_POLICY"
    CRYPTO_ONCHAIN = "CRYPTO_ONCHAIN"
    REGIME_CROSS_ASSET = "REGIME_CROSS_ASSET"


class RouteAction(StrEnum):
    ROUTE = "ROUTE"
    SUPPRESS = "SUPPRESS"
    ABSTAIN = "ABSTAIN"


class RoutingPriority(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


def _normalized_strings(values: tuple[str, ...], *, required: bool = False) -> tuple[str, ...]:
    normalized = tuple(sorted({str(value) for value in values if str(value).strip()}))
    if required and not normalized:
        raise ValueError("ROUTING_REASON_CODES_REQUIRED")
    return normalized


@dataclass(frozen=True, slots=True)
class RoutingDecisionV1:
    """Logical specialist intent, not a scheduled or executing job."""

    routing_decision_id: str
    schema_version: str
    detection_ref: ContractReference
    decision_time_ns: int
    expert_domain: ExpertDomain
    route_action: RouteAction
    priority: RoutingPriority
    reason_codes: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    optional_capabilities: tuple[str, ...]
    quality: QualitySummary
    router_lineage: ComponentLineage
    deadline_time_ns: int | None = None
    expires_at_ns: int | None = None
    ttl_ns: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_id(self.routing_decision_id, field_name="routing_decision_id")
        validate_schema_version(self.schema_version)
        validate_timestamp_ns(self.decision_time_ns, field_name="decision_time_ns")
        if self.detection_ref.kind != ContractKind.DETECTION.value:
            raise ValueError("ROUTE_DETECTION_REF_KIND_INVALID")
        if not self.router_lineage.component_id or not self.router_lineage.component_version:
            raise ValueError("ROUTER_LINEAGE_IDENTITY_REQUIRED")
        if not isinstance(self.expert_domain, ExpertDomain):
            object.__setattr__(self, "expert_domain", ExpertDomain(str(self.expert_domain)))
        if not isinstance(self.route_action, RouteAction):
            object.__setattr__(self, "route_action", RouteAction(str(self.route_action)))
        if not isinstance(self.priority, RoutingPriority):
            object.__setattr__(self, "priority", RoutingPriority(str(self.priority)))
        object.__setattr__(self, "reason_codes", _normalized_strings(self.reason_codes, required=True))
        object.__setattr__(self, "required_capabilities", _normalized_strings(self.required_capabilities))
        object.__setattr__(self, "optional_capabilities", _normalized_strings(self.optional_capabilities))
        timestamps = (self.deadline_time_ns, self.expires_at_ns, self.ttl_ns)
        if self.route_action == RouteAction.ROUTE:
            if any(value is None for value in timestamps):
                raise ValueError("EXECUTABLE_ROUTE_TIMESTAMPS_REQUIRED")
            assert self.deadline_time_ns is not None and self.expires_at_ns is not None and self.ttl_ns is not None
            validate_timestamp_ns(self.deadline_time_ns, field_name="deadline_time_ns")
            validate_timestamp_ns(self.expires_at_ns, field_name="expires_at_ns")
            validate_timestamp_ns(self.ttl_ns, field_name="ttl_ns")
            if self.ttl_ns <= 0:
                raise ValueError("ROUTE_TTL_MUST_BE_POSITIVE")
            if self.deadline_time_ns <= self.decision_time_ns:
                raise ValueError("ROUTE_DEADLINE_NOT_FUTURE")
            if self.deadline_time_ns > self.expires_at_ns:
                raise ValueError("ROUTE_DEADLINE_AFTER_EXPIRATION")
            if self.expires_at_ns - self.decision_time_ns != self.ttl_ns:
                raise ValueError("ROUTE_TTL_MISMATCH")
        elif any(value is not None for value in timestamps):
            raise ValueError("NON_EXECUTABLE_ROUTE_TIMESTAMPS_FORBIDDEN")
        if not isinstance(self.metadata, dict):
            raise ValueError("ROUTING_METADATA_INVALID")


_ROUTING_ALLOWED = dataclass_field_names(RoutingDecisionV1)


def routing_decision_v1_to_dict(record: RoutingDecisionV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "routing_decision_id": record.routing_decision_id,
        "schema_version": record.schema_version,
        "detection_ref": contract_reference_to_dict(record.detection_ref),
        "decision_time_ns": record.decision_time_ns,
        "expert_domain": record.expert_domain.value,
        "route_action": record.route_action.value,
        "priority": record.priority.value,
        "reason_codes": list(record.reason_codes),
        "required_capabilities": list(record.required_capabilities),
        "optional_capabilities": list(record.optional_capabilities),
        "quality": quality_summary_to_dict(record.quality),
        "router_lineage": component_lineage_to_dict(record.router_lineage),
    }
    if record.deadline_time_ns is not None:
        body["deadline_time_ns"] = record.deadline_time_ns
        body["expires_at_ns"] = record.expires_at_ns
        body["ttl_ns"] = record.ttl_ns
    if record.metadata:
        body["metadata"] = dict(record.metadata)
    return body


def routing_decision_v1_from_dict(payload: dict[str, Any]) -> RoutingDecisionV1:
    reject_unknown_keys(payload, _ROUTING_ALLOWED)
    lineage = component_lineage_from_dict(payload.get("router_lineage"))
    if lineage is None:
        raise ValueError("ROUTER_LINEAGE_REQUIRED")
    return RoutingDecisionV1(
        routing_decision_id=str(payload["routing_decision_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        detection_ref=contract_reference_from_dict(payload["detection_ref"]),
        decision_time_ns=int(payload["decision_time_ns"]),
        expert_domain=ExpertDomain(str(payload["expert_domain"])),
        route_action=RouteAction(str(payload["route_action"])),
        priority=RoutingPriority(str(payload["priority"])),
        reason_codes=tuple(payload["reason_codes"]),
        required_capabilities=tuple(payload.get("required_capabilities") or ()),
        optional_capabilities=tuple(payload.get("optional_capabilities") or ()),
        deadline_time_ns=payload.get("deadline_time_ns"),
        expires_at_ns=payload.get("expires_at_ns"),
        ttl_ns=payload.get("ttl_ns"),
        quality=quality_summary_from_dict(payload["quality"]),
        router_lineage=lineage,
        metadata=dict(payload.get("metadata") or {}),
    )


__all__ = [
    "ExpertDomain",
    "RouteAction",
    "RoutingDecisionV1",
    "RoutingPriority",
    "routing_decision_v1_from_dict",
    "routing_decision_v1_to_dict",
]
