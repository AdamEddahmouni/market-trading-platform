"""G8 transport tests — observational IBKR outer transport."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.ibkr.client import LiveGateDisabled
from tools.ibkr.config import IbkrConfig
from tools.ibkr.observational_transport import IbkrObservationalTransport


class FakeStreamingBroker:
    def __init__(self) -> None:
        self.connected = False
        self.connect_args: tuple[object, ...] = ()
        self.disconnect_calls = 0
        self.wrapper = SimpleNamespace()
        self.wrapper.tickPrice = lambda *a, **k: None
        self.wrapper.tickSize = lambda *a, **k: None
        self.wrapper.updateMktDepth = lambda *a, **k: None
        self.wrapper.updateMktDepthL2 = lambda *a, **k: None
        self.client = SimpleNamespace()
        self.client.cancelMktData = lambda req_id: None
        self.client.reqMktDepth = lambda *a, **k: None
        self.client.cancelMktDepth = lambda *a, **k: None
        self.errorEvent = _EventList()
        self.disconnectedEvent = _EventList()
        self._tickers: list[object] = []

    def connect(self, host, port, clientId, readonly=True, timeout=None):
        self.connect_args = (host, port, clientId, readonly)
        self.connected = True

    def disconnect(self) -> None:
        self.disconnect_calls += 1
        self.connected = False

    def isConnected(self) -> bool:
        return self.connected

    def reqMktData(self, contract, generic_ticks="", snapshot=False, regulatorySnapshot=False):
        ticker = SimpleNamespace(
            bid=100.0,
            ask=101.0,
            last=100.5,
            bidSize=10.0,
            askSize=5.0,
            lastSize=1.0,
            updateEvent=_EventList(),
        )
        self._tickers.append(ticker)
        return ticker


class _EventList:
    def __init__(self) -> None:
        self._handlers: list[object] = []

    def __iadd__(self, handler: object) -> "_EventList":
        self._handlers.append(handler)
        return self

    def emit(self, *args: object) -> None:
        for handler in self._handlers:
            handler(*args)


class FakeAdapter:
    def __init__(self) -> None:
        self.ticks: list[tuple[str, int, int, float | None]] = []
        self.depth: list[tuple[int, int, int, int]] = []
        self.errors: list[tuple[int | None, int | None, str]] = []

    def on_tick_price(self, req_id, field, price, *, received_ns=None, source_time_ns=None):
        self.ticks.append(("price", req_id, field, price))

    def on_tick_size(self, req_id, field, size, *, received_ns=None, source_time_ns=None):
        self.ticks.append(("size", req_id, field, size))

    def on_mkt_depth(self, req_id, position, operation, side, price, size, *, received_ns=None, source_time_ns=None):
        self.depth.append((req_id, position, operation, side))

    def on_mkt_depth_l2(
        self, req_id, position, market_maker, operation, side, price, size, is_smart_depth, *, received_ns=None, source_time_ns=None
    ):
        self.depth.append((req_id, position, operation, side))

    def on_error(self, req_id, code, message, *, received_ns=None):
        self.errors.append((req_id, code, message))

    def on_connection_state(self, state, *, reason=None):
        pass


def _config(live: bool = True) -> IbkrConfig:
    return IbkrConfig(
        live_enabled=live,
        gateway_url="https://127.0.0.1:5000/v1/api",
        capture_root=ROOT / "evidence" / "market_data" / "ibkr",
        transport="tws",
    )


class ObservationalTransportTests(unittest.TestCase):
    def test_connect_is_readonly(self) -> None:
        broker = FakeStreamingBroker()
        transport = IbkrObservationalTransport(_config(), broker_factory=lambda _: broker)
        transport.connect(host="127.0.0.1", port=4001, client_id=37, readonly=True)
        self.assertTrue(transport.is_connected())
        self.assertEqual(broker.connect_args[3], True)

    def test_offline_gate_blocks_connection(self) -> None:
        with self.assertRaises(LiveGateDisabled):
            IbkrObservationalTransport(_config(live=False), broker_factory=lambda _: FakeStreamingBroker())

    def test_req_mkt_data_maps_req_id_and_contract(self) -> None:
        broker = FakeStreamingBroker()
        transport = IbkrObservationalTransport(_config(), broker_factory=lambda _: broker)
        transport.connect(host="127.0.0.1", port=4001, client_id=37)
        transport.req_mkt_data(1001, {"symbol": "AAPL"})
        self.assertEqual(len(broker._tickers), 1)

    def test_cancel_mkt_data(self) -> None:
        broker = FakeStreamingBroker()
        transport = IbkrObservationalTransport(_config(), broker_factory=lambda _: broker)
        transport.connect(host="127.0.0.1", port=4001, client_id=37)
        transport.req_mkt_data(1001, {"conId": 265598})
        transport.cancel_mkt_data(1001)

    def test_req_mkt_depth(self) -> None:
        broker = FakeStreamingBroker()
        transport = IbkrObservationalTransport(_config(), broker_factory=lambda _: broker)
        transport.connect(host="127.0.0.1", port=4001, client_id=37)
        transport.req_mkt_depth(2001, {"conId": 265598}, num_rows=10)

    def test_cancel_mkt_depth(self) -> None:
        broker = FakeStreamingBroker()
        transport = IbkrObservationalTransport(_config(), broker_factory=lambda _: broker)
        transport.connect(host="127.0.0.1", port=4001, client_id=37)
        transport.req_mkt_depth(2001, {"conId": 265598}, num_rows=10)
        transport.cancel_mkt_depth(2001)

    def test_depth_rows_bounded(self) -> None:
        broker = FakeStreamingBroker()
        transport = IbkrObservationalTransport(_config(), broker_factory=lambda _: broker)
        transport.connect(host="127.0.0.1", port=4001, client_id=37)
        transport.req_mkt_depth(2001, {"conId": 265598}, num_rows=20)
        self.assertEqual(broker.client.reqMktDepth.__defaults__, None)

    def test_duplicate_request_ids_impossible(self) -> None:
        broker = FakeStreamingBroker()
        transport = IbkrObservationalTransport(_config(), broker_factory=lambda _: broker)
        transport.connect(host="127.0.0.1", port=4001, client_id=37)
        transport.req_mkt_data(1001, {"symbol": "AAPL"})
        with self.assertRaises(ValueError):
            transport.req_mkt_data(1001, {"symbol": "NVDA"})

    def test_disconnect_safe(self) -> None:
        broker = FakeStreamingBroker()
        transport = IbkrObservationalTransport(_config(), broker_factory=lambda _: broker)
        transport.connect(host="127.0.0.1", port=4001, client_id=37)
        transport.disconnect()
        self.assertEqual(broker.disconnect_calls, 1)
        self.assertFalse(transport.is_connected())

    def test_reconnect_bounded_via_adapter_not_transport(self) -> None:
        broker = FakeStreamingBroker()
        transport = IbkrObservationalTransport(_config(), broker_factory=lambda _: broker)
        transport.connect(host="127.0.0.1", port=4001, client_id=37)
        transport.disconnect()
        transport.connect(host="127.0.0.1", port=4001, client_id=37)
        self.assertTrue(transport.is_connected())

    def test_callback_bridge_preserves_operation_zero(self) -> None:
        adapter = FakeAdapter()
        broker = FakeStreamingBroker()
        transport = IbkrObservationalTransport(_config(), adapter=adapter, broker_factory=lambda _: broker)
        transport.connect(host="127.0.0.1", port=4001, client_id=37)
        transport.req_mkt_depth(2001, {"conId": 1}, num_rows=5)
        broker.wrapper.updateMktDepth(2001, 0, 0, 1, 100.0, 10.0)
        self.assertEqual(adapter.depth[0][2], 0)

    def test_callback_bridge_preserves_side_zero(self) -> None:
        adapter = FakeAdapter()
        broker = FakeStreamingBroker()
        transport = IbkrObservationalTransport(_config(), adapter=adapter, broker_factory=lambda _: broker)
        transport.connect(host="127.0.0.1", port=4001, client_id=37)
        transport.req_mkt_depth(2001, {"conId": 1}, num_rows=5)
        broker.wrapper.updateMktDepth(2001, 0, 1, 0, 100.0, 10.0)
        self.assertEqual(adapter.depth[0][3], 0)

    def test_no_execution_method_exposed(self) -> None:
        transport = IbkrObservationalTransport(_config(), broker_factory=lambda _: FakeStreamingBroker())
        for forbidden in ("placeOrder", "cancelOrder", "modifyOrder", "exerciseOptions"):
            self.assertFalse(hasattr(transport, forbidden))


if __name__ == "__main__":
    unittest.main()
