"""Tests for research analytics UI projection."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.ui_api.projections import (
    build_attention_page,
    build_research_analytics_payload,
)
from market_platform_foundation.ui_api.store import ReplayStore

COLLECTION_ROOT = ROOT.parent


class ResearchAnalyticsProjectionTests(unittest.TestCase):
    store: ReplayStore

    @classmethod
    def setUpClass(cls) -> None:
        cls.store = ReplayStore(collection_root=COLLECTION_ROOT)
        cls.store.load()

    def test_attention_tier_summary_present(self) -> None:
        page = build_attention_page(self.store)
        summary = page.get("tier_summary")
        self.assertIsInstance(summary, list)
        self.assertTrue(summary)
        self.assertIn("label", summary[0])
        self.assertIn("count", summary[0])

    def test_research_analytics_payload_structure(self) -> None:
        payload = build_research_analytics_payload(self.store)
        self.assertEqual(payload["authority_boundary"], "READ_ONLY_RESEARCH_VISUALIZATION")
        panels = payload["panels"]
        self.assertIn("attention_tiers", panels)
        self.assertIn("strategy_outcomes", panels)
        self.assertIn("risk_decisions", panels)
        self.assertIn("squeeze_outcomes", panels)
        self.assertIn("squeeze_historical_cohort", panels)
        historical = panels["squeeze_historical_cohort"]
        self.assertTrue(historical["available"])
        self.assertGreater(len(historical["series"]), 0)
        strategy = panels["strategy_outcomes"]
        self.assertIsInstance(strategy.get("signal_timeline"), list)

    def test_research_analytics_respects_cutoff(self) -> None:
        full = build_research_analytics_payload(self.store)
        self.store.set_cursor_index(0)
        early = build_research_analytics_payload(self.store)
        self.assertLessEqual(
            len(early["panels"]["strategy_outcomes"]["signal_timeline"]),
            len(full["panels"]["strategy_outcomes"]["signal_timeline"]),
        )


if __name__ == "__main__":
    unittest.main()
