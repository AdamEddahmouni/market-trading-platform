"""Injection point for a delayed, read-only futures source (IBKR delayed market data).

The Screener's Futures universe takes its contract catalog from Moomoo OpenD. When
OpenD supplies no futures quotes or bars (no futures entitlement), an outer bootstrap
may inject a second, *delayed* source here. It only fills values the primary source
did not supply, and everything it supplies is labeled ``DELAYED``; it is never
presented as live and carries no execution authority.

``src/market_platform_foundation`` never imports the concrete implementation
(``tools/ibkr/futures_delayed.py``); the outer bootstrap constructs and injects it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

SOURCE_ID = "IBKR_DELAYED"
PROVIDER = "IBKR"


@dataclass(frozen=True, slots=True)
class FuturesContractRef:
    """The identity facts a second source needs to find the same dated contract."""

    key: str             # the Screener's instrument id for the row
    root: str            # e.g. "ES"
    contract_month: str  # "YYYYMM"
    expiry: str          # ISO last trade date from the catalog; used to confirm the match


class DelayedFuturesSource(Protocol):
    def quotes(self, contracts: list[FuturesContractRef]) -> dict[str, dict[str, Any]]:
        """Cached delayed quotes by ``key``; never blocks on the provider.

        Each value: ``{"last", "bid", "ask", "prev_close", "volume", "updated_s"}`` (floats or None,
        ``updated_s`` epoch seconds of the last provider update). Contracts not yet resolved are absent.
        """

    def bars(self, contract: FuturesContractRef, timeframe: str) -> list[dict[str, Any]] | None:
        """Delayed OHLCV bars ``{"start_s", "end_s", "open", "high", "low", "close", "volume"}``, oldest first.

        ``None`` when the contract is not resolved or the provider did not answer in time.
        """

    def status(self) -> dict[str, Any]:
        """``{"connected": bool, "reason": str | None}``."""


_SOURCE: DelayedFuturesSource | None = None


def inject_delayed_futures_source(source: DelayedFuturesSource | None) -> None:
    global _SOURCE
    _SOURCE = source


def delayed_futures_source() -> DelayedFuturesSource | None:
    return _SOURCE


__all__ = ["PROVIDER", "SOURCE_ID", "DelayedFuturesSource", "FuturesContractRef", "delayed_futures_source",
           "inject_delayed_futures_source"]
