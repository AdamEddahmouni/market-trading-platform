"""Operational health for SEC FTD source."""

from __future__ import annotations

from dataclasses import dataclass

from ..sec_edgar.transport import SecTransport


@dataclass(frozen=True, slots=True)
class SecFtdHealth:
    reachable: bool
    latest_period_discovered: str
    latest_period_captured: str
    last_successful_retrieval: str
    latest_hash: str
    parser_health: str
    request_count: int
    cache_hits: int
    error_count: int
    last_status: str
    publication_expected_not_observed: bool = False


def health_from_runtime(
    transport: SecTransport,
    *,
    latest_period_discovered: str = "",
    latest_period_captured: str = "",
    last_successful_retrieval: str = "",
    latest_hash: str = "",
    parser_health: str = "UNKNOWN",
    publication_expected_not_observed: bool = False,
) -> SecFtdHealth:
    reachable = transport.last_status == "ok" or transport.request_count > 0
    return SecFtdHealth(
        reachable=reachable,
        latest_period_discovered=latest_period_discovered,
        latest_period_captured=latest_period_captured,
        last_successful_retrieval=last_successful_retrieval,
        latest_hash=latest_hash,
        parser_health=parser_health,
        request_count=transport.request_count,
        cache_hits=transport.cache_hits,
        error_count=transport.error_count,
        last_status=transport.last_status,
        publication_expected_not_observed=publication_expected_not_observed,
    )


__all__ = ["SecFtdHealth", "health_from_runtime"]
