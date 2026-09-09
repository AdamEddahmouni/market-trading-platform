"""G8 IBKR observational runtime bridge (src-side, no tools import).

Accepts an injected transport instance (or an injected construction protocol)
and wires it into the G7 composition graph. Concrete ``tools/ibkr`` transport
construction lives in the outer bootstrap, never here.
"""

from __future__ import annotations

from typing import Any, Protocol

from ..providers.ibkr_observational.adapter import IbkrObservationalAdapter, IbkrObservationalConfig
from ..xa01.registry import get_registry
from .runtime_composition import ObservationalRuntimeComposition


class IbkrObservationalTransportProvider(Protocol):
    """Src-defined injection protocol. Outer bootstrap supplies the instance."""

    def construct(self) -> tuple[Any, IbkrObservationalConfig]:
        """Return ``(transport, adapter_config)``. Construction is outer-owned."""


_INJECTED_PROVIDER: IbkrObservationalTransportProvider | None = None


def inject_ibkr_observational_provider(
    provider: IbkrObservationalTransportProvider | None,
) -> None:
    """Register or clear the outer IBKR transport constructor."""

    global _INJECTED_PROVIDER
    _INJECTED_PROVIDER = provider


def injected_ibkr_observational_provider() -> IbkrObservationalTransportProvider | None:
    return _INJECTED_PROVIDER


def attach_ibkr_observational_runtime(
    composition: ObservationalRuntimeComposition,
    transport: Any,
    *,
    config: IbkrObservationalConfig,
    connect: bool = True,
) -> IbkrObservationalAdapter:
    """Attach canonical IBKR adapter with injected outer transport."""
    adapter = composition.attach_ibkr_adapter(
        transport,
        config=config,
        lookup=get_registry(),
    )
    attach = getattr(transport, "attach_adapter", None)
    if callable(attach):
        attach(adapter)
    if connect and config.live_enabled:
        adapter.connect()
        composition.sync_ibkr_runtime_state()
    return adapter


def shutdown_ibkr_observational_runtime(composition: ObservationalRuntimeComposition) -> None:
    composition.shutdown()


__all__ = [
    "IbkrObservationalTransportProvider",
    "attach_ibkr_observational_runtime",
    "inject_ibkr_observational_provider",
    "injected_ibkr_observational_provider",
    "shutdown_ibkr_observational_runtime",
]
