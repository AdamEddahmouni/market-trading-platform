"""Runtime provider composition registry per ADR-PROV-001."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from .contracts import (
    DisclosureProvider,
    EquityQuoteProvider,
    OptionChainProvider,
    PaperExecutionProvider,
    ReferenceDataProvider,
)
from .stubs import (
    DisabledPaperExecutionProvider,
    UnconfiguredDisclosureProvider,
    UnconfiguredEquityQuoteProvider,
    UnconfiguredOptionChainProvider,
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


__all__ = [
    "ProviderComposition",
    "configure_provider_composition",
    "get_provider_composition",
]
