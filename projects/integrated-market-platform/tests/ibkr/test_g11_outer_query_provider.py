"""G11 outer IBKR query provider injection tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.market_data.ibkr_query_bridge import (
    injected_ibkr_readonly_query_provider,
    inject_ibkr_readonly_query_provider,
)
from tools.ibkr.query_provider import (
    IbkrOuterReadOnlyQueryProvider,
    IbkrReadOnlyQueryBootstrap,
)
from tools.ibkr.runtime_bootstrap import install_ibkr_observational_provider


class _FakeClient:
    def __init__(self) -> None:
        self.closed = False

    def request_json(self, method: str, path: str, *, params=None, body=None):
        if path == "/iserver/secdef/search":
            return [{"symbol": params.get("symbol"), "conid": 1, "secType": "STK"}]
        if path == "/hmds/history":
            return {"data": [{"t": 1, "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}]}
        if path == "/portfolio/accounts":
            return {"accounts": ["DU123"]}
        return {}

    def close(self) -> None:
        self.closed = True


class G11OuterQueryProviderTests(unittest.TestCase):
    def test_outer_provider_implements_protocol(self) -> None:
        provider = IbkrOuterReadOnlyQueryProvider(_FakeClient())
        rows = provider.fetch_secdef_search("AAPL")
        self.assertEqual(len(rows), 1)
        history = provider.fetch_historical_bars(con_id=1, period="1d", bar="1h")
        self.assertIn("data", history)
        accounts = provider.fetch_portfolio_accounts()
        self.assertIn("accounts", accounts)
        provider.shutdown()
        self.assertFalse(provider.is_available())

    def test_install_registers_factory(self) -> None:
        inject_ibkr_readonly_query_provider(None)
        install_ibkr_observational_provider()
        factory = injected_ibkr_readonly_query_provider()
        self.assertIsNotNone(factory)

    @patch("tools.ibkr.query_provider.IbkrConfig.from_env")
    @patch("tools.ibkr.query_provider.IbkrClient")
    def test_bootstrap_respects_live_gate(self, client_cls, from_env) -> None:
        from tools.ibkr.client import LiveGateDisabled
        from tools.ibkr.config import IbkrConfig

        from_env.return_value = IbkrConfig(
            live_enabled=False,
            gateway_url="https://127.0.0.1:5000/v1/api",
            capture_root=ROOT / "evidence" / "market_data" / "ibkr",
        )
        with self.assertRaises(LiveGateDisabled):
            IbkrReadOnlyQueryBootstrap().construct()


if __name__ == "__main__":
    unittest.main()
