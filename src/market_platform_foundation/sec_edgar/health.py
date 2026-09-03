"""Provider health. Reachable != no new filings."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SecHealth:
    reachable: bool
    last_status: str
    request_count: int
    error_count: int
    cache_hits: int
    last_filing_observation: str = ""
    note: str = "reachable_does_not_mean_no_new_filing"


def health_from_transport(transport: object, *, last_filing_observation: str = "") -> SecHealth:
    return SecHealth(
        reachable=getattr(transport, "last_status", "") == "ok",
        last_status=str(getattr(transport, "last_status", "unknown")),
        request_count=int(getattr(transport, "request_count", 0)),
        error_count=int(getattr(transport, "error_count", 0)),
        cache_hits=int(getattr(transport, "cache_hits", 0)),
        last_filing_observation=last_filing_observation,
    )
