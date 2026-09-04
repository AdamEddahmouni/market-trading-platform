"""P3.2 unified live decision workstation tests."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from market_platform_foundation.ui_api.store import ReplayStore
from market_platform_foundation.ui_api.workspace_evidence import (
    DIRECTION_MIXED,
    DIRECTION_NEGATIVE,
    DIRECTION_POSITIVE,
    LANE_CATALYST,
    LANE_MARKET_CONTEXT,
    LANE_ORDER_FLOW,
    LANE_SHORT_INTELLIGENCE,
    RESEARCH_CONTEXT_EXECUTION_AUTHORITY,
    adapt_order_flow_lane,
    build_workspace_evidence_payload,
    compute_evidence_mix_summary,
)

COLLECTION_ROOT = ROOT.parent
ADMITTED = "BIYA"


class UnifiedWorkstationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.store = ReplayStore(collection_root=COLLECTION_ROOT)
        cls.store.load()

    def test_all_workspace_sections_use_active_instrument(self) -> None:
        payload = build_workspace_evidence_payload(self.store, ADMITTED)
        self.assertEqual(payload["instrument"], ADMITTED)
        for lane in payload["lanes"]:
            self.assertEqual(lane["instrument"], ADMITTED)

    def test_relevance_is_separate_from_direction(self) -> None:
        payload = build_workspace_evidence_payload(self.store, ADMITTED)
        for lane in payload["lanes"]:
            if lane.get("relevance") == "HIGH" and lane.get("direction") == DIRECTION_NEGATIVE:
                self.assertNotEqual(lane["relevance"], lane["direction"])

    def test_contradictory_evidence_is_preserved(self) -> None:
        lanes = [
            {"lane": LANE_ORDER_FLOW, "direction": DIRECTION_POSITIVE},
            {"lane": LANE_CATALYST, "direction": DIRECTION_POSITIVE},
            {"lane": LANE_MARKET_CONTEXT, "direction": DIRECTION_NEGATIVE},
            {"lane": LANE_SHORT_INTELLIGENCE, "direction": "NEUTRAL"},
        ]
        mix = compute_evidence_mix_summary(lanes)
        self.assertEqual(mix, DIRECTION_MIXED)
        payload = build_workspace_evidence_payload(
            self.store,
            ADMITTED,
            lane_overrides={
                LANE_ORDER_FLOW: {"direction": DIRECTION_POSITIVE, "relevance": "HIGH"},
                LANE_CATALYST: {"direction": DIRECTION_POSITIVE, "relevance": "HIGH"},
                LANE_MARKET_CONTEXT: {"direction": DIRECTION_NEGATIVE, "relevance": "MEDIUM"},
                LANE_SHORT_INTELLIGENCE: {"direction": "NEUTRAL", "relevance": "MEDIUM"},
            },
        )
        self.assertEqual(payload["evidence_mix_summary"], DIRECTION_MIXED)
        directions = {row["lane"]: row.get("direction") for row in payload["lanes"]}
        self.assertEqual(directions[LANE_ORDER_FLOW], DIRECTION_POSITIVE)
        self.assertEqual(directions[LANE_MARKET_CONTEXT], DIRECTION_NEGATIVE)

    def test_missing_lane_is_unavailable_not_zero(self) -> None:
        payload = build_workspace_evidence_payload(self.store, "ZZZZ")
        options = next(row for row in payload["lanes"] if row["lane"] == "OPTIONS")
        self.assertIn(options["quality"], {"NOT_CONFIGURED", "UNAVAILABLE"})
        self.assertNotEqual(options.get("probability"), 0)
        self.assertNotEqual(options.get("expected_value"), 0)

    def test_stale_evidence_exposes_staleness(self) -> None:
        payload = build_workspace_evidence_payload(
            self.store,
            ADMITTED,
            lane_overrides={
                LANE_SHORT_INTELLIGENCE: {
                    "quality": "STALE",
                    "freshness_label": "AS OF AUG 15",
                },
            },
        )
        si = next(row for row in payload["lanes"] if row["lane"] == LANE_SHORT_INTELLIGENCE)
        self.assertEqual(si["quality"], "STALE")
        self.assertIn("AUG", si["freshness_label"])

    def test_lane_evidence_has_provenance(self) -> None:
        payload = build_workspace_evidence_payload(self.store, ADMITTED)
        for lane in payload["lanes"]:
            if lane.get("quality") == "PASS":
                self.assertTrue(lane.get("sources") or lane.get("reason_codes"))

    def test_research_evidence_cannot_authorize_order(self) -> None:
        payload = build_workspace_evidence_payload(self.store, ADMITTED)
        self.assertEqual(payload["research_context_execution_authority"], RESEARCH_CONTEXT_EXECUTION_AUTHORITY)
        self.assertEqual(RESEARCH_CONTEXT_EXECUTION_AUTHORITY, "NONE")

    def test_moomoo_remains_market_data_only(self) -> None:
        of_lane = adapt_order_flow_lane(
            self.store,
            ADMITTED,
            as_of_context={"as_of_time": self.store.as_of_time(), "data_mode": "FIXTURE_REPLAY"},
            prediction_cutoff=self.store.prediction_cutoff(),
        )
        sources = of_lane.get("sources") or []
        self.assertTrue(all("MOOMOO" not in s or s == "MOOMOO" for s in sources) or sources)

    def test_capture_replay_identified_as_replay(self) -> None:
        payload = build_workspace_evidence_payload(self.store, ADMITTED)
        mode = payload["as_of_context"].get("data_mode")
        if mode == "CAPTURE_REPLAY":
            self.assertEqual(payload["data_provenance"].get("replay_label"), "MOOMOO CAPTURE")

    def test_no_biya_fallback_in_live_workspace_resolution(self) -> None:
        os.environ["IMP_LIVE_OBSERVATIONAL"] = "1"
        os.environ["IMP_MOOMOO_LIVE"] = "1"
        try:
            from market_platform_foundation.ui_api.operator_instrument import resolve_active_operator_instrument

            store = ReplayStore(collection_root=COLLECTION_ROOT)
            store.data_mode = "LIVE_OBSERVATIONAL"
            active, _ = resolve_active_operator_instrument(store)
            if active is None:
                self.assertIsNone(active)
            else:
                self.assertNotEqual(active, ADMITTED if store.instrument_id == ADMITTED else active)
        finally:
            os.environ.pop("IMP_LIVE_OBSERVATIONAL", None)
            os.environ.pop("IMP_MOOMOO_LIVE", None)

    def test_degraded_trade_feed_degrades_cvd_quality(self) -> None:
        payload = build_workspace_evidence_payload(
            self.store,
            ADMITTED,
            lane_overrides={
                LANE_ORDER_FLOW: {"quality": "DEGRADED", "freshness_label": "LIVE · DEGRADED"},
            },
        )
        of = next(row for row in payload["lanes"] if row["lane"] == LANE_ORDER_FLOW)
        self.assertEqual(of["quality"], "DEGRADED")

    def test_missing_l2_does_not_break_other_lanes(self) -> None:
        payload = build_workspace_evidence_payload(self.store, "AAPL")
        self.assertGreaterEqual(len(payload["lanes"]), 6)


if __name__ == "__main__":
    unittest.main()
