"""Intraday chain snapshot contract for O11 0DTE prerequisites.

One record = one underlying-level intraday option-chain snapshot with a
bitemporal ``event_time_ns`` / ``available_time_ns`` pair, mirroring the
event-time/available-time discipline of the ``cboe_options`` evidence
contracts (imported read-only; never edited).

Deterministic 0DTE rule
-----------------------
A snapshot is 0DTE iff the expiration timestamp and the snapshot's event time
fall on the **same America/New_York calendar date**. All calendar conversions
run through :data:`ET_TIMEZONE_NAME` via :mod:`zoneinfo`, because US equity
option expirations settle against the **16:00 ET session close**
(:data:`SESSION_CLOSE_ET_HOUR`). The ET session close anchors the trading-day
boundary: the "0DTE day" spans from the prior session close to 16:00 ET of the
expiry day, which calendar-date equality in ET implements exactly — a snapshot
stamped any wall-clock time on expiry day in ET (including post-close up to
local midnight) still classifies as same-expiry-day. Comparing UTC dates
instead would misclassify evening-ET snapshots across the midnight-UTC
boundary. DST transitions are resolved by ``zoneinfo`` using wall-clock ET
dates; no fixed UTC offset is ever assumed.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

# cboe_options vocabulary — imported only, never modified.
from market_platform_foundation.cboe_options.contracts import (  # noqa: F401  (re-exported vocabulary)
    AvailabilityPrecision,
    CoverageScope,
    OptionsFeatureLayer,
    PitHistoryClass,
)

ET_TIMEZONE_NAME = "America/New_York"
_ET = ZoneInfo(ET_TIMEZONE_NAME)
SESSION_CLOSE_ET_HOUR = 16
SESSION_CLOSE_ET_MINUTE = 0
_NANOSECONDS_PER_SECOND = 1_000_000_000


class ZeroDTESnapshotLifecycle(StrEnum):
    OBSERVED = "OBSERVED"
    RETRACTED = "RETRACTED"


@dataclass(frozen=True, slots=True)
class IntradayChainSnapshotRecord:
    """One underlying-level intraday chain snapshot (contract fixture shape).

    Quotes/strikes/multiplier only — no Greeks, no IV, no dealer positioning.
    ``research_only`` is fixed ``True``: nothing here may feed a directive.
    """

    underlying: str
    event_time_ns: int
    available_time_ns: int
    expiration_timestamp_ns: int
    strikes: tuple[float, ...]
    multiplier: int | None
    best_bid: float | None
    best_ask: float | None
    publisher: str
    retrieved_time: str
    ingested_time: str
    content_hash: str
    availability_precision: AvailabilityPrecision = AvailabilityPrecision.TIMESTAMP
    coverage_scope: CoverageScope = CoverageScope.COVERAGE_SCOPE_UNCERTAIN
    history_class: PitHistoryClass = PitHistoryClass.PROSPECTIVE_VERSIONED_PIT
    feature_layer: OptionsFeatureLayer = OptionsFeatureLayer.RAW
    source_symbol: str = ""
    quality_flags: tuple[str, ...] = ()
    provenance_ref: str = ""
    lifecycle: str = ZeroDTESnapshotLifecycle.OBSERVED.value
    research_only: bool = True
    predictive: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.strikes, tuple):
            raise TypeError("strikes must be an immutable tuple")
        if any(not isinstance(strike, (int, float)) or isinstance(strike, bool) for strike in self.strikes):
            raise TypeError("strikes entries must be numeric")
        for name in ("event_time_ns", "available_time_ns", "expiration_timestamp_ns"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer epoch nanosecond value")
        for name in ("best_bid", "best_ask"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool)):
                raise TypeError(f"{name} must be numeric or None")


def et_calendar_date(epoch_ns: int) -> str:
    """ISO calendar date of ``epoch_ns`` in America/New_York wall clock."""
    moment = datetime.fromtimestamp(epoch_ns / _NANOSECONDS_PER_SECOND, tz=timezone.utc)
    return moment.astimezone(_ET).date().isoformat()


def expiration_session_close_ns(expiration_timestamp_ns: int) -> int:
    """Epoch ns of the 16:00 America/New_York session close on the expiry's ET calendar date."""
    expiry_date = et_calendar_date(expiration_timestamp_ns)
    close_wall = datetime.fromisoformat(f"{expiry_date}T{SESSION_CLOSE_ET_HOUR:02d}:{SESSION_CLOSE_ET_MINUTE:02d}:00")
    return int(close_wall.replace(tzinfo=_ET).timestamp() * _NANOSECONDS_PER_SECOND)


