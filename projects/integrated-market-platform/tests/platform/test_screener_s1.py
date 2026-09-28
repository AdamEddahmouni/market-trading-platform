"""S1 broad screener contract and bounded viewport subscription tests."""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from market_platform_foundation.finviz.screener import FinvizScreenerRow
from market_platform_foundation.ui_api.screener_projections import MAX_WINDOW, ScreenerService


class Source:
    def __init__(self, success: bool = True):
        self.success = success
        self.calls = 0

    def fetch_export(self, *, filter_expr: str, columns: str):
        self.calls += 1
        assert filter_expr == "geo_usa,ind_stocksonly"
        assert columns == "1,2,3,4,5,6,25,30,31,59,64,65,66,67"
        return {
            "success": self.success,
            "error": None if self.success else "NOT_CONFIGURED",
            "received_at": "2026-09-25T13:00:00Z",
            "rows": [
                FinvizScreenerRow(ticker=f"T{i:04d}", company=f"Company {i}", price=float(i),
                                    volume=i * 100, short_float_pct=None)
                for i in range(240)
            ] if self.success else [],
        }


class Runtime:
    def __init__(self):
        self.active: set[tuple[str, str]] = set()
        self.state = SimpleNamespace(quote_for=lambda symbol: None)

    def subscribe(self, *, instrument_id, consumer_id, **kwargs):
        self.active.add((consumer_id, instrument_id))
        return [{"accepted": True}]

    def unsubscribe(self, *, instrument_id, consumer_id, **kwargs):
        self.active.discard((consumer_id, instrument_id))
        return [{"released": True}]


class ScreenerS1Tests(unittest.TestCase):
    def test_broad_contract_search_sort_and_field_truth(self):
        source = Source()
        service = ScreenerService(source_factory=lambda: source, runtime_getter=lambda **_: None)
        result = service.read()
        self.assertEqual(result["schema_version"], "screener/1.0.0")
        self.assertEqual(result["result_count"], 240)
        self.assertEqual(result["rows"][0]["symbol"], "T0239")
        self.assertEqual(result["rows"][0]["fields"]["short_float_pct"]["state"], "UNAVAILABLE")
        self.assertEqual(result["rows"][0]["fields"]["price"]["source"], "FINVIZ_ELITE")
        self.assertEqual(service.read(search="Company 42")["result_count"], 1)
        self.assertEqual(service.read(search="T0002")["rows"][0]["symbol"], "T0002")
        self.assertEqual(service.read(sort="price", descending=False)["rows"][0]["symbol"], "T0000")
        self.assertEqual(source.calls, 1)

    def test_no_capture_or_fixture_fallback(self):
        service = ScreenerService(source_factory=lambda: Source(False), runtime_getter=lambda **_: None)
        result = service.read()
        self.assertEqual(result["rows"], [])
        self.assertEqual(result["source_error"], "NOT_CONFIGURED")
        self.assertEqual(result["provider_health"][0]["state"], "UNAVAILABLE")

    def test_retry_refresh_bypasses_failed_source_cache(self):
        source = Source(False)
        service = ScreenerService(source_factory=lambda: source, runtime_getter=lambda **_: None)
        first = service.read()
        self.assertEqual(first["source_error"], "NOT_CONFIGURED")
        source.success = True
        self.assertEqual(service.read()["source_error"], "NOT_CONFIGURED")
        refreshed = service.read(force_refresh=True)
        self.assertEqual(refreshed["result_count"], 240)
        self.assertIsNone(refreshed["source_error"])
        self.assertEqual(source.calls, 2)

    def test_window_reconciles_and_releases_only_its_consumer(self):
        runtime = Runtime()
        runtime.active.add(("another-consumer", "T0001"))
        service = ScreenerService(source_factory=Source, runtime_getter=lambda **_: runtime)
        service.read()
        first = service.window("client_1", ["T0001", "T0002"])
        self.assertEqual(first["active"], 2)
        self.assertEqual(first["quotes"]["T0001"]["state"], "UNAVAILABLE")
        service.window("client_1", ["T0002", "T0003"])
        self.assertNotIn(("main-screener:client_1", "T0001"), runtime.active)
        self.assertIn(("another-consumer", "T0001"), runtime.active)
        with self.assertRaisesRegex(ValueError, "WINDOW_LIMIT_EXCEEDED"):
            service.window("client_1", ["T0001"] * (MAX_WINDOW + 1))
        service.release("client_1")
        self.assertEqual(runtime.active, {("another-consumer", "T0001")})

    def test_quote_states_and_field_provenance_are_separate_from_snapshot(self):
        runtime = Runtime()
        quote = SimpleNamespace(
            bid_price=20.0, ask_price=20.1, last_price=20.05, volume=1000,
            received_ns=time.time_ns(), available_time_ns=time.time_ns(),
            quality="PASS", admission="DISPLAY_ADMITTED", provider="MOOMOO",
        )
        runtime.state.quote_for = lambda symbol: quote
        service = ScreenerService(source_factory=Source, runtime_getter=lambda **_: runtime)
        snapshot = service.read()["rows"][0]
        live = service.window("client_1", ["T0000"])["quotes"]["T0000"]
        self.assertEqual(live["state"], "LIVE")
        self.assertEqual(live["fields"]["bid"]["source"], "MOOMOO")
        self.assertEqual(snapshot["fields"]["short_float_pct"]["source"], "FINVIZ_ELITE")
        quote.quality = "DELAYED"
        self.assertEqual(service.window("client_1", ["T0000"])["quotes"]["T0000"]["state"], "DELAYED")
        quote.quality = "PASS"
        quote.received_ns -= 10_000_000_000
        self.assertEqual(service.window("client_1", ["T0000"])["quotes"]["T0000"]["state"], "STALE")
        service.release("client_1")

    def test_failed_refresh_retains_aged_snapshot_and_expiry_releases(self):
        source = Source()
        runtime = Runtime()
        current = [100.0]
        service = ScreenerService(
            source_factory=lambda: source, runtime_getter=lambda **_: runtime,
            monotonic=lambda: current[0],
        )
        service.read()
        service.window("client_1", ["T0001"])
        current[0] += 121
        source.success = False
        degraded = service.read()
        self.assertEqual(degraded["result_count"], 240)
        self.assertEqual(degraded["provider_health"][0]["state"], "DEGRADED")
        self.assertEqual(degraded["rows"][0]["fields"]["price"]["as_of"], "2026-09-25T13:00:00Z")
        service._expire_clients()
        self.assertFalse(runtime.active)


if __name__ == "__main__":
    unittest.main()
