"""S1 broad screener contract and bounded viewport subscription tests."""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from market_platform_foundation.finviz.screener import FinvizScreenerRow
from market_platform_foundation.ui_api.screener_projections import MAX_WINDOW, SCREENER_COLUMNS, ScreenerService


class Source:
    def __init__(self, success: bool = True):
        self.success = success
        self.calls = 0

    def fetch_export(self, *, filter_expr: str, columns: str):
        self.calls += 1
        assert filter_expr == "geo_usa"  # S13: fund exclusion is an IMP admission rule, not a Finviz filter
        assert columns == SCREENER_COLUMNS
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

    def test_bid_ask_spread_filter_and_sort_through_one_universe_snapshot(self):
        class Transport:
            def __init__(self):
                self.calls: list[int] = []
                self.available = True

            def fetch_market_snapshot(self, codes):
                self.calls.append(len(codes))
                if not self.available:
                    return {"reason_code": "OPEND_UNAVAILABLE", "rows": None}
                # T0005 is a listing the vendor does not carry: it is simply absent.
                return {"reason_code": None, "rows": [
                    {"code": code, "update_time": "2026-10-01 12:00:00", "last_price": 10.0,
                     "bid_price": float(code[4:]) or 0.5, "ask_price": (float(code[4:]) or 0.5) * 1.01,
                     "overnight_price": 0.0} for code in codes if code != "US.T0005"]}

        transport = Transport()
        clock = [1000.0]
        service = ScreenerService(source_factory=Source, runtime_getter=lambda **_: None,
                                  quote_transport_getter=lambda: transport, monotonic=lambda: clock[0])
        self.assertEqual(service.read()["snapshot"], None)
        self.assertEqual(transport.calls, [])  # no bid/ask in the query: no snapshot is taken

        rule = [{"id": "a", "field": "bid", "operator": "gte", "value": 200}]
        result = service.read(filters=rule, sort="bid", descending=False, limit=10)
        self.assertEqual(transport.calls, [240])
        self.assertEqual(result["result_count"], 40)
        self.assertEqual([row["symbol"] for row in result["rows"][:2]], ["T0200", "T0201"])
        field = result["rows"][0]["fields"]["bid"]
        self.assertEqual((field["value"], field["source"], field["state"]), (200.0, "MOOMOO_OPEND_SNAPSHOT", "SNAPSHOT"))
        self.assertEqual((result["snapshot"]["total"], result["snapshot"]["returned"]), (240, 239))
        # A later page reads the snapshot its first page was ordered from, without a new one.
        later = service.read(filters=rule, sort="bid", descending=False, limit=10, offset=10,
                             result_set=result["result_set_id"])
        self.assertEqual(later["rows"][0]["symbol"], "T0210")
        self.assertEqual(transport.calls, [240])
        with self.assertRaisesRegex(ValueError, "RESULT_SET_CHANGED"):
            service.read(limit=10, offset=10, result_set=result["result_set_id"])
        # The unlisted row has no bid, so no bid rule matches it and it sorts last.
        self.assertEqual(service.read(sort="bid", descending=False, limit=240)["rows"][-1]["symbol"], "T0005")

        # No snapshot: the query says so instead of filtering on the few live rows.
        transport.available = False
        clock[0] += 61
        down = service.read(filters=rule)
        self.assertEqual((down["result_count"], down["source_error"]), (0, "OPEND_UNAVAILABLE"))
        self.assertEqual(down["provider_health"][1], {"provider": "MOOMOO_OPEND_SNAPSHOT", "role": "MARKET_SNAPSHOT",
                                                     "state": "UNAVAILABLE", "reason": "OPEND_UNAVAILABLE"})
        self.assertEqual(service.read()["result_count"], 240)  # everything else still works

    def test_exact_ticker_search_lists_that_ticker_first(self):
        class TickerSource(Source):
            def fetch_export(self, *, filter_expr: str, columns: str):
                export = super().fetch_export(filter_expr=filter_expr, columns=columns)
                export["rows"] = [FinvizScreenerRow(ticker=ticker, company=f"{ticker} Inc", price=1.0, volume=volume,
                                                    short_float_pct=None)
                                  for ticker, volume in (("SPYG", 900), ("SPY", 100), ("SPYV", 500), ("ASPY", 700))]
                return export

        service = ScreenerService(source_factory=TickerSource, runtime_getter=lambda **_: None)
        # Volume descending would put SPY last; the exact match goes first, the rest keep the sort.
        self.assertEqual([row["symbol"] for row in service.read(search="spy")["rows"]], ["SPY", "SPYG", "ASPY", "SPYV"])
        self.assertEqual([row["symbol"] for row in service.read(search="SP")["rows"]], ["SPYG", "ASPY", "SPYV", "SPY"])

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

    def test_missing_quote_reports_the_feed_state_not_a_blanket_wait(self):
        runtime = Runtime()
        service = ScreenerService(source_factory=Source, runtime_getter=lambda **_: runtime)
        service.read()

        def reason() -> str:
            return service.window("client_1", ["T0001"])["quotes"]["T0001"]["reason"]

        # No feed at all (OpenD was down when the runtime started) is not "awaiting a quote".
        self.assertEqual(reason(), "OPEND_UNAVAILABLE")
        runtime.feed = SimpleNamespace(subscription_errors={})
        runtime.lifecycle = SimpleNamespace(connection_state="DISCONNECTED")
        self.assertEqual(reason(), "OPEND_UNAVAILABLE")
        runtime.lifecycle.connection_state = "CONNECTED"
        self.assertEqual(reason(), "AWAITING_QUOTE")
        runtime.feed.subscription_errors[("US.T0001", "QUOTE")] = {"message": "No permission: quote card required"}
        self.assertEqual(reason(), "ENTITLEMENT_MISSING")
        runtime.feed.subscription_errors[("US.T0001", "QUOTE")] = {"message": "Subscription quota exceeded"}
        self.assertEqual(reason(), "PROVIDER_QUOTA_EXHAUSTED")
        self.assertEqual(service.quote_for("T0001")["reason"], "PROVIDER_QUOTA_EXHAUSTED")
        service.release("client_1")

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
        # Polled every second but not updated by the provider for two minutes: stale, aged by the provider.
        quote.received_ns = time.time_ns()
        quote.event_time_ns = quote.received_ns - 120_000_000_000
        aged = service.window("client_1", ["T0000"])["quotes"]["T0000"]
        self.assertEqual(aged["state"], "STALE")
        self.assertEqual(aged["reason"], "NO_QUOTE_UPDATE_WITHIN_TTL")
        self.assertGreaterEqual(aged["age_ms"], 120_000)
        quote.event_time_ns = quote.received_ns - 2_000_000_000
        self.assertEqual(service.window("client_1", ["T0000"])["quotes"]["T0000"]["state"], "LIVE")
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
