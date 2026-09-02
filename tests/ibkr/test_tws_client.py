from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools.ibkr.client import EndpointNotAllowed, LiveGateDisabled
from tools.ibkr.config import IbkrConfig
from tools.ibkr.tws_client import (
    TwsCapabilityUnavailable,
    TwsDependencyError,
    TwsIbkrClient,
)


class FakeBroker:
    def __init__(self) -> None:
        self.connected = False
        self.connect_args: tuple[object, ...] = ()
        self.disconnect_calls = 0
        self.calls: list[tuple[str, object]] = []
        self.order_calls: list[object] = []

    def connect(self, host, port, clientId, timeout, readonly):
        self.connect_args = (host, port, clientId, timeout, readonly)
        self.connected = True
        return True

    def disconnect(self) -> None:
        self.disconnect_calls += 1
        self.connected = False

    def isConnected(self) -> bool:
        return self.connected

    def reqMatchingSymbols(self, symbol):
        self.calls.append(("matching", symbol))
        return [
            SimpleNamespace(
                contract=SimpleNamespace(
                    symbol=symbol,
                    conId=265598,
                    secType="STK",
                    primaryExchange="NASDAQ",
                )
            )
        ]

    def reqMktData(self, contract, *args, **kwargs):
        self.calls.append(("market_data", contract))
        return SimpleNamespace(
            contract=contract,
            bid=225.0,
            ask=225.1,
            last=225.05,
            volume=100,
        )

    def reqMarketDataType(self, marketDataType):
        self.calls.append(("market_data_type", marketDataType))

    def reqHistoricalData(self, contract, *args, **kwargs):
        self.calls.append(("history", contract))
        return [
            SimpleNamespace(
                date="20260901 16:00:00",
                open=224.0,
                high=226.0,
                low=223.0,
                close=225.0,
                volume=1000,
            )
        ]

    def reqSecDefOptParams(self, *args, **kwargs):
        self.calls.append(("options", args))
        return [
            SimpleNamespace(
                exchange="SMART",
                tradingClass="AAPL",
                expirations={"20260918"},
                strikes={225.0},
            )
        ]

    def reqScannerParameters(self):
        self.calls.append(("scanner", None))
        return "<ScannerParameters />"

    def accountSummary(self):
        self.calls.append(("portfolio", None))
        return [SimpleNamespace(account="DU-SECRET", tag="NetLiquidation", value="1000")]


