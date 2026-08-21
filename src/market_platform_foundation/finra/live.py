"""Opt-in live FINRA client. Observations are never auto-admitted."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from .auth import FinraTokenManager
from .client_config import load_finra_credentials
from .query import query_reg_sho_daily, query_short_interest
from .short_interest import normalize_short_interest_row
from .short_sale_volume import normalize_short_sale_row
from .transport import FinraTransport
from ..short_intelligence.identity import SymbolMap


def live_enabled() -> bool:
    return os.environ.get("IMP_FINRA_LIVE") == "1"


def transport_from_env() -> FinraTransport:
    credentials = load_finra_credentials()
    return FinraTransport(FinraTokenManager(credentials))


def probe_short_interest(transport: FinraTransport, symbol_map: SymbolMap, symbol: str, settlement_date: str | None = None):
    observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    response = query_short_interest(transport, symbol=symbol, settlement_date=settlement_date, limit=20)
    return tuple(
        normalize_short_interest_row(
            row,
            symbol_map=symbol_map,
            observed_time=observed,
            retrieved_time=observed,
            finra_request_id=response.request_id,
        )
        for row in response.records
    )


def probe_short_sale_volume(transport: FinraTransport, symbol_map: SymbolMap, symbol: str, trade_report_date: str | None = None):
    observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    response = query_reg_sho_daily(transport, symbol=symbol, trade_report_date=trade_report_date, limit=50)
    return tuple(
        normalize_short_sale_row(
            row,
            symbol_map=symbol_map,
            observed_time=observed,
            retrieved_time=observed,
            finra_request_id=response.request_id,
        )
        for row in response.records
    )
