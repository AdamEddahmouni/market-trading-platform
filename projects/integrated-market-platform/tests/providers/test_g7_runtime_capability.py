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
    ConfiguredState,
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
        from market_platform_foundation.providers.moomoo_opend_capability import (
            MOOMOO_OPEND_FORBIDDEN_CAPABILITIES,
            MOOMOO_OPEND_PROVIDER_ID,
        )

        for cap in MOOMOO_OPEND_FORBIDDEN_CAPABILITIES:
            view = registry.view_capability(MOOMOO_OPEND_PROVIDER_ID, cap)
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

    def test_opend_is_known_observational_l1_provider(self) -> None:
        from market_platform_foundation.providers.adapters.yahoo_delayed_equity_quote import (
            YAHOO_PROVIDER_ID,
        )
        from market_platform_foundation.providers.moomoo_opend_capability import (
            MOOMOO_OPEND_PROVIDER_ID,
            US_EQUITY_L1_CAPABILITY,
        )

        registry = RuntimeCapabilityRegistry()
        self.assertIn(MOOMOO_OPEND_PROVIDER_ID, registry.providers_for_lane_capability(CAP_L1))
        self.assertNotIn(YAHOO_PROVIDER_ID, registry.providers_for_lane_capability(CAP_L1))
        view = registry.view_capability(MOOMOO_OPEND_PROVIDER_ID, CAP_L1)
        self.assertTrue(view.implemented)
        self.assertEqual(view.capability_id, US_EQUITY_L1_CAPABILITY)
        self.assertEqual(view.lane_capability_id, CAP_L1)
        self.assertEqual(view.runtime_state, RuntimeCapabilityState.PROVIDER_UNAVAILABLE)

    def test_opend_hop_l1_selects_after_healthy_stamp(self) -> None:
        from market_platform_foundation.providers.moomoo_opend_capability import (
            MOOMOO_OPEND_PROVIDER_ID,
        )

        registry = RuntimeCapabilityRegistry()
        registry.set_runtime_state(
            ProviderRuntimeState(
                provider_id=MOOMOO_OPEND_PROVIDER_ID,
                health=ProviderHealth.HEALTHY,
                entitlement=EntitlementState.ENTITLED,
                timeliness=DataTimeliness.REAL_TIME,
                live_verified=False,
                notes="PATH_A_ONE_SHOT",
            )
        )
        selector = ObservationalProviderSelector(registry)
        result = selector.select(
            ObservationalSelectionRequest(
                capability_id=CAP_L1,
                instrument_id="AAPL",
                require_real_time=True,
                provider_id=MOOMOO_OPEND_PROVIDER_ID,
            )
        )
        self.assertEqual(result.outcome, SelectionOutcome.SELECTED)
        self.assertEqual(result.provider_id, MOOMOO_OPEND_PROVIDER_ID)
        self.assertFalse(
            any(item.startswith("UNKNOWN_PROVIDER:") for item in result.diagnostics)
        )

    def test_opend_down_is_provider_down_not_unknown(self) -> None:
        from market_platform_foundation.providers.moomoo_opend_capability import (
            MOOMOO_OPEND_PROVIDER_ID,
        )

        selector = ObservationalProviderSelector()
        result = selector.select(
            ObservationalSelectionRequest(
                capability_id=CAP_L1,
                instrument_id="AAPL",
                require_real_time=True,
                provider_id=MOOMOO_OPEND_PROVIDER_ID,
            )
        )
        self.assertEqual(result.outcome, SelectionOutcome.PROVIDER_DOWN)
        self.assertIsNone(result.provider_id)
        self.assertIn(f"PROVIDER_DOWN:{MOOMOO_OPEND_PROVIDER_ID}", result.diagnostics)
        self.assertNotIn(f"UNKNOWN_PROVIDER:{MOOMOO_OPEND_PROVIDER_ID}", result.diagnostics)

    def test_yahoo_overlay_is_never_hop_l1(self) -> None:
        from market_platform_foundation.providers.adapters.yahoo_delayed_equity_quote import (
            YAHOO_PROVIDER_ID,
        )

        selector = ObservationalProviderSelector()
        result = selector.select(
            ObservationalSelectionRequest(
                capability_id=CAP_L1,
                instrument_id="AAPL",
                provider_id=YAHOO_PROVIDER_ID,
            )
        )
        self.assertEqual(result.outcome, SelectionOutcome.NO_PROVIDER)
        self.assertIsNone(result.provider_id)
        self.assertEqual(result.diagnostics, (f"UNKNOWN_PROVIDER:{YAHOO_PROVIDER_ID}",))

    def test_yahoo_overlay_is_registered_delayed_not_l1(self) -> None:
        from market_platform_foundation.providers.adapters.yahoo_delayed_equity_quote import (
            YAHOO_CAPABILITY,
            YAHOO_PROVIDER_ID,
        )
        from market_platform_foundation.providers.runtime_capability import (
            CAP_DELAYED_OVERLAY,
        )
        from market_platform_foundation.providers.yahoo_delayed_capability import (
            YAHOO_LICENSE_CLASS,
            YAHOO_NORMALIZER_VERSION,
        )

        registry = RuntimeCapabilityRegistry()
        overlay_providers = registry.providers_for_lane_capability(CAP_DELAYED_OVERLAY)
        self.assertIn(YAHOO_PROVIDER_ID, overlay_providers)
        self.assertNotIn(YAHOO_PROVIDER_ID, registry.providers_for_lane_capability(CAP_L1))
        view = registry.view_capability(
            YAHOO_PROVIDER_ID, CAP_DELAYED_OVERLAY, instrument_id="AAPL"
        )
        self.assertTrue(view.implemented)
        self.assertEqual(view.capability_id, YAHOO_CAPABILITY)
        self.assertEqual(view.lane_capability_id, CAP_DELAYED_OVERLAY)
        self.assertEqual(view.timeliness, DataTimeliness.DELAYED)
        self.assertNotEqual(view.timeliness, DataTimeliness.REAL_TIME)
        self.assertEqual(view.entitlement, EntitlementState.DELAYED)
        self.assertEqual(view.runtime_state, RuntimeCapabilityState.DEGRADED)
        self.assertEqual(view.provenance.get("overlay_role"), "DELAYED_EOD")
        self.assertFalse(view.provenance.get("hop_l1"))
        self.assertEqual(view.provenance.get("instrument_id"), "AAPL")
        descriptor = next(
            cap
            for cap in registry.implemented_capabilities(YAHOO_PROVIDER_ID)
            if cap.capability_id == YAHOO_CAPABILITY
        )
        self.assertTrue(descriptor.supports_history)
        self.assertFalse(descriptor.supports_pit)
        self.assertEqual(descriptor.license_class, YAHOO_LICENSE_CLASS)
        self.assertEqual(descriptor.normalizer_version, YAHOO_NORMALIZER_VERSION)

    def test_yahoo_overlay_require_real_time_is_delayed_rejected(self) -> None:
        from market_platform_foundation.providers.adapters.yahoo_delayed_equity_quote import (
            YAHOO_PROVIDER_ID,
        )
        from market_platform_foundation.providers.runtime_capability import (
            CAP_DELAYED_OVERLAY,
        )

        registry = RuntimeCapabilityRegistry()
        view = registry.view_capability(
            YAHOO_PROVIDER_ID,
            CAP_DELAYED_OVERLAY,
            instrument_id="AAPL",
            require_real_time=True,
        )
        self.assertEqual(view.runtime_state, RuntimeCapabilityState.DELAYED)
        selector = ObservationalProviderSelector(registry)
        result = selector.select(
            ObservationalSelectionRequest(
                capability_id=CAP_DELAYED_OVERLAY,
                instrument_id="AAPL",
                require_real_time=True,
                provider_id=YAHOO_PROVIDER_ID,
            )
        )
        self.assertEqual(result.outcome, SelectionOutcome.DELAYED_REJECTED)

    def test_yahoo_overlay_selects_without_require_real_time(self) -> None:
        from market_platform_foundation.providers.adapters.yahoo_delayed_equity_quote import (
            YAHOO_PROVIDER_ID,
        )
        from market_platform_foundation.providers.runtime_capability import (
            CAP_DELAYED_OVERLAY,
        )

        selector = ObservationalProviderSelector()
        result = selector.select(
            ObservationalSelectionRequest(
                capability_id=CAP_DELAYED_OVERLAY,
                instrument_id="AAPL",
                provider_id=YAHOO_PROVIDER_ID,
            )
        )
        self.assertEqual(result.outcome, SelectionOutcome.SELECTED)
        self.assertEqual(result.provider_id, YAHOO_PROVIDER_ID)
        self.assertEqual(result.provenance["instrument_id"], "AAPL")
        self.assertEqual(result.provenance.get("overlay_role"), "DELAYED_EOD")
        self.assertFalse(result.provenance.get("hop_l1"))
        self.assertEqual(result.capability_view.timeliness, DataTimeliness.DELAYED)

    def test_yahoo_overlay_stamped_real_time_still_views_delayed(self) -> None:
        from market_platform_foundation.providers.adapters.yahoo_delayed_equity_quote import (
            YAHOO_PROVIDER_ID,
        )
        from market_platform_foundation.providers.runtime_capability import (
            CAP_DELAYED_OVERLAY,
        )

        registry = RuntimeCapabilityRegistry()
        registry.set_runtime_state(
            ProviderRuntimeState(
                provider_id=YAHOO_PROVIDER_ID,
                health=ProviderHealth.HEALTHY,
                entitlement=EntitlementState.ENTITLED,
                timeliness=DataTimeliness.REAL_TIME,
                live_verified=True,
                notes="SHOULD_NOT_BECOME_HOP_L1",
            )
        )
        stored = registry.runtime_state_for(YAHOO_PROVIDER_ID)
        self.assertEqual(stored.timeliness, DataTimeliness.DELAYED)
        self.assertEqual(stored.entitlement, EntitlementState.DELAYED)
        self.assertFalse(stored.live_verified)
        self.assertIn("DELAYED_OVERLAY_NOT_REAL_TIME", stored.notes)
        view = registry.view_capability(YAHOO_PROVIDER_ID, CAP_DELAYED_OVERLAY)
        self.assertEqual(view.timeliness, DataTimeliness.DELAYED)
        self.assertNotEqual(view.timeliness, DataTimeliness.REAL_TIME)
        self.assertEqual(view.runtime_state, RuntimeCapabilityState.DEGRADED)
        self.assertFalse(view.provenance.get("hop_l1"))

    def test_yahoo_overlay_execution_forbidden(self) -> None:
        from market_platform_foundation.providers.adapters.yahoo_delayed_equity_quote import (
            YAHOO_PROVIDER_ID,
        )
        from market_platform_foundation.providers.yahoo_delayed_capability import (
            YAHOO_FORBIDDEN_CAPABILITIES,
        )

        registry = RuntimeCapabilityRegistry()
        for cap in YAHOO_FORBIDDEN_CAPABILITIES:
            view = registry.view_capability(YAHOO_PROVIDER_ID, cap)
            self.assertEqual(view.reason_code, "EXECUTION_CAPABILITY_FORBIDDEN")

    def test_yahoo_overlay_rejects_es_instrument(self) -> None:
        from market_platform_foundation.providers.adapters.yahoo_delayed_equity_quote import (
            YAHOO_PROVIDER_ID,
        )
        from market_platform_foundation.providers.runtime_capability import (
            CAP_DELAYED_OVERLAY,
        )

        selector = ObservationalProviderSelector()
        result = selector.select(
            ObservationalSelectionRequest(
                capability_id=CAP_DELAYED_OVERLAY,
                instrument_id="ES=F",
                provider_id=YAHOO_PROVIDER_ID,
            )
        )
        self.assertEqual(result.outcome, SelectionOutcome.UNSUPPORTED_INSTRUMENT)
        self.assertEqual(
            result.diagnostics,
            ("ES_FUTURES_NOT_SUPPORTED_BY_DELAYED_EQUITY_OVERLAY",),
        )

    def test_supported_is_not_configured(self) -> None:
        from market_platform_foundation.providers.ibkr_observational.capability import (
            IBKR_PROVIDER_ID,
        )

        registry = RuntimeCapabilityRegistry()
        registry.set_runtime_state(
            ProviderRuntimeState(
                provider_id=IBKR_PROVIDER_ID,
                health=ProviderHealth.HEALTHY,
                entitlement=EntitlementState.ENTITLED,
                timeliness=DataTimeliness.REAL_TIME,
                live_verified=True,
                configured=ConfiguredState.NOT_CONFIGURED,
            )
        )
        view = registry.view_capability(IBKR_PROVIDER_ID, CAP_L1, instrument_id="AAPL")
        self.assertTrue(view.implemented)
        self.assertEqual(view.configured, ConfiguredState.NOT_CONFIGURED)
        self.assertEqual(view.runtime_state, RuntimeCapabilityState.NOT_CONFIGURED)
        self.assertEqual(view.provenance["axes"]["supported"], True)
        self.assertEqual(view.provenance["axes"]["configured"], "NOT_CONFIGURED")
        selector = ObservationalProviderSelector(registry)
        result = selector.select(
            ObservationalSelectionRequest(
                capability_id=CAP_L1,
                instrument_id="AAPL",
                require_real_time=True,
                provider_id=IBKR_PROVIDER_ID,
            )
        )
        self.assertEqual(result.outcome, SelectionOutcome.NOT_CONFIGURED)

    def test_configured_is_not_entitled(self) -> None:
        from market_platform_foundation.providers.ibkr_observational.capability import (
            IBKR_PROVIDER_ID,
        )

        registry = RuntimeCapabilityRegistry()
        registry.set_runtime_state(
            ProviderRuntimeState(
                provider_id=IBKR_PROVIDER_ID,
                health=ProviderHealth.HEALTHY,
                entitlement=EntitlementState.UNKNOWN,
                timeliness=DataTimeliness.REAL_TIME,
                live_verified=True,
                configured=ConfiguredState.CONFIGURED,
            )
        )
        view = registry.view_capability(
            IBKR_PROVIDER_ID, CAP_L1, instrument_id="AAPL", require_real_time=True
        )
        self.assertEqual(view.configured, ConfiguredState.CONFIGURED)
        self.assertEqual(view.entitlement, EntitlementState.UNKNOWN)
        self.assertEqual(view.runtime_state, RuntimeCapabilityState.NOT_ENTITLED)
        self.assertEqual(view.reason_code, "ENTITLEMENT_UNKNOWN")
        self.assertEqual(view.provenance["axes"]["configured"], "CONFIGURED")
        self.assertNotEqual(view.provenance["axes"]["entitled"], "ENTITLED")

    def test_entitled_is_not_fresh(self) -> None:
        from market_platform_foundation.providers.ibkr_observational.capability import (
            IBKR_PROVIDER_ID,
        )

        registry = RuntimeCapabilityRegistry()
        registry.set_runtime_state(
            ProviderRuntimeState(
                provider_id=IBKR_PROVIDER_ID,
                health=ProviderHealth.HEALTHY,
                entitlement=EntitlementState.ENTITLED,
                timeliness=DataTimeliness.UNKNOWN,
                live_verified=True,
                configured=ConfiguredState.CONFIGURED,
            )
        )
        view = registry.view_capability(
            IBKR_PROVIDER_ID, CAP_L1, instrument_id="AAPL", require_real_time=True
        )
        self.assertEqual(view.entitlement, EntitlementState.ENTITLED)
        self.assertEqual(view.timeliness, DataTimeliness.UNKNOWN)
        self.assertFalse(view.provenance["axes"]["fresh"])
        self.assertEqual(view.runtime_state, RuntimeCapabilityState.FRESHNESS_UNKNOWN)
        selector = ObservationalProviderSelector(registry)
        result = selector.select(
            ObservationalSelectionRequest(
                capability_id=CAP_L1,
                instrument_id="AAPL",
                require_real_time=True,
                provider_id=IBKR_PROVIDER_ID,
            )
        )
        self.assertEqual(result.outcome, SelectionOutcome.FRESHNESS_UNKNOWN)

    def test_yahoo_overlay_configured_is_still_not_hop_l1_or_fresh(self) -> None:
        from market_platform_foundation.providers.adapters.yahoo_delayed_equity_quote import (
            YAHOO_PROVIDER_ID,
        )
        from market_platform_foundation.providers.runtime_capability import (
            CAP_DELAYED_OVERLAY,
        )

        registry = RuntimeCapabilityRegistry()
        view = registry.view_capability(
            YAHOO_PROVIDER_ID, CAP_DELAYED_OVERLAY, instrument_id="AAPL"
        )
        self.assertTrue(view.implemented)
        self.assertEqual(view.configured, ConfiguredState.CONFIGURED)
        self.assertEqual(view.entitlement, EntitlementState.DELAYED)
        self.assertFalse(view.provenance["axes"]["fresh"])
        self.assertFalse(view.provenance.get("hop_l1"))
        selector = ObservationalProviderSelector(registry)
        result = selector.select(
            ObservationalSelectionRequest(
                capability_id=CAP_L1,
                instrument_id="AAPL",
                require_real_time=True,
                provider_id=YAHOO_PROVIDER_ID,
            )
        )
        self.assertEqual(result.outcome, SelectionOutcome.NO_PROVIDER)
        self.assertEqual(result.diagnostics, (f"UNKNOWN_PROVIDER:{YAHOO_PROVIDER_ID}",))


if __name__ == "__main__":
    unittest.main()
