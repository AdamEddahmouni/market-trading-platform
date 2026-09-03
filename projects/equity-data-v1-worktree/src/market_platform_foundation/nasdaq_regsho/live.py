"""Opt-in Nasdaq threshold retrieval. No FINRA credential."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from .threshold import normalize_threshold_file, parse_threshold_file
from .transport import NasdaqTransport
from ..short_intelligence.identity import SymbolMap


def live_enabled() -> bool:
    return os.environ.get("IMP_NASDAQ_REGSHO_LIVE") == "1"


def fetch_threshold_observations(
    transport: NasdaqTransport,
    symbol_map: SymbolMap,
    trade_date: str,
    *,
    requested_symbols: tuple[str, ...] | None = None,
) -> tuple:
    observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw = transport.fetch_threshold_file(trade_date)
    parsed = parse_threshold_file(raw, trade_date=trade_date)
    return normalize_threshold_file(
        parsed,
        symbol_map=symbol_map,
        observed_time=observed,
        retrieved_time=observed,
        requested_symbols=requested_symbols,
    )
