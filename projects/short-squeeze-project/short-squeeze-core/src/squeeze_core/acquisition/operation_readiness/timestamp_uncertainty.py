"""Bidirectional 1-minute bar-timestamp uncertainty (Batch 06 left START/END UNKNOWN).

Batch 06 established the timestamp is epoch seconds / UTC but NOT whether it marks the
interval START or END. For a bar of known size ``d`` and timestamp ``t`` the true
interval is exactly one of ``[t, t+d]`` (t is START) or ``[t-d, t]`` (t is END). This
module reasons conservatively across BOTH interpretations using exact ``datetime`` /
``timedelta`` arithmetic and never chooses one interpretation. It never reads OHLCV.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from .models import TimestampUncertaintyEnvelope


def possible_completion_instants(
    event_timestamp: datetime, bar_interval_seconds: int
) -> tuple[datetime, datetime]:
    """The two possible interval-END (completion) instants: (earliest, latest).

    Under interpretation B (t = END) completion is ``t``; under interpretation A
    (t = START) completion is ``t + d``. ``t <= t + d``, so earliest = t, latest = t+d.
    """
    delta = timedelta(seconds=bar_interval_seconds)
    return event_timestamp, event_timestamp + delta


def possible_start_instants(
    event_timestamp: datetime, bar_interval_seconds: int
) -> tuple[datetime, datetime]:
    """The two possible interval-START instants: (earliest, latest).

    Under interpretation B (t = END) start is ``t - d``; under A (t = START) start is
    ``t``. So earliest = t - d, latest = t.
    """
    delta = timedelta(seconds=bar_interval_seconds)
    return event_timestamp - delta, event_timestamp


def definitely_completed_before(
    event_timestamp: datetime, bar_interval_seconds: int, boundary: datetime
) -> bool:
    """True iff the bar is completed at-or-before ``boundary`` under BOTH interpretations.

    Binding instant is the *latest* possible completion (``t + d``); if even that is
    ``<= boundary`` the bar is definitely completed by the boundary regardless of which
    interpretation is correct.
    """
    _, latest = possible_completion_instants(event_timestamp, bar_interval_seconds)
    return latest <= boundary


def definitely_starts_after(
    event_timestamp: datetime, bar_interval_seconds: int, boundary: datetime
) -> bool:
    """True iff the bar starts at-or-after ``boundary`` under BOTH interpretations.

    Binding instant is the *earliest* possible start (``t - d``); if even that is
    ``>= boundary`` the whole bar lies at/after the boundary either way.
    """
    earliest, _ = possible_start_instants(event_timestamp, bar_interval_seconds)
    return earliest >= boundary


def straddles_boundary(
    event_timestamp: datetime, bar_interval_seconds: int, boundary: datetime
) -> bool:
    """True iff the bar can be neither definitely-completed-before nor definitely-after.

    A straddle means at least one interpretation places the boundary strictly inside the
    bar, so completed-before-boundary alignment cannot be established conservatively.
    """
    return not (
        definitely_completed_before(event_timestamp, bar_interval_seconds, boundary)
        or definitely_starts_after(event_timestamp, bar_interval_seconds, boundary)
    )


def build_envelope(
    event_timestamp: datetime, bar_interval_seconds: int, boundary: datetime
) -> TimestampUncertaintyEnvelope:
    earliest, latest = possible_completion_instants(event_timestamp, bar_interval_seconds)
    return TimestampUncertaintyEnvelope(
        event_timestamp=event_timestamp,
        bar_interval_seconds=bar_interval_seconds,
        earliest_possible_completion=earliest,
        latest_possible_completion=latest,
        boundary=boundary,
        definitely_completed_before_boundary=definitely_completed_before(
            event_timestamp, bar_interval_seconds, boundary
        ),
        straddles_boundary=straddles_boundary(
            event_timestamp, bar_interval_seconds, boundary
        ),
    )


__all__ = [
    "possible_completion_instants",
    "possible_start_instants",
    "definitely_completed_before",
    "definitely_starts_after",
    "straddles_boundary",
    "build_envelope",
]
