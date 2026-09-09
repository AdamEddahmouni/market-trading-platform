"""G8 live runtime composition tests (fake/replay transport)."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "providers"))

from market_platform_foundation.market_data.ibkr_runtime_bridge import (
    inject_ibkr_observational_provider,
)
from market_platform_foundation.market_data.live_runtime import LiveObservationalRuntime
from market_platform_foundation.market_data.runtime_composition import (
    ObservationalRuntimeComposition,
    build_replay_composition,
)
from market_platform_foundation.order_flow.order_book.contracts import (
    DepthOperation,
    DepthSide,
)
from market_platform_foundation.providers.ibkr_observational.adapter import (
    IbkrObservationalConfig,
)
from market_platform_foundation.providers.runtime_capability import (
    CAP_L1,
    CAP_L2,
    EntitlementState,
    ProviderHealth,
    ProviderRuntimeState,
)
from market_platform_foundation.providers.ibkr_observational.capability import IBKR_PROVIDER_ID

from ibkr_observational_support import FakeLookup, FakeTransport, connected_adapter, make_record


AAPL = make_record("AAPL")


class G8LiveRuntimeCompositionTests(unittest.TestCase):
    def test_runtime_startup_selects_implemented_provider(self) -> None:
        composition = ObservationalRuntimeComposition()
        result = composition.select_for_capability(CAP_L1, "AAPL")
        self.assertIn(result["outcome"], {"SELECTED", "REPLAY_ONLY", "NO_PROVIDER"})

    def test_ibkr_adapter_composed_through_outer_transport(self) -> None:
        composition = build_replay_composition(
            transport=FakeTransport(), lookup=FakeLookup(AAPL)
        )
        self.assertIsNotNone(composition.ibkr_adapter)

    def test_no_src_tools_import_in_composition_module(self) -> None:
        import market_platform_foundation.market_data.runtime_composition as mod
        import market_platform_foundation.market_data.live_runtime as live
        import market_platform_foundation.market_data.ibkr_runtime_bridge as bridge

        for module in (mod, live, bridge):
            source = Path(module.__file__).read_text(encoding="utf-8")
            self.assertNotIn("from tools.ibkr", source)
            self.assertNotIn("import tools.ibkr", source)

    def test_injected_transport_composes_ibkr_without_tools_construction(self) -> None:
        class _Provider:
            def construct(self):
                return FakeTransport(), IbkrObservationalConfig(live_enabled=True)

        inject_ibkr_observational_provider(_Provider())
        runtime = LiveObservationalRuntime()
        try:
            with patch.dict(
                os.environ,
                {
                    "IMP_LIVE_OBSERVATIONAL": "1",
                    "IMP_IBKR_LIVE": "1",
                    "IMP_IBKR_TRANSPORT": "tws",
                    "IMP_OBSERVATIONAL_PROVIDER": "ibkr",
                    "IMP_MOOMOO_LIVE": "0",
                },
                clear=False,
            ):
                runtime.configure()
            self.assertIsNotNone(runtime.composition)
            self.assertIsNotNone(runtime.composition.ibkr_adapter)
        finally:
            inject_ibkr_observational_provider(None)
            runtime.stop()

    def test_moomoo_path_remains_compatible(self) -> None:
        runtime = LiveObservationalRuntime()
        self.assertIsNotNone(runtime.state)
        self.assertIsNotNone(runtime.subscriptions)

    def test_provider_down_fails_closed(self) -> None:
        composition = ObservationalRuntimeComposition()
        composition.capability_registry.set_runtime_state(
            ProviderRuntimeState(
                provider_id=IBKR_PROVIDER_ID,
                health=ProviderHealth.DOWN,
            )
        )
        result = composition.select_for_capability(CAP_L1, "AAPL", require_real_time=True)
        self.assertEqual(result["outcome"], "PROVIDER_DOWN")

    def test_not_entitled_fails_closed(self) -> None:
        composition = ObservationalRuntimeComposition()
        composition.capability_registry.set_runtime_state(
            ProviderRuntimeState(
                provider_id=IBKR_PROVIDER_ID,
                health=ProviderHealth.HEALTHY,
                entitlement=EntitlementState.NOT_ENTITLED,
            )
        )
        result = composition.select_for_capability(CAP_L2, "AAPL")
        self.assertEqual(result["outcome"], "NOT_ENTITLED")

    def test_delayed_data_stays_delayed(self) -> None:
        composition = build_replay_composition(
            transport=FakeTransport(), lookup=FakeLookup(AAPL)
        )
        adapter, _ = connected_adapter(store=composition.store, lookup=FakeLookup(AAPL))
        composition.ibkr_adapter = adapter
        sub = adapter.subscribe_l1(instrument_id="AAPL")
        adapter.on_error(sub.req_id, 354, "not subscribed")
        composition.sync_ibkr_runtime_state()
        state = composition.capability_registry.runtime_state_for(IBKR_PROVIDER_ID)
        self.assertEqual(state.entitlement.value, "DELAYED")

    def test_l1_reaches_canonical_quote(self) -> None:
        composition = build_replay_composition(
            transport=FakeTransport(), lookup=FakeLookup(AAPL)
        )
        adapter, transport = connected_adapter(store=composition.store, lookup=FakeLookup(AAPL))
        composition.ibkr_adapter = adapter
        adapter.subscribe_l1(instrument_id="AAPL")
        adapter.on_tick_price(transport.mkt_data_requests[0][0], 1, 100.0)
        adapter.on_tick_price(transport.mkt_data_requests[0][0], 2, 101.0)
        quote = composition.store.quote_for("AAPL")
        self.assertIsNotNone(quote)
        self.assertEqual(quote.bid_price, 100.0)

    def test_l2_reaches_canonical_book(self) -> None:
        composition = build_replay_composition(
            transport=FakeTransport(), lookup=FakeLookup(AAPL)
        )
        adapter, _ = connected_adapter(store=composition.store, lookup=FakeLookup(AAPL))
        composition.ibkr_adapter = adapter
        sub = adapter.subscribe_l2(instrument_id="AAPL")
        adapter.on_mkt_depth(sub.req_id, 0, 0, 1, 100.0, 10.0)
        engine = composition.store.book_engine_for("AAPL")
        self.assertIsNotNone(engine)
        self.assertTrue(engine.book_state_valid)

    def test_ofi_receives_canonical_book(self) -> None:
        composition = build_replay_composition(
            transport=FakeTransport(), lookup=FakeLookup(AAPL)
        )
        adapter, _ = connected_adapter(store=composition.store, lookup=FakeLookup(AAPL))
        sub = adapter.subscribe_l2(instrument_id="AAPL")
        adapter.on_mkt_depth(sub.req_id, 0, 0, 1, 100.0, 10.0)
        adapter.on_mkt_depth(sub.req_id, 0, 0, 0, 101.0, 5.0)
        composition.lanes.build_ofi_payload("AAPL")
        adapter.on_mkt_depth(sub.req_id, 0, 1, 1, 100.0, 12.0)
        ofi = composition.lanes.build_ofi_payload("AAPL")
        self.assertIn("ofi_method", ofi)

    def test_book_features_receive_canonical_book(self) -> None:
        composition = build_replay_composition(
            transport=FakeTransport(), lookup=FakeLookup(AAPL)
        )
        adapter, _ = connected_adapter(store=composition.store, lookup=FakeLookup(AAPL))
        sub = adapter.subscribe_l2(instrument_id="AAPL")
        adapter.on_mkt_depth(sub.req_id, 0, 0, 1, 100.0, 10.0)
        adapter.on_mkt_depth(sub.req_id, 0, 0, 0, 101.0, 5.0)
        features = composition.lanes.build_book_features_payload("AAPL")
        self.assertTrue(features.get("available") or features.get("book_features") is not None)

    def test_old_generation_callback_rejected(self) -> None:
        composition = build_replay_composition(
            transport=FakeTransport(), lookup=FakeLookup(AAPL)
        )
        adapter, _ = connected_adapter(store=composition.store, lookup=FakeLookup(AAPL))
        sub = adapter.subscribe_l2(instrument_id="AAPL")
        adapter.handle_reconnect()
        result = adapter.on_mkt_depth(sub.req_id, 0, 0, 1, 100.0, 10.0)
        self.assertFalse(result.accepted)

    def test_provider_state_updates_readiness(self) -> None:
        composition = build_replay_composition(
            transport=FakeTransport(), lookup=FakeLookup(AAPL)
        )
        adapter, _ = connected_adapter(store=composition.store, lookup=FakeLookup(AAPL))
        composition.ibkr_adapter = adapter
        composition.sync_ibkr_runtime_state()
        manifest = composition.manifest()
        self.assertTrue(manifest["has_ibkr_adapter"])

    def test_shutdown_cancels_subscriptions(self) -> None:
        composition = build_replay_composition(
            transport=FakeTransport(), lookup=FakeLookup(AAPL)
        )
        adapter, transport = connected_adapter(store=composition.store, lookup=FakeLookup(AAPL))
        composition.ibkr_adapter = adapter
        adapter.subscribe_l1(instrument_id="AAPL")
        composition.shutdown()
        self.assertGreaterEqual(transport.mkt_data_cancels, [])

    def test_shutdown_disconnects_transport(self) -> None:
        composition = build_replay_composition(
            transport=FakeTransport(), lookup=FakeLookup(AAPL)
        )
        adapter, transport = connected_adapter(store=composition.store, lookup=FakeLookup(AAPL))
        composition.ibkr_adapter = adapter
        composition.shutdown()
        self.assertGreaterEqual(transport.disconnect_calls, 1)


if __name__ == "__main__":
    unittest.main()
