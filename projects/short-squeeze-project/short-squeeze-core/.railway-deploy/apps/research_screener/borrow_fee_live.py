"""Borrow fee live provider.

Attempts to retrieve borrow fee from the IBKR session via a secondary
market-data request (generic tick 258) that fires after the base quote
has completed, so it cannot block primary price data.
"""

from __future__ import annotations

from typing import Any


class BorrowFeeProvider:
    """Live borrow-fee data source.

    Uses a secondary IBKR market-data request specifically for generic
    tick 258 (borrow fee / shortable fee rate). This is a separate
    request from the base quote so that permission-scoped fundamentals
    failures cannot prevent price/volume ticks from arriving.
    """

    def __init__(self) -> None:
        self._cache: dict[str, float | None] = {}
        self._last_attempt: dict[str, str] = {}
        self.configured = False

    def status(self) -> dict[str, Any]:
        return {
            "provider": "IBKR Borrow Fee (secondary)",
            "configured": self.configured,
            "cached_symbols": len(self._cache),
            "detail": (
                "Uses generic tick 258 on a separate market-data request. "
                "Requires IBKR market-data entitlement that includes "
                "fundamental ratios."
            ),
        }

    def fetch(self, symbol: str) -> float | None:
        """Return cached borrow fee or None."""
        return self._cache.get(symbol)

    def _request_borrow_fee(self, symbol: str) -> float | None:
        """Secondary market-data request for generic tick 258.

        To be implemented when IBKR session with borrow-fee entitlement
        is available. The separate request ensures base quote completion
        is never blocked by a fundamentals rejection.
        """
        return None

    def refresh_for(self, symbol: str) -> float | None:
        result = self._request_borrow_fee(symbol)
        self._cache[symbol] = result
        return result


class NullBorrowFeeProvider:
    configured = False

    def fetch(self, symbol: str) -> float | None:
        return None

    def status(self) -> dict[str, Any]:
        return {
            "provider": "IBKR Borrow Fee (secondary)",
            "configured": False,
            "detail": (
                "Borrow fee requires IBKR market-data entitlement that "
                "includes fundamental ratios (generic tick 258). "
                "Not available under the current connection."
            ),
        }

    def refresh_for(self, symbol: str) -> float | None:
        return None
