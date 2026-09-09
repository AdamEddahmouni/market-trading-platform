"""G11.1 live evidence and gate-semantics tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.providers.ibkr_observational.capability import (
    IBKR_CAPABILITY_HISTORICAL_BARS,
    IBKR_CAPABILITY_L1,
    IBKR_CAPABILITY_L2,
    IBKR_PROVIDER_ID,
)
from market_platform_foundation.providers.live_evidence import (
    CapabilityLiveEvidenceRow,
    LiveCapabilityResult,
    apply_live_evidence,
)
from market_platform_foundation.providers.runtime_capability import (
    RuntimeCapabilityRegistry,
    RuntimeCapabilityState,
)
from tools.ibkr.canary import classify_gate
from tools.ibkr.config import IbkrConfig


class G111LiveEvidenceTests(unittest.TestCase):
    def test_gate_disabled_is_not_environment_unavailable(self) -> None:
        config = IbkrConfig(
            live_enabled=False,
            gateway_url="https://127.0.0.1:5000/v1/api",
            capture_root=ROOT / "evidence" / "market_data" / "ibkr",
            transport="tws",
        )
        gate = classify_gate(config)
        self.assertEqual(gate["gate_state"], "LIVE_ACCESS_NOT_ENABLED_BY_CONFIG")
        self.assertTrue(any("LIVE_ACCESS_NOT_ENABLED_BY_CONFIG" in item for item in gate["blockers"]))
        self.assertFalse(any("ENVIRONMENT_UNAVAILABLE" in item for item in gate["blockers"]))

    def test_live_evidence_upgrades_one_capability_only(self) -> None:
        registry = RuntimeCapabilityRegistry()
        apply_live_evidence(
            registry,
            IBKR_PROVIDER_ID,
            {
                IBKR_CAPABILITY_HISTORICAL_BARS: CapabilityLiveEvidenceRow(
                    capability_id=IBKR_CAPABILITY_HISTORICAL_BARS,
                    connection=True,
                    request_accepted=True,
                    data_received=True,
                    entitlement="ENTITLED",
                    freshness="REALTIME",
                    canonical_normalization=True,
                    result=LiveCapabilityResult.LIVE_PROVIDER_VERIFIED,
                ),
                IBKR_CAPABILITY_L2: CapabilityLiveEvidenceRow(
                    capability_id=IBKR_CAPABILITY_L2,
                    connection=True,
                    request_accepted=True,
                    data_received=False,
                    entitlement="NOT_ENTITLED",
                    result=LiveCapabilityResult.LIVE_CONNECTED_NOT_ENTITLED,
                ),
            },
        )
        hist = registry.view_capability(
            IBKR_PROVIDER_ID, IBKR_CAPABILITY_HISTORICAL_BARS, instrument_id="AAPL"
        )
        l2 = registry.view_capability(IBKR_PROVIDER_ID, IBKR_CAPABILITY_L2, instrument_id="AAPL")
        l1 = registry.view_capability(IBKR_PROVIDER_ID, IBKR_CAPABILITY_L1, instrument_id="AAPL")
        self.assertEqual(hist.runtime_state, RuntimeCapabilityState.READY)
        self.assertEqual(l2.runtime_state, RuntimeCapabilityState.NOT_ENTITLED)
        self.assertEqual(l1.runtime_state, RuntimeCapabilityState.LIVE_PROVIDER_UNVERIFIED)

    def test_delayed_entitlement_cannot_upgrade_realtime(self) -> None:
        registry = RuntimeCapabilityRegistry()
        apply_live_evidence(
            registry,
            IBKR_PROVIDER_ID,
            {
                IBKR_CAPABILITY_L1: CapabilityLiveEvidenceRow(
                    capability_id=IBKR_CAPABILITY_L1,
                    connection=True,
                    request_accepted=True,
                    data_received=True,
                    entitlement="ENTITLED_DELAYED",
                    freshness="DELAYED",
                    canonical_normalization=True,
                    result=LiveCapabilityResult.LIVE_PROVIDER_VERIFIED,
                ),
            },
        )
        view = registry.view_capability(
            IBKR_PROVIDER_ID,
            IBKR_CAPABILITY_L1,
            instrument_id="AAPL",
            require_real_time=True,
        )
        self.assertEqual(view.runtime_state, RuntimeCapabilityState.DELAYED)


if __name__ == "__main__":
    unittest.main()
