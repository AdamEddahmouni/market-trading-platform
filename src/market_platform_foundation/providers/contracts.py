"""Broker-neutral provider contracts per ADR-PROV-001."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


PROVIDER_UNAVAILABLE = "PROVIDER_NOT_CONFIGURED"
EXECUTION_DISABLED = "EXECUTION_NOT_ENABLED"


@dataclass(frozen=True)
class ProviderResult:
    """Normalized provider response with explicit availability semantics."""

    status: str
    events: tuple[dict[str, Any], ...] = ()
    reason_code: str | None = None
    provider_id: str = ""
    capability: str = ""


@dataclass(frozen=True)
class SymbolMapping:
    provider_symbol: str
    instrument_id: str
    venue_id: str = "US_EQUITY"


class DisclosureProvider(Protocol):
    """SEC and other public disclosure sources (Form 4, 13D/G, 13F)."""

    provider_id: str
    capability: str

    def fetch_disclosures(
        self,
        symbol: str,
        *,
        as_of_time_ns: int | None = None,
    ) -> ProviderResult:
        ...


class ReferenceDataProvider(Protocol):
    """CIK and symbol cross-reference lookups."""

    provider_id: str
    capability: str

    def resolve_symbol(self, symbol: str) -> ProviderResult:
        ...


class EquityQuoteProvider(Protocol):
    """Delayed or entitled equity quote snapshots."""

    provider_id: str
    capability: str

    def fetch_quote(self, symbol: str) -> ProviderResult:
        ...


class OptionChainProvider(Protocol):
    """Options chain snapshots (Tradier-class capability)."""

    provider_id: str
    capability: str

    def fetch_chain(
        self,
        symbol: str,
        *,
        expiration: str | None = None,
        as_of_time_ns: int | None = None,
    ) -> ProviderResult:
        ...


class FuturesChainProvider(Protocol):
    """Futures chain snapshots with canonical contract metadata."""

    provider_id: str
    capability: str

    def fetch_chain(self, symbol: str, *, as_of_time_ns: int | None = None) -> ProviderResult:
        ...


class DistributionForecastProvider(Protocol):
    """Physical return distribution forecasts (SHARED P2)."""

    provider_id: str
    capability: str

    def fetch_distribution_forecast(
        self,
        symbol: str,
        *,
        as_of_time_ns: int | None = None,
    ) -> ProviderResult:
        ...


class OrderFlowProvider(Protocol):
    """Signed volume / CVD order-flow snapshots."""

    provider_id: str
    capability: str

    def fetch_order_flow(
        self,
        symbol: str,
        *,
        as_of_time_ns: int | None = None,
    ) -> ProviderResult:
        ...


class PaperExecutionProvider(Protocol):
    """Paper execution — disabled unless explicitly enabled."""

    provider_id: str
    capability: str

    def place_order(self, intent: dict[str, Any]) -> ProviderResult:
        ...


__all__ = [
    "DisclosureProvider",
    "DistributionForecastProvider",
    "EquityQuoteProvider",
    "EXECUTION_DISABLED",
    "FuturesChainProvider",
    "OptionChainProvider",
    "OrderFlowProvider",
    "PaperExecutionProvider",
    "PROVIDER_UNAVAILABLE",
    "ProviderResult",
    "ReferenceDataProvider",
    "SymbolMapping",
]
