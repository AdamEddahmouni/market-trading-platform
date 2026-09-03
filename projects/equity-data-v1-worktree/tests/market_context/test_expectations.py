"""Tests for MC6 expectations / surprise."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.market_context import ContextQualityFlag  # noqa: E402
from market_platform_foundation.market_context.expectations import (  # noqa: E402
    build_fixture_surprise_pipeline,
    load_expectations_fixture,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.providers.projections import (  # noqa: E402
    build_workspace_market_context_payload,
)

EXPECTATIONS_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_expectations_slice.json"
EXPECTED_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_surprise_expected.json"
CUTOFF = "2026-07-23T00:00:00.000000000Z"
CUTOFF_NS = iso_to_epoch_ns(CUTOFF)


class TestMC6SurprisePipeline(unittest.TestCase):
    def test_revenue_surprise_positive(self) -> None:
        rows = load_expectations_fixture(EXPECTATIONS_FIXTURE)
        _, surprises, summaries, _ = build_fixture_surprise_pipeline(
            rows,
            prediction_cutoff=CUTOFF_NS,
        )
        revenue = [item for item in summaries if item.metric_name == "revenue" and item.surprise_available]
        self.assertEqual(len(revenue), 1)
        self.assertEqual(revenue[0].actual_value, "42.5")
        self.assertEqual(revenue[0].expected_value, "40.5")
        self.assertEqual(len(surprises), 1)

    def test_missing_consensus_fail_closed(self) -> None:
        rows = load_expectations_fixture(EXPECTATIONS_FIXTURE)
        _, surprises, summaries, _ = build_fixture_surprise_pipeline(
            rows,
            prediction_cutoff=CUTOFF_NS,
        )
        eps_rows = [item for item in summaries if item.metric_name == "eps"]
        self.assertEqual(len(eps_rows), 1)
        self.assertFalse(eps_rows[0].surprise_available)
        self.assertIn(
            ContextQualityFlag.SURPRISE_UNAVAILABLE.value,
            eps_rows[0].quality_flags,
        )
        self.assertEqual(len([s for s in surprises if s.metric_name == "eps"]), 0)

    def test_pit_excludes_future_consensus(self) -> None:
        rows = load_expectations_fixture(EXPECTATIONS_FIXTURE)
        early_cutoff = iso_to_epoch_ns("2026-07-15T09:00:00.000000000Z")
        _, surprises, summaries, _ = build_fixture_surprise_pipeline(
            rows,
            prediction_cutoff=early_cutoff,
        )
        self.assertEqual(len(surprises), 0)
        revenue = [item for item in summaries if item.metric_name == "revenue"]
        self.assertTrue(revenue)
        self.assertFalse(revenue[0].surprise_available)

    def test_golden_workspace_surprise_block(self) -> None:
        expected = json.loads(EXPECTED_FIXTURE.read_text(encoding="utf-8"))
        payload = build_workspace_market_context_payload(
            "BOXL",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=CUTOFF_NS,
        )
        self.assertTrue(payload["surprise_available"])
        self.assertEqual(payload["surprise_count"], expected["surprise_count"])
        self.assertEqual(len(payload["surprise_summaries"]), len(expected["surprise_summaries"]))
        summary = payload["surprise_summaries"][0]
        expected_summary = expected["surprise_summaries"][0]
        self.assertEqual(summary["metric_name"], expected_summary["metric_name"])
        self.assertEqual(summary["surprise"], expected_summary["surprise"])


if __name__ == "__main__":
    unittest.main()
