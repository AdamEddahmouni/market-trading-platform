"""Acceptance: HOT_PATH_TELEMETRY_SOFTWARE_WIRED (fixture/software measured wiring)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from market_platform_foundation.canonical import canonical_bytes, sha256_bytes
from market_platform_foundation.hot_path_telemetry.exercise import validate_baseline_document
from market_platform_foundation.hot_path_telemetry.software_wired import build_software_wired_document, fixture_sha256

ARTIFACT_DIR = Path(__file__).resolve().parent
ACCEPTANCE_NAME = "HOT_PATH_TELEMETRY_SOFTWARE_WIRED"
ACCEPTANCE_PATH = ARTIFACT_DIR / "hot_path_telemetry_software_wired_acceptance.json"
BASELINE_PATH = ARTIFACT_DIR / "software_wired_hot_path.json"


class HotPathTelemetrySoftwareWiredAcceptanceTests(unittest.TestCase):
    def test_hot_path_telemetry_software_wired(self) -> None:
        document = build_software_wired_document()
        body = document.to_dict()
        validate_baseline_document(body)
        self.assertEqual(body["artifact_type"], "SOFTWARE_WIRED_HOT_PATH")
        self.assertEqual(body["metadata"]["acceptance"], ACCEPTANCE_NAME)
        self.assertGreater(body["timestamp_presence"]["router_dispatched_at"]["present_count"], 0)
        self.assertGreater(body["timestamp_presence"]["detected_at"]["present_count"], 0)

        baseline_bytes = canonical_bytes(body)
        baseline_sha = sha256_bytes(baseline_bytes).upper()
        acceptance = {
            "acceptance": ACCEPTANCE_NAME,
            "baseline_artifact": BASELINE_PATH.name,
            "baseline_sha256": baseline_sha,
            "fixture_sha256": fixture_sha256(
                Path(__file__).resolve().parents[1] / "fixtures" / "market_data" / "moomoo" / "captured-aapl.jsonl"
            ),
        }
        if ACCEPTANCE_PATH.exists():
            pinned = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
            self.assertEqual(pinned["acceptance"], ACCEPTANCE_NAME)
            if pinned.get("baseline_sha256"):
                self.assertEqual(pinned["baseline_sha256"], baseline_sha)


if __name__ == "__main__":
    unittest.main()
