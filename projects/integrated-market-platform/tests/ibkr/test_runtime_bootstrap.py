"""Outer IBKR runtime bootstrap owns concrete transport construction."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from tools.ibkr.runtime_bootstrap import (  # noqa: E402
    IbkrObservationalRuntimeBootstrap,
    install_ibkr_observational_provider,
)


class _EventList:
    def __iadd__(self, handler: object) -> "_EventList":
        return self


class FakeStreamingBroker:
    def __init__(self) -> None:
        self.errorEvent = _EventList()
        self.disconnectedEvent = _EventList()
        self.wrapper = SimpleNamespace()
        self.client = SimpleNamespace()

    def connect(self, *args, **kwargs) -> None:
        return None

    def disconnect(self) -> None:
        return None

    def isConnected(self) -> bool:
        return False


class RuntimeBootstrapTests(unittest.TestCase):
    def test_bootstrap_constructs_transport_outside_src(self) -> None:
        env = {
            "IMP_IBKR_LIVE": "1",
            "IMP_IBKR_TRANSPORT": "tws",
            "IMP_IBKR_TWS_HOST": "127.0.0.1",
            "IMP_IBKR_TWS_PORT": "4001",
            "IMP_IBKR_TWS_CLIENT_ID": "37",
            "IMP_IBKR_GATEWAY_URL": "https://127.0.0.1:5000/v1/api",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch(
                "tools.ibkr.observational_transport._default_broker_factory",
                return_value=FakeStreamingBroker(),
            ):
                transport, config = IbkrObservationalRuntimeBootstrap().construct()
        self.assertTrue(config.live_enabled)
        self.assertTrue(hasattr(transport, "req_mkt_data"))
        self.assertFalse(hasattr(transport, "placeOrder"))

    def test_install_registers_src_injection_protocol(self) -> None:
        from market_platform_foundation.market_data.ibkr_runtime_bridge import (
            inject_ibkr_observational_provider,
            injected_ibkr_observational_provider,
        )

        inject_ibkr_observational_provider(None)
        try:
            install_ibkr_observational_provider()
            provider = injected_ibkr_observational_provider()
            self.assertIsNotNone(provider)
            self.assertTrue(hasattr(provider, "construct"))
        finally:
            inject_ibkr_observational_provider(None)


if __name__ == "__main__":
    unittest.main()
