"""Map platform taxonomies into hot-path quality counters."""

from __future__ import annotations

from market_platform_foundation.intelligence.normalization.errors import NormalizationErrorCode
from market_platform_foundation.intelligence.quality.models import QualityFindingCode
from market_platform_foundation.intelligence.replay.models import DeliveryAction
from market_platform_foundation.intelligence.temporal.models import TemporalViolationCode

from .models import HotPathQualityCounters

_PIT_REJECT = frozenset(
    {
        QualityFindingCode.FUTURE_INFORMATION.value,
        TemporalViolationCode.FUTURE_INFORMATION.value,
    }
)
_DUPLICATE = frozenset(
    {
        QualityFindingCode.EXACT_DUPLICATE.value,
        TemporalViolationCode.EXACT_DUPLICATE.value,
    }
)
_CONFLICT = frozenset(
    {
        QualityFindingCode.CONFLICTING_DUPLICATE.value,
        QualityFindingCode.PROVIDER_CONFLICT.value,
        TemporalViolationCode.CONFLICTING_DUPLICATE.value,
    }
)
_STALE = frozenset(
    {
        QualityFindingCode.STALE_INFORMATION.value,
        QualityFindingCode.STALE_INFERENCE.value,
        QualityFindingCode.BORROW_STALE.value,
        QualityFindingCode.SHORT_INTEREST_STALE.value,
        TemporalViolationCode.STALE_INFORMATION.value,
    }
)
_ENTITLEMENT = frozenset(
    {
        QualityFindingCode.NOT_ENTITLED.value,
        QualityFindingCode.NOT_SUBSCRIBED.value,
    }
)
_UNKNOWN_IDENTITY = frozenset(
    {
        NormalizationErrorCode.INVALID_INSTRUMENT.value,
        NormalizationErrorCode.INVALID_PROVIDER_IDENTIFIER.value,
    }
)
_PARSER = frozenset(code.value for code in NormalizationErrorCode)


def apply_delivery_action(counters: HotPathQualityCounters, action: DeliveryAction) -> HotPathQualityCounters:
    if action == DeliveryAction.ENTITLEMENT_BLOCK:
        return HotPathQualityCounters(**{**counters.to_dict(), "entitlement_blocked": counters.entitlement_blocked + 1})
    if action in {
        DeliveryAction.DELIVER,
        DeliveryAction.DELAY,
        DeliveryAction.THROTTLE_DELAY,
    }:
        return HotPathQualityCounters(**{**counters.to_dict(), "received": counters.received + 1})
    return counters


def apply_finding_code(counters: HotPathQualityCounters, code: str) -> HotPathQualityCounters:
    data = counters.to_dict()
    if code in _PIT_REJECT:
        data["pit_rejected"] += 1
    elif code in _DUPLICATE:
        data["duplicates"] += 1
    elif code in _CONFLICT:
        data["conflicts"] += 1
    elif code in _STALE:
        data["stale"] += 1
    elif code in _ENTITLEMENT:
        data["entitlement_blocked"] += 1
    elif code in _UNKNOWN_IDENTITY:
        data["unknown_identity"] += 1
    elif code in _PARSER:
        data["parser_failures"] += 1
    return HotPathQualityCounters(**data)


def record_normalized_success(counters: HotPathQualityCounters, *, count: int = 1) -> HotPathQualityCounters:
    data = counters.to_dict()
    data["normalized"] += count
    data["pit_accepted"] += count
    return HotPathQualityCounters(**data)


def record_router_failure(counters: HotPathQualityCounters, *, count: int = 1) -> HotPathQualityCounters:
    data = counters.to_dict()
    data["router_failures"] += count
    return HotPathQualityCounters(**data)


__all__ = [
    "apply_delivery_action",
    "apply_finding_code",
    "record_normalized_success",
    "record_router_failure",
]
