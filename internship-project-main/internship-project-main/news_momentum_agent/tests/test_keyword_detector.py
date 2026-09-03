"""Unit tests for keyword scoring behavior."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from social.keyword_detector import normalize_post_text, score_post_for_catalyst


class KeywordDetectorTests(unittest.TestCase):
    """Validate normalization, aliases, and configurable thresholds."""

    def test_normalize_post_text_preserves_cashtag(self) -> None:
        text = "Big!!! News?? watch $AAPL   now."
        self.assertEqual(normalize_post_text(text), "big news watch $aapl now")

    def test_aliases_improve_match_rate(self) -> None:
        result = score_post_for_catalyst(
            post_text="Company just got FDA greenlight and won contract.",
            high_alert_threshold=3,
            watch_threshold=1,
            enable_aliases=True,
        )
        self.assertGreaterEqual(int(result["total_score"]), 5)
        self.assertEqual(result["escalation_level"], "HIGH_ALERT")

    def test_threshold_overrides_change_escalation(self) -> None:
        result = score_post_for_catalyst(
            post_text="premarket volume spike",
            high_alert_threshold=2,
            watch_threshold=1,
            enable_aliases=False,
        )
        self.assertEqual(result["total_score"], 2)
        self.assertEqual(result["escalation_level"], "HIGH_ALERT")


if __name__ == "__main__":
    unittest.main()
