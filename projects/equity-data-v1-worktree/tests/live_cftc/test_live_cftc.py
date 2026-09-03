"""Optional live CFTC COT probe tests — network required."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cftc.health import live_probe, source_health


@unittest.skipUnless(os.environ.get("RUN_LIVE_CFTC") == "1", "Set RUN_LIVE_CFTC=1 to run live CFTC tests")
class LiveCftcTests(unittest.TestCase):
    def test_cftc_reachable(self) -> None:
        health = source_health()
        self.assertTrue(health["reachable"])

    def test_live_probe_characterizes_datasets(self) -> None:
        probe = live_probe()
        self.assertTrue(probe["reachable"])
        self.assertIn("tff_futures_only", probe)
        self.assertIn("disaggregated_futures_only", probe)
        self.assertIn("product_hierarchy", probe)
        if probe.get("latest_observed_release"):
            self.assertRegex(str(probe["latest_observed_release"]), r"^\d{4}-\d{2}-\d{2}$")


if __name__ == "__main__":
    unittest.main()
