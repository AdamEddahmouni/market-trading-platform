"""Borrow fee live provider.

Attempts to retrieve borrow fee from the IBKR session via a secondary
market-data request after the base quote has completed, so it cannot block
primary price data. The request mechanism is not implemented yet.
"""

from __future__ import annotations

from typing import Any


class BorrowFeeProvider:
    """Live borrow-fee data source.

    A future implementation must verify the IBKR API mechanism and applicable
    market-data entitlement before returning a fee. It remains separate from
    the base quote so that an unavailable fee cannot block price or volume.
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
                "Borrow-fee retrieval is not implemented. It requires a verified "
                "IBKR API mechanism and the applicable market-data entitlement."
            ),
        }

    def fetch(self, symbol: str) -> float | None:
        """Return cached borrow fee or None."""
        return self._cache.get(symbol)

    def _request_borrow_fee(self, symbol: str) -> float | None:
        """Placeholder for a verified secondary market-data request.

        To be implemented only after the API mechanism and entitlement are
        confirmed. The separate request ensures base quote completion is never
        blocked by an unavailable borrow-fee field.
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
                "Borrow-fee retrieval is unavailable until a verified IBKR API "
                "mechanism and applicable market-data entitlement are configured."
            ),
        }

    def refresh_for(self, symbol: str) -> float | None:
        return None
