"""Quality and capability policy configuration (BUILD 04)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import DecisionAction, IntelligenceCapability


@dataclass(frozen=True, slots=True)
class QualityPolicy:
    """Immutable policy for mapping findings and capability state to decisions."""

    policy_id: str = "default"
    policy_version: str = "1"
    crossed_book_action: DecisionAction = DecisionAction.FAIL_CLOSED
    invalid_quote_action: DecisionAction = DecisionAction.FAIL_CLOSED
    future_information_action: DecisionAction = DecisionAction.FAIL_CLOSED
    provider_disconnect_action: DecisionAction = DecisionAction.FAIL_CLOSED
    required_unavailable_action: DecisionAction = DecisionAction.FAIL_CLOSED
    optional_unavailable_action: DecisionAction = DecisionAction.DEGRADE
    unknown_mandatory_action: DecisionAction = DecisionAction.ABSTAIN
    unknown_optional_action: DecisionAction = DecisionAction.DEGRADE
    stale_borrow_action: DecisionAction = DecisionAction.ABSTAIN
    stale_short_interest_action: DecisionAction = DecisionAction.DEGRADE
    provider_conflict_action: DecisionAction = DecisionAction.DEGRADE
    require_provider_agreement: bool = False
    allow_degraded_single_source_on_conflict: bool = True
    price_conflict_tolerance_bps: float = 10.0
    freshness_max_age_ns: dict[str, int] | None = None

    def __post_init__(self) -> None:
        if self.price_conflict_tolerance_bps < 0:
            raise ValueError("PRICE_CONFLICT_TOLERANCE_BPS_NEGATIVE")
        if self.freshness_max_age_ns is not None:
            if not isinstance(self.freshness_max_age_ns, dict):
                raise ValueError("FRESHNESS_MAX_AGE_NS_INVALID")
            for key, value in self.freshness_max_age_ns.items():
                if value < 0:
                    raise ValueError("FRESHNESS_MAX_AGE_NS_NEGATIVE")

    def max_age_for_capability(self, capability: IntelligenceCapability) -> int | None:
        if not self.freshness_max_age_ns:
            return None
        return self.freshness_max_age_ns.get(capability.value)

    def with_overrides(self, **kwargs: Any) -> QualityPolicy:
        current = {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "crossed_book_action": self.crossed_book_action,
            "invalid_quote_action": self.invalid_quote_action,
            "future_information_action": self.future_information_action,
            "provider_disconnect_action": self.provider_disconnect_action,
            "required_unavailable_action": self.required_unavailable_action,
            "optional_unavailable_action": self.optional_unavailable_action,
            "unknown_mandatory_action": self.unknown_mandatory_action,
            "unknown_optional_action": self.unknown_optional_action,
            "stale_borrow_action": self.stale_borrow_action,
            "stale_short_interest_action": self.stale_short_interest_action,
            "provider_conflict_action": self.provider_conflict_action,
            "require_provider_agreement": self.require_provider_agreement,
            "allow_degraded_single_source_on_conflict": self.allow_degraded_single_source_on_conflict,
            "price_conflict_tolerance_bps": self.price_conflict_tolerance_bps,
            "freshness_max_age_ns": self.freshness_max_age_ns,
        }
        current.update(kwargs)
        return QualityPolicy(**current)


DEFAULT_QUALITY_POLICY = QualityPolicy()


__all__ = ["DEFAULT_QUALITY_POLICY", "QualityPolicy"]
