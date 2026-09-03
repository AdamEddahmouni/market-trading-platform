"""Provider conflict detection (BUILD 04)."""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts.event import EventV1
from .models import (
    FindingSeverity,
    IntelligenceCapability,
    QualityFinding,
    QualityFindingCode,
    capability_for_event_type,
)
from .policy import QualityPolicy
from .validators import quote_mid_price, validate_event_structure


@dataclass(frozen=True, slots=True)
class ComparableObservation:
    event: EventV1
    capability: IntelligenceCapability
    measurement_key: str
    value: float


def _measurement_key(event: EventV1, capability: IntelligenceCapability) -> str | None:
    if capability == IntelligenceCapability.QUOTES:
        return "mid_price"
    if capability == IntelligenceCapability.TRADES:
        px = event.payload.get("price") or event.payload.get("px")
        return "trade_price" if px is not None else None
    return None


def _measurement_value(event: EventV1, capability: IntelligenceCapability, key: str) -> float | None:
    if key == "mid_price":
        return quote_mid_price(event.payload)
    if key == "trade_price":
        try:
            return float(event.payload.get("price") or event.payload.get("px"))
        except (TypeError, ValueError):
            return None
    return None


def build_comparable_observations(events: list[EventV1]) -> list[ComparableObservation]:
    rows: list[ComparableObservation] = []
    for event in events:
        capability = capability_for_event_type(event.event_type)
        if capability is None:
            continue
        key = _measurement_key(event, capability)
        if key is None:
            continue
        value = _measurement_value(event, capability, key)
        if value is None:
            continue
        rows.append(
            ComparableObservation(
                event=event,
                capability=capability,
                measurement_key=key,
                value=value,
            )
        )
    return rows


def _structurally_valid_for_conflict(event: EventV1) -> bool:
    findings = validate_event_structure(event)
    blocking = {
        QualityFindingCode.CROSSED_BOOK.value,
        QualityFindingCode.INVALID_QUOTE.value,
        QualityFindingCode.FUTURE_INFORMATION.value,
    }
    return not any(finding.code in blocking for finding in findings)


def detect_provider_conflicts(
    events: list[EventV1],
    *,
    policy: QualityPolicy,
    instrument_id: str | None = None,
) -> tuple[QualityFinding, ...]:
    """Detect conflicting valid observations from independent providers."""
    eligible_events = [event for event in events if _structurally_valid_for_conflict(event)]
    comparable = [
        row
        for row in build_comparable_observations(eligible_events)
        if instrument_id is None or row.event.instrument_id == instrument_id
    ]
    findings: list[QualityFinding] = []
    grouped: dict[tuple[str, IntelligenceCapability, str, str | None], list[ComparableObservation]] = {}
    for row in comparable:
        key = (row.measurement_key, row.capability, row.event.instrument_id or "", row.measurement_key)
        grouped.setdefault(key, []).append(row)

    for (measurement_key, capability, inst, _), rows in sorted(grouped.items()):
        if len(rows) < 2:
            continue
        providers = {row.event.source.provider_id for row in rows}
        if len(providers) < 2:
            continue
        values = [row.value for row in rows]
        baseline = values[0]
        if baseline == 0:
            continue
        tolerance = policy.price_conflict_tolerance_bps / 10_000.0
        conflict = any(abs(value - baseline) / abs(baseline) > tolerance for value in values[1:])
        if not conflict:
            continue
        findings.append(
            QualityFinding(
                code=QualityFindingCode.PROVIDER_CONFLICT.value,
                severity=FindingSeverity.WARNING,
                message=(
                    f"PROVIDER_CONFLICT: {capability.value} {measurement_key} for {inst or 'GLOBAL'} "
                    f"differs beyond tolerance across providers {sorted(providers)}"
                ),
                capability=capability,
                instrument_id=inst or None,
                observed_at_ns=max(row.event.available_time_ns for row in rows),
                evidence={
                    "providers": sorted(providers),
                    "values": {row.event.source.provider_id: row.value for row in rows},
                    "tolerance_bps": policy.price_conflict_tolerance_bps,
                    "event_ids": [row.event.event_id for row in rows],
                },
            )
        )
    return tuple(findings)


__all__ = [
    "ComparableObservation",
    "build_comparable_observations",
    "detect_provider_conflicts",
]
