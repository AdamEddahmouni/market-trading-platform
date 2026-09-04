"""Versioned deterministic BUILD 09 detector and router policy."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from types import MappingProxyType
from typing import Mapping

from ...canonical import canonical_bytes, sha256_bytes
from ..contracts import ExpertDomain, RoutingPriority, SemanticEventType
from ..quality import IntelligenceCapability

ONE_SECOND_NS = 1_000_000_000
ONE_MINUTE_NS = 60 * ONE_SECOND_NS


@dataclass(frozen=True, slots=True)
class DetectionPolicyV1:
    policy_id: str = "event-detector-policy"
    policy_version: str = "1"
    order_flow_window_ns: int = 300 * ONE_SECOND_NS
    order_flow_threshold: float = 0.15
    liquidity_entry_bps: float = 50.0
    liquidity_exit_bps: float = 30.0
    short_interest_relative_change_threshold: float = 0.10
    allow_degraded_inputs: bool = False
    max_scopes: int = 1024
    max_seen_news_events: int = 4096

    def __post_init__(self) -> None:
        if not self.policy_id or not self.policy_version:
            raise ValueError("DETECTION_POLICY_IDENTITY_INVALID")
        if (
            isinstance(self.order_flow_window_ns, bool)
            or not isinstance(self.order_flow_window_ns, int)
            or self.order_flow_window_ns <= 0
        ):
            raise ValueError("ORDER_FLOW_WINDOW_NS_INVALID")
        if (
            isinstance(self.order_flow_threshold, bool)
            or not isinstance(self.order_flow_threshold, (int, float))
            or not math.isfinite(float(self.order_flow_threshold))
            or self.order_flow_threshold <= 0
        ):
            raise ValueError("ORDER_FLOW_THRESHOLD_INVALID")
        if self.liquidity_entry_bps <= 0 or self.liquidity_exit_bps < 0:
            raise ValueError("LIQUIDITY_THRESHOLDS_INVALID")
        if self.liquidity_exit_bps >= self.liquidity_entry_bps:
            raise ValueError("LIQUIDITY_EXIT_MUST_BE_BELOW_ENTRY")
        if self.short_interest_relative_change_threshold <= 0:
            raise ValueError("SHORT_INTEREST_THRESHOLD_INVALID")
        if self.max_scopes <= 0 or self.max_seen_news_events <= 0:
            raise ValueError("DETECTOR_STATE_BOUND_INVALID")

    @property
    def identity(self) -> str:
        payload = {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "order_flow_window_ns": self.order_flow_window_ns,
            "order_flow_threshold": self.order_flow_threshold,
            "liquidity_entry_bps": self.liquidity_entry_bps,
            "liquidity_exit_bps": self.liquidity_exit_bps,
            "short_interest_relative_change_threshold": self.short_interest_relative_change_threshold,
            "allow_degraded_inputs": self.allow_degraded_inputs,
            "max_scopes": self.max_scopes,
            "max_seen_news_events": self.max_seen_news_events,
        }
        return f"DTPOL-{sha256_bytes(canonical_bytes(payload))}"


@dataclass(frozen=True, slots=True)
class RouteTemplate:
    semantic_event_type: SemanticEventType
    expert_domain: ExpertDomain
    required_capabilities: tuple[IntelligenceCapability, ...]
    optional_capabilities: tuple[IntelligenceCapability, ...]
    base_priority: RoutingPriority
    deadline_offset_ns: int
    ttl_ns: int
    degrade_on_optional_missing: bool = True


_DEFAULT_TEMPLATES = {
    SemanticEventType.ORDER_FLOW_REVERSAL: RouteTemplate(
        SemanticEventType.ORDER_FLOW_REVERSAL,
        ExpertDomain.MICROSTRUCTURE,
        (IntelligenceCapability.QUOTES, IntelligenceCapability.TRADES),
        (IntelligenceCapability.DEPTH,),
        RoutingPriority.HIGH,
        5 * ONE_SECOND_NS,
        30 * ONE_SECOND_NS,
        False,
    ),
    SemanticEventType.LIQUIDITY_EVENT: RouteTemplate(
        SemanticEventType.LIQUIDITY_EVENT,
        ExpertDomain.MICROSTRUCTURE,
        (IntelligenceCapability.QUOTES,),
        (IntelligenceCapability.DEPTH,),
        RoutingPriority.HIGH,
        5 * ONE_SECOND_NS,
        30 * ONE_SECOND_NS,
    ),
    SemanticEventType.UNUSUAL_OPTIONS_ACTIVITY: RouteTemplate(
        SemanticEventType.UNUSUAL_OPTIONS_ACTIVITY,
        ExpertDomain.DERIVATIVES,
        (IntelligenceCapability.OPTIONS_CHAIN,),
        (),
        RoutingPriority.HIGH,
        30 * ONE_SECOND_NS,
        5 * ONE_MINUTE_NS,
    ),
    SemanticEventType.BORROW_CHANGE: RouteTemplate(
        SemanticEventType.BORROW_CHANGE,
        ExpertDomain.POSITIONING_BORROW,
        (IntelligenceCapability.SHORT_INTEREST,),
        (IntelligenceCapability.BORROW,),
        RoutingPriority.NORMAL,
        15 * ONE_MINUTE_NS,
        4 * 60 * ONE_MINUTE_NS,
    ),
    SemanticEventType.NEWS_EVENT: RouteTemplate(
        SemanticEventType.NEWS_EVENT,
        ExpertDomain.NARRATIVE_SENTIMENT,
        (IntelligenceCapability.NEWS,),
        (IntelligenceCapability.FILINGS,),
        RoutingPriority.NORMAL,
        2 * ONE_MINUTE_NS,
        30 * ONE_MINUTE_NS,
    ),
    SemanticEventType.REGIME_SHIFT: RouteTemplate(
        SemanticEventType.REGIME_SHIFT,
        ExpertDomain.REGIME_CROSS_ASSET,
        (IntelligenceCapability.MACRO,),
        (IntelligenceCapability.QUOTES,),
        RoutingPriority.HIGH,
        5 * ONE_MINUTE_NS,
        60 * ONE_MINUTE_NS,
    ),
}


@dataclass(frozen=True, slots=True)
class RoutingPolicyV1:
    policy_id: str = "smart-router-policy"
    policy_version: str = "1"
    allow_degraded: bool = True
    severity_promotions: bool = True
    deadline_overrides_ns: Mapping[SemanticEventType, int] = field(default_factory=dict)
    ttl_overrides_ns: Mapping[SemanticEventType, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.policy_id:
            raise ValueError("ROUTING_POLICY_IDENTITY_INVALID")
        object.__setattr__(self, "deadline_overrides_ns", MappingProxyType(dict(self.deadline_overrides_ns)))
        object.__setattr__(self, "ttl_overrides_ns", MappingProxyType(dict(self.ttl_overrides_ns)))
        for mapping in (self.deadline_overrides_ns, self.ttl_overrides_ns):
            for value in mapping.values():
                if (
                    isinstance(value, bool)
                    or not isinstance(value, int)
                    or value <= 0
                ):
                    raise ValueError("ROUTING_TIME_OFFSET_INVALID")
        for event_type in SemanticEventType:
            template = self.template_for(event_type, validate=False)
            if template.deadline_offset_ns <= 0 or template.ttl_ns <= 0:
                raise ValueError("ROUTING_TIME_OFFSETS_MUST_BE_POSITIVE")
            if template.deadline_offset_ns > template.ttl_ns:
                raise ValueError("ROUTING_DEADLINE_AFTER_TTL")

    def template_for(self, event_type: SemanticEventType, *, validate: bool = True) -> RouteTemplate:
        _ = validate
        base = _DEFAULT_TEMPLATES[event_type]
        return RouteTemplate(
            semantic_event_type=base.semantic_event_type,
            expert_domain=base.expert_domain,
            required_capabilities=base.required_capabilities,
            optional_capabilities=base.optional_capabilities,
            base_priority=base.base_priority,
            deadline_offset_ns=self.deadline_overrides_ns.get(event_type, base.deadline_offset_ns),
            ttl_ns=self.ttl_overrides_ns.get(event_type, base.ttl_ns),
            degrade_on_optional_missing=base.degrade_on_optional_missing,
        )

    @property
    def identity(self) -> str:
        templates = []
        for event_type in SemanticEventType:
            row = self.template_for(event_type)
            templates.append(
                {
                    "event_type": event_type.value,
                    "expert_domain": row.expert_domain.value,
                    "required": [cap.value for cap in row.required_capabilities],
                    "optional": [cap.value for cap in row.optional_capabilities],
                    "base_priority": row.base_priority.value,
                    "deadline_offset_ns": row.deadline_offset_ns,
                    "ttl_ns": row.ttl_ns,
                }
            )
        payload = {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "allow_degraded": self.allow_degraded,
            "severity_promotions": self.severity_promotions,
            "templates": templates,
        }
        return f"RTPOL-{sha256_bytes(canonical_bytes(payload))}"


__all__ = ["DetectionPolicyV1", "RouteTemplate", "RoutingPolicyV1"]
