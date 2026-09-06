"""P1-4: discovery vs workspace kebab vs evidence LaneId mapping."""

from __future__ import annotations

import unittest

from market_platform_foundation.cross_lane.evidence import LaneId
from market_platform_foundation.discovery.mixed import LANES_BY_SCREEN
from market_platform_foundation.lanes.vocabulary import (
    DISCOVERY_LANES,
    DISCOVERY_LANE_TO_WORKSPACE_MODULE,
    LANE_ID_TO_WORKSPACE_MODULE,
    UI_EVIDENCE_LANE_TO_WORKSPACE_MODULE,
    workspace_module_for_discovery_lane,
    workspace_module_for_lane_id,
    workspace_module_for_ui_evidence_lane,
)
from market_platform_foundation.ui_api.workspace_evidence import (
    LANE_CATALYST,
    LANE_FUTURES,
    LANE_MARKET_CONTEXT,
    LANE_OPTIONS,
    LANE_ORDER_FLOW,
    LANE_SHORT_INTELLIGENCE,
    LANE_SHORT_SQUEEZE,
    LANE_WHALE_INSIDER,
)


class LaneVocabularyMappingTests(unittest.TestCase):
    def test_discovery_lanes_cover_mixed_queue_buckets(self) -> None:
        used = {lane for lanes in LANES_BY_SCREEN.values() for lane in lanes}
        self.assertEqual(used, set(DISCOVERY_LANES))
        self.assertEqual(set(DISCOVERY_LANE_TO_WORKSPACE_MODULE), set(DISCOVERY_LANES))

    def test_every_lane_id_has_a_workspace_crosswalk_row(self) -> None:
        self.assertEqual(set(LANE_ID_TO_WORKSPACE_MODULE), {item.value for item in LaneId})

    def test_market_context_maps_to_catalyst_not_order_book(self) -> None:
        self.assertEqual(workspace_module_for_lane_id(LaneId.MARKET_CONTEXT.value), "catalyst")
        self.assertEqual(workspace_module_for_ui_evidence_lane(LANE_MARKET_CONTEXT), "catalyst")
        self.assertEqual(workspace_module_for_discovery_lane("CATALYST"), "catalyst")
        self.assertNotEqual(LANE_ID_TO_WORKSPACE_MODULE["market_context"], "order-book")
        self.assertNotEqual(UI_EVIDENCE_LANE_TO_WORKSPACE_MODULE["MARKET_CONTEXT"], "order-book")
        self.assertEqual(workspace_module_for_lane_id("order_flow"), "order-flow")

    def test_ui_evidence_tokens_cover_workspace_envelope_lanes(self) -> None:
        expected = {
            LANE_SHORT_SQUEEZE,
            LANE_ORDER_FLOW,
            LANE_MARKET_CONTEXT,
            LANE_CATALYST,
            LANE_OPTIONS,
            LANE_FUTURES,
            LANE_SHORT_INTELLIGENCE,
            LANE_WHALE_INSIDER,
        }
        self.assertEqual(set(UI_EVIDENCE_LANE_TO_WORKSPACE_MODULE), expected)

    def test_screener_only_discovery_lanes_have_no_workspace_page(self) -> None:
        self.assertIsNone(workspace_module_for_discovery_lane("MOMENTUM"))
        self.assertIsNone(workspace_module_for_discovery_lane("SWING"))
        self.assertEqual(workspace_module_for_discovery_lane("SQUEEZE"), "squeeze")


if __name__ == "__main__":
    unittest.main()
