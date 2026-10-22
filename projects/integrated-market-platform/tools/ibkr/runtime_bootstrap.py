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
from typing import Any

from market_platform_foundation.market_data.delayed_futures_bridge import inject_delayed_futures_source
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
from .futures_delayed import CLIENT_ID_OFFSET, IbkrDelayedFutures
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


def install_delayed_futures_source(env: Any = os.environ) -> IbkrDelayedFutures | None:
    """Inject the delayed futures source when IBKR TWS access is explicitly enabled; otherwise leave it absent."""

    cfg = IbkrConfig.from_env(env, root=ROOT)
    if not cfg.live_enabled or str(env.get("IMP_IBKR_TRANSPORT", "")).strip().lower() != "tws":
        return None
    source = IbkrDelayedFutures(host=cfg.tws_host, port=cfg.tws_port, client_id=cfg.tws_client_id + CLIENT_ID_OFFSET)
    inject_delayed_futures_source(source)
    source.start()
    return source


__all__ = [
    "IbkrObservationalRuntimeBootstrap",
    "install_delayed_futures_source",
    "install_ibkr_observational_provider",
]
