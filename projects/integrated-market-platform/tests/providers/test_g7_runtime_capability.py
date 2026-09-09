"""G7 provider runtime capability and selection tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.providers.ibkr_observational.capability import (  # noqa: E402
    IBKR_CAPABILITY_L1,
    IBKR_CAPABILITY_L2,
    IBKR_FORBIDDEN_CAPABILITIES,
    IBKR_PROVIDER_ID,
)
from market_platform_foundation.providers.registry import ProviderRegistry  # noqa: E402
from market_platform_foundation.providers.runtime_capability import (  # noqa: E402
    CAP_L1,
    CAP_L2,
    DataTimeliness,
    EntitlementState,
    ProviderHealth,
    ProviderRuntimeState,
    RuntimeCapabilityRegistry,
    RuntimeCapabilityState,
)
from market_platform_foundation.providers.runtime_selection import (  # noqa: E402
    ObservationalProviderSelector,
    ObservationalSelectionRequest,
    SelectionOutcome,
)
from market_platform_foundation.xa01.enums import InstrumentKind  # noqa: E402


class RuntimeCapabilityTests(unittest.TestCase):
    def test_ibkr_l2_implemented_capability_discovered(self) -> None:
        registry = RuntimeCapabilityRegistry()
        view = registry.view_capability(IBKR_PROVIDER_ID, IBKR_CAPABILITY_L2)
        self.assertTrue(view.implemented)
        self.assertEqual(view.lane_capability_id, CAP_L2)

    def test_unknown_capability_rejected(self) -> None:
        registry = RuntimeCapabilityRegistry()
        view = registry.view_capability(IBKR_PROVIDER_ID, "NONEXISTENT_CAPABILITY")
        self.assertFalse(view.implemented)
        self.assertEqual(view.runtime_state, RuntimeCapabilityState.UNAVAILABLE)

    def test_execution_capability_forbidden(self) -> None:
        registry = RuntimeCapabilityRegistry()
        for cap in IBKR_FORBIDDEN_CAPABILITIES:
            view = registry.view_capability(IBKR_PROVIDER_ID, cap)
            self.assertEqual(view.reason_code, "EXECUTION_CAPABILITY_FORBIDDEN")

    def test_not_entitled_degraded(self) -> None:
        registry = RuntimeCapabilityRegistry()
        registry.set_runtime_state(
            ProviderRuntimeState(
                provider_id=IBKR_PROVIDER_ID,
                entitlement=EntitlementState.NOT_ENTITLED,
            )
        )
        view = registry.view_capability(IBKR_PROVIDER_ID, IBKR_CAPABILITY_L1)
        self.assertEqual(view.runtime_state, RuntimeCapabilityState.NOT_ENTITLED)

    def test_delayed_remains_delayed(self) -> None:
        registry = RuntimeCapabilityRegistry()
        registry.set_runtime_state(
            ProviderRuntimeState(
                provider_id=IBKR_PROVIDER_ID,
                timeliness=DataTimeliness.DELAYED,
                entitlement=EntitlementState.DELAYED,
                live_verified=True,
            )
        )
        view = registry.view_capability(
            IBKR_PROVIDER_ID, IBKR_CAPABILITY_L1, require_real_time=True
        )
        self.assertEqual(view.runtime_state, RuntimeCapabilityState.DELAYED)

    def test_stale_not_treated_fresh(self) -> None:
        registry = RuntimeCapabilityRegistry()
        registry.set_runtime_state(
            ProviderRuntimeState(
                provider_id=IBKR_PROVIDER_ID,
                timeliness=DataTimeliness.STALE,
                live_verified=True,
            )
        )
        view = registry.view_capability(IBKR_PROVIDER_ID, IBKR_CAPABILITY_L2)
        self.assertEqual(view.runtime_state, RuntimeCapabilityState.STALE)

    def test_provider_health_down_blocks(self) -> None:
        registry = RuntimeCapabilityRegistry()
        registry.set_runtime_state(
            ProviderRuntimeState(
                provider_id=IBKR_PROVIDER_ID,
                health=ProviderHealth.DOWN,
            )
        )
        view = registry.view_capability(IBKR_PROVIDER_ID, IBKR_CAPABILITY_L1)
        self.assertEqual(view.runtime_state, RuntimeCapabilityState.PROVIDER_UNAVAILABLE)

    def test_live_unverified_for_ibkr(self) -> None:
        registry = RuntimeCapabilityRegistry()
        view = registry.view_capability(IBKR_PROVIDER_ID, IBKR_CAPABILITY_L1)
        self.assertEqual(view.runtime_state, RuntimeCapabilityState.LIVE_PROVIDER_UNVERIFIED)

    def test_selection_deterministic(self) -> None:
        selector = ObservationalProviderSelector()
        req = ObservationalSelectionRequest(capability_id=CAP_L1, instrument_id="AAPL")
        first = selector.select(req)
        second = selector.select(req)
        self.assertEqual(first.provider_id, second.provider_id)
        self.assertEqual(first.outcome, second.outcome)

    def test_unknown_provider_fails_explicitly(self) -> None:
        selector = ObservationalProviderSelector()
        result = selector.select(
            ObservationalSelectionRequest(
                capability_id=CAP_L1,
                instrument_id="AAPL",
                provider_id="unknown.provider",
            )
        )
        self.assertEqual(result.outcome, SelectionOutcome.NO_PROVIDER)

    def test_future_family_rejected_for_contract_observation(self) -> None:
        selector = ObservationalProviderSelector()
        from market_platform_foundation.providers.runtime_capability import CAP_FUTURE_CONTRACT

        result = selector.select(
            ObservationalSelectionRequest(
                capability_id=CAP_FUTURE_CONTRACT,
                instrument_id="ES",
                instrument_kind=InstrumentKind.FUTURE_FAMILY.value,
            )
        )
        self.assertEqual(result.outcome, SelectionOutcome.UNSUPPORTED_INSTRUMENT)

    def test_option_underlying_only_rejected(self) -> None:
        selector = ObservationalProviderSelector()
        from market_platform_foundation.providers.runtime_capability import CAP_OPTION_CONTRACT

        result = selector.select(
            ObservationalSelectionRequest(
                capability_id=CAP_OPTION_CONTRACT,
                instrument_id="NVDA",
                instrument_kind=InstrumentKind.TRADABLE_SECURITY.value,
            )
        )
        self.assertEqual(result.outcome, SelectionOutcome.UNSUPPORTED_INSTRUMENT)

    def test_canonical_instrument_required(self) -> None:
        selector = ObservationalProviderSelector()
        result = selector.select(
            ObservationalSelectionRequest(capability_id=CAP_L2, instrument_id="")
        )
        self.assertEqual(result.outcome, SelectionOutcome.UNSUPPORTED_INSTRUMENT)

    def test_provenance_preserved_in_selection(self) -> None:
        selector = ObservationalProviderSelector()
        result = selector.select(
            ObservationalSelectionRequest(
                capability_id=CAP_L1,
                instrument_id="NVDA",
                allow_replay=True,
            )
        )
        self.assertIn(result.outcome, {SelectionOutcome.SELECTED, SelectionOutcome.REPLAY_ONLY})
        self.assertIn("instrument_id", result.provenance)
        self.assertEqual(result.provenance["instrument_id"], "NVDA")


if __name__ == "__main__":
    unittest.main()
