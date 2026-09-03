"""Deterministic replay fault rules and delivery scheduling (BUILD 07)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..contracts.event import EventV1
from ..temporal.validation import event_sort_key
from .errors import ReplayConfigurationError
from .models import (
    DeliveryAction,
    DisconnectPolicy,
    ReplayDeliveryEnvelope,
    ReplayMode,
    ThrottleOverflowAction,
)


@dataclass(frozen=True, slots=True)
class DelayRule:
    rule_id: str
    delay_ns: int
    provider_id: str | None = None
    event_type: str | None = None
    instrument_id: str | None = None
    event_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.delay_ns < 0:
            raise ReplayConfigurationError("DELAY_RULE_NEGATIVE", "delay_ns must be non-negative")
        object.__setattr__(self, "event_ids", tuple(sorted({str(value) for value in self.event_ids})))


@dataclass(frozen=True, slots=True)
class DropRule:
    rule_id: str
    provider_id: str | None = None
    event_type: str | None = None
    instrument_id: str | None = None
    event_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_ids", tuple(sorted({str(value) for value in self.event_ids})))


@dataclass(frozen=True, slots=True)
class DisconnectWindow:
    rule_id: str
    provider_id: str
    start_time_ns: int
    end_time_ns: int
    policy: DisconnectPolicy = DisconnectPolicy.DROP

    def __post_init__(self) -> None:
        if self.start_time_ns >= self.end_time_ns:
            raise ReplayConfigurationError(
                "DISCONNECT_WINDOW_INVALID",
                "disconnect window must satisfy start < end",
            )

    def contains(self, time_ns: int) -> bool:
        return self.start_time_ns <= time_ns < self.end_time_ns


@dataclass(frozen=True, slots=True)
class ThrottleRule:
    rule_id: str
    provider_id: str
    max_deliveries: int
    window_ns: int
    overflow_action: ThrottleOverflowAction = ThrottleOverflowAction.DROP

    def __post_init__(self) -> None:
        if self.max_deliveries <= 0:
            raise ReplayConfigurationError("THROTTLE_MAX_INVALID", "max_deliveries must be positive")
        if self.window_ns <= 0:
            raise ReplayConfigurationError("THROTTLE_WINDOW_INVALID", "window_ns must be positive")


@dataclass(frozen=True, slots=True)
class ReplayFaultProfile:
    """Serializable deterministic fault configuration."""

    profile_version: str = "1"
    delay_rules: tuple[DelayRule, ...] = ()
    drop_rules: tuple[DropRule, ...] = ()
    disconnect_windows: tuple[DisconnectWindow, ...] = ()
    throttle_rules: tuple[ThrottleRule, ...] = ()

    def has_faults(self) -> bool:
        return bool(self.delay_rules or self.drop_rules or self.disconnect_windows or self.throttle_rules)


def _matches_selector(
    event: EventV1,
    *,
    provider_id: str | None,
    event_type: str | None,
    instrument_id: str | None,
    event_ids: tuple[str, ...],
) -> bool:
    if event_ids and event.event_id not in event_ids:
        return False
    if provider_id is not None and event.source.provider_id != provider_id:
        return False
    if event_type is not None and event.event_type != event_type:
        return False
    if instrument_id is not None and event.instrument_id != instrument_id:
        return False
    return True


def _disconnect_window_at(
    windows: tuple[DisconnectWindow, ...],
    *,
    provider_id: str,
    time_ns: int,
) -> DisconnectWindow | None:
    for window in windows:
        if window.provider_id == provider_id and window.contains(time_ns):
            return window
    return None


def _apply_faults_to_event(
    event: EventV1,
    *,
    mode: ReplayMode,
    fault_profile: ReplayFaultProfile,
    replay_end_ns: int,
) -> ReplayDeliveryEnvelope:
    recorded = event.available_time_ns
    provider_id = event.source.provider_id
    matched: list[str] = []

    if mode == ReplayMode.OBSERVED_REPLAY and not fault_profile.has_faults():
        effective = recorded
        if effective > replay_end_ns:
            return ReplayDeliveryEnvelope(
                event_id=event.event_id,
                recorded_available_time_ns=recorded,
                effective_delivery_time_ns=effective,
                delivery_action=DeliveryAction.DROP,
                matched_fault_rules=("REPLAY_END",),
                provider_id=provider_id,
            )
        return ReplayDeliveryEnvelope(
            event_id=event.event_id,
            recorded_available_time_ns=recorded,
            effective_delivery_time_ns=effective,
            delivery_action=DeliveryAction.DELIVER,
            provider_id=provider_id,
        )

    # 1. Hard drop rules
    for rule in fault_profile.drop_rules:
        if _matches_selector(
            event,
            provider_id=rule.provider_id,
            event_type=rule.event_type,
            instrument_id=rule.instrument_id,
            event_ids=rule.event_ids,
        ):
            matched.append(rule.rule_id)
            return ReplayDeliveryEnvelope(
                event_id=event.event_id,
                recorded_available_time_ns=recorded,
                effective_delivery_time_ns=recorded,
                delivery_action=DeliveryAction.DROP,
                matched_fault_rules=tuple(matched),
                provider_id=provider_id,
            )

    # 2. Disconnect at recorded availability
    disconnect = _disconnect_window_at(
        fault_profile.disconnect_windows,
        provider_id=provider_id,
        time_ns=recorded,
    )
    if disconnect is not None:
        matched.append(disconnect.rule_id)
        if disconnect.policy == DisconnectPolicy.DROP:
            return ReplayDeliveryEnvelope(
                event_id=event.event_id,
                recorded_available_time_ns=recorded,
                effective_delivery_time_ns=recorded,
                delivery_action=DeliveryAction.DISCONNECT_DROP,
                matched_fault_rules=tuple(matched),
                provider_id=provider_id,
            )
        # BUFFER: release at reconnect time
        effective = max(recorded, disconnect.end_time_ns)
    else:
        effective = recorded

    # 3. Delay rules (last matching delay wins deterministically by rule order)
    action = DeliveryAction.DELIVER
    for rule in fault_profile.delay_rules:
        if _matches_selector(
            event,
            provider_id=rule.provider_id,
            event_type=rule.event_type,
            instrument_id=rule.instrument_id,
            event_ids=rule.event_ids,
        ):
            effective = max(effective, recorded + rule.delay_ns)
            action = DeliveryAction.DELAY
            matched.append(rule.rule_id)

    if effective > replay_end_ns:
        matched.append("REPLAY_END")
        return ReplayDeliveryEnvelope(
            event_id=event.event_id,
            recorded_available_time_ns=recorded,
            effective_delivery_time_ns=effective,
            delivery_action=DeliveryAction.DROP,
            matched_fault_rules=tuple(matched),
            provider_id=provider_id,
        )

    return ReplayDeliveryEnvelope(
        event_id=event.event_id,
        recorded_available_time_ns=recorded,
        effective_delivery_time_ns=effective,
        delivery_action=action,
        matched_fault_rules=tuple(matched),
        provider_id=provider_id,
    )


def _apply_throttle(
    envelopes: tuple[ReplayDeliveryEnvelope, ...],
    throttle_rules: tuple[ThrottleRule, ...],
) -> tuple[ReplayDeliveryEnvelope, ...]:
    if not throttle_rules:
        return envelopes
    by_event = {envelope.event_id: envelope for envelope in envelopes}
    adjusted: dict[str, ReplayDeliveryEnvelope] = dict(by_event)

    for rule in throttle_rules:
        provider_events = [
            envelope
            for envelope in envelopes
            if envelope.provider_id == rule.provider_id
            and envelope.delivery_action not in {DeliveryAction.DROP, DeliveryAction.DISCONNECT_DROP}
        ]
        ordered = sorted(
            provider_events,
            key=lambda row: (row.effective_delivery_time_ns, row.event_id),
        )
        window_start: int | None = None
        delivered_in_window = 0
        buffered: list[ReplayDeliveryEnvelope] = []
        for envelope in ordered:
            effective = envelope.effective_delivery_time_ns
            if window_start is None or effective >= window_start + rule.window_ns:
                window_start = effective
                delivered_in_window = 0
                buffered = []
            if delivered_in_window < rule.max_deliveries:
                delivered_in_window += 1
                continue
            if rule.overflow_action == ThrottleOverflowAction.DROP:
                adjusted[envelope.event_id] = ReplayDeliveryEnvelope(
                    event_id=envelope.event_id,
                    recorded_available_time_ns=envelope.recorded_available_time_ns,
                    effective_delivery_time_ns=envelope.effective_delivery_time_ns,
                    delivery_action=DeliveryAction.DROP,
                    matched_fault_rules=(*envelope.matched_fault_rules, rule.rule_id),
                    provider_id=envelope.provider_id,
                )
            else:
                release_time = window_start + rule.window_ns
                adjusted[envelope.event_id] = ReplayDeliveryEnvelope(
                    event_id=envelope.event_id,
                    recorded_available_time_ns=envelope.recorded_available_time_ns,
                    effective_delivery_time_ns=release_time,
                    delivery_action=DeliveryAction.THROTTLE_DELAY,
                    matched_fault_rules=(*envelope.matched_fault_rules, rule.rule_id),
                    provider_id=envelope.provider_id,
                )
    return tuple(adjusted[event_id] for event_id in sorted(adjusted))


def build_delivery_schedule(
    events: tuple[EventV1, ...],
    *,
    mode: ReplayMode,
    fault_profile: ReplayFaultProfile,
    replay_end_ns: int,
) -> tuple[ReplayDeliveryEnvelope, ...]:
    """Precompute deterministic delivery envelopes — input order independent."""
    ordered_events = sorted(events, key=event_sort_key)
    preliminary = tuple(
        _apply_faults_to_event(
            event,
            mode=mode,
            fault_profile=fault_profile,
            replay_end_ns=replay_end_ns,
        )
        for event in ordered_events
    )
    return _apply_throttle(preliminary, fault_profile.throttle_rules)


def fault_profile_to_dict(profile: ReplayFaultProfile) -> dict[str, Any]:
    return {
        "profile_version": profile.profile_version,
        "delay_rules": [
            {
                "rule_id": rule.rule_id,
                "delay_ns": rule.delay_ns,
                "provider_id": rule.provider_id,
                "event_type": rule.event_type,
                "instrument_id": rule.instrument_id,
                "event_ids": list(rule.event_ids),
            }
            for rule in profile.delay_rules
        ],
        "drop_rules": [
            {
                "rule_id": rule.rule_id,
                "provider_id": rule.provider_id,
                "event_type": rule.event_type,
                "instrument_id": rule.instrument_id,
                "event_ids": list(rule.event_ids),
            }
            for rule in profile.drop_rules
        ],
        "disconnect_windows": [
            {
                "rule_id": window.rule_id,
                "provider_id": window.provider_id,
                "start_time_ns": window.start_time_ns,
                "end_time_ns": window.end_time_ns,
                "policy": window.policy.value,
            }
            for window in profile.disconnect_windows
        ],
        "throttle_rules": [
            {
                "rule_id": rule.rule_id,
                "provider_id": rule.provider_id,
                "max_deliveries": rule.max_deliveries,
                "window_ns": rule.window_ns,
                "overflow_action": rule.overflow_action.value,
            }
            for rule in profile.throttle_rules
        ],
    }


__all__ = [
    "DelayRule",
    "DisconnectWindow",
    "DropRule",
    "ReplayFaultProfile",
    "ThrottleRule",
    "build_delivery_schedule",
    "fault_profile_to_dict",
]
