"""S4 Screener specialist panels: demand, subscriptions, Order Flow, CVD, Level 2, charts, futures, layout."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tools" / "moomoo"))

import test_screener_s3 as s3  # noqa: E402  (shared S3 preview fixtures)

from market_platform_foundation.market_data.capabilities import CapabilityState, MarketCapability  # noqa: E402
from market_platform_foundation.market_data.live_admission import ADMISSION_DISPLAY  # noqa: E402
from market_platform_foundation.market_data.live_runtime import LiveObservationalRuntime  # noqa: E402
from market_platform_foundation.market_data.provider_lifecycle import ProviderConnectionState  # noqa: E402
from market_platform_foundation.platform.security.route_policy import policy_for_route  # noqa: E402
from market_platform_foundation.ui_api.screener_config import (  # noqa: E402
    DEFAULT_PANEL_LAYOUT, LAST_KEY, PANEL_BY_UNIVERSE_KEY, PANEL_KEY, ScreenerConfigRepository, validate_panel_layout,
    validate_screen,
)
from market_platform_foundation.ui_api.screener_universes import universe_spec  # noqa: E402
from market_platform_foundation.ui_api.screener_specialist import (  # noqa: E402
    MAX_SPECIALIST_INSTRUMENTS, PROVIDER_HOLD_SECONDS, ScreenerSpecialistService, aggressor_view,
)

SECOND = 1_000_000_000
T0 = s3.ns(2026, 9, 25, 10, 0)
CAUSAL = s3.CAUSAL


class Clock:
    def __init__(self, now: int = T0):
        self.now = now
        self.mono = 1000.0

    def ns(self) -> int:
        return self.now

    def monotonic(self) -> float:
        return self.mono

    def advance(self, seconds: float) -> None:
        self.now += int(seconds * SECOND)
        self.mono += seconds


class Registry:
    def __init__(self, entitled: dict[str, bool] | None = None, reason: str | None = "NOT_ENTITLED"):
        self.entitled = entitled or {}
        self.reason = reason

    def get(self, capability):
        if capability not in self.entitled:
            return None
        entitled = self.entitled[capability]
        return CapabilityState(capability=MarketCapability(capability), provider_supports=True,
                               account_entitled=entitled, adapter_implemented=True,
                               runtime_tested=True, data_currently_fresh=True, reason_code=None if entitled else self.reason)


def make_runtime(clock: Clock, *, max_trades: int = 500, feed: bool = True) -> LiveObservationalRuntime:
    runtime = LiveObservationalRuntime()
    runtime.subscriptions.clock = clock.ns
    runtime.state.max_trades = max_trades
    runtime.capability_registry = Registry()  # type: ignore[assignment]
    runtime.feed = SimpleNamespace(subscription_errors={}) if feed else None
    runtime.lifecycle.mark_connected()
    runtime.lifecycle.connected_ns = clock.now - 3600 * SECOND
    runtime.lifecycle.last_received_ns = clock.now
    return runtime


def ingest(runtime, capability: str, instrument: str, payload: dict, *, event_ns: int, received_ns: int) -> None:
    """The real Moomoo ingestion path: an admitted record through ``apply_admitted``."""

    runtime.state.apply_admitted({
        "admission": {"display": ADMISSION_DISPLAY},
        "envelope": {"instrument_id": instrument, "event_time": event_ns, "available_time": received_ns},
        "record": {"capability": capability, "raw_payload": payload, "provider": "moomoo",
                   "clocks": {"received_time_ns": received_ns}},
    })


def tick(runtime, instrument, *, seq, price, volume, direction, event_ns, received_ns=None, ticker_type=None):
    payload = {"code": f"US.{instrument}", "sequence": seq, "price": price, "volume": volume,
               "ticker_direction": direction, "time": "2026-09-25 10:00:00"}
    if ticker_type:
        payload["type"] = ticker_type
    ingest(runtime, "US_EQUITY_TICKS", instrument, payload, event_ns=event_ns,
           received_ns=received_ns if received_ns is not None else event_ns + 5_000_000)


def book(runtime, instrument, bids, asks, *, received_ns):
    ingest(runtime, "US_EQUITY_DEPTH", instrument,
           {"code": f"US.{instrument}", "Bid": [(p, s, 0, {}) for p, s in bids], "Ask": [(p, s, 0, {}) for p, s in asks]},
           event_ns=received_ns - 2_000_000, received_ns=received_ns)


KNOWN = {"NVDA", "AAPL", "MSFT", "TSLA", "AMD", "INTC", "META", "AMZN"}


def make_service(clock: Clock, runtime, *, session="REGULAR"):
    session_state = {"label": session}
    service = ScreenerSpecialistService(runtime_getter=lambda: runtime, known_instrument=lambda i: i in KNOWN,
                                        session_label=lambda: session_state["label"], now_ns=clock.ns,
                                        monotonic=clock.monotonic, schedule_expiry=False)
    return service, session_state


def provider_keys(runtime) -> set[str]:
    return set(runtime.subscriptions.active_keys)


class DemandAndSubscriptionTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.runtime = make_runtime(self.clock)
        self.service, _ = make_service(self.clock, self.runtime)

    def test_order_flow_and_cvd_share_one_provider_trade_subscription(self):
        result = self.service.demand("c1", "NVDA", ["order_flow", "cvd"])
        self.assertTrue(all(item["accepted"] for item in result["capabilities"]))
        self.assertEqual(provider_keys(self.runtime), {"NVDA:US_EQUITY_TICKS"})
        self.assertEqual(self.runtime.subscriptions.ref_count(instrument_id="NVDA", capability="US_EQUITY_TICKS"), 2)
        self.service.demand("c1", "NVDA", ["cvd"])  # close Order Flow: CVD keeps the feed
        self.assertEqual(provider_keys(self.runtime), {"NVDA:US_EQUITY_TICKS"})
        self.assertEqual(self.runtime.subscriptions.ref_count(instrument_id="NVDA", capability="US_EQUITY_TICKS"), 1)
        self.service.demand("c1", "NVDA", [])  # close CVD: last consumer releases
        self.assertEqual(provider_keys(self.runtime), set())

    def test_level2_acquires_depth_only_when_open_and_chart_futures_acquire_nothing(self):
        self.service.demand("c1", "NVDA", ["charts", "futures"])
        self.assertEqual(provider_keys(self.runtime), set())
        self.service.demand("c1", "NVDA", ["charts", "level2"])
        self.assertEqual(provider_keys(self.runtime), {"NVDA:US_EQUITY_DEPTH"})

    def test_ticker_switch_releases_old_and_acquires_new(self):
        self.service.demand("c1", "AAPL", ["order_flow", "cvd", "level2"])
        self.assertEqual(provider_keys(self.runtime), {"AAPL:US_EQUITY_TICKS", "AAPL:US_EQUITY_DEPTH"})
        self.service.demand("c1", "NVDA", ["order_flow", "cvd", "level2"])
        self.assertEqual(provider_keys(self.runtime), {"NVDA:US_EQUITY_TICKS", "NVDA:US_EQUITY_DEPTH"})
        self.assertEqual(self.service.order_flow("AAPL")["state"], "CONNECTING")  # nothing stale for AAPL
        self.service.demand("c1", None, ["order_flow"])  # selection cleared
        self.assertEqual(provider_keys(self.runtime), set())

    def test_independent_clients_reference_count_and_release(self):
        self.service.demand("c1", "NVDA", ["cvd"])
        self.service.demand("c2", "NVDA", ["order_flow"])
        self.assertEqual(self.runtime.subscriptions.ref_count(instrument_id="NVDA", capability="US_EQUITY_TICKS"), 2)
        self.service.release("c1")
        self.assertEqual(provider_keys(self.runtime), {"NVDA:US_EQUITY_TICKS"})
        self.clock.advance(46)  # c2 stopped heart-beating
        self.service.expire()
        self.assertEqual(provider_keys(self.runtime), set())

    def test_rapid_switching_is_bounded_by_provider_hold_window(self):
        symbols = sorted(KNOWN)[: MAX_SPECIALIST_INSTRUMENTS + 1]
        for symbol in symbols[:-1]:
            result = self.service.demand("c1", symbol, ["order_flow", "level2"])
            self.assertTrue(all(item["accepted"] for item in result["capabilities"]), symbol)
            self.clock.advance(1)
        busy = self.service.demand("c1", symbols[-1], ["order_flow", "level2"])
        self.assertEqual({item["reason"] for item in busy["capabilities"]}, {"SUBSCRIPTION_BUSY"})
        self.assertEqual(provider_keys(self.runtime), set())
        self.assertEqual(self.service.order_flow(symbols[-1])["state"], "SUBSCRIPTION_BUSY")
        self.clock.advance(PROVIDER_HOLD_SECONDS)
        again = self.service.demand("c1", symbols[-1], ["order_flow", "level2"])
        self.assertTrue(all(item["accepted"] for item in again["capabilities"]))
        self.assertEqual(len(provider_keys(self.runtime)), 2)

    def test_adding_a_panel_on_the_same_instrument_is_never_busy(self):
        for symbol in sorted(KNOWN)[:MAX_SPECIALIST_INSTRUMENTS]:
            self.service.demand("c1", symbol, ["order_flow"])
        current = sorted(KNOWN)[MAX_SPECIALIST_INSTRUMENTS - 1]
        result = self.service.demand("c1", current, ["order_flow", "level2"])
        self.assertTrue(all(item["accepted"] for item in result["capabilities"]))

    def test_invalid_demand_is_rejected(self):
        for args in (("bad id!", "NVDA", ["cvd"]), ("c1", "NOPE", ["cvd"]), ("c1", "NVDA", ["workbook"]),
                     ("c1", "NVDA", ["cvd", "cvd"])):
            with self.assertRaises(ValueError):
                self.service.demand(*args)

    def test_no_runtime_reports_unavailable_without_subscribing(self):
        service, _ = make_service(self.clock, None)
        result = service.demand("c1", "NVDA", ["order_flow"])
        self.assertEqual(result["capabilities"][0]["reason"], "LIVE_RUNTIME_UNAVAILABLE")
        payload = service.order_flow("NVDA")
        self.assertEqual((payload["state"], payload["reason"], payload["tape"]), ("UNAVAILABLE", "LIVE_RUNTIME_UNAVAILABLE", []))

    def test_routes_are_read_scoped(self):
        for path in ("/screener/order-flow", "/screener/cvd", "/screener/depth", "/screener/chart", "/screener/futures-context"):
            self.assertEqual(policy_for_route("GET", path).capability, "state.read")
        self.assertEqual(policy_for_route("POST", "/screener/panels").capability, "state.read")


class OrderFlowTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.runtime = make_runtime(self.clock)
        self.service, self.session = make_service(self.clock, self.runtime)
        self.service.demand("c1", "NVDA", ["order_flow", "cvd"])

    def test_aggressor_states_preserve_epistemic_truth(self):
        self.assertEqual(aggressor_view({"aggressor_side": "BUY", "aggressor_provenance": "PROVIDER_NATIVE"}),
                         {"state": "INFERRED", "side": "BUY", "method": "PROVIDER_TICKER_DIRECTION"})
        self.assertEqual(aggressor_view({"aggressor_side": "SELL", "aggressor_provenance": "EXCHANGE_NATIVE"})["state"], "NATIVE")
        self.assertEqual(aggressor_view({"aggressor_side": "SELL", "aggressor_provenance": "LEE_READY"})["method"], "LEE_READY")
        self.assertEqual(aggressor_view({"aggressor_side": "UNKNOWN", "aggressor_provenance": "UNKNOWN"}),
                         {"state": "UNKNOWN", "side": None, "method": "UNCLASSIFIED"})

    def test_summary_tape_ordering_and_conditions(self):
        base = self.clock.now
        tick(self.runtime, "NVDA", seq=1, price=100.0, volume=100, direction="BUY", event_ns=base + 1 * SECOND)
        tick(self.runtime, "NVDA", seq=3, price=100.2, volume=50, direction="NEUTRAL", event_ns=base + 3 * SECOND, ticker_type="ODD_LOT")
        tick(self.runtime, "NVDA", seq=2, price=100.1, volume=300, direction="SELL", event_ns=base + 2 * SECOND)  # out of order
        tick(self.runtime, "NVDA", seq=2, price=100.1, volume=300, direction="SELL", event_ns=base + 2 * SECOND)  # duplicate push
        self.clock.advance(4)
        payload = self.service.order_flow("NVDA")
        self.assertEqual(payload["state"], "CURRENT")
        self.assertEqual([row["trade_id"] for row in payload["tape"]], ["3", "2", "1"])  # newest first, event-time order
        summary = payload["summary"]
        self.assertEqual((summary["trade_count"], summary["buy_volume"], summary["sell_volume"], summary["unknown_volume"]),
                         (3, 100.0, 300.0, 50.0))
        self.assertEqual(summary["net_signed_volume"], -200.0)
        self.assertAlmostEqual(summary["classified_volume_pct"], 400 / 450 * 100)
        self.assertEqual((summary["inferred_count"], summary["unknown_count"], summary["native_count"]), (2, 1, 0))
        self.assertIsNone(summary["trades_per_minute"])  # a 2 s span is not a defensible rate
        self.assertEqual(payload["tape"][0]["condition"], "ODD_LOT")
        self.assertIsNone(payload["tape"][1]["condition"])
        self.assertEqual(payload["tape"][1]["aggressor"]["state"], "INFERRED")
        self.assertEqual(payload["window"]["basis"], "SINCE_SUBSCRIPTION")
        self.assertIsNotNone(payload["latest_event_at"])

    def test_large_print_threshold_is_deterministic(self):
        for seq in range(25):
            tick(self.runtime, "NVDA", seq=seq, price=100, volume=10_000 if seq == 24 else 100, direction="BUY",
                 event_ns=self.clock.now + seq * SECOND)
        payload = self.service.order_flow("NVDA")
        self.assertEqual(payload["summary"]["large_print_threshold"], 1000)
        self.assertEqual([row["large"] for row in payload["tape"][:2]], [True, False])

    def test_trades_from_an_earlier_subscription_are_excluded(self):
        tick(self.runtime, "AAPL", seq=1, price=1, volume=1, direction="BUY", event_ns=self.clock.now - 10 * SECOND)
        self.clock.advance(5)
        self.service.demand("c1", "AAPL", ["order_flow"])
        tick(self.runtime, "AAPL", seq=2, price=2, volume=5, direction="SELL", event_ns=self.clock.now + SECOND)
        payload = self.service.order_flow("AAPL")
        self.assertEqual([row["trade_id"] for row in payload["tape"]], ["2"])

    def test_bounded_buffer_rolls_over_and_is_labelled(self):
        runtime = make_runtime(self.clock, max_trades=10)
        service, _ = make_service(self.clock, runtime)
        service.demand("c1", "NVDA", ["order_flow"])
        for seq in range(15):
            tick(runtime, "NVDA", seq=seq, price=100, volume=1, direction="BUY", event_ns=self.clock.now + seq * SECOND)
        payload = service.order_flow("NVDA")
        self.assertEqual(len(runtime.state.trades_for("NVDA")), 10)
        self.assertEqual(payload["summary"]["trade_count"], 10)
        self.assertEqual((payload["window"]["basis"], payload["window"]["truncated"], payload["window"]["max_records"]),
                         ("LAST_N_CAPTURED", True, 10))

    def test_session_closed_stale_disconnected_and_awaiting(self):
        self.assertEqual((self.service.order_flow("NVDA")["state"], self.service.order_flow("NVDA")["reason"]), ("CURRENT", "AWAITING_DATA"))
        tick(self.runtime, "NVDA", seq=1, price=100, volume=10, direction="BUY", event_ns=self.clock.now)
        self.session["label"] = "CLOSED"
        closed = self.service.order_flow("NVDA")
        self.assertEqual((closed["state"], len(closed["tape"])), ("SESSION_CLOSED", 1))
        self.session["label"] = "REGULAR"
        self.clock.advance(31)
        self.assertEqual((self.service.order_flow("NVDA")["state"], self.service.order_flow("NVDA")["reason"]), ("STALE", "FEED_SILENT"))
        self.runtime.lifecycle.mark_disconnected("OPEND_UNREACHABLE")
        disconnected = self.service.order_flow("NVDA")
        self.assertEqual((disconnected["state"], disconnected["tape"], disconnected["summary"]), ("DISCONNECTED", [], None))

    def test_entitlement_and_provider_refusals(self):
        self.runtime.capability_registry = Registry({"US_EQUITY_TICKS": False})  # type: ignore[assignment]
        self.assertEqual(self.service.order_flow("NVDA")["state"], "NOT_ENTITLED")
        self.runtime.capability_registry = Registry({"US_EQUITY_TICKS": True})  # type: ignore[assignment]
        self.runtime.feed.subscription_errors[("US.NVDA", "TICKER")] = {"message": "Insufficient quote permission", "at_ns": 1}
        self.assertEqual(self.service.cvd("NVDA")["state"], "NOT_ENTITLED")
        self.runtime.feed.subscription_errors[("US.NVDA", "TICKER")] = {"message": "Subscription quota exceeded", "at_ns": 1}
        self.assertEqual(self.service.order_flow("NVDA")["reason"], "PROVIDER_QUOTA_EXHAUSTED")

    def test_stale_probe_is_unverified_not_refused(self):
        self.runtime.capability_registry = Registry({"US_EQUITY_TICKS": False}, reason="PROBE_STALE")  # type: ignore[assignment]
        tick(self.runtime, "NVDA", seq=1, price=100, volume=10, direction="BUY", event_ns=self.clock.now)
        payload = self.service.order_flow("NVDA")
        self.assertEqual((payload["state"], payload["entitlement"], len(payload["tape"])), ("CURRENT", "UNVERIFIED", 1))
        self.runtime.feed.subscription_errors[("US.NVDA", "TICKER")] = {"message": "No permission for this quote", "at_ns": 1}
        self.assertEqual(self.service.order_flow("NVDA")["state"], "NOT_ENTITLED")  # the provider's own refusal decides

    def test_fixture_fed_runtime_is_unavailable_not_substituted(self):
        runtime = make_runtime(self.clock, feed=False)
        service, _ = make_service(self.clock, runtime)
        service.demand("c1", "NVDA", ["order_flow", "cvd"])
        tick(runtime, "NVDA", seq=1, price=100, volume=10, direction="BUY", event_ns=self.clock.now)
        for payload in (service.order_flow("NVDA"), service.cvd("NVDA")):
            self.assertEqual((payload["state"], payload["reason"]), ("UNAVAILABLE", "NO_CURRENT_FEED"))
            self.assertIsNone(payload["summary"])

    def test_no_causal_or_recommendation_language(self):
        tick(self.runtime, "NVDA", seq=1, price=100, volume=10, direction="BUY", event_ns=self.clock.now)
        text = json.dumps([self.service.order_flow("NVDA"), self.service.cvd("NVDA")])
        self.assertIsNone(CAUSAL.search(text))
        self.assertNotIn("bullish", text.lower())


class CvdTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.runtime = make_runtime(self.clock)
        self.service, self.session = make_service(self.clock, self.runtime)
        self.service.demand("c1", "NVDA", ["cvd"])

    def test_deterministic_cumulative_delta_with_unknown_trades(self):
        base = self.clock.now
        rows = [(1, "BUY", 100), (2, "SELL", 40), (3, "NEUTRAL", 500), (4, "BUY", 10)]
        for seq, direction, volume in rows:
            tick(self.runtime, "NVDA", seq=seq, price=100, volume=volume, direction=direction, event_ns=base + seq * SECOND)
        payload = self.service.cvd("NVDA")
        self.assertEqual(payload["derivation"], "DERIVED")
        self.assertEqual([point["cvd"] for point in payload["points"]], [100, 60, 60, 70])
        self.assertEqual([point["delta"] for point in payload["points"]], [100, -40, 0, 10])
        summary = payload["summary"]
        self.assertEqual((summary["cvd"], summary["classified_volume"], summary["unknown_volume"]), (70, 150, 500))
        self.assertAlmostEqual(summary["classified_volume_pct"], 150 / 650 * 100)
        self.assertEqual(summary["aggressor_states"], {"NATIVE": 0, "INFERRED": 3, "UNKNOWN": 1})
        self.assertEqual(summary["methods"], ["PROVIDER_TICKER_DIRECTION"])
        self.assertEqual(payload["window"]["basis"], "SINCE_SUBSCRIPTION")
        self.assertEqual(self.service.cvd("NVDA"), {**payload, "generated_at": self.service.cvd("NVDA")["generated_at"]})

    def test_negative_flat_empty_and_recent_delta(self):
        empty = self.service.cvd("NVDA")
        self.assertEqual((empty["points"], empty["summary"]["cvd"], empty["summary"]["recent_delta"]), ([], 0.0, None))
        base = self.clock.now
        tick(self.runtime, "NVDA", seq=1, price=100, volume=500, direction="SELL", event_ns=base)
        tick(self.runtime, "NVDA", seq=2, price=100, volume=100, direction="BUY", event_ns=base + 90 * SECOND)
        payload = self.service.cvd("NVDA")
        self.assertEqual(payload["summary"]["cvd"], -400)
        self.assertEqual(payload["summary"]["recent_delta"], 100)  # only the last 60 s
        tick(self.runtime, "NVDA", seq=3, price=100, volume=400, direction="BUY", event_ns=base + 91 * SECOND)
        self.assertEqual(self.service.cvd("NVDA")["summary"]["cvd"], 0)

    def test_rapid_switch_never_labels_old_values_with_new_instrument(self):
        tick(self.runtime, "NVDA", seq=1, price=100, volume=500, direction="BUY", event_ns=self.clock.now)
        self.service.demand("c1", "AAPL", ["cvd"])
        aapl = self.service.cvd("AAPL")
        self.assertEqual((aapl["instrument_id"], aapl["points"]), ("AAPL", []))
        self.assertEqual(self.service.cvd("NVDA")["state"], "CONNECTING")

    def test_reconnect_resets_the_window(self):
        tick(self.runtime, "NVDA", seq=1, price=100, volume=500, direction="BUY", event_ns=self.clock.now)
        self.clock.advance(10)
        self.runtime.lifecycle.connected_ns = self.clock.now
        tick(self.runtime, "NVDA", seq=2, price=100, volume=7, direction="SELL", event_ns=self.clock.now + SECOND)
        payload = self.service.cvd("NVDA")
        self.assertEqual(payload["summary"]["cvd"], -7)
        self.assertEqual(payload["window"]["anchor_at"], s3.datetime.fromtimestamp(self.clock.now / SECOND, tz=s3.ZoneInfo("UTC")).isoformat().replace("+00:00", "Z"))


class DepthTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.runtime = make_runtime(self.clock)
        self.service, self.session = make_service(self.clock, self.runtime)
        self.service.demand("c1", "NVDA", ["level2"])

    def test_current_ladder_best_spread_cumulative_and_imbalance(self):
        book(self.runtime, "NVDA", [(102.12, 500), (102.11, 1200), (102.10, 300)],
             [(102.14, 900), (102.15, 250), (102.16, 400)], received_ns=self.clock.now)
        self.clock.advance(0.2)
        payload = self.service.depth("NVDA")
        self.assertEqual(payload["state"], "CURRENT")
        self.assertEqual([row["price"] for row in payload["bids"]], [102.12, 102.11, 102.10])
        self.assertEqual([row["price"] for row in payload["asks"]], [102.14, 102.15, 102.16])
        self.assertEqual([row["cumulative_size"] for row in payload["bids"]], [500, 1700, 2000])
        self.assertEqual([row["cumulative_size"] for row in payload["asks"]], [900, 1150, 1550])
        self.assertEqual((payload["best_bid"], payload["best_ask"]), (102.12, 102.14))
        self.assertAlmostEqual(payload["spread"], 0.02)
        top5 = payload["imbalance"][0]
        self.assertEqual((top5["levels"], top5["bid_size"], top5["ask_size"], top5["complete"]), (5, 2000, 1550, False))
        self.assertAlmostEqual(top5["bid_share"], 2000 / 3550)
        self.assertEqual(payload["completeness"]["basis"], "PROVIDER_MBP_TOP_N")
        self.assertEqual(payload["freshness"]["status"], "FRESH")
        self.assertEqual(payload["freshness"]["age_ms"], 200)

    def test_stale_ttl_partial_and_session_closed(self):
        book(self.runtime, "NVDA", [(10.0, 5)], [(10.1, 5)], received_ns=self.clock.now)
        self.clock.advance(6)
        stale = self.service.depth("NVDA")
        self.assertEqual((stale["state"], stale["reason"], stale["freshness"]["ttl_ms"]), ("STALE", "NO_BOOK_UPDATE_WITHIN_TTL", 5000))
        book(self.runtime, "NVDA", [(10.0, 5)], [], received_ns=self.clock.now)
        partial = self.service.depth("NVDA")
        self.assertEqual((partial["state"], partial["quality_flags"], partial["spread"]), ("PARTIAL", ["ONE_SIDED"], None))
        self.session["label"] = "CLOSED"
        self.assertEqual(self.service.depth("NVDA")["state"], "SESSION_CLOSED")

    def test_crossed_and_malformed_books_are_never_shown(self):
        book(self.runtime, "NVDA", [(10.2, 5)], [(10.1, 5)], received_ns=self.clock.now)
        crossed = self.service.depth("NVDA")
        self.assertEqual((crossed["state"], crossed["reason"], crossed["bids"], crossed["asks"]), ("INVALID", "CROSSED_BOOK", [], []))
        book(self.runtime, "NVDA", [(10.0, 5), (9.9, -3)], [(10.1, 5)], received_ns=self.clock.now)
        malformed = self.service.depth("NVDA")
        self.assertEqual((malformed["state"], malformed["bids"]), ("INVALID", []))

    def test_snapshot_replaces_atomically_and_reconnect_hides_old_book(self):
        book(self.runtime, "NVDA", [(10.0, 5), (9.9, 5)], [(10.1, 5)], received_ns=self.clock.now)
        book(self.runtime, "NVDA", [(10.05, 7)], [(10.1, 2)], received_ns=self.clock.now)
        self.assertEqual([row["price"] for row in self.service.depth("NVDA")["bids"]], [10.05])
        self.runtime.lifecycle.mark_disconnected("OPEND_UNREACHABLE")
        disconnected = self.service.depth("NVDA")
        self.assertEqual((disconnected["state"], disconnected["bids"]), ("DISCONNECTED", []))
        self.clock.advance(1)
        self.runtime.lifecycle.mark_connected()
        self.runtime.lifecycle.connected_ns = self.clock.now
        awaiting = self.service.depth("NVDA")
        self.assertEqual((awaiting["state"], awaiting["reason"], awaiting["bids"]), ("CONNECTING", "AWAITING_BOOK_SNAPSHOT", []))
        book(self.runtime, "NVDA", [(11.0, 1)], [(11.1, 1)], received_ns=self.clock.now + 1000)
        self.assertEqual([row["price"] for row in self.service.depth("NVDA")["bids"]], [11.0])

    def test_book_from_an_earlier_subscription_and_other_ticker_is_hidden(self):
        book(self.runtime, "AAPL", [(200.0, 5)], [(200.1, 5)], received_ns=self.clock.now - SECOND)
        self.service.demand("c1", "AAPL", ["level2"])
        self.assertEqual(self.service.depth("AAPL")["state"], "CONNECTING")
        self.assertEqual(self.service.depth("NVDA")["state"], "CONNECTING")  # NVDA released; never AAPL's book

    def test_entitlement_missing(self):
        self.runtime.capability_registry = Registry({"US_EQUITY_DEPTH": False})  # type: ignore[assignment]
        payload = self.service.depth("NVDA")
        self.assertEqual((payload["state"], payload["reason"], payload["bids"]), ("NOT_ENTITLED", "ENTITLEMENT_MISSING", []))


class PushFeedSubscriptionTests(unittest.TestCase):
    """Provider slots follow OpenD's answer, not IMP's intent."""

    class Ft:
        RET_OK = 0
        SubType = SimpleNamespace(QUOTE="QUOTE", TICKER="TICKER", ORDER_BOOK="ORDER_BOOK")
        Session = SimpleNamespace(ALL="ALL")

    class Ctx:
        def __init__(self):
            self.subscribe_ret, self.unsubscribe_ret, self.calls = 0, 0, []

        def subscribe(self, codes, subtypes, **_kwargs):
            self.calls.append(("sub", codes[0], subtypes[0]))
            return self.subscribe_ret, "Insufficient quote permission" if self.subscribe_ret else ""

        def unsubscribe(self, codes, subtypes):
            self.calls.append(("unsub", codes[0], subtypes[0]))
            return self.unsubscribe_ret, "unsubscribe within one minute" if self.unsubscribe_ret else ""

        def get_stock_quote(self, _codes):
            return -1, None

    def setUp(self):
        from push_feed import MoomooPushFeed
        from market_platform_foundation.market_data.subscription_manager import LiveSubscriptionManager

        self.clock = Clock()
        self.manager = LiveSubscriptionManager(clock=self.clock.ns)
        self.feed = MoomooPushFeed(subscriptions=self.manager, on_record=lambda _record: None, clock=self.clock.ns)
        self.ctx = self.Ctx()

    def test_refused_unsubscribe_keeps_the_provider_slot_and_retries(self):
        self.manager.acquire(instrument_id="NVDA", capability="US_EQUITY_TICKS", consumer_id="a")
        self.feed._sync_subscriptions(self.ctx, self.Ft)
        self.manager.release(instrument_id="NVDA", capability="US_EQUITY_TICKS", consumer_id="a")
        self.ctx.unsubscribe_ret = -1
        self.feed._sync_subscriptions(self.ctx, self.Ft)
        self.assertIn(("US.NVDA", "TICKER"), self.feed._subscribed_subtypes)
        self.feed._sync_subscriptions(self.ctx, self.Ft)  # inside back-off: no retry storm
        self.assertEqual(sum(1 for call in self.ctx.calls if call[0] == "unsub"), 1)
        self.clock.advance(6)
        self.ctx.unsubscribe_ret = 0
        self.feed._sync_subscriptions(self.ctx, self.Ft)
        self.assertNotIn(("US.NVDA", "TICKER"), self.feed._subscribed_subtypes)

    def test_refused_subscribe_is_recorded_and_backed_off(self):
        self.ctx.subscribe_ret = -1
        self.manager.acquire(instrument_id="NVDA", capability="US_EQUITY_DEPTH", consumer_id="a")
        self.feed._sync_subscriptions(self.ctx, self.Ft)
        self.feed._sync_subscriptions(self.ctx, self.Ft)
        self.assertEqual(sum(1 for call in self.ctx.calls if call[0] == "sub"), 1)
        self.assertIn("permission", self.feed.subscription_errors[("US.NVDA", "ORDER_BOOK")]["message"])
        self.manager.release(instrument_id="NVDA", capability="US_EQUITY_DEPTH", consumer_id="a")
        self.feed._sync_subscriptions(self.ctx, self.Ft)
        self.assertEqual(self.feed.subscription_errors, {})

    def test_activation_time_is_recorded_and_cleared(self):
        self.manager.acquire(instrument_id="NVDA", capability="TRADES", consumer_id="a")
        self.assertEqual(self.manager.activated_at(instrument_id="NVDA", capability="US_EQUITY_TICKS"), self.clock.now)
        self.clock.advance(5)
        self.manager.acquire(instrument_id="NVDA", capability="TRADES", consumer_id="b")
        self.assertEqual(self.manager.activated_at(instrument_id="NVDA", capability="US_EQUITY_TICKS"), self.clock.now - 5 * SECOND)
        self.manager.release(instrument_id="NVDA", capability="TRADES", consumer_id="a")
        self.manager.release(instrument_id="NVDA", capability="TRADES", consumer_id="b")
        self.assertIsNone(self.manager.activated_at(instrument_id="NVDA", capability="US_EQUITY_TICKS"))


class PanelLayoutTests(unittest.TestCase):
    LAYOUT = {"grid": {"root": {"type": "branch", "data": [{"type": "leaf", "data": {"views": ["cvd", "level2"], "activeView": "cvd", "id": "1"}, "size": 400}], "size": 300},
                       "width": 1200, "height": 300, "orientation": "HORIZONTAL"},
              "panels": {"cvd": {"id": "cvd", "contentComponent": "cvd", "title": "CVD"},
                         "level2": {"id": "level2", "contentComponent": "level2", "title": "Level 2"}},
              "activeGroup": "1"}

    def valid(self, **overrides):
        return {"version": 1, "open_panels": ["cvd", "level2"], "active_panel": "cvd", "dock_height": 320,
                "dockview_layout": json.loads(json.dumps(self.LAYOUT)), **overrides}

    def test_valid_layout_round_trips(self):
        self.assertEqual(validate_panel_layout(self.valid())["open_panels"], ["cvd", "level2"])
        self.assertIsNone(validate_panel_layout(self.valid(open_panels=[], active_panel=None, dockview_layout=None))["dockview_layout"])

    def test_market_data_and_unknown_panels_are_rejected(self):
        with_params = self.valid()
        with_params["dockview_layout"]["panels"]["cvd"]["params"] = {"cvd": 1234}
        nested = self.valid()
        nested["dockview_layout"]["panels"]["cvd"]["title"] = {"price": 1}
        mismatch = self.valid(open_panels=["cvd"], active_panel="cvd")
        rogue_view = self.valid()
        rogue_view["dockview_layout"]["grid"]["root"]["data"][0]["data"]["views"].append("workbook")
        for raw in (with_params, nested, mismatch, rogue_view, self.valid(version=2), self.valid(open_panels=["workbook"]),
                    self.valid(active_panel="charts"), self.valid(dock_height=20), self.valid(dock_height=True), "junk"):
            with self.assertRaises(ValueError):
                validate_panel_layout(raw)
        huge = self.valid()
        huge["dockview_layout"]["grid"]["padding"] = "x" * 40_000
        with self.assertRaises(ValueError):
            validate_panel_layout(huge)

    def test_repository_persists_separately_and_falls_back_on_corruption(self):
        class Store:
            def __init__(self):
                self.values = {}

            def get_preferences(self):
                return dict(self.values)

            def set_preference(self, key, value):
                self.values[key] = value

        store = Store()
        repository = ScreenerConfigRepository(store)
        self.assertEqual(repository.get_panel_layout(), DEFAULT_PANEL_LAYOUT)
        repository.save_panel_layout(self.valid())
        self.assertEqual(repository.get_panel_layout()["active_panel"], "cvd")
        self.assertEqual(set(store.values), {PANEL_KEY})  # saved screens are untouched
        store.values[PANEL_KEY] = {"version": 99, "open_panels": ["cvd"]}
        self.assertEqual(repository.get_panel_layout(), DEFAULT_PANEL_LAYOUT)
        store.values[PANEL_KEY] = "corrupt"
        self.assertEqual(repository.get_panel_layout(), DEFAULT_PANEL_LAYOUT)

    def test_layouts_persist_per_universe_and_migrate_the_global_layout(self):
        class Store:
            def __init__(self):
                self.values = {}

            def get_preferences(self):
                return dict(self.values)

            def set_preference(self, key, value):
                self.values[key] = value

        store = Store()
        repository = ScreenerConfigRepository(store)
        # A pre-existing global layout is every universe's default until that universe saves its own.
        repository.save_panel_layout(self.valid())
        self.assertEqual(repository.get_panel_layout("CRYPTO")["open_panels"], ["cvd", "level2"])
        crypto = self.valid(open_panels=["news"], active_panel="news", dockview_layout=None, dock_height=500)
        repository.save_panel_layout(crypto, "CRYPTO")
        layouts = repository.get_panel_layouts()
        self.assertEqual(layouts["CRYPTO"]["open_panels"], ["news"])
        self.assertEqual(layouts["CRYPTO"]["dock_height"], 500)
        self.assertEqual(layouts["US_EQUITIES"]["open_panels"], ["cvd", "level2"])
        self.assertEqual(store.values[PANEL_KEY]["open_panels"], ["cvd", "level2"])  # a universe save never rewrites the global
        store.values[PANEL_BY_UNIVERSE_KEY]["CRYPTO"] = {"version": 99}
        self.assertEqual(repository.get_panel_layout("CRYPTO")["open_panels"], ["cvd", "level2"])  # corrupt → global
        with self.assertRaises(ValueError):
            repository.save_panel_layout(crypto, "MARS")
        with self.assertRaises(ValueError):
            repository.get_panel_layout("MARS")

    def test_last_screen_is_remembered_per_universe(self):
        class Store:
            def __init__(self):
                self.values = {}

            def get_preferences(self):
                return dict(self.values)

            def set_preference(self, key, value):
                self.values[key] = value

        store = Store()
        repository = ScreenerConfigRepository(store)
        us = {"name": "Last", "universe": "US_EQUITIES", "filters": [], "view": "Overview",
              "sort": {"field": "volume", "descending": True},
              "columns": {"visible": ["symbol", "price"], "order": ["symbol", "price"], "widths": {}, "pinned": ["symbol"]}}
        # Legacy: only the single last screen exists; it is remembered for its own universe.
        store.values[LAST_KEY] = validate_screen(us, identity="user-last")
        self.assertEqual(set(repository.get_last_by_universe()), {"US_EQUITIES"})
        crypto_spec = universe_spec("CRYPTO")
        crypto_columns = ["symbol", *[column for column in crypto_spec.columns if column != "symbol"][:1]]
        crypto = {**us, "universe": "CRYPTO", "sort": {"field": crypto_columns[-1], "descending": False},
                  "columns": {"visible": crypto_columns, "order": crypto_columns, "widths": {}, "pinned": ["symbol"]}}
        repository.save_last(crypto)
        by_universe = repository.get_last_by_universe()
        self.assertEqual(set(by_universe), {"US_EQUITIES", "CRYPTO"})
        self.assertEqual(by_universe["US_EQUITIES"]["columns"]["visible"], ["symbol", "price"])
        self.assertEqual(repository.get_last()["universe"], "CRYPTO")


class ChartAndFuturesPanelTests(unittest.TestCase):
    def test_chart_reuses_the_preview_bar_contract_and_levels(self):
        bars = s3.StaticBars({("RGTI", "5m"): s3.series(), ("RGTI", "15m"): s3.series(timeframe="15m")})
        service = s3.preview_service(bars=bars, quotes={"RGTI": s3.live_quote(6.5)})
        chart = service.chart("RGTI", timeframe="5m", scope="EXTENDED")
        preview = service.read("RGTI")
        self.assertEqual(chart["schema_version"], "screener-chart/1.0.0")
        self.assertEqual(chart["bars"], preview["bars"])
        self.assertEqual(chart["levels"]["zones"], preview["levels"]["zones"])
        self.assertEqual(chart["levels"]["calculated_at"], preview["levels"]["calculated_at"])  # one cached structure
        self.assertEqual(chart["levels"]["price"]["source"], "L1_QUOTE")
        self.assertEqual(bars.reads, [("RGTI", "5m", "EXTENDED"), ("RGTI", "5m", "EXTENDED")])
        self.assertNotIn("why", chart)
        self.assertEqual(service.chart("RGTI", timeframe="15m")["bars"]["timeframe"], "15m")
        self.assertIsNone(service.chart("NOPE"))

    def test_chart_unavailable_and_stale_bars_have_no_levels(self):
        for state, reason in (("UNAVAILABLE", "BAR_SOURCE_UNAVAILABLE"), ("STALE", None)):
            bars = s3.StaticBars({("RGTI", "5m"): s3.series(state=state, reason=reason)})
            chart = s3.preview_service(bars=bars).chart("RGTI")
            self.assertEqual((chart["levels"]["state"], chart["levels"]["zones"]), ("UNAVAILABLE", []))
        closed = s3.preview_service(bars=s3.StaticBars({("RGTI", "5m"): s3.series(state="SESSION_CLOSED")})).chart("RGTI")
        self.assertEqual(closed["levels"]["price"]["source"], "LAST_BAR_CLOSE")  # bar close is never an L1 price

    def test_futures_context_reuses_the_s3_mapping_without_fixture_prices(self):
        from market_platform_foundation.ui_api.screener_futures_context import FuturesContextService

        service = s3.preview_service(futures=FuturesContextService(transport_getter=lambda: None, bridge=lambda: None))
        payload = service.futures_context("RGTI")
        self.assertEqual(payload["schema_version"], "screener-futures-context/1.0.0")
        roots = [item["root"] for item in payload["futures"]["items"]]
        self.assertEqual(roots, [item["root"] for item in service.read("RGTI")["futures"]["items"]])
        self.assertIn("NQ", roots)
        self.assertTrue(all(item["quote"] is None and item["unavailable_reason"] for item in payload["futures"]["items"]))
        self.assertIsNone(CAUSAL.search(json.dumps(payload)))
        self.assertIsNone(service.futures_context("NOPE"))


if __name__ == "__main__":
    unittest.main()
