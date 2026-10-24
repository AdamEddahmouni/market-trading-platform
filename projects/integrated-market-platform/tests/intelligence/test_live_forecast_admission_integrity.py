from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

from market_platform_foundation.intelligence.production import live_training
from market_platform_foundation.intelligence.production import training_build
from market_platform_foundation.strategy.path_a_live_forecast import live_strategy_definition
from market_platform_foundation.strategy.preregistration import build_preregistration
from market_platform_foundation.ui_api.paper_live_forecast import LiveForecastHook
from tests.intelligence.test_live_forecast_training import examples


class AdmissionIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory()
        cls.fixture_root = Path(cls.fixture.name)
        rows = examples(600)
        cls.built_at = max(e.label_available_time_ns for e in rows) + 1
        cls.record = live_training.build_instrument(
            "AAPL", rows, output_dir=cls.fixture_root / "PFB-test", decision_time_ns=cls.built_at)
        assert cls.record["status"] == "BUILT" and cls.record["eligible"], cls.record
        registered_at = datetime.fromtimestamp(cls.built_at / 1e9, UTC).isoformat()
        cls.preregistration = build_preregistration(live_strategy_definition(), registered_at=registered_at)

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        shutil.copytree(self.fixture_root / "PFB-test", self.root / "PFB-test")
        (self.root / "preregistration.json").write_text(json.dumps(self.preregistration), encoding="utf-8")
        (self.root / "ACTIVE.json").write_text(json.dumps(dict(
            schema_version="imp-live-forecast-active/1.0.0", build_id="PFB-test", instruments=["AAPL"],
            activated_at=datetime.fromtimestamp(self.built_at / 1e9, UTC).isoformat())), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def change_evaluation(self, change):
        path = self.root / "PFB-test" / "AAPL" / "evaluation.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        change(payload)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def assert_refused(self):
        hook = LiveForecastHook(self.root)
        self.assertEqual(hook.artifacts, {})
        self.assertIn("AAPL", hook.refused)

    def test_exact_scored_artifacts_are_admitted(self):
        self.assertEqual(sorted(LiveForecastHook(self.root).artifacts), ["AAPL"])

    def test_calibrator_identity_must_match_evaluation(self):
        self.change_evaluation(lambda p: p.update(calibration_model_id="CAL-unscored"))
        self.assert_refused()

    def test_calibrator_parameters_cannot_change_under_same_identity(self):
        [path] = (self.root / "PFB-test" / "AAPL" / "calibration").glob("*.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["parameters"]["intercept"] += 1.0
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.assert_refused()

    def test_model_parameters_cannot_change_under_same_identity(self):
        [path] = (self.root / "PFB-test" / "AAPL" / "model").glob("*.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["parameters"]["intercept"] += 1.0
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.assert_refused()

    def test_both_payload_hashes_are_required_and_verified(self):
        for key in ("model_payload_sha256", "calibration_payload_sha256"):
            original = dict(self.record["artifact_hashes"])
            for missing in (True, False):
                with self.subTest(key=key, missing=missing):
                    changed = dict(original)
                    if missing:
                        changed.pop(key)
                    else:
                        changed[key] = "0" * 64
                    self.change_evaluation(lambda p: p.update(artifact_hashes=changed))
                    self.assert_refused()

    def test_malformed_hash_manifest_is_refused(self):
        for hashes in (None, [], "untrusted"):
            with self.subTest(hashes=hashes):
                self.change_evaluation(lambda p: p.update(artifact_hashes=hashes))
                self.assert_refused()


class HoldoutIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.rows = examples(600)
        self.cutoff = max(e.label_available_time_ns for e in self.rows) + 1

    def tearDown(self):
        self.tmp.cleanup()

    def assert_blocked(self, rows, cutoff, reason):
        # Reaching holdout scoring at all is forbidden for these corpus rows.
        with mock.patch.object(live_training, "score_holdout", side_effect=AssertionError("unsafe holdout scored")):
            record = live_training.build_instrument("AAPL", rows, output_dir=self.root, decision_time_ns=cutoff)
        self.assertEqual(record["status"], "BLOCKED", record)
        self.assertFalse(record["eligible"])
        self.assertIn(reason, record["reason_codes"])
        self.assertFalse((self.root / "AAPL" / "evaluation.json").exists())

    def test_holdout_labels_at_or_after_build_cutoff_are_refused(self):
        for offset in (0, -1):
            with self.subTest(offset=offset):
                self.assert_blocked(self.rows, self.cutoff - 1 + offset, "HOLDOUT_LABELS_NOT_YET_AVAILABLE")

    def test_unknown_holdout_label_is_refused_before_scoring(self):
        for label in (None, -1, 2, "1", 0.5):
            with self.subTest(label=label):
                self.assert_blocked(self.rows[:-1] + [replace(self.rows[-1], label=label)], self.cutoff, "INVALID_LABEL")

    def test_unknown_holdout_availability_is_refused_before_scoring(self):
        for availability in (None, "unknown", 0.5):
            with self.subTest(availability=availability):
                rows = self.rows[:-1] + [replace(self.rows[-1], label_available_time_ns=availability)]
                self.assert_blocked(rows, self.cutoff, "LABEL_AVAILABILITY_UNKNOWN")

    def test_holdout_label_before_horizon_completion_is_refused(self):
        last = self.rows[-1]
        rows = self.rows[:-1] + [replace(last, label_available_time_ns=last.snapshot.decision_time_ns + 1)]
        self.assert_blocked(rows, self.cutoff, "LABEL_AVAILABLE_BEFORE_HORIZON_COMPLETION")

    def test_existing_calibration_cutoff_reason_is_preserved(self):
        self.assert_blocked(self.rows, self.rows[0].snapshot.decision_time_ns, "CALIBRATION_LABELS_NOT_YET_AVAILABLE")

    def test_rebuilt_calibrator_identity_is_verified_before_holdout_scoring(self):
        original = training_build.build_path_a_production_artifacts

        def changed(*args, **kwargs):
            return replace(original(*args, **kwargs), calibration_model_id="CAL-unscored")

        with mock.patch.object(training_build, "build_path_a_production_artifacts", side_effect=changed):
            self.assert_blocked(self.rows, self.cutoff, "REBUILT_ARTIFACT_IDENTITY_OR_HASH_MISMATCH")

    def test_rebuilt_payload_hashes_are_verified_before_holdout_scoring(self):
        original = training_build.build_path_a_production_artifacts

        def changed(*args, **kwargs):
            built = original(*args, **kwargs)
            return replace(built, artifact_hashes=dict(built.artifact_hashes, calibration_payload_sha256="0" * 64))

        with mock.patch.object(training_build, "build_path_a_production_artifacts", side_effect=changed):
            self.assert_blocked(self.rows, self.cutoff, "REBUILT_ARTIFACT_IDENTITY_OR_HASH_MISMATCH")


class ExclusionIntegrityTests(unittest.TestCase):
    def test_label_interval_crossing_bad_feed_is_removed_and_semantics_are_recorded(self):
        rows = examples(600)
        rule = dict(instrument_ids="ALL", decision_time_from="2025-10-14T13:40:00Z",
                    decision_time_to="2025-10-14T13:40:00Z", reason="FEED_LAG_DEGRADED_WINDOW")
        keyed = [(("AAPL", row.snapshot.decision_time_ns), row) for row in rows]
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(live_training, "load_training_examples", return_value=keyed):
            root = Path(tmp)
            corpus = root / "corpus.jsonl"
            corpus.write_text("", encoding="utf-8")
            summary = live_training.build_from_corpus(
                [corpus], output_root=root / "models", decision_time_ns=max(e.label_available_time_ns for e in rows) + 1,
                exclusions=[rule])
            # Decisions at 13:35:00 through 13:40:00 have label windows overlapping the bad instant.
            self.assertEqual(summary["excluded_examples"], {"FEED_LAG_DEGRADED_WINDOW": 11})
            self.assertEqual(summary["exclusion_semantics"], "DECISION_TO_LABEL_AVAILABILITY_INCLUSIVE")
            manifest = json.loads((root / "models" / summary["build_id"] / "AAPL" / "training-manifest.json").read_text())
            self.assertEqual(manifest["source"]["exclusion_semantics"], "DECISION_TO_LABEL_AVAILABILITY_INCLUSIVE")
            used = {e["snapshot_id"] for e in (*manifest["examples"], *manifest["calibration_examples"])}
            self.assertFalse(used & {f"snap-AAPL-{index}" for index in range(10, 21)})


if __name__ == "__main__":
    unittest.main()
