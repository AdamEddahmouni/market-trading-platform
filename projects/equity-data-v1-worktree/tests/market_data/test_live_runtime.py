from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.market_data.live_runtime import LiveObservationalRuntime, reset_live_runtime
from market_platform_foundation.market_data.subscription_manager import SubscriptionPriority

FIXTURE = ROOT / "tests/fixtures/market_data/moomoo/captured-aapl.jsonl"


class LiveRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_live_runtime()

    def tearDown(self) -> None:
        reset_live_runtime()

    def test_subscription_ref_count(self) -> None:
        runtime = LiveObservationalRuntime()
        first = runtime.subscribe(
            instrument_id="AAPL",
            capabilities=["BASIC_QUOTE"],
            consumer_id="workspace",
            priority=SubscriptionPriority.ACTIVE_WORKSPACE,
        )
        second = runtime.subscribe(
            instrument_id="AAPL",
            capabilities=["BASIC_QUOTE"],
            consumer_id="portfolio",
            priority=SubscriptionPriority.PINNED_WATCHLIST,
        )
        self.assertTrue(first[0]["accepted"])
        self.assertTrue(second[0]["accepted"])
        self.assertEqual(second[0]["ref_count"], 2)
        runtime.unsubscribe(instrument_id="AAPL", capabilities=["BASIC_QUOTE"], consumer_id="workspace")
        active = runtime.subscriptions.active_subscriptions()
        self.assertEqual(len(active), 1)

    def test_quota_exhaustion(self) -> None:
        runtime = LiveObservationalRuntime()
        runtime.subscriptions.max_quota = 1
        runtime.subscribe(instrument_id="AAPL", capabilities=["BASIC_QUOTE"], consumer_id="a")
        denied = runtime.subscribe(instrument_id="NVDA", capabilities=["BASIC_QUOTE"], consumer_id="b")
        self.assertFalse(denied[0]["accepted"])
        self.assertEqual(denied[0]["reason"], "QUOTA_EXHAUSTED")

    def test_fixture_feed_updates_state(self) -> None:
        runtime = LiveObservationalRuntime()
        count = runtime.feed_fixture_path(FIXTURE)
        self.assertEqual(count, 3)
        quote = runtime.state.quote_for("AAPL")
        self.assertIsNotNone(quote)
        assert quote is not None
        self.assertAlmostEqual(quote.last_price or 0, 190.1)
        self.assertGreaterEqual(len(runtime.state.trades_for("AAPL")), 1)

    def test_two_symbol_isolation(self) -> None:
        runtime = LiveObservationalRuntime()
        aapl = {
            "capability": "US_EQUITY_L1",
            "clocks": {"event_time_ns": 100, "provider_time_ns": 100, "received_time_ns": 200},
            "instrument_id": "AAPL",
            "provider": "moomoo",
            "provider_symbol": "US.AAPL",
            "raw_payload": {"ask_price": 2, "ask_vol": 1, "bid_price": 1, "bid_vol": 1, "last_price": 1.5},
            "sequence": 1,
        }
        nvda = {
            "capability": "US_EQUITY_L1",
            "clocks": {"event_time_ns": 100, "provider_time_ns": 100, "received_time_ns": 200},
            "instrument_id": "NVDA",
            "provider": "moomoo",
            "provider_symbol": "US.NVDA",
            "raw_payload": {"ask_price": 20, "ask_vol": 1, "bid_price": 19, "bid_vol": 1, "last_price": 19.5},
            "sequence": 1,
        }
        runtime.ingest_record(aapl, wall_now_ns=250)
        runtime.ingest_record(nvda, wall_now_ns=250)
        self.assertAlmostEqual(runtime.state.quote_for("AAPL").last_price or 0, 1.5)
        self.assertAlmostEqual(runtime.state.quote_for("NVDA").last_price or 0, 19.5)

    def test_reconnect_lifecycle(self) -> None:
        runtime = LiveObservationalRuntime()
        runtime.feed_fixture_path(FIXTURE)
        runtime.simulate_disconnect()
        self.assertEqual(runtime.lifecycle.connection_state.value, "DISCONNECTED")
        runtime.simulate_reconnect()
        self.assertIn(runtime.lifecycle.connection_state.value, {"CONNECTED", "CONNECTED_DEGRADED"})

    def test_provider_neutral_envelope_no_moomoo_fields_required(self) -> None:
        runtime = LiveObservationalRuntime()
        runtime.feed_fixture_path(FIXTURE)
        quote = runtime.state.quote_for("AAPL")
        payload = quote.to_dict() if quote else {}
        for forbidden in ("US.AAPL", "moomoo.opend", "OpenQuoteContext"):
            self.assertNotIn(forbidden, str(payload))

    def test_recorder_bounds_do_not_raise(self) -> None:
        from tempfile import TemporaryDirectory

        from market_platform_foundation.market_data.recorder import ObservationalRecorder

        with TemporaryDirectory() as tmp:
            runtime = LiveObservationalRuntime()
            runtime.recorder = ObservationalRecorder(capture_id="bound", root=Path(tmp), max_records=1)
            count = runtime.feed_fixture_path(FIXTURE)
            self.assertEqual(count, 3)
            self.assertEqual(runtime.recorder.event_count, 1)
            self.assertGreaterEqual(runtime.recorder.quality_summary.get("CAPTURE_BOUND_EXCEEDED", 0), 1)

    @mock.patch.dict(
        os.environ,
        {"IMP_LIVE_OBSERVATIONAL": "1", "IMP_LIVE_FIXTURE_FEED": str(FIXTURE), "IMP_MOOMOO_LIVE": "0"},
    )
    def test_get_live_runtime_fixture_mode(self) -> None:
        from market_platform_foundation.market_data.live_runtime import get_live_runtime

        reset_live_runtime()
        runtime = get_live_runtime(create=True)
        self.assertIsNotNone(runtime)
        assert runtime is not None
        self.assertIsNotNone(runtime.state.quote_for("AAPL"))

    def test_instrument_capabilities_use_registry_and_do_not_treat_stale_as_live(self) -> None:
        from market_platform_foundation.market_data.capabilities import CapabilityState, MarketCapability
        from market_platform_foundation.market_data.capability_registry import VerifiedCapabilityRegistry

        runtime = LiveObservationalRuntime()
        runtime.capability_registry = VerifiedCapabilityRegistry()
        runtime.capability_registry.is_stale = False
        runtime.capability_probe = {
            MarketCapability.US_EQUITY_L1.value: CapabilityState(
                capability=MarketCapability.US_EQUITY_L1,
                provider_supports=True,
                account_entitled=True,
                adapter_implemented=True,
                runtime_tested=True,
                data_currently_fresh=True,
            ),
            MarketCapability.US_EQUITY_TICKS.value: CapabilityState(
                capability=MarketCapability.US_EQUITY_TICKS,
                provider_supports=True,
                account_entitled=True,
                adapter_implemented=True,
                runtime_tested=True,
                data_currently_fresh=True,
            ),
            MarketCapability.US_EQUITY_DEPTH.value: CapabilityState(
                capability=MarketCapability.US_EQUITY_DEPTH,
                provider_supports=True,
                account_entitled=True,
                adapter_implemented=True,
                runtime_tested=True,
                data_currently_fresh=True,
            ),
        }
        with mock.patch.dict(os.environ, {"IMP_MOOMOO_LIVE": "1", "IMP_LIVE_OBSERVATIONAL": "1"}):
            rows = {row["capability_id"]: row for row in runtime.instrument_capabilities("AAPL")}
        self.assertEqual(rows["BASIC_QUOTE"]["state"], "AVAILABLE")
        self.assertEqual(rows["BASIC_QUOTE"]["registry_capability"], "US_EQUITY_L1")
        self.assertEqual(rows["ORDER_FLOW"]["state"], "AVAILABLE")
        self.assertEqual(rows["ORDER_FLOW"]["registry_capability"], "US_EQUITY_TICKS")
        runtime.capability_registry.is_stale = True
        with mock.patch.dict(os.environ, {"IMP_MOOMOO_LIVE": "1", "IMP_LIVE_OBSERVATIONAL": "1"}):
            stale_rows = {row["capability_id"]: row for row in runtime.instrument_capabilities("AAPL")}
        self.assertEqual(stale_rows["BASIC_QUOTE"]["state"], "UNAVAILABLE")
        self.assertEqual(stale_rows["BASIC_QUOTE"]["reason"], "PROBE_STALE")
        self.assertNotEqual(stale_rows["BASIC_QUOTE"]["state"], "HEALTHY")
        with mock.patch.dict(os.environ, {"IMP_MOOMOO_LIVE": "0", "IMP_LIVE_OBSERVATIONAL": "1"}):
            off_rows = {row["capability_id"]: row for row in runtime.instrument_capabilities("AAPL")}
        self.assertEqual(off_rows["TRADES"]["state"], "NOT_CONFIGURED")
        self.assertEqual(off_rows["INTERNAL_PAPER"]["state"], "NOT_CONFIGURED")

    def test_internal_paper_capability_follows_env_not_fill_gate(self) -> None:
        runtime = LiveObservationalRuntime()
        runtime.lifecycle.execution_use = "DISPLAY_ONLY"
        paper_flags = {
            "IMP_LIVE_OBSERVATIONAL": "1",
            "IMP_PAPER_EXECUTION": "1",
            "IMP_LIVE_INTERNAL_SIMULATION": "1",
        }
        with mock.patch.dict(os.environ, paper_flags):
            rows = {row["capability_id"]: row for row in runtime.instrument_capabilities("AAPL")}
        self.assertEqual(rows["INTERNAL_PAPER"]["state"], "AVAILABLE")
        self.assertEqual(rows["INTERNAL_PAPER"]["reason"], "AWAITING_ELIGIBLE_LIVE_EVENT")
        self.assertNotEqual(rows["INTERNAL_PAPER"]["reason"], "INTERNAL_PAPER_GATED")
        runtime.lifecycle.execution_use = "INTERNAL_PAPER_ELIGIBLE"
        with mock.patch.dict(os.environ, paper_flags):
            eligible = {row["capability_id"]: row for row in runtime.instrument_capabilities("AAPL")}
        self.assertEqual(eligible["INTERNAL_PAPER"]["state"], "AVAILABLE")
        self.assertIsNone(eligible["INTERNAL_PAPER"]["reason"])
        with mock.patch.dict(os.environ, {**paper_flags, "IMP_LIVE_INTERNAL_SIMULATION": "0"}):
            off = {row["capability_id"]: row for row in runtime.instrument_capabilities("AAPL")}
        self.assertEqual(off["INTERNAL_PAPER"]["state"], "NOT_CONFIGURED")


if __name__ == "__main__":
    unittest.main()
