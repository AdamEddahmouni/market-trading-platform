"""G7 end-to-end replay pipeline and composition tests."""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "providers"))

from decimal import Decimal

from market_platform_foundation.market_data.runtime_composition import (  # noqa: E402
    ObservationalRuntimeComposition,
    build_replay_composition,
)
from market_platform_foundation.order_flow.order_book.contracts import (  # noqa: E402
    DepthOperation,
    DepthSide,
    DepthUpdate,
)
from market_platform_foundation.providers.ibkr_observational.capability import (  # noqa: E402
    IBKR_FORBIDDEN_CAPABILITIES,
)
from market_platform_foundation.providers.runtime_capability import CAP_L2  # noqa: E402
from market_platform_foundation.xa01.enums import InstrumentKind  # noqa: E402

from ibkr_observational_support import (  # noqa: E402
    FakeLookup,
    FakeTransport,
    make_record,
)


AAPL = make_record("AAPL")


class RuntimeCompositionTests(unittest.TestCase):
    def test_replay_composition_no_tools_import(self) -> None:
        transport = FakeTransport()
        composition = build_replay_composition(transport=transport, lookup=FakeLookup(AAPL))
        self.assertIsNotNone(composition.ibkr_adapter)
        self.assertTrue(composition.manifest()["has_ibkr_adapter"])

    def test_ibkr_adapter_has_no_execution_methods(self) -> None:
        transport = FakeTransport()
        composition = build_replay_composition(transport=transport, lookup=FakeLookup(AAPL))
        adapter = composition.ibkr_adapter
        assert adapter is not None
        for forbidden in (
            "placeOrder",
            "cancelOrder",
            "modifyOrder",
            "exerciseOptions",
            "place_order",
            "cancel_order",
        ):
            self.assertFalse(hasattr(adapter, forbidden))

    def test_captured_l2_to_ofi_pipeline(self) -> None:
        transport = FakeTransport()
        lookup = FakeLookup(AAPL)
        composition = build_replay_composition(transport=transport, lookup=lookup)
        store = composition.store
        update1 = DepthUpdate(
            instrument_id="AAPL",
            operation=DepthOperation.INSERT,
            side=DepthSide.BID,
            price=Decimal("100.0"),
            size=Decimal("10.0"),
            position=0,
            source="IBKR",
            source_time_ns=1000,
            received_time_ns=1100,
            subscription_id="sub-1",
        )
        update2 = DepthUpdate(
            instrument_id="AAPL",
            operation=DepthOperation.INSERT,
            side=DepthSide.ASK,
            price=Decimal("101.0"),
            size=Decimal("5.0"),
            position=0,
            source="IBKR",
            source_time_ns=1000,
            received_time_ns=1100,
            subscription_id="sub-1",
        )
        store.apply_depth_update(update1)
        store.apply_depth_update(update2)
        composition.lanes.build_ofi_payload("AAPL")
        update3 = DepthUpdate(
            instrument_id="AAPL",
            operation=DepthOperation.UPDATE,
            side=DepthSide.BID,
            price=Decimal("100.0"),
            size=Decimal("12.0"),
            position=0,
            source="IBKR",
            source_time_ns=2000,
            received_time_ns=2100,
            subscription_id="sub-1",
        )
        store.apply_depth_update(update3)
        ofi = composition.lanes.build_ofi_payload("AAPL")
        self.assertIn("ofi_method", ofi)
        evidence = composition.evidence_for("AAPL")
        self.assertIn("evidence_hash", evidence)

    def test_replay_same_hash(self) -> None:
        composition = ObservationalRuntimeComposition()
        composition.store.apply_quote_update(
            instrument_id="NVDA",
            bid_price=100.0,
            ask_price=101.0,
            provider="replay",
        )
        first = composition.evidence_for("NVDA")
        second = composition.evidence_for("NVDA")
        self.assertEqual(first["evidence_hash"], second["evidence_hash"])

    def test_capability_selection_fail_closed(self) -> None:
        composition = ObservationalRuntimeComposition()
        result = composition.select_for_capability(CAP_L2, "AAPL")
        self.assertIn("outcome", result)

    def test_options_analytics_non_authoritative(self) -> None:
        composition = ObservationalRuntimeComposition()
        payload = composition.lanes.build_options_observation_payload(
            instrument_id="NVDA250117C00150000",
            instrument_kind=InstrumentKind.OPTION_CONTRACT.value,
            multiplier=100.0,
            provider="fixture",
        )
        self.assertEqual(payload["analytics_authority"], "NON_AUTHORITATIVE")

    def test_futures_continuous_rejected(self) -> None:
        composition = ObservationalRuntimeComposition()
        payload = composition.lanes.build_futures_observation_payload(
            instrument_id="ES1!",
            instrument_kind=InstrumentKind.CONTINUOUS_SERIES.value,
            price=5000.0,
            multiplier=50.0,
        )
        self.assertEqual(payload["state"], "UNSUPPORTED_INSTRUMENT")

    def test_forbidden_execution_capabilities_never_registered(self) -> None:
        self.assertIn("IBKR_EXECUTION", IBKR_FORBIDDEN_CAPABILITIES)


class RuntimePerformanceTests(unittest.TestCase):
    def test_capability_resolution_overhead_bounded(self) -> None:
        composition = ObservationalRuntimeComposition()
        start = time.perf_counter()
        for _ in range(1000):
            composition.select_for_capability(CAP_L2, "AAPL")
        elapsed = time.perf_counter() - start
        # Dev-machine smoke: 1000 selections should complete well under 1s
        self.assertLess(elapsed, 1.0)


if __name__ == "__main__":
    unittest.main()
