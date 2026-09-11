"""Regression tests for ReplayStore-scoped capability projection cache."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.ui_api.projections import build_capabilities
from market_platform_foundation.ui_api.store import ReplayStore, TRACKED_ASSISTANT_AUDIT_ROOT


class CapabilitiesProjectionCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ReplayStore(
            collection_root=ROOT.parent,
            assistant_audit_root=TRACKED_ASSISTANT_AUDIT_ROOT,
        )
        self.store.load()

    def test_build_capabilities_reuses_store_cache(self) -> None:
        with mock.patch(
            "market_platform_foundation.ui_api.projections.disclosure_available",
            return_value=True,
        ) as disclosure_available:
            first = build_capabilities(self.store)
            second = build_capabilities(self.store)
            disclosure_available.assert_called_once()
        self.assertEqual(first, second)
        self.assertIsNot(first, second)

    def test_cache_invalidates_when_cursor_changes(self) -> None:
        with mock.patch(
            "market_platform_foundation.ui_api.projections.disclosure_available",
            return_value=True,
        ) as disclosure_available:
            build_capabilities(self.store)
            self.store.cursor_index = max(0, self.store.cursor_index - 1)
            build_capabilities(self.store)
            self.assertEqual(disclosure_available.call_count, 2)


if __name__ == "__main__":
    unittest.main()
