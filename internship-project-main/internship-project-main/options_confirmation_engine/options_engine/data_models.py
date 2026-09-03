"""Typed data structures for normalized options snapshots.

Purpose
-------
Canonical wire format between chain providers, feature code, snapshot store, and
research adapters — one ``Snapshot`` per ticker per as-of timestamp.

Features / API role
-------------------
- ``ContractRow``: single option line (strike, side, greeks, quotes, OI/volume).
- ``Snapshot``: ticker, spot, expirations, contracts, ``data_quality_flags``,
  ``provider`` tag. ``to_dict()`` for JSON persistence.

How ``news_momentum_agent`` consumes it
---------------------------------------
``evaluation/historical_chain_adapter.rows_to_snapshot`` builds these types from
IVolatility CSV rows so replay uses the same ``compute_features`` / ``score_options``
path as live ingest.

Options-specific vs reusable
----------------------------
Options-specific field names (side, strike, IV, delta). Reusable as a generic
tabular-ingest target for any provider that maps into ``ContractRow``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class ContractRow:
    """Normalized options contract row."""

    contract_symbol: str
    side: str
    strike: float
    expiration: str
    implied_volatility: float
    volume: float
    open_interest: float
    bid: float
    ask: float
    last_price: float
    in_the_money: bool
    delta: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize this contract row to a plain dict for JSON storage."""
        return asdict(self)


@dataclass
class Snapshot:
    """Normalized snapshot for one ticker at one point in time."""

    ticker: str
    as_of: str
    spot_price: float
    expirations: List[str] = field(default_factory=list)
    contracts: List[ContractRow] = field(default_factory=list)
    data_quality_flags: List[str] = field(default_factory=list)
    provider: str = "yfinance"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize snapshot and nested contracts for JSON persistence."""
        return {
            "ticker": self.ticker,
            "as_of": self.as_of,
            "spot_price": self.spot_price,
            "expirations": self.expirations,
            "contracts": [row.to_dict() for row in self.contracts],
            "data_quality_flags": self.data_quality_flags,
            "provider": self.provider,
        }

