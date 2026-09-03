"""Futures macro / fundamental event engine (F7) — calendar risk, not equity catalyst."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from ..providers.contracts import ProviderResult

MACRO_EVENTS_VERSION = "futures_macro_events_v1"
DEFAULT_EVENT_WINDOW_HOURS = 48
SURPRISE_ELEVATED_THRESHOLD = 1.5


class MacroRiskRegime(StrEnum):
    ELEVATED = "ELEVATED"
    NORMAL = "NORMAL"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class MacroEventSnapshot:
    instrument_family: str
    upcoming_event_id: str | None = None
    upcoming_event_type: str | None = None
    upcoming_scheduled_time: str | None = None
    nearest_past_event_id: str | None = None
    nearest_past_event_type: str | None = None
    event_window_active: bool = False
    surprise_zscore: float | None = None
    macro_risk_regime: MacroRiskRegime = MacroRiskRegime.UNAVAILABLE
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = "macro.fixture.futures_macro"


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _decision_time_iso(decision_time: int | str) -> str:
    if isinstance(decision_time, int):
        secs = decision_time // 1_000_000_000
        dt = datetime.fromtimestamp(secs, tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.000000000Z")
    return str(decision_time)


def filter_pit_events(
    events: list[dict[str, Any]],
    decision_time: int | str,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Return PIT-valid macro rows using release_time or scheduled_time."""
    decision_iso = _decision_time_iso(decision_time)
    decision_dt = _parse_time(decision_iso)
    quality_flags: list[str] = []
    pit_valid: list[dict[str, Any]] = []

    for event in events:
        release_time = str(event.get("release_time") or "")
        scheduled_time = str(event.get("scheduled_time") or "")
        anchor = release_time or scheduled_time
        anchor_dt = _parse_time(anchor)
        if anchor_dt is None:
            continue
        if decision_dt is not None and anchor_dt > decision_dt:
            continue
        pit_valid.append(event)

    if not pit_valid and events:
        quality_flags.append("MACRO_CONSENSUS_MISSING")
    return pit_valid, quality_flags


def compute_surprise_zscore(consensus: float | None, actual: float | None) -> float | None:
    if consensus is None or actual is None:
        return None
    diff = abs(actual - consensus)
    scale = max(abs(consensus), 0.01)
    return round(diff / scale, 6)


def event_window_active(
    decision_time: int | str,
    scheduled_time: str,
    *,
    window_hours: int = DEFAULT_EVENT_WINDOW_HOURS,
) -> bool:
    decision_dt = _parse_time(_decision_time_iso(decision_time))
    scheduled_dt = _parse_time(scheduled_time)
    if decision_dt is None or scheduled_dt is None:
        return False
    if scheduled_dt < decision_dt:
        return False
    delta_hours = (scheduled_dt - decision_dt).total_seconds() / 3600.0
    return 0 <= delta_hours <= window_hours


def macro_snapshot_to_dict(snapshot: MacroEventSnapshot) -> dict[str, Any]:
    return {
        "instrument_family": snapshot.instrument_family,
        "upcoming_event_id": snapshot.upcoming_event_id,
        "upcoming_event_type": snapshot.upcoming_event_type,
        "upcoming_scheduled_time": snapshot.upcoming_scheduled_time,
        "nearest_past_event_id": snapshot.nearest_past_event_id,
        "nearest_past_event_type": snapshot.nearest_past_event_type,
        "event_window_active": snapshot.event_window_active,
        "surprise_zscore": snapshot.surprise_zscore,
        "macro_risk_regime": snapshot.macro_risk_regime.value,
        "quality_flags": list(snapshot.quality_flags),
        "provenance_ref": snapshot.provenance_ref,
        "macro_events_version": MACRO_EVENTS_VERSION,
    }