class TwsIbkrClientTests(unittest.TestCase):
    def _config(self, root: Path, **overrides: str) -> IbkrConfig:
        return IbkrConfig.from_env({"IMP_IBKR_LIVE": "1", "IMP_IBKR_TRANSPORT": "tws", **overrides}, root=root)

    def _client(self, root: Path) -> tuple[TwsIbkrClient, FakeBroker]:
        broker = FakeBroker()
        client = TwsIbkrClient(self._config(root), broker_factory=lambda _config: broker)
        return client, broker

    def test_connects_to_validated_tws_settings_in_read_only_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client, broker = self._client(Path(tmp))
        self.assertEqual(broker.connect_args[:3], ("127.0.0.1", 4001, 37))
        self.assertTrue(broker.connect_args[4])
        client.close()

    def test_contract_search_uses_read_only_matching_symbols_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client, broker = self._client(Path(tmp))
            result = client.request_json(
                "GET",
                "/iserver/secdef/search",
                params={"symbol": "AAPL"},
            )
            client.close()
        self.assertEqual(result[0]["symbol"], "AAPL")
        self.assertEqual(result[0]["conid"], 265598)
        self.assertEqual(broker.order_calls, [])

    def test_resolved_stock_contract_uses_smart_exchange_for_follow_up_requests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client, broker = self._client(Path(tmp))
            client.request_json("GET", "/iserver/secdef/search", params={"symbol": "AAPL"})
            client.request_json(
                "GET",
                "/iserver/marketdata/snapshot",
                params={"conids": "265598"},
            )
            client.close()
        contract = next(value for name, value in broker.calls if name == "market_data")
        self.assertEqual(getattr(contract, "exchange", None), "SMART")
        self.assertIn(("market_data_type", 3), broker.calls)

    def test_empty_history_is_reported_as_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            broker = FakeBroker()
            broker.reqHistoricalData = lambda *args, **kwargs: []
            client = TwsIbkrClient(self._config(Path(tmp)), broker_factory=lambda _config: broker)
            client.request_json("GET", "/iserver/secdef/search", params={"symbol": "AAPL"})
            with self.assertRaises(TwsCapabilityUnavailable):
                client.request_json(
                    "GET",
                    "/hmds/history",
                    params={"conid": "265598", "period": "1d", "bar": "1h"},
                )
            client.close()

    def test_history_datetime_is_serialized_before_capture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            broker = FakeBroker()
            broker.reqHistoricalData = lambda *args, **kwargs: [
                SimpleNamespace(
                    date=datetime(2026, 9, 1, 16, tzinfo=timezone.utc),
                    open=224.0,
                    high=226.0,
                    low=223.0,
                    close=225.0,
                    volume=1000,
                )
            ]
            client = TwsIbkrClient(self._config(Path(tmp)), broker_factory=lambda _config: broker)
            client.request_json("GET", "/iserver/secdef/search", params={"symbol": "AAPL"})
            result = client.request_json(
                "GET",
                "/hmds/history",
                params={"conid": "265598", "period": "1d", "bar": "1h"},
            )
            client.close()
        self.assertEqual(result["data"][0]["t"], "2026-09-01T16:00:00+00:00")

    def test_observational_paths_return_normalized_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client, broker = self._client(Path(tmp))
            search = client.request_json("GET", "/iserver/secdef/search", params={"symbol": "AAPL"})
            conid = str(search[0]["conid"])
            snapshot = client.request_json(
                "GET",
                "/iserver/marketdata/snapshot",
                params={"conids": conid},
            )
            history = client.request_json(
                "GET",
                "/hmds/history",
                params={"conid": conid, "period": "1d", "bar": "1h"},
            )
            options = client.request_json("GET", "/trsrv/secdef", params={"symbols": "AAPL"})
            scanner = client.request_json("GET", "/iserver/scanner/params")
            portfolio = client.request_json("GET", "/portfolio/accounts")
            client.close()
        self.assertEqual(snapshot[0]["conid"], 265598)
        self.assertEqual(history["data"][0]["c"], 225.0)
        self.assertEqual(options[0]["tradingClass"], "AAPL")
        self.assertTrue(scanner["available"])
        self.assertTrue(portfolio[0]["available"])
        self.assertEqual(broker.order_calls, [])

    def test_auth_status_reflects_socket_connection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client, broker = self._client(Path(tmp))
            status = client.request_json("GET", "/iserver/auth/status")
            client.close()
        self.assertEqual(status, {"connected": True, "authenticated": True})
        self.assertNotIn(("matching", "AAPL"), broker.calls)

    def test_unsupported_paths_are_rejected_before_broker_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client, broker = self._client(Path(tmp))
            with self.assertRaises(EndpointNotAllowed):
                client.request_json("POST", "/iserver/account/DU123/orders")
            client.close()
        self.assertEqual(broker.calls, [])

    def test_disabled_gate_stops_before_broker_factory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(LiveGateDisabled):
                TwsIbkrClient(
                    IbkrConfig.from_env({"IMP_IBKR_TRANSPORT": "tws"}, root=Path(tmp)),
                    broker_factory=lambda _config: self.fail("broker factory called"),
                )

    def test_missing_optional_dependency_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(sys.modules, {"ib_insync": None}):
                with self.assertRaises(TwsDependencyError):
                    TwsIbkrClient(self._config(Path(tmp)))

    def test_close_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client, broker = self._client(Path(tmp))
            client.close()
            client.close()
        self.assertEqual(broker.disconnect_calls, 1)


if __name__ == "__main__":
    unittest.main()