def snapshot_dte_hours(record: IntradayChainSnapshotRecord) -> float:
    """Hours between the snapshot event time and expiration (negative once expired)."""
    return (record.expiration_timestamp_ns - record.event_time_ns) / (
        _NANOSECONDS_PER_SECOND * 3600.0
    )


def is_zero_dte_snapshot(record: IntradayChainSnapshotRecord) -> bool:
    """Deterministic rule: same America/New_York calendar date, session-close anchored."""
    return et_calendar_date(record.event_time_ns) == et_calendar_date(record.expiration_timestamp_ns)


def snapshot_to_dict(record: IntradayChainSnapshotRecord) -> dict[str, Any]:
    data: dict[str, Any] = {f.name: getattr(record, f.name) for f in fields(record)}
    data["availability_precision"] = record.availability_precision.value
    data["coverage_scope"] = record.coverage_scope.value
    data["history_class"] = record.history_class.value
    data["feature_layer"] = record.feature_layer.value
    data["quality_flags"] = list(record.quality_flags)
    data["derived"] = {
        "dte_hours": snapshot_dte_hours(record),
        "is_zero_dte": is_zero_dte_snapshot(record),
        "expiration_session_close_ns": expiration_session_close_ns(record.expiration_timestamp_ns),
    }
    return data


def snapshot_from_dict(payload: dict[str, Any]) -> IntradayChainSnapshotRecord:
    strikes = payload.get("strikes", ())
    if not isinstance(strikes, (list, tuple)):
        raise TypeError("strikes must be a list or tuple")
    quality_flags = payload.get("quality_flags", ())
    if isinstance(quality_flags, str):
        raise TypeError("quality_flags must be a sequence of strings, not one string")
    return IntradayChainSnapshotRecord(
        underlying=str(payload["underlying"]),
        event_time_ns=int(payload["event_time_ns"]),
        available_time_ns=int(payload["available_time_ns"]),
        expiration_timestamp_ns=int(payload["expiration_timestamp_ns"]),
        strikes=tuple(float(strike) for strike in strikes),
        multiplier=int(payload["multiplier"]) if payload.get("multiplier") is not None else None,
        publisher=str(payload["publisher"]),
        retrieved_time=str(payload.get("retrieved_time", "")),
        ingested_time=str(payload.get("ingested_time", "")),
        content_hash=str(payload.get("content_hash", "")),
        availability_precision=AvailabilityPrecision(
            payload.get("availability_precision", AvailabilityPrecision.TIMESTAMP.value)
        ),
        best_bid=float(payload["best_bid"]) if payload.get("best_bid") is not None else None,
        best_ask=float(payload["best_ask"]) if payload.get("best_ask") is not None else None,
        coverage_scope=CoverageScope(
            payload.get("coverage_scope", CoverageScope.COVERAGE_SCOPE_UNCERTAIN.value)
        ),
        history_class=PitHistoryClass(
            payload.get("history_class", PitHistoryClass.PROSPECTIVE_VERSIONED_PIT.value)
        ),
        feature_layer=OptionsFeatureLayer(
            payload.get("feature_layer", OptionsFeatureLayer.RAW.value)
        ),
        source_symbol=str(payload.get("source_symbol", "")),
        quality_flags=tuple(str(flag) for flag in quality_flags),
        provenance_ref=str(payload.get("provenance_ref", "")),
        lifecycle=str(payload.get("lifecycle", ZeroDTESnapshotLifecycle.OBSERVED.value)),
    )


__all__ = [
    "AvailabilityPrecision",
    "CoverageScope",
    "ET_TIMEZONE_NAME",
    "IntradayChainSnapshotRecord",
    "OptionsFeatureLayer",
    "PitHistoryClass",
    "SESSION_CLOSE_ET_HOUR",
    "SESSION_CLOSE_ET_MINUTE",
    "ZeroDTESnapshotLifecycle",
    "et_calendar_date",
    "expiration_session_close_ns",
    "is_zero_dte_snapshot",
    "snapshot_dte_hours",
    "snapshot_from_dict",
    "snapshot_to_dict",
]