def build_macro_event_snapshot(
    events: list[dict[str, Any]],
    *,
    instrument_family: str,
    decision_time: int | str,
    window_hours: int = DEFAULT_EVENT_WINDOW_HOURS,
) -> MacroEventSnapshot:
    decision_dt = _parse_time(_decision_time_iso(decision_time))
    quality_flags: list[str] = []

    upcoming: dict[str, Any] | None = None
    nearest_past: dict[str, Any] | None = None
    best_surprise: float | None = None

    for event in events:
        scheduled = str(event.get("scheduled_time", ""))
        scheduled_dt = _parse_time(scheduled)
        if scheduled_dt is None or decision_dt is None:
            continue
        if scheduled_dt >= decision_dt:
            if upcoming is None or scheduled_dt < _parse_time(str(upcoming.get("scheduled_time", "")) or ""):
                upcoming = event
        else:
            if nearest_past is None or scheduled_dt > _parse_time(
                str(nearest_past.get("scheduled_time", "")) or ""
            ):
                nearest_past = event
        consensus = event.get("consensus")
        actual = event.get("actual")
        if consensus is not None and actual is not None:
            z = compute_surprise_zscore(float(consensus), float(actual))
            if z is not None and (best_surprise is None or z > best_surprise):
                best_surprise = z

    window_active = False
    upcoming_type = None
    upcoming_id = None
    upcoming_scheduled = None
    if upcoming is not None:
        upcoming_type = str(upcoming.get("event_type", ""))
        upcoming_id = str(upcoming.get("event_id", ""))
        upcoming_scheduled = str(upcoming.get("scheduled_time", ""))
        window_active = event_window_active(
            decision_time,
            upcoming_scheduled,
            window_hours=window_hours,
        )

    regime = MacroRiskRegime.NORMAL
    if upcoming is None and nearest_past is None:
        regime = MacroRiskRegime.UNAVAILABLE
        quality_flags.append("MACRO_CONSENSUS_MISSING")
    elif window_active or (
        best_surprise is not None and best_surprise >= SURPRISE_ELEVATED_THRESHOLD
    ):
        regime = MacroRiskRegime.ELEVATED

    return MacroEventSnapshot(
        instrument_family=instrument_family,
        upcoming_event_id=upcoming_id,
        upcoming_event_type=upcoming_type,
        upcoming_scheduled_time=upcoming_scheduled,
        nearest_past_event_id=str(nearest_past.get("event_id", "")) if nearest_past else None,
        nearest_past_event_type=str(nearest_past.get("event_type", "")) if nearest_past else None,
        event_window_active=window_active,
        surprise_zscore=best_surprise,
        macro_risk_regime=regime,
        quality_flags=tuple(dict.fromkeys(quality_flags)),
    )


def macro_events_payload(
    macro_result: ProviderResult,
    *,
    instrument_family: str,
    decision_time: int | str,
) -> dict[str, Any]:
    """Build workspace macro event payload with fail-closed semantics."""
    if macro_result.status != "available" or not macro_result.events:
        return {
            "available": False,
            "reason": macro_result.reason_code or "MACRO_EVENTS_UNAVAILABLE",
            "futures_macro_available": False,
            "macro_events_version": MACRO_EVENTS_VERSION,
        }

    events = [row for row in macro_result.events if isinstance(row, dict)]
    all_events = events
    pit_events, pit_flags = filter_pit_events(events, decision_time)

    snapshot = build_macro_event_snapshot(
        all_events,
        instrument_family=instrument_family,
        decision_time=decision_time,
    )
    combined_flags = tuple(dict.fromkeys(list(snapshot.quality_flags) + pit_flags))
    snapshot = MacroEventSnapshot(
        instrument_family=snapshot.instrument_family,
        upcoming_event_id=snapshot.upcoming_event_id,
        upcoming_event_type=snapshot.upcoming_event_type,
        upcoming_scheduled_time=snapshot.upcoming_scheduled_time,
        nearest_past_event_id=snapshot.nearest_past_event_id,
        nearest_past_event_type=snapshot.nearest_past_event_type,
        event_window_active=snapshot.event_window_active,
        surprise_zscore=snapshot.surprise_zscore,
        macro_risk_regime=snapshot.macro_risk_regime,
        quality_flags=combined_flags,
        provenance_ref=snapshot.provenance_ref,
    )

    payload = macro_snapshot_to_dict(snapshot)
    available = snapshot.macro_risk_regime != MacroRiskRegime.UNAVAILABLE
    payload["available"] = available
    return {
        "available": available,
        "macro_event_snapshot": payload,
        "futures_macro_available": available,
        "macro_risk_regime": snapshot.macro_risk_regime.value,
        "event_window_active": snapshot.event_window_active,
        "quality_flags": list(combined_flags),
        "macro_events_version": MACRO_EVENTS_VERSION,
    }


__all__ = [
    "DEFAULT_EVENT_WINDOW_HOURS",
    "MACRO_EVENTS_VERSION",
    "MacroRiskRegime",
    "MacroEventSnapshot",
    "build_macro_event_snapshot",
    "compute_surprise_zscore",
    "event_window_active",
    "filter_pit_events",
    "macro_events_payload",
    "macro_snapshot_to_dict",
]
