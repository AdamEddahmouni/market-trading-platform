"""Temporal integrity helpers. OF eligibility uses recorded_at, never event_time."""

from __future__ import annotations

from .errors import OF02Error, OF02ErrorCode


def assert_not_backdated(*, recorded_at_ns: int, claimed_recorded_at_ns: int | None) -> None:
    if claimed_recorded_at_ns is None:
        return
    if claimed_recorded_at_ns != recorded_at_ns:
        raise OF02Error(
            OF02ErrorCode.BACKDATE_PROHIBITED,
            "callers must not override OF recorded_at",
            {
                "recorded_at_ns": recorded_at_ns,
                "claimed_recorded_at_ns": claimed_recorded_at_ns,
            },
        )


def of_reference_eligible_at(*, recorded_at_ns: int, cutoff_ns: int) -> bool:
    """True only if the OF commit had already occurred at cutoff.

    Historical source event_time is intentionally ignored.
    """

    return recorded_at_ns <= cutoff_ns


def reject_future_information(*, decision_time_ns: int, of_recorded_at_ns: int) -> None:
    if of_recorded_at_ns <= decision_time_ns:
        return
    raise OF02Error(
        OF02ErrorCode.FUTURE_INFORMATION,
        "retrospective OF records recorded after decision_time are not historically eligible",
        {"decision_time_ns": decision_time_ns, "of_recorded_at_ns": of_recorded_at_ns},
    )
