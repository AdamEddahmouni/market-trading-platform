"""Smoke tests for state helper behavior."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import extract_state_items, merge_nested_dicts


class MainHelperTests(unittest.TestCase):
    """Validate state/helper functions used by scheduler runtime."""

    def test_extract_state_items_supports_wrapped_and_legacy(self) -> None:
        legacy_items, legacy_meta = extract_state_items([{"ticker": "AAPL"}])
        self.assertEqual(len(legacy_items), 1)
        self.assertEqual(legacy_meta, {})

        wrapped_items, wrapped_meta = extract_state_items({"meta": {"cycle_id": 1}, "items": [{"ticker": "MSFT"}]})
        self.assertEqual(len(wrapped_items), 1)
        self.assertEqual(wrapped_meta.get("cycle_id"), 1)

    def test_merge_nested_dicts_preserves_defaults(self) -> None:
        defaults = {"social": {"watch_threshold": 1, "high_alert_threshold": 3}, "agent": {"buy_threshold": 0.5}}
        user = {"social": {"watch_threshold": 2}}
        merged = merge_nested_dicts(defaults, user)
        self.assertEqual(merged["social"]["watch_threshold"], 2)
        self.assertEqual(merged["social"]["high_alert_threshold"], 3)
        self.assertEqual(merged["agent"]["buy_threshold"], 0.5)


if __name__ == "__main__":
    unittest.main()
