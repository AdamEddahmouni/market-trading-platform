"""Tests for herd urgency and quadrant helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.herd_scorer import (
    build_candidate,
    classify_herd_stage,
    compute_herd_urgency,
    quadrant_label,
)


class HerdScorerTests(unittest.TestCase):
    def test_herd_forming_stage(self) -> None:
        self.assertEqual(classify_herd_stage(2.0, 4), "herd_forming")
        self.assertEqual(classify_herd_stage(1.6, 0), "coiled")
        self.assertEqual(classify_herd_stage(6.0, 1, percent_change=8.0), "herd_here")

    def test_urgency_increases_with_social(self) -> None:
        low = compute_herd_urgency(relative_volume=1.5, social_score=0)
        high = compute_herd_urgency(relative_volume=1.5, social_score=4)
        self.assertGreater(high, low)

    def test_path_b_urgency_from_dte(self) -> None:
        urgent = compute_herd_urgency(dte=1, volume_oi_spike=3.0)
        calm = compute_herd_urgency(dte=14, volume_oi_spike=1.0)
        self.assertGreater(urgent, calm)

    def test_zero_dte_urgency_floor(self) -> None:
        """Pure 0DTE alone must clear Path B override threshold (~55)."""
        urgency = compute_herd_urgency(dte=0, volume_oi_spike=0.0)
        self.assertGreaterEqual(urgency, 55.0)
        one_dte = compute_herd_urgency(dte=1, volume_oi_spike=0.0)
        self.assertGreater(urgency, one_dte)

    def test_quadrant_labels(self) -> None:
        self.assertEqual(quadrant_label(0.5, 70), "Q1")
        self.assertEqual(quadrant_label(-0.5, 20), "Q2")
        self.assertEqual(quadrant_label(-0.5, 70), "Q3")
        self.assertEqual(quadrant_label(0.5, 20), "Q4")

    def test_build_candidate(self) -> None:
        row = build_candidate(
            ticker="BOXL",
            source="news",
            relative_volume=4.0,
            social_signal_level="HIGH_ALERT",
            social_score=5,
            news_score=0.7,
            options_score=72,
        )
        self.assertEqual(row["ticker"], "BOXL")
        self.assertEqual(row["quadrant"], "Q1")
        self.assertEqual(row["herd_stage"], "herd_forming")


if __name__ == "__main__":
    unittest.main()
