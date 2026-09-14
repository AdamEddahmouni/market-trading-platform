"""Yahoo delayed overlay must never occupy hop L1.

OpenD down stays OpenD-unavailable. After G7 registers Yahoo as
``US_EQUITY_SNAPSHOT``, viewing Yahoo as ``OBSERVATIONAL_L1`` must not
resolve to IBKR_L1 / ``US_EQUITY_L1`` or look implemented.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.market_data.runtime_composition import (  # noqa: E402
    ObservationalRuntimeComposition,
)
from market_platform_foundation.providers.adapters.yahoo_delayed_equity_quote import (  # noqa: E402
    YAHOO_CAPABILITY,
    YAHOO_PROVIDER_ID,
)
from market_platform_foundation.providers.ibkr_observational.capability import (  # noqa: E402
    IBKR_CAPABILITY_L1,
)
from market_platform_foundation.providers.moomoo_opend_capability import (  # noqa: E402
    MOOMOO_OPEND_PROVIDER_ID,
)
from market_platform_foundation.providers.runtime_capability import (  # noqa: E402
    CAP_DELAYED_OVERLAY,
    CAP_L1,
    DataTimeliness,
    EntitlementState,
    RuntimeCapabilityRegistry,
    RuntimeCapabilityState,
)
from market_platform_foundation.providers.runtime_selection import (  # noqa: E402
    ObservationalProviderSelector,
    ObservationalSelectionRequest,
)


class YahooNeverHopL1Tests(unittest.TestCase):
    def test_yahoo_l1_view_is_unavailable_not_ibkr_alias(self) -> None:
        registry = RuntimeCapabilityRegistry()
        view = registry.view_capability(
            YAHOO_PROVIDER_ID, CAP_L1, instrument_id="AAPL"
        )
        self.assertFalse(view.implemented)
        self.assertEqual(view.runtime_state, RuntimeCapabilityState.UNAVAILABLE)
        self.assertEqual(view.reason_code, "DELAYED_OVERLAY_NOT_HOP_L1")
        self.assertEqual(view.capability_id, YAHOO_CAPABILITY)
        self.assertNotEqual(view.capability_id, IBKR_CAPABILITY_L1)
        self.assertNotEqual(view.capability_id, "US_EQUITY_L1")
        self.assertEqual(view.lane_capability_id, CAP_L1)
        self.assertEqual(view.timeliness, DataTimeliness.DELAYED)
        self.assertEqual(view.entitlement, EntitlementState.DELAYED)
        self.assertFalse(view.provenance.get("hop_l1"))
        self.assertEqual(view.provenance.get("overlay_role"), "DELAYED_EOD")

    def test_yahoo_us_equity_l1_registry_id_is_also_rejected(self) -> None:
        registry = RuntimeCapabilityRegistry()
        view = registry.view_capability(
            YAHOO_PROVIDER_ID, "US_EQUITY_L1", instrument_id="AAPL"
        )
        self.assertFalse(view.implemented)
        self.assertEqual(view.reason_code, "DELAYED_OVERLAY_NOT_HOP_L1")
        self.assertFalse(view.provenance.get("hop_l1"))

    def test_unpinned_l1_select_never_returns_yahoo(self) -> None:
        selector = ObservationalProviderSelector()
        result = selector.select(
            ObservationalSelectionRequest(
                capability_id=CAP_L1,
                instrument_id="AAPL",
                require_real_time=True,
            )
        )
        self.assertNotEqual(result.provider_id, YAHOO_PROVIDER_ID)
        self.assertNotIn(
            f"SELECTED:{YAHOO_PROVIDER_ID}", result.diagnostics
        )
        if result.outcome.value == "SELECTED":
            self.assertNotEqual(result.provider_id, YAHOO_PROVIDER_ID)

    def test_opend_down_does_not_select_yahoo_as_l1(self) -> None:
        selector = ObservationalProviderSelector()
        result = selector.select(
            ObservationalSelectionRequest(
                capability_id=CAP_L1,
                instrument_id="AAPL",
                require_real_time=True,
                provider_id=MOOMOO_OPEND_PROVIDER_ID,
            )
        )
        self.assertEqual(result.outcome.value, "PROVIDER_DOWN")
        self.assertIsNone(result.provider_id)
        unpinned = selector.select(
            ObservationalSelectionRequest(
                capability_id=CAP_L1,
                instrument_id="AAPL",
                require_real_time=True,
            )
        )
        self.assertNotEqual(unpinned.provider_id, YAHOO_PROVIDER_ID)

    def test_delayed_overlay_lane_still_selects_yahoo(self) -> None:
        registry = RuntimeCapabilityRegistry()
        overlay = registry.view_capability(
            YAHOO_PROVIDER_ID, CAP_DELAYED_OVERLAY, instrument_id="AAPL"
        )
        self.assertTrue(overlay.implemented)
        self.assertEqual(overlay.lane_capability_id, CAP_DELAYED_OVERLAY)
        self.assertFalse(overlay.provenance.get("hop_l1"))
        selector = ObservationalProviderSelector(registry)
        selected = selector.select(
            ObservationalSelectionRequest(
                capability_id=CAP_DELAYED_OVERLAY,
                instrument_id="AAPL",
                provider_id=YAHOO_PROVIDER_ID,
            )
        )
        self.assertEqual(selected.outcome.value, "SELECTED")
        self.assertEqual(selected.provider_id, YAHOO_PROVIDER_ID)
        self.assertFalse(selected.provenance.get("hop_l1"))

    def test_hop_snapshot_does_not_treat_yahoo_as_l1(self) -> None:
        composition = ObservationalRuntimeComposition()
        snapshot = composition.runtime_capability_snapshot_for(
            "AAPL",
            provider_id=YAHOO_PROVIDER_ID,
            capability_id=CAP_L1,
        )
        view = snapshot["runtime_capability"]
        self.assertEqual(view["provider_id"], YAHOO_PROVIDER_ID)
        self.assertFalse(view["implemented"])
        self.assertEqual(view["reason_code"], "DELAYED_OVERLAY_NOT_HOP_L1")
        self.assertFalse(view["provenance"].get("hop_l1"))
        self.assertEqual(snapshot["provider_id"], YAHOO_PROVIDER_ID)
        self.assertIsNone(snapshot["quote_provider"])
