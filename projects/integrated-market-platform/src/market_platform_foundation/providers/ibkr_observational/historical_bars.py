"""Canonical IBKR historical bar normalization (G10 / BL-0301).

Provider-specific bar rows from outer ``tools/ibkr`` REST/TWS surfaces are
normalized into the IMP observational bar vocabulary. This module is the
canonical normalization boundary — outer code injects raw facts; src owns
semantics. No look-ahead, no fabricated source timestamps, no implicit
adjusted/unadjusted conversion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class ObservationalHistoricalBar:
    """Canonical historical bar fact (read-only observational)."""

    instrument_id: str
    provider: str
    interval: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    source_time_ns: int | None
    available_time_ns: int | None
    received_time_ns: int | None
    adjustment_status: str
    provenance: str
    pit_semantics: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "adjustment_status": self.adjustment_status,
            "available_time_ns": self.available_time_ns,
            "close": self.close,
            "high": self.high,
            "instrument_id": self.instrument_id,
            "interval": self.interval,
            "low": self.low,
            "open": self.open,
            "pit_semantics": self.pit_semantics,
            "provenance": self.provenance,
            "provider": self.provider,
            "received_time_ns": self.received_time_ns,
            "source_time_ns": self.source_time_ns,
            "volume": self.volume,
        }


def normalize_ibkr_history_row(
    row: Mapping[str, Any],
    *,
    instrument_id: str,
    provider: str = "IBKR",
    interval: str,
    received_time_ns: int | None = None,
) -> ObservationalHistoricalBar:
    """Normalize one IBKR history row (``t/o/h/l/c/v`` keys) to canonical facts."""
    source_raw = row.get("t") or row.get("time") or row.get("date")
    source_time_ns = _coerce_source_time_ns(source_raw)
    if source_time_ns is None:
        raise ValueError("historical bar missing source/event time")
    return ObservationalHistoricalBar(
        instrument_id=instrument_id.upper(),
        provider=provider,
        interval=interval,
        open=float(row.get("o") or row.get("open") or 0),
        high=float(row.get("h") or row.get("high") or 0),
        low=float(row.get("l") or row.get("low") or 0),
        close=float(row.get("c") or row.get("close") or 0),
        volume=float(row.get("v") or row.get("volume") or 0),
        source_time_ns=source_time_ns,
        available_time_ns=source_time_ns,
        received_time_ns=received_time_ns,
        adjustment_status=str(row.get("adjustment_status") or "UNADJUSTED"),
        provenance="IBKR_HISTORICAL",
        pit_semantics="POINT_IN_TIME",
    )


def normalize_ibkr_history_payload(
    payload: Mapping[str, Any],
    *,
    instrument_id: str,
    provider: str = "IBKR",
    interval: str,
    received_time_ns: int | None = None,
) -> list[ObservationalHistoricalBar]:
    """Normalize an IBKR ``/hmds/history`` or TWS history payload."""
    rows = payload.get("data")
    if not isinstance(rows, Sequence):
        raise ValueError("history payload missing data sequence")
    return [
        normalize_ibkr_history_row(
            row,
            instrument_id=instrument_id,
            provider=provider,
            interval=interval,
            received_time_ns=received_time_ns,
        )
        for row in rows
        if isinstance(row, Mapping)
    ]


def _coerce_source_time_ns(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        # IB may return seconds or ms; treat large values as ms already.
        if value > 10_000_000_000_000:
            return value
        if value > 10_000_000_000:
            return value * 1_000_000
        return value * 1_000_000_000
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        parsed = int(text)
        if parsed > 10_000_000_000_000:
            return parsed
        if parsed > 10_000_000_000:
            return parsed * 1_000_000
        return parsed * 1_000_000_000
    return None


__all__ = [
    "ObservationalHistoricalBar",
    "normalize_ibkr_history_payload",
    "normalize_ibkr_history_row",
]
