"""Staleness / freshness evaluation for the canonical L2 book (G5 / ARCH-009).

Freshness is a *pure* function of explicit state — never a wall clock read
inside deterministic paths. A stale-but-valid book is reported as STALE (not
silently collapsed into INVALID), and an INVALID book is never reported FRESH.

The four states:

- FRESH — valid book and age <= stale_after_ns.
- STALE — valid book but age > stale_after_ns (explicit staleness qualifier).
- INVALID — the book state itself is not trustworthy (validity first).
- UNAVAILABLE — no event data yet / freshness cannot be evaluated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .contracts import BOOK_MODEL_VERSION, BookStatusReason, BookValidity, FreshnessStatus


class BookStateView(Protocol):
    """Minimal protocol satisfied by :class:`IncrementalOrderBook`."""

    instrument_id: str
    model_version: str
    validity: BookValidity
    invalidation_reason: BookStatusReason
    last_source_time_ns: int | None
    last_received_time_ns: int | None
    is_empty: bool

    @property
    def book_state_valid(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class FreshnessPolicy:
    """Staleness policy — thresholds belong here, never in projections."""

    stale_after_ns: int = 5_000_000_000  # 5 seconds default
    name: str = "default"

    def __post_init__(self) -> None:
        if isinstance(self.stale_after_ns, bool) or not isinstance(self.stale_after_ns, int):
            raise ValueError(f"stale_after_ns must be int ns: {self.stale_after_ns!r}")
        if self.stale_after_ns < 0:
            raise ValueError("stale_after_ns must be >= 0")


@dataclass(frozen=True, slots=True)
class FreshnessEvaluation:
    status: FreshnessStatus
    policy_name: str
    as_of_time_ns: int
    age_ns: int | None = None
    stale_after_ns: int | None = None
    reason_code: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "as_of_time_ns": self.as_of_time_ns,
            "freshness_status": self.status.value,
            "policy": self.policy_name,
            "reason_code": self.reason_code,
        }
        if self.age_ns is not None:
            payload["age_ns"] = self.age_ns
        if self.stale_after_ns is not None:
            payload["stale_after_ns"] = self.stale_after_ns
        return payload


def evaluate_book_freshness(
    book: BookStateView,
    as_of_time_ns: int,
    policy: FreshnessPolicy,
) -> FreshnessEvaluation:
    """Pure freshness evaluation — deterministic for a fixed ``as_of_time_ns``.

    INVALID beats STALE: a book whose state is untrustworthy is never FRESH.
    UNAVAILABLE covers "no authoritative events yet" and "no timestamp to age".
    """
    if isinstance(as_of_time_ns, bool) or not isinstance(as_of_time_ns, int):
        raise ValueError(f"as_of_time_ns must be int ns: {as_of_time_ns!r}")

    if not book.book_state_valid:
        reason = "EMPTY_BOOK" if book.is_empty else book.invalidation_reason.value
        return FreshnessEvaluation(
            status=FreshnessStatus.INVALID if book.validity is BookValidity.INVALID else FreshnessStatus.UNAVAILABLE,
            policy_name=policy.name,
            as_of_time_ns=as_of_time_ns,
            reason_code=reason,
        )

    last_time = book.last_received_time_ns
    if last_time is None:
        # Valid levels with no clock (pure replay of price-only events): cannot
        # evaluate age truthfully.
        return FreshnessEvaluation(
            status=FreshnessStatus.UNAVAILABLE,
            policy_name=policy.name,
            as_of_time_ns=as_of_time_ns,
            reason_code="NO_RECEIVED_TIME",
        )
    age_ns = as_of_time_ns - last_time
    if age_ns > policy.stale_after_ns:
        return FreshnessEvaluation(
            status=FreshnessStatus.STALE,
            policy_name=policy.name,
            as_of_time_ns=as_of_time_ns,
            age_ns=age_ns,
            stale_after_ns=policy.stale_after_ns,
            reason_code="STALE_AFTER_THRESHOLD",
        )
    return FreshnessEvaluation(
        status=FreshnessStatus.FRESH,
        policy_name=policy.name,
        as_of_time_ns=as_of_time_ns,
        age_ns=age_ns,
        stale_after_ns=policy.stale_after_ns,
        reason_code="FRESH",
    )


__all__ = [
    "BOOK_MODEL_VERSION",
    "BookStateView",
    "FreshnessEvaluation",
    "FreshnessPolicy",
    "evaluate_book_freshness",
]
