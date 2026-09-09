"""G11 IBKR read-only query runtime bridge (src-side, no tools import)."""

from __future__ import annotations

from typing import Any, Protocol

from ..providers.ibkr_observational.query_provider import (
    IbkrObservationalQueryService,
    IbkrReadOnlyQueryProvider,
)
from .runtime_composition import ObservationalRuntimeComposition


class IbkrReadOnlyQueryProviderFactory(Protocol):
    """Outer bootstrap supplies read-only query provider instances."""

    def construct(self) -> IbkrReadOnlyQueryProvider: ...


_INJECTED_QUERY_PROVIDER: IbkrReadOnlyQueryProviderFactory | None = None


def inject_ibkr_readonly_query_provider(
    provider: IbkrReadOnlyQueryProviderFactory | None,
) -> None:
    """Register or clear the outer IBKR read-only query constructor."""

    global _INJECTED_QUERY_PROVIDER
    _INJECTED_QUERY_PROVIDER = provider


def injected_ibkr_readonly_query_provider() -> IbkrReadOnlyQueryProviderFactory | None:
    return _INJECTED_QUERY_PROVIDER


def attach_ibkr_query_service(
    composition: ObservationalRuntimeComposition,
    provider: IbkrReadOnlyQueryProvider,
    *,
    lookup: Any | None = None,
) -> IbkrObservationalQueryService:
    """Attach canonical query service with injected outer provider."""
    return composition.attach_ibkr_query_service(provider, lookup=lookup)


__all__ = [
    "IbkrReadOnlyQueryProviderFactory",
    "attach_ibkr_query_service",
    "inject_ibkr_readonly_query_provider",
    "injected_ibkr_readonly_query_provider",
]
