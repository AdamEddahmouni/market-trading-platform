"""Outer IBKR observational runtime bootstrap (G8).

Constructs the concrete TWS transport and injects it into canonical src
runtime. ``src/market_platform_foundation`` must never import this module.

Dependency direction:
    tools/ibkr/runtime_bootstrap.py
        ↓ constructs IbkrObservationalTransport
        ↓ injects IbkrObservationalTransportProvider
    src live_runtime / ObservationalRuntimeComposition
        ↓ IbkrTransport protocol
    IbkrObservationalAdapter
"""

from __future__ import annotations

import os
from pathlib import Path

from market_platform_foundation.market_data.ibkr_runtime_bridge import (
    inject_ibkr_observational_provider,
)
from market_platform_foundation.market_data.ibkr_query_bridge import (
    inject_ibkr_readonly_query_provider,
)
from market_platform_foundation.providers.ibkr_observational.adapter import (
    IbkrObservationalConfig,
)

from .config import IbkrConfig
from .observational_transport import IbkrObservationalTransport
from .query_provider import IbkrReadOnlyQueryBootstrap

ROOT = Path(__file__).resolve().parents[2]


class IbkrObservationalRuntimeBootstrap:
    """Outer construction boundary for ``IbkrObservationalTransport``."""

    def construct(self) -> tuple[IbkrObservationalTransport, IbkrObservationalConfig]:
        cfg = IbkrConfig.from_env(os.environ, root=ROOT)
        transport = IbkrObservationalTransport(cfg)
        adapter_config = IbkrObservationalConfig(
            live_enabled=cfg.live_enabled,
            host=cfg.tws_host,
            port=cfg.tws_port,
            client_id=cfg.tws_client_id,
            readonly=True,
            capture_path=str(cfg.capture_root / "callback-capture.jsonl"),
        )
        return transport, adapter_config


def install_ibkr_observational_provider() -> None:
    """Register the outer constructor with canonical live_runtime."""

    inject_ibkr_observational_provider(IbkrObservationalRuntimeBootstrap())
    inject_ibkr_readonly_query_provider(IbkrReadOnlyQueryBootstrap())


__all__ = [
    "IbkrObservationalRuntimeBootstrap",
    "install_ibkr_observational_provider",
]
