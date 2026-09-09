"""G10 — canonical depth runtime admissibility (BL-0303).

Connects G5 ``FreshnessPolicy`` to runtime capability/readiness truth. Evaluation
is pure for a fixed ``as_of_time_ns`` — no wall-clock reads inside deterministic
paths.

Precedence (highest first):

1. ``NOT_ENTITLED`` / ``PROVIDER_UNAVAILABLE``
2. ``INVALID`` (structural book invalidity)
3. ``UNAVAILABLE`` (no timestamp / no book)
4. ``STALE`` (valid book past TTL)
5. ``ADMISSIBLE`` (fresh, entitled, connected)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ..order_flow.order_book.contracts import FreshnessStatus
from ..order_flow.order_book.freshness import (
    BookStateView,
    FreshnessEvaluation,
    FreshnessPolicy,
    evaluate_book_freshness,
)
from ..providers.runtime_capability import EntitlementState, ProviderHealth


class DepthAdmissibilityStatus(StrEnum):
    ADMISSIBLE = "ADMISSIBLE"
    STALE = "STALE"
    INVALID = "INVALID"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_ENTITLED = "NOT_ENTITLED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class DepthAdmissionContext:
    """Runtime axes that gate depth admissibility beyond book freshness."""

    entitlement: EntitlementState = EntitlementState.UNKNOWN
    provider_health: ProviderHealth = ProviderHealth.UNKNOWN
    provider_connected: bool = True
    generation: int = 0


@dataclass(frozen=True, slots=True)
class DepthAdmissibilityResult:
    status: DepthAdmissibilityStatus
    freshness_status: FreshnessStatus
    admissible: bool
    reason_code: str
    freshness: FreshnessEvaluation | None = None
    generation: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "admissible": self.admissible,
            "freshness_status": self.freshness_status.value,
            "generation": self.generation,
            "reason_code": self.reason_code,
            "status": self.status.value,
        }
        if self.freshness is not None:
            payload["freshness"] = self.freshness.to_dict()
        return payload


def evaluate_depth_admissibility(
    book: BookStateView | None,
    *,
    as_of_time_ns: int,
    policy: FreshnessPolicy,
    context: DepthAdmissionContext | None = None,
) -> DepthAdmissibilityResult:
    """Evaluate whether depth may be presented as authoritative live state."""
    ctx = context or DepthAdmissionContext()
    if isinstance(as_of_time_ns, bool) or not isinstance(as_of_time_ns, int):
        raise ValueError(f"as_of_time_ns must be int ns: {as_of_time_ns!r}")

    if not ctx.provider_connected or ctx.provider_health is ProviderHealth.DOWN:
        return DepthAdmissibilityResult(
            status=DepthAdmissibilityStatus.PROVIDER_UNAVAILABLE,
            freshness_status=FreshnessStatus.UNAVAILABLE,
            admissible=False,
            reason_code="PROVIDER_UNAVAILABLE",
            generation=ctx.generation,
        )

    if ctx.entitlement is EntitlementState.NOT_ENTITLED:
        return DepthAdmissibilityResult(
            status=DepthAdmissibilityStatus.NOT_ENTITLED,
            freshness_status=FreshnessStatus.UNAVAILABLE,
            admissible=False,
            reason_code="NOT_ENTITLED",
            generation=ctx.generation,
        )

    if book is None:
        return DepthAdmissibilityResult(
            status=DepthAdmissibilityStatus.UNAVAILABLE,
            freshness_status=FreshnessStatus.UNAVAILABLE,
            admissible=False,
            reason_code="NO_BOOK",
            generation=ctx.generation,
        )

    freshness = evaluate_book_freshness(book, as_of_time_ns=as_of_time_ns, policy=policy)
    if freshness.status is FreshnessStatus.INVALID:
        return DepthAdmissibilityResult(
            status=DepthAdmissibilityStatus.INVALID,
            freshness_status=freshness.status,
            admissible=False,
            reason_code=freshness.reason_code or "INVALID_BOOK",
            freshness=freshness,
            generation=ctx.generation,
        )
    if freshness.status is FreshnessStatus.UNAVAILABLE:
        return DepthAdmissibilityResult(
            status=DepthAdmissibilityStatus.UNAVAILABLE,
            freshness_status=freshness.status,
            admissible=False,
            reason_code=freshness.reason_code or "UNAVAILABLE",
            freshness=freshness,
            generation=ctx.generation,
        )
    if freshness.status is FreshnessStatus.STALE:
        return DepthAdmissibilityResult(
            status=DepthAdmissibilityStatus.STALE,
            freshness_status=freshness.status,
            admissible=False,
            reason_code=freshness.reason_code or "STALE_AFTER_THRESHOLD",
            freshness=freshness,
            generation=ctx.generation,
        )

    return DepthAdmissibilityResult(
        status=DepthAdmissibilityStatus.ADMISSIBLE,
        freshness_status=freshness.status,
        admissible=True,
        reason_code="FRESH",
        freshness=freshness,
        generation=ctx.generation,
    )


__all__ = [
    "DepthAdmissionContext",
    "DepthAdmissibilityResult",
    "DepthAdmissibilityStatus",
    "evaluate_depth_admissibility",
]
