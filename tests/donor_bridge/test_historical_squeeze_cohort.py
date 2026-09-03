"""Tests for historical squeeze cohort projection."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.donor_bridge.historical_cohort import (  # noqa: E402
    build_historical_cohort_summary_panel,
    build_historical_squeeze_context,
    load_historical_cohort,
)
from market_platform_foundation.donor_bridge.projections import (  # noqa: E402
    build_workspace_squeeze_payload,
)


class HistoricalSqueezeCohortTests(unittest.TestCase):
    def test_fixture_loads_expanded_boundaries(self) -> None:
        cohort = load_historical_cohort()
        self.assertEqual(cohort["case_boundary_count"], 35)
        self.assertEqual(len(cohort["entries"]), 35)

    def test_batch3f05_external_symbol_in_cohort(self) -> None:
        context = build_historical_squeeze_context("AACB")
        self.assertTrue(context["available"])
        self.assertEqual(context["primary_case"]["case_id"], "BATCH3F05_AACB_20260817")
        self.assertEqual(context["primary_case"]["discovery_lane"], "FRESH_FINVIZ_ELITE_EXPORT")

    def test_avtx_in_cohort(self) -> None:
        context = build_historical_squeeze_context("AVTX")
        self.assertTrue(context["available"])
        self.assertEqual(context["membership"], "IN_COHORT")
        self.assertEqual(context["primary_case"]["case_id"], "AVTX_ARTIFACT_DISCOVERY")
        self.assertTrue(context["in_frozen_demo"])

    def test_biya_has_two_boundaries(self) -> None:
        context = build_historical_squeeze_context("BIYA")
        self.assertTrue(context["available"])
        self.assertEqual(len(context["case_boundaries"]), 2)
        case_ids = {entry["case_id"] for entry in context["case_boundaries"]}
        self.assertIn("BIYA_EARLIEST_BOUNDARY", case_ids)
        self.assertIn("BIYA_LATEST_BOUNDARY", case_ids)

    def test_unknown_symbol_not_in_cohort(self) -> None:
        context = build_historical_squeeze_context("ZZZZ")
        self.assertFalse(context["available"])
        self.assertEqual(context["membership"], "NOT_IN_COHORT")
        self.assertIn("ZZZZ", context["reason"])

    def test_summary_panel_has_series(self) -> None:
        panel = build_historical_cohort_summary_panel()
        self.assertTrue(panel["available"])
        self.assertGreater(len(panel["series"]), 0)
        self.assertEqual(panel["cohort_metadata"]["case_boundary_count"], 35)

    def test_workspace_payload_includes_historical_context_when_donor_down(self) -> None:
        payload = build_workspace_squeeze_payload("AVTX", base_url="http://127.0.0.1:59999")
        self.assertFalse(payload["available"])
        historical = payload.get("historical_context")
        self.assertIsInstance(historical, dict)
        self.assertTrue(historical.get("available"))
        self.assertEqual(historical.get("primary_case", {}).get("symbol"), "AVTX")


if __name__ == "__main__":
    unittest.main()
