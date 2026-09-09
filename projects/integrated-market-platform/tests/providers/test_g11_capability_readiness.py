"""G11 runtime capability readiness tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "providers"))

from market_platform_foundation.market_data.runtime_composition import (
    ObservationalRuntimeComposition,
)
from market_platform_foundation.providers.ibkr_observational.capability import (
    IBKR_CAPABILITY_ACCOUNT_READ,
    IBKR_CAPABILITY_CONTRACT_RESOLUTION,
    IBKR_CAPABILITY_HISTORICAL_BARS,
)
from market_platform_foundation.providers.runtime_capability import (
    CAP_HISTORICAL_BARS,
    ProviderHealth,
    ProviderRuntimeState,
    RuntimeCapabilityRegistry,
)

from ibkr_observational_support import FakeLookup, FakeQueryProvider, make_record


AAPL = make_record("AAPL")


class G11CapabilityReadinessTests(unittest.TestCase):
    def test_query_capabilities_implemented(self) -> None:
        registry = RuntimeCapabilityRegistry()
        for cap in (
            IBKR_CAPABILITY_CONTRACT_RESOLUTION,
            IBKR_CAPABILITY_HISTORICAL_BARS,
            IBKR_CAPABILITY_ACCOUNT_READ,
        ):
            view = registry.view_capability("ibkr.observational", cap, instrument_id="AAPL")
            self.assertTrue(view.implemented)

    def test_runtime_wired_after_query_attach(self) -> None:
        composition = ObservationalRuntimeComposition()
        composition.attach_ibkr_query_service(
            FakeQueryProvider(),
            lookup=FakeLookup(AAPL),
        )
        manifest = composition.manifest()
        self.assertTrue(manifest["has_ibkr_query_service"])

    def test_not_entitled_rejects_query(self) -> None:
        registry = RuntimeCapabilityRegistry()
        registry.set_runtime_state(
            ProviderRuntimeState(
                provider_id="ibkr.observational",
                health=ProviderHealth.HEALTHY,
                entitlement=__import__(
                    "market_platform_foundation.providers.runtime_capability",
                    fromlist=["EntitlementState"],
                ).EntitlementState.NOT_ENTITLED,
            )
        )
        composition = ObservationalRuntimeComposition(capability_registry=registry)
        composition.attach_ibkr_query_service(
            FakeQueryProvider(
                secdef_rows={
                    "AAPL": [
                        {
                            "symbol": "AAPL",
                            "conid": 1,
                            "secType": "STK",
                            "exchange": "SMART",
                            "currency": "USD",
                        }
                    ]
                }
            ),
            lookup=FakeLookup(AAPL),
        )
        result = composition.fetch_historical_bars("AAPL")
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "CAPABILITY_REJECTED")

    def test_live_verified_remains_false(self) -> None:
        registry = RuntimeCapabilityRegistry()
        runtime = registry.runtime_state_for("ibkr.observational")
        self.assertFalse(runtime.live_verified)
        self.assertEqual(runtime.notes, "LIVE_PROVIDER_UNVERIFIED")

    def test_capability_axes_separate_for_historical(self) -> None:
        registry = RuntimeCapabilityRegistry()
        hist = registry.view_capability(
            "ibkr.observational",
            IBKR_CAPABILITY_HISTORICAL_BARS,
            instrument_id="AAPL",
        )
        l2 = registry.view_capability(
            "ibkr.observational",
            "IBKR_L2",
            instrument_id="AAPL",
        )
        self.assertEqual(hist.lane_capability_id, CAP_HISTORICAL_BARS)
        self.assertNotEqual(hist.lane_capability_id, l2.lane_capability_id)


if __name__ == "__main__":
    unittest.main()
