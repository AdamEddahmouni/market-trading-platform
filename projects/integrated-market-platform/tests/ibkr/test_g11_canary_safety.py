"""G11 canary harness fail-closed safety tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.ibkr.canary import IbkrReadOnlyCanary
from tools.ibkr.config import IbkrConfig


class G11CanarySafetyTests(unittest.TestCase):
    def test_blocked_when_live_disabled(self) -> None:
        config = IbkrConfig(
            live_enabled=False,
            gateway_url="https://127.0.0.1:5000/v1/api",
            capture_root=ROOT / "evidence" / "market_data" / "ibkr",
        )
        report = IbkrReadOnlyCanary().run(config)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertTrue(
            any("LIVE_ACCESS_NOT_ENABLED_BY_CONFIG" in item for item in report["blockers"])
        )

    @patch("tools.ibkr.canary.probe_loopback", return_value=True)
    @patch("tools.ibkr.canary.build_query_provider")
    @patch("tools.ibkr.canary.resolve_working_client_id")
    def test_bounded_request_count(self, resolve_client, build_provider, _probe) -> None:
        resolve_client.return_value = (
            37,
            {"connection_result": "CONNECTED", "host": "127.0.0.1", "port": 4001},
        )
        class FakeProvider:
            def fetch_secdef_search(self, symbol):
                return [{"conid": 1, "symbol": symbol, "secType": "STK"}]

            def fetch_historical_bars(self, *, con_id, period, bar):
                return {"data": []}

            def fetch_portfolio_accounts(self):
                return {"accounts": ["DU1"]}

            def shutdown(self) -> None:
                return None

        build_provider.return_value = FakeProvider()
        config = IbkrConfig(
            live_enabled=True,
            gateway_url="https://127.0.0.1:5000/v1/api",
            capture_root=ROOT / "evidence" / "market_data" / "ibkr",
            transport="tws",
        )
        report = IbkrReadOnlyCanary(max_requests=1, include_account=True, include_streaming=False).run(config)
        self.assertEqual(report["status"], "COMPLETE")
        self.assertLessEqual(report["request_count"], 1)

    def test_gate_classification_distinct_from_transport(self) -> None:
        from tools.ibkr.canary import classify_gate

        config = IbkrConfig(
            live_enabled=False,
            gateway_url="https://127.0.0.1:5000/v1/api",
            capture_root=ROOT / "evidence" / "market_data" / "ibkr",
            transport="tws",
        )
        gate = classify_gate(config)
        self.assertEqual(gate["gate_state"], "LIVE_ACCESS_NOT_ENABLED_BY_CONFIG")
        self.assertIn("tws", gate["transport_probe"])

    def test_no_execution_surface_in_canary_module(self) -> None:
        from tools.ibkr.canary import assert_no_execution_surface

        assert_no_execution_surface()


if __name__ == "__main__":
    unittest.main()
