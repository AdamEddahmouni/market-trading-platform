"""Outer IBKR read-only query provider (G11).

Adapts existing ``IbkrClient`` / ``TwsIbkrClient`` to the canonical src
read-only query protocol (structural typing; registration via runtime_bootstrap).
Never imported by src.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .client import IbkrClient, LiveGateDisabled
from .config import IbkrConfig
from .tws_client import TwsIbkrClient


class IbkrOuterReadOnlyQueryProvider:
    """Read-only REST/TWS query adapter for canonical src injection."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self._closed = False

    def is_available(self) -> bool:
        return not self._closed

    def fetch_secdef_search(self, symbol: str) -> Sequence[Mapping[str, Any]]:
        payload = self._client.request_json(
            "GET",
            "/iserver/secdef/search",
            params={"symbol": symbol.strip().upper()},
        )
        if isinstance(payload, list):
            return payload
        if isinstance(payload, Mapping):
            rows = payload.get("sections") or payload.get("data") or ()
            if isinstance(rows, list):
                return rows
        return []

    def fetch_historical_bars(
        self,
        *,
        con_id: int,
        period: str,
        bar: str,
    ) -> Mapping[str, Any]:
        payload = self._client.request_json(
            "GET",
            "/hmds/history",
            params={"conid": con_id, "period": period, "bar": bar},
        )
        if not isinstance(payload, Mapping):
            return {"data": []}
        return payload

    def fetch_historical_trades(
        self,
        *,
        con_id: int,
        start_time_ns: int,
        end_time_ns: int,
        number_of_ticks: int = 1000,
    ) -> Mapping[str, Any]:
        fetch = getattr(self._client, "fetch_historical_trades", None)
        if not callable(fetch):
            return {
                "data": [],
                "reason": "REST_HISTORICAL_TRADES_UNAVAILABLE",
                "transport": "rest",
            }
        payload = fetch(
            con_id=con_id,
            start_time_ns=start_time_ns,
            end_time_ns=end_time_ns,
            number_of_ticks=number_of_ticks,
        )
        if not isinstance(payload, Mapping):
            return {"data": []}
        return payload

    def fetch_portfolio_accounts(self) -> Mapping[str, Any]:
        payload = self._client.request_json("GET", "/portfolio/accounts")
        if isinstance(payload, Mapping):
            return payload
        if isinstance(payload, list):
            return {"accounts": payload}
        return {"accounts": []}

    def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        close = getattr(self._client, "close", None)
        if callable(close):
            close()


def build_query_provider(config: IbkrConfig) -> IbkrOuterReadOnlyQueryProvider:
    """Construct outer query provider from config (fail-closed when live disabled)."""
    if not config.live_enabled:
        raise LiveGateDisabled("IMP_IBKR_LIVE is not enabled")
    if config.transport == "tws":
        return IbkrOuterReadOnlyQueryProvider(TwsIbkrClient(config))
    return IbkrOuterReadOnlyQueryProvider(IbkrClient(config))


class IbkrReadOnlyQueryBootstrap:
    """Outer construction boundary for read-only query provider."""

    def __init__(self, *, config: IbkrConfig | None = None) -> None:
        import os
        from pathlib import Path

        self._root = Path(__file__).resolve().parents[2]
        self._config = config

    def construct(self) -> IbkrOuterReadOnlyQueryProvider:
        cfg = self._config or IbkrConfig.from_env(__import__("os").environ, root=self._root)
        return build_query_provider(cfg)


__all__ = [
    "IbkrOuterReadOnlyQueryProvider",
    "IbkrReadOnlyQueryBootstrap",
    "build_query_provider",
]
