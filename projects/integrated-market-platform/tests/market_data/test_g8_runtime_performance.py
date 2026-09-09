"""G8 observational runtime overhead measurements (fake/replay only).

Classification: LIVE_RUNTIME_PERFORMANCE_MEASURED —
development-machine observational measurement only;
not provider-network throughput;
not production SLA.
"""

from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "providers"))

from market_platform_foundation.market_data.runtime_composition import (  # noqa: E402
    ObservationalRuntimeComposition,
)
from market_platform_foundation.providers.ibkr_observational.adapter import (  # noqa: E402
    IbkrObservationalConfig,
)
from market_platform_foundation.providers.ibkr_observational.capture import (  # noqa: E402
    replay_records,
)
from market_platform_foundation.providers.ibkr_observational.constants import (  # noqa: E402
    IB_OP_INSERT,
    IB_OP_UPDATE,
    IB_SIDE_BID,
)
from tools.ibkr.config import IbkrConfig  # noqa: E402
from tools.ibkr.observational_transport import IbkrObservationalTransport  # noqa: E402

from ibkr_observational_support import FakeLookup, FakeTransport, connected_adapter, make_record  # noqa: E402

AAPL = make_record("AAPL")
N = 5_000
EVIDENCE_PATH = ROOT / "artifacts" / "g8-runtime-performance.json"
_RESULTS: dict[str, float] = {}


class _EventList:
    def __init__(self) -> None:
        self._handlers: list[object] = []

    def __iadd__(self, handler: object) -> "_EventList":
        self._handlers.append(handler)
        return self


class FakeStreamingBroker:
    def __init__(self) -> None:
        self.connected = False
        self.wrapper = SimpleNamespace()
        self.wrapper.tickPrice = lambda *a, **k: None
        self.wrapper.tickSize = lambda *a, **k: None
        self.wrapper.updateMktDepth = lambda *a, **k: None
        self.wrapper.updateMktDepthL2 = lambda *a, **k: None
        self.client = SimpleNamespace()
        self.client.cancelMktData = lambda req_id: None
        self.client.reqMktDepth = lambda *a, **k: None
        self.client.cancelMktDepth = lambda req_id, is_smart_depth=False: None
        self.errorEvent = _EventList()
        self.disconnectedEvent = _EventList()

    def connect(self, host, port, clientId, readonly=True, timeout=None):
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def isConnected(self) -> bool:
        return self.connected

    def reqMktData(self, contract, generic_ticks="", snapshot=False, regulatorySnapshot=False):
        return SimpleNamespace(updateEvent=_EventList())


def _config() -> IbkrConfig:
    return IbkrConfig(
        live_enabled=True,
        gateway_url="https://127.0.0.1:5000/v1/api",
        capture_root=ROOT / "evidence" / "market_data" / "ibkr",
        transport="tws",
    )


class G8RuntimePerformanceTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls) -> None:
        if not _RESULTS:
            return
        payload = {
            "classification": "LIVE_RUNTIME_PERFORMANCE_MEASURED",
            "disclaimer": (
                "development-machine observational measurement only; "
                "not provider-network throughput; not production SLA."
            ),
            "iterations": N,
            "measurements": _RESULTS,
        }
        EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def test_outer_callback_bridge_to_canonical_adapter(self) -> None:
        composition = ObservationalRuntimeComposition()
        broker = FakeStreamingBroker()
        transport = IbkrObservationalTransport(_config(), broker_factory=lambda _: broker)
        adapter = composition.attach_ibkr_adapter(
            transport,
            config=IbkrObservationalConfig(live_enabled=True),
            lookup=FakeLookup(AAPL),
        )
        transport.attach_adapter(adapter)
        adapter.connect()
        sub = adapter.subscribe_l2(instrument_id="AAPL")
        self.assertTrue(sub.accepted, sub.reason)
        broker.wrapper.updateMktDepth(sub.req_id, 0, IB_OP_INSERT, IB_SIDE_BID, 100.0, 10.0)
        started = time.perf_counter()
        for i in range(N):
            broker.wrapper.updateMktDepth(sub.req_id, 0, IB_OP_UPDATE, IB_SIDE_BID, 100.0, float(10 + i % 5))
        elapsed = time.perf_counter() - started
        _RESULTS["callback_bridge_seconds"] = elapsed
        _RESULTS["callback_bridge_events_per_sec"] = N / elapsed
        self.assertGreater(N / elapsed, 100, f"callback bridge too slow: {N / elapsed:.0f}/s")

    def test_startup_composition(self) -> None:
        repeats = 200
        started = time.perf_counter()
        for _ in range(repeats):
            composition = ObservationalRuntimeComposition()
            composition.attach_ibkr_adapter(
                FakeTransport(),
                config=IbkrObservationalConfig(live_enabled=True),
                lookup=FakeLookup(AAPL),
            )
        elapsed = time.perf_counter() - started
        _RESULTS["startup_composition_repeats"] = float(repeats)
        _RESULTS["startup_composition_seconds_total"] = elapsed
        _RESULTS["startup_composition_seconds_each"] = elapsed / repeats
        self.assertLess(elapsed / repeats, 0.05)

    def test_subscribe_cancel_lifecycle(self) -> None:
        adapter, _ = connected_adapter(lookup=FakeLookup(AAPL))
        started = time.perf_counter()
        for _ in range(N):
            sub = adapter.subscribe_l1(instrument_id="AAPL")
            self.assertTrue(sub.accepted, sub.reason)
            adapter.cancel_l1("AAPL")
        elapsed = time.perf_counter() - started
        _RESULTS["subscribe_cancel_seconds"] = elapsed
        _RESULTS["subscribe_cancel_cycles_per_sec"] = N / elapsed
        self.assertGreater(N / elapsed, 100)

    def test_capture_replay_bridge(self) -> None:
        adapter, _ = connected_adapter(lookup=FakeLookup(AAPL))
        sub = adapter.subscribe_l2(instrument_id="AAPL")
        self.assertTrue(sub.accepted, sub.reason)
        records = [
            {
                "callback_kind": "DEPTH",
                "req_id": sub.req_id,
                "position": 0,
                "operation": IB_OP_INSERT,
                "side": IB_SIDE_BID,
                "price": 100.0,
                "size": 10.0,
                "market_maker": "",
                "is_smart_depth": False,
            }
            for _ in range(N)
        ]
        started = time.perf_counter()
        replay_records(records, dispatch=adapter.on_captured_record)
        elapsed = time.perf_counter() - started
        _RESULTS["capture_replay_seconds"] = elapsed
        _RESULTS["capture_replay_events_per_sec"] = N / elapsed
        self.assertGreater(N / elapsed, 1_000)


if __name__ == "__main__":
    unittest.main()
