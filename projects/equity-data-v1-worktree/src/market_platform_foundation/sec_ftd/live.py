"""Opt-in live SEC FTD retrieval. No credentials required."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from ..sec_edgar.transport import SecTransport
from ..short_intelligence.identity import SymbolMap
from .discovery import latest_discovered_period
from .normalize import normalize_ftd_archive
from .parser import parse_archive_bytes
from .periods import FtdPeriod, parse_period_key
from .transport import FtdTransport


def live_enabled() -> bool:
    return os.environ.get("IMP_SEC_FTD_LIVE") == "1"


def transport_from_env() -> SecTransport:
    return SecTransport(user_agent=os.environ.get("SEC_USER_AGENT", ""))


def fetch_ftd_observations(
    transport: FtdTransport,
    symbol_map: SymbolMap,
    *,
    period_key: str | None = None,
    requested_symbols: tuple[str, ...] | None = None,
) -> tuple:
    observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if period_key:
        period = parse_period_key(period_key)
    else:
        latest = latest_discovered_period(transport.transport)
        if latest is None:
            raise OSError("SEC_FTD_DISCOVERY_EMPTY")
        period = latest.period
    capture = transport.fetch_archive(period, retrieved_time=observed, first_observed_time=observed)
    parsed = parse_archive_bytes(capture.content_bytes, period_key=period.period_key)
    return normalize_ftd_archive(
        parsed,
        period=period,
        symbol_map=symbol_map,
        observed_time=observed,
        retrieved_time=observed,
        requested_symbols=requested_symbols,
    )


__all__ = ["FtdPeriod", "fetch_ftd_observations", "live_enabled", "transport_from_env"]
