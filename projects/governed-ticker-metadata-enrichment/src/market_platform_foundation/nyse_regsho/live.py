"""Opt-in NYSE Group threshold retrieval."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from .threshold import normalize_threshold_file, parse_threshold_file
from .transport import NyseTransport
from ..short_intelligence.identity import SymbolMap


def live_enabled() -> bool:
    return os.environ.get("IMP_NYSE_REGSHO_LIVE") == "1"


def fetch_threshold_observations(
    transport: NyseTransport,
    symbol_map: SymbolMap,
    trade_date: str,
    *,
    market: str,
    requested_symbols: tuple[str, ...] | None = None,
) -> tuple:
    observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw = transport.fetch_threshold_file(trade_date, market=market)
    parsed = parse_threshold_file(raw, trade_date=trade_date, source_market=market)
    return normalize_threshold_file(
        parsed,
        symbol_map=symbol_map,
        observed_time=observed,
        retrieved_time=observed,
        requested_symbols=requested_symbols,
    )
