"""Opt-in live FRED / ALFRED probes — requires IMP_FRED_LIVE=1 and FRED_API_KEY."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.fred.health import alfred_revision_proof, capability_report, live_probe_v1, live_probe_v2
from market_platform_foundation.fred.live import api_key_present, live_enabled, transport_from_env
from market_platform_foundation.fred.reconcile import reconcile_current_values
from market_platform_foundation.fred.registry import lookup_canonical
from market_platform_foundation.fred.sync import FredSync
from market_platform_foundation.fred.normalize import normalize_v1_observation_row, normalize_v2_observation_row


@unittest.skipUnless(os.environ.get("IMP_FRED_LIVE") == "1", "Set IMP_FRED_LIVE=1 for live FRED tests")
@unittest.skipUnless(api_key_present(), "FRED_API_KEY required for live FRED tests")
class LiveFredTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.v1, cls.v2 = transport_from_env()
        cls.sync = FredSync(v1=cls.v1, v2=cls.v2)

    def test_v1_probe(self) -> None:
        probe = live_probe_v1(self.v1)
        self.assertTrue(probe.get("reachable"), probe.get("error"))
        self.assertTrue(probe.get("series_metadata"))
        self.assertGreater(probe.get("vintage_dates", 0), 0)
        self.assertGreater(probe.get("current_observations", 0), 0)
        self.assertGreater(probe.get("release_dates", 0), 0)

    def test_v2_cpi_release(self) -> None:
        probe = live_probe_v2(self.v2, release_id=10)
        self.assertTrue(probe.get("reachable"), probe.get("error"))
        self.assertGreater(probe.get("observation_count", 0), 0)
        self.assertGreater(probe.get("series_count", 0), 0)
        self.assertIn("copyright_ids_sample", probe)

    def test_v1_v2_reconciliation_cpi(self) -> None:
        entry = lookup_canonical("US_CORE_CPI")
        assert entry is not None
        v1_rows = self.v1.series_observations("CPILFESL", output_type=1, sort_order="desc", limit=1)
        target_date = str(v1_rows["observations"][0].get("date", ""))
        v1_obs = normalize_v1_observation_row(
            v1_rows["observations"][0],
            entry=entry,
            retrieved_time="live",
            observed_time="live",
        )
        v2_page = self.v2.fetch_release_observations(10, max_pages=10)
        v2_obs = None
        for page in v2_page.pages:
            for row in page.observations:
                if str(row.get("series_id")) == "CPILFESL" and str(row.get("date", "")) == target_date:
                    v2_obs = normalize_v2_observation_row(row, retrieved_time="live", observed_time="live")
                    break
            if v2_obs is not None:
                break
        result = reconcile_current_values(v1_observation=v1_obs, v2_observation=v2_obs)
        self.assertIsNotNone(result.series_id)
        self.assertEqual(result.series_id, "CPILFESL")
        if v2_obs is not None and v1_obs is not None:
            self.assertTrue(result.match, f"v1={result.v1_value} v2={result.v2_value}")

    def test_alfred_revision_proof(self) -> None:
        proof = alfred_revision_proof(self.v1)
        self.assertEqual(proof.get("status"), "observed", proof.get("error"))
        macro = proof.get("macro_as_of", {})
        t1 = macro.get("T1_initial_knowledge", macro.get("T1_initial_vintage", {}))
        today = macro.get("today", {})
        self.assertIsNotNone(t1.get("value"))
        self.assertIsNotNone(today.get("value"))
        if proof.get("initial", {}).get("value") != proof.get("current", {}).get("value"):
            self.assertNotEqual(t1.get("value"), today.get("value"))

    def test_capability_report_live(self) -> None:
        report = capability_report(live=True)
        self.assertEqual(report["source"], "fred_alfred")
        self.assertTrue(report["api_key_present"])
        self.assertEqual(report.get("classification"), "OBSERVED")
        health = report.get("health", {})
        self.assertTrue(health.get("V1_REACHABLE"))
        self.assertTrue(health.get("V2_REACHABLE"))
        self.assertEqual(report.get("alfred_revision_proof", {}).get("status"), "observed")
        out = ROOT / "evidence" / "fred" / "capability-report.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
