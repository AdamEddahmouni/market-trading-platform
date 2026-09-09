"""G15 BL-0802 — browser product acceptance via Playwright + deterministic harness."""

from __future__ import annotations

import os
import shutil
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _playwright_available() -> bool:
    e2e_dir = ROOT / "e2e"
    if not (e2e_dir / "node_modules" / "@playwright").exists():
        return False
    return shutil.which("npm") is not None or shutil.which("npm.cmd") is not None


@unittest.skipUnless(_playwright_available(), "Playwright E2E dependencies not installed")
class BrowserProductAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools.e2e.harness import ProductAcceptanceHarness

        cls.harness = ProductAcceptanceHarness()
        cls.services = cls.harness.start(prepare_fixture=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.harness.stop()

    def test_playwright_product_acceptance_suite(self) -> None:
        from tools.e2e.harness import run_playwright

        exit_code = run_playwright(ui_base=self.services.ui_base)
        self.assertEqual(exit_code, 0, "Playwright product acceptance suite failed")


@unittest.skipUnless(_playwright_available(), "Playwright E2E dependencies not installed")
class E2EHarnessContractTests(unittest.TestCase):
    def test_harness_starts_and_stops_cleanly(self) -> None:
        from tools.e2e.harness import ProductAcceptanceHarness

        harness = ProductAcceptanceHarness()
        services = harness.start(prepare_fixture=True)
        self.assertTrue(services.api_base.startswith("http://"))
        self.assertTrue(services.ui_base.startswith("http://"))
        harness.stop()

    def test_fast_validation_excludes_e2e_suite(self) -> None:
        from tools.validation_manifest import load_manifest
        from tools.validate import _e2e_exclusive_suite_ids, _mandatory_selectors, select_changed

        manifest = load_manifest(ROOT / "tools" / "validation_manifest.json")
        fast = _mandatory_selectors(manifest)
        self.assertTrue(fast)
        e2e_suite = manifest.suite_by_id("product_acceptance")
        self.assertIn("e2e", e2e_suite.tiers)
        self.assertNotIn("full", e2e_suite.tiers)
        self.assertIn("product_acceptance", _e2e_exclusive_suite_ids(manifest))
        changed = select_changed(
            manifest,
            (
                "tests/product_acceptance/test_browser_acceptance.py",
                "ui/src/components/paper/OrderTicket.tsx",
            ),
        )
        self.assertNotIn("product_acceptance", changed.selected_suite_ids)
