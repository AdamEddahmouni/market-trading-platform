"""Fail-closed provider stubs for unconfigured capabilities."""

from __future__ import annotations

from typing import Any

from .contracts import (
    EXECUTION_DISABLED,
    PROVIDER_UNAVAILABLE,
    ProviderResult,
)


class UnconfiguredDisclosureProvider:
    provider_id = "stub.disclosure.unconfigured"
    capability = "disclosure"

    def fetch_disclosures(
        self,
        symbol: str,
        *,
        as_of_time_ns: int | None = None,
    ) -> ProviderResult:
        del symbol, as_of_time_ns
        return ProviderResult(
            status="unavailable",
            reason_code=PROVIDER_UNAVAILABLE,
            provider_id=self.provider_id,
            capability=self.capability,
        )


class UnconfiguredReferenceDataProvider:
    provider_id = "stub.reference.unconfigured"
    capability = "reference_data"

    def resolve_symbol(self, symbol: str) -> ProviderResult:
        del symbol
        return ProviderResult(
            status="unavailable",
            reason_code=PROVIDER_UNAVAILABLE,
            provider_id=self.provider_id,
            capability=self.capability,
        )


class UnconfiguredEquityQuoteProvider:
    provider_id = "stub.equity_quote.unconfigured"
    capability = "equity_quote"

    def fetch_quote(self, symbol: str) -> ProviderResult:
        del symbol
        return ProviderResult(
            status="unavailable",
            reason_code=PROVIDER_UNAVAILABLE,
            provider_id=self.provider_id,
            capability=self.capability,
        )


class UnconfiguredOptionChainProvider:
    provider_id = "stub.option_chain.unconfigured"
    capability = "option_chain"

    def fetch_chain(
        self,
        symbol: str,
        *,
        expiration: str | None = None,
        as_of_time_ns: int | None = None,
    ) -> ProviderResult:
        del symbol, expiration, as_of_time_ns
        return ProviderResult(
            status="unavailable",
            reason_code=PROVIDER_UNAVAILABLE,
            provider_id=self.provider_id,
            capability=self.capability,
        )


class UnconfiguredFuturesChainProvider:
    provider_id = "stub.futures_chain.unconfigured"
    capability = "futures_chain"

    def fetch_chain(self, symbol: str, *, as_of_time_ns: int | None = None) -> ProviderResult:
        del symbol, as_of_time_ns
        return ProviderResult(
            status="unavailable",
            reason_code=PROVIDER_UNAVAILABLE,
            provider_id=self.provider_id,
            capability=self.capability,
        )


class UnconfiguredDistributionForecastProvider:
    provider_id = "stub.distribution.unconfigured"
    capability = "distribution_forecast"

    def fetch_distribution_forecast(
        self,
        symbol: str,
        *,
        as_of_time_ns: int | None = None,
    ) -> ProviderResult:
        del symbol, as_of_time_ns
        return ProviderResult(
            status="unavailable",
            reason_code=PROVIDER_UNAVAILABLE,
            provider_id=self.provider_id,
            capability=self.capability,
        )


class DisabledPaperExecutionProvider:
    """Paper execution remains disabled unless EXECUTION_ENABLE=1 (never in CI)."""

    provider_id = "stub.execution.disabled"
    capability = "paper_execution"

    def __init__(self, *, enabled: bool = False) -> None:
        self._enabled = enabled

    def place_order(self, intent: dict[str, Any]) -> ProviderResult:
        del intent
        if not self._enabled:
            return ProviderResult(
                status="unavailable",
                reason_code=EXECUTION_DISABLED,
                provider_id=self.provider_id,
                capability=self.capability,
            )
        return ProviderResult(
            status="unavailable",
            reason_code="EXECUTION_ADAPTER_NOT_IMPLEMENTED",
            provider_id=self.provider_id,
            capability=self.capability,
        )


__all__ = [
    "DisabledPaperExecutionProvider",
    "UnconfiguredDisclosureProvider",
    "UnconfiguredDistributionForecastProvider",
    "UnconfiguredEquityQuoteProvider",
    "UnconfiguredFuturesChainProvider",
    "UnconfiguredOptionChainProvider",
    "UnconfiguredReferenceDataProvider",
]
