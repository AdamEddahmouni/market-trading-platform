"""Acceptance: HOT_PATH_TELEMETRY_BASELINE_READY (fixture/replay measured baseline)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from market_platform_foundation.canonical import write_canonical_json
from market_platform_foundation.hot_path_telemetry.baseline import build_replay_latency_baseline, fixture_sha256
from market_platform_foundation.rt01.workloads import fixture_path

ACCEPTANCE_NAME = "HOT_PATH_TELEMETRY_BASELINE_READY"
ARTIFACT_DIR = Path(__file__).resolve().parent
BASELINE_PATH = ARTIFACT_DIR / "replay_latency_baseline.json"
ACCEPTANCE_PATH = ARTIFACT_DIR / "hot_path_telemetry_baseline_acceptance.json"


class HotPathTelemetryBaselineAcceptanceTests(unittest.TestCase):
    def test_hot_path_telemetry_baseline_ready(self) -> None:
        path = fixture_path()
        expected_hash = fixture_sha256(path)
        document = build_replay_latency_baseline()
        body = document.to_dict()
        self.assertEqual(body["artifact_type"], "REPLAY_LATENCY_BASELINE")
        self.assertEqual(body["measurement_class"], "MEASURED_FIXTURE_REPLAY")
        self.assertEqual(body["fixture_sha256"], expected_hash)
        self.assertNotEqual(body["rt01_span_count"], 0)
        self.assertIn("p50_ns", body["latency_segments_ns"]["imp_receive_to_normalized"])
        self.assertEqual(
            body["timestamp_exercise"]["opportunity_created_at"],
            "NOT_EXERCISED",
        )
        self.assertEqual(
            body["timestamp_exercise"]["operator_surfaced_at"],
            "NOT_EXERCISED",
        )

        write_canonical_json(BASELINE_PATH, body)
        acceptance = {
            "acceptance": ACCEPTANCE_NAME,
            "baseline_artifact": BASELINE_PATH.name,
            "baseline_sha256": fixture_sha256(BASELINE_PATH),
            "fixture_sha256": expected_hash,
        }
        write_canonical_json(ACCEPTANCE_PATH, acceptance)
        loaded = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(loaded["acceptance"], ACCEPTANCE_NAME)


if __name__ == "__main__":
    unittest.main()
