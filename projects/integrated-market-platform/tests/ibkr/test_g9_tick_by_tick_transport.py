"""G9 outer transport tick-by-tick surface (offline / fake broker)."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from ibkr.config import IbkrConfig
from ibkr.observational_transport import IbkrObservationalTransport, LiveGateDisabled


def _tws_config(*, live_enabled: bool) -> IbkrConfig:
    return IbkrConfig.from_env(os.environ, root=ROOT)


class _RecordingAdapter:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def on_tick_by_tick_all_last(self, req_id, tick_type, price, size, **kwargs) -> None:
        self.calls.append((req_id, tick_type, price, size, kwargs))

    def on_error(self, req_id, code, message, **kwargs) -> None:
        pass

    def on_connection_state(self, state, *, reason=None) -> None:
        pass


class _FakeBroker:
    def __init__(self) -> None:
        self.client = SimpleNamespace(
            reqTickByTickData=lambda *args: None,
            cancelTickByTickData=lambda req_id: None,
        )
        self.wrapper = SimpleNamespace(tickByTickAllLast=lambda *args, **kwargs: None)
        self.connected = True

    def connect(self, *args, **kwargs) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def isConnected(self) -> bool:
        return self.connected


class G9TickByTickTransportTests(unittest.TestCase):
    def test_live_gate_required(self) -> None:
        base = _tws_config(live_enabled=False)
        config = IbkrConfig(
            live_enabled=False,
            gateway_url=base.gateway_url,
            capture_root=base.capture_root,
            transport="tws",
            tws_host=base.tws_host,
            tws_port=base.tws_port,
            tws_client_id=base.tws_client_id,
        )
        with self.assertRaises(LiveGateDisabled):
            IbkrObservationalTransport(config, broker_factory=lambda c: _FakeBroker())

    def test_req_tick_by_tick_records_request(self) -> None:
        base = _tws_config(live_enabled=True)
        config = IbkrConfig(
            live_enabled=True,
            gateway_url=base.gateway_url,
            capture_root=base.capture_root,
            transport="tws",
            tws_host=base.tws_host,
            tws_port=base.tws_port,
            tws_client_id=base.tws_client_id,
        )
        broker = _FakeBroker()
        calls: list[tuple] = []
        broker.client.reqTickByTickData = lambda *args: calls.append(args)
        transport = IbkrObservationalTransport(config, broker_factory=lambda c: broker)
        transport.req_tick_by_tick_data(42, {"symbol": "AAPL"})
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], 42)

    def test_wrapper_forwards_tick_by_tick_callback(self) -> None:
        base = _tws_config(live_enabled=True)
        config = IbkrConfig(
            live_enabled=True,
            gateway_url=base.gateway_url,
            capture_root=base.capture_root,
            transport="tws",
            tws_host=base.tws_host,
            tws_port=base.tws_port,
            tws_client_id=base.tws_client_id,
        )
        broker = _FakeBroker()
        adapter = _RecordingAdapter()
        transport = IbkrObservationalTransport(config, adapter=adapter, broker_factory=lambda c: broker)
        transport.req_tick_by_tick_data(7, {"symbol": "AAPL"})
        attrib = SimpleNamespace(pastLimit=False, unreported=False)
        broker.wrapper.tickByTickAllLast(7, 2, 1_700_000_000, 100.5, 10.0, attrib, "NASDAQ", "")
        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(adapter.calls[0][0], 7)
        self.assertEqual(adapter.calls[0][2], 100.5)


if __name__ == "__main__":
    unittest.main()
