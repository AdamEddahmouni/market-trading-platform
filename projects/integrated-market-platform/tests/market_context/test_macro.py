"""Tests for MC11 macro context evidence."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cross_lane.evidence import EvidenceSignal  # noqa: E402
from market_platform_foundation.market_context.macro import (  # noqa: E402
    build_fixture_macro_pipeline,
    build_macro_cross_lane_evidence,
    load_macro_context_fixture,
    macro_summary_to_dict,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.providers.projections import (  # noqa: E402
    build_workspace_market_context_payload,
)

MACRO_SLICE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_macro_context_slice.json"
EXPECTED_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_macro_context_expected.json"
CUTOFF = "2026-07-23T00:00:00.000000000Z"
CUTOFF_NS = iso_to_epoch_ns(CUTOFF)


class TestMC11MacroContext(unittest.TestCase):
    def test_macro_pipeline_matches_golden_fixture(self) -> None:
        events = load_macro_context_fixture(MACRO_SLICE)
        _, summary, _ = build_fixture_macro_pipeline(events, prediction_cutoff=CUTOFF_NS)
        expected = json.loads(EXPECTED_FIXTURE.read_text(encoding="utf-8"))
        payload = macro_summary_to_dict(summary)
        for key, value in expected["macro_context_summary"].items():
            self.assertEqual(payload.get(key), value, msg=key)
        self.assertTrue(summary.macro_context_available)

    def test_pit_excludes_future_macro_releases(self) -> None:
        events = load_macro_context_fixture(MACRO_SLICE)
        early_cutoff = iso_to_epoch_ns("2026-07-01T00:00:00.000000000Z")
        _, summary, _ = build_fixture_macro_pipeline(events, prediction_cutoff=early_cutoff)
        self.assertFalse(summary.macro_context_available)

    def test_cross_lane_publishes_macro_regime_context(self) -> None:
        events = load_macro_context_fixture(MACRO_SLICE)
        _, summary, _ = build_fixture_macro_pipeline(events, prediction_cutoff=CUTOFF_NS)
        evidence = build_macro_cross_lane_evidence(summary, prediction_cutoff=CUTOFF_NS)
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["signal"], EvidenceSignal.MACRO_REGIME_CONTEXT.value)

    def test_workspace_projection_includes_macro_context(self) -> None:
        payload = build_workspace_market_context_payload(
            "BOXL",
            as_of_context={"as_of_time_ns": CUTOFF_NS},
            prediction_cutoff=CUTOFF_NS,
        )
        self.assertTrue(payload.get("macro_context_available"))
        summary = payload.get("macro_context_summary", {})
        self.assertEqual(summary.get("growth_regime"), "EXPANDING")
        self.assertEqual(summary.get("inflation_regime"), "ELEVATED")
        signals = [item.get("signal") for item in payload.get("cross_lane_evidence", [])]
        self.assertIn(EvidenceSignal.MACRO_REGIME_CONTEXT.value, signals)


if __name__ == "__main__":
    unittest.main()
