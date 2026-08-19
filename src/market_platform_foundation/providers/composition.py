"""Runtime provider composition registry per ADR-PROV-001."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from .contracts import (
    DisclosureProvider,
    DistributionForecastProvider,
    EquityQuoteProvider,
    FuturesBarsProvider,
    FuturesChainProvider,
    FuturesPositioningProvider,
    OptionChainProvider,
    OrderFlowProvider,
    PaperExecutionProvider,
    ReferenceDataProvider,
)
from .stubs import (
    DisabledPaperExecutionProvider,
    UnconfiguredDisclosureProvider,
    UnconfiguredDistributionForecastProvider,
    UnconfiguredEquityQuoteProvider,
    UnconfiguredFuturesBarsProvider,
    UnconfiguredFuturesChainProvider,
    UnconfiguredFuturesPositioningProvider,
    UnconfiguredOptionChainProvider,
    UnconfiguredOrderFlowProvider,
    UnconfiguredReferenceDataProvider,
)


@dataclass
class ProviderComposition:
    disclosure: DisclosureProvider = field(default_factory=UnconfiguredDisclosureProvider)
    reference_data: ReferenceDataProvider = field(
        default_factory=UnconfiguredReferenceDataProvider
    )
    equity_quote: EquityQuoteProvider = field(default_factory=UnconfiguredEquityQuoteProvider)
    option_chain: OptionChainProvider = field(default_factory=UnconfiguredOptionChainProvider)
    futures_chain: FuturesChainProvider = field(default_factory=UnconfiguredFuturesChainProvider)
    futures_positioning: FuturesPositioningProvider = field(
        default_factory=UnconfiguredFuturesPositioningProvider
    )
    futures_bars: FuturesBarsProvider = field(default_factory=UnconfiguredFuturesBarsProvider)
    distribution_forecast: DistributionForecastProvider = field(
        default_factory=UnconfiguredDistributionForecastProvider
    )
    order_flow: OrderFlowProvider = field(default_factory=UnconfiguredOrderFlowProvider)
    paper_execution: PaperExecutionProvider = field(
        default_factory=lambda: DisabledPaperExecutionProvider(
            enabled=os.environ.get("EXECUTION_ENABLE") == "1"
        )
    )

    def as_manifest(self) -> dict[str, Any]:
        providers = [
            self.disclosure,
            self.reference_data,
            self.equity_quote,
            self.option_chain,
            self.futures_chain,
            self.futures_positioning,
            self.futures_bars,
            self.distribution_forecast,
            self.order_flow,
            self.paper_execution,
        ]
        return {
            "capabilities": sorted(
                {
                    "capability": provider.capability,
                    "provider_id": provider.provider_id,
                }
                for provider in providers
            ),
            "logical_id": "providers.composition_manifest",
        }


_DEFAULT_COMPOSITION: ProviderComposition | None = None


def configure_provider_composition(composition: ProviderComposition | None) -> None:
    global _DEFAULT_COMPOSITION
    _DEFAULT_COMPOSITION = composition


def get_provider_composition() -> ProviderComposition:
    if _DEFAULT_COMPOSITION is None:
        return ProviderComposition()
    return _DEFAULT_COMPOSITION


def configure_fixture_provider_composition() -> ProviderComposition:
    """Register admitted fixture chain providers without enabling live adapters."""
    from .adapters.fixture_distribution import FixtureDistributionForecastProvider
    from .adapters.fixture_futures_bars import FixtureFuturesBarsProvider
    from .adapters.fixture_futures_chain import FixtureFuturesChainProvider
    from .adapters.fixture_futures_positioning import FixtureFuturesPositioningProvider
    from .adapters.fixture_option_chain import FixtureOptionChainProvider
    from .adapters.order_flow_factory import build_order_flow_provider

    composition = ProviderComposition(
        option_chain=FixtureOptionChainProvider(),
        futures_chain=FixtureFuturesChainProvider(),
        futures_positioning=FixtureFuturesPositioningProvider(),
        futures_bars=FixtureFuturesBarsProvider(),
        distribution_forecast=FixtureDistributionForecastProvider(),
        order_flow=build_order_flow_provider(),
    )
    configure_provider_composition(composition)
    return composition


__all__ = [
    "ProviderComposition",
    "configure_fixture_provider_composition",
    "configure_provider_composition",
    "get_provider_composition",
]
