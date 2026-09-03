"""Scheduled macro / Fed catalyst calendar (research only).

Purpose
-------
Tag research panel rows with scheduled FOMC/CPI/NFP proximity for pattern mining.

Features / API role
-------------------
``default_macro_events``, ``catalyst_features_for_day``, ``enrich_rows_with_calendar``.

How this uses ``options_confirmation_engine``
-----------------------------------------------
Independent of the engine — enriches evaluation panel rows consumed alongside
``options_score`` / ``options_bias`` from replay.

Options-specific vs reusable
----------------------------
Fully reusable macro calendar; static 2026 H1 list, not live economic data feed.

Static list covering the IVolatility historical window (2026 H1–mid-year).
Sources: Federal Reserve FOMC schedule; BLS Employment Situation & CPI calendars.
Not exhaustive — major recurring high-impact prints only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class MacroEvent:
    """One scheduled macro catalyst on a calendar day."""

    day: date
    kind: str  # fomc | cpi | nfp | other
    label: str
    hour_et: int = 8  # approximate ET release/decision hour


# FOMC: policy statement ~14:00 ET on the second day of each meeting.
_FOMC_DECISION_DAYS_2026 = (
    date(2026, 1, 28),
    date(2026, 3, 18),
    date(2026, 4, 29),
    date(2026, 6, 17),
    date(2026, 7, 29),
    date(2026, 9, 16),
    date(2026, 10, 28),
    date(2026, 12, 9),
)

# Also tag meeting day 1 (often elevated vol into the decision).
_FOMC_DAY1_2026 = (
    date(2026, 1, 27),
    date(2026, 3, 17),
    date(2026, 4, 28),
    date(2026, 6, 16),
    date(2026, 7, 28),
    date(2026, 9, 15),
    date(2026, 10, 27),
    date(2026, 12, 8),
)

# BLS Employment Situation (NFP) 08:30 ET — 2026 schedule (selected months).
_NFP_2026 = (
    date(2026, 1, 9),
    date(2026, 2, 6),
    date(2026, 3, 6),
    date(2026, 4, 3),
    date(2026, 5, 1),
    date(2026, 6, 5),
    date(2026, 7, 2),
)

# CPI 08:30 ET — 2026 schedule (selected months).
_CPI_2026 = (
    date(2026, 1, 13),
    date(2026, 2, 13),
    date(2026, 3, 11),
    date(2026, 4, 10),
    date(2026, 5, 12),
    date(2026, 6, 10),
    date(2026, 7, 14),
)


def default_macro_events() -> List[MacroEvent]:
    """Return the static 2026 FOMC/CPI/NFP event list for enrichment."""
    events: List[MacroEvent] = []
    for d in _FOMC_DECISION_DAYS_2026:
        events.append(MacroEvent(d, "fomc", "FOMC decision / press conference", hour_et=14))
    for d in _FOMC_DAY1_2026:
        events.append(MacroEvent(d, "fomc", "FOMC meeting day 1", hour_et=9))
    for d in _NFP_2026:
        events.append(MacroEvent(d, "nfp", "Employment Situation (NFP)", hour_et=8))
    for d in _CPI_2026:
        events.append(MacroEvent(d, "cpi", "Consumer Price Index", hour_et=8))
    events.sort(key=lambda e: (e.day, e.hour_et, e.kind))
    return events


def _parse_session_date(row: Dict[str, Any]) -> Optional[date]:
    for key in ("session_date", "timestamp", "rejected_at"):
        text = str(row.get(key) or "")
        if len(text) >= 10 and text[4] == "-":
            try:
                return date.fromisoformat(text[:10])
            except ValueError:
                continue
    return None


def _event_datetimes(events: Sequence[MacroEvent]) -> List[datetime]:
    out: List[datetime] = []
    for ev in events:
        # Store as naive ET wall-clock then treat as UTC-offset-naive for hour math;
        # research panel timestamps are typically UTC afternoon for EOD — we use date-level
        # proximity primarily and hour deltas as coarse features.
        out.append(datetime(ev.day.year, ev.day.month, ev.day.day, ev.hour_et, tzinfo=timezone.utc))
    return sorted(out)


def catalyst_features_for_day(
    day: date,
    *,
    events: Optional[Sequence[MacroEvent]] = None,
    as_of_hour_utc: int = 21,
) -> Dict[str, Any]:
    """Compute catalyst proximity features for one session date (EOD-oriented)."""
    events = list(events or default_macro_events())
    event_days = {e.day for e in events}
    is_day = day in event_days
    kinds = sorted({e.kind for e in events if e.day == day})

    as_of = datetime(day.year, day.month, day.day, as_of_hour_utc, tzinfo=timezone.utc)
    stamps = _event_datetimes(events)

    hours_until: Optional[float] = None
    hours_since: Optional[float] = None
    for ts in stamps:
        delta_h = (ts - as_of).total_seconds() / 3600.0
        if delta_h >= 0:
            hours_until = delta_h if hours_until is None else min(hours_until, delta_h)
        else:
            hours_since = -delta_h if hours_since is None else min(hours_since, -delta_h)

    return {
        "is_scheduled_catalyst_day": bool(is_day),
        "catalyst_kinds": ",".join(kinds) if kinds else "",
        "hours_until_next_catalyst": hours_until,
        "hours_since_last_catalyst": hours_since,
    }


def enrich_rows_with_calendar(
    rows: Sequence[Dict[str, Any]],
    *,
    events: Optional[Sequence[MacroEvent]] = None,
) -> List[Dict[str, Any]]:
    """Attach catalyst-day and hours-until/since features to each panel row."""
    events = list(events or default_macro_events())
    out: List[Dict[str, Any]] = []
    for row in rows:
        copy = dict(row)
        day = _parse_session_date(copy)
        if day is None:
            copy.setdefault("is_scheduled_catalyst_day", False)
            copy.setdefault("hours_until_next_catalyst", None)
            copy.setdefault("hours_since_last_catalyst", None)
            out.append(copy)
            continue
        feats = catalyst_features_for_day(day, events=events)
        copy.update(feats)
        out.append(copy)
    return out
