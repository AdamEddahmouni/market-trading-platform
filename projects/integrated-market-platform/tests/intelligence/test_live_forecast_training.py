from __future__ import annotations

import json
import random
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.intelligence.production import live_training
from market_platform_foundation.intelligence.production.training_build import _examples_from_manifest

HORIZON_NS = 300_000_000_000
STEP_NS = 30_000_000_000
START_NS = 1_760_448_600_000_000_000  # a fixed session timestamp; nothing reads the wall clock


def examples(count, *, signal=True, seed=7, instrument="AAPL"):
    rng = random.Random(seed)
    rows = []
    for index in range(count):
        momentum = rng.uniform(-0.002, 0.002)
        nss = rng.uniform(-0.5, 0.5)
        if signal:
            label = 1 if momentum + rng.gauss(0, 0.0006) > 0 else 0
        else:
            label = rng.randint(0, 1)
        decision = START_NS + index * STEP_NS
        rows.append(dict(snapshot_id=f"snap-{instrument}-{index}", decision_time_ns=decision, label=label,
                         label_available_time_ns=decision + HORIZON_NS + 1_000_000_000, momentum=momentum, net_signed_share=nss))
    return _examples_from_manifest(dict(scope=dict(instrument_ids=[instrument]), examples=rows))


class SplitTests(unittest.TestCase):
    def test_each_split_starts_after_every_label_of_the_previous_one(self):
        split = live_training.time_ordered_split(examples(200))
        self.assertTrue(split.train and split.calibration and split.holdout)
        self.assertGreater(split.calibration[0].snapshot.decision_time_ns, max(e.label_available_time_ns for e in split.train))
        self.assertGreater(split.holdout[0].snapshot.decision_time_ns, max(e.label_available_time_ns for e in split.calibration))
        # A 5-minute horizon on a 30-second grid overlaps ten points: those are dropped, never shared.
        self.assertEqual(split.embargo_dropped, 20)
        self.assertEqual(len(split.train) + len(split.calibration) + len(split.holdout) + split.embargo_dropped, 200)

    def test_order_is_by_decision_time_not_input_order(self):
        rows = list(examples(100))
        split = live_training.time_ordered_split(reversed(rows))
        times = [e.snapshot.decision_time_ns for e in (*split.train, *split.calibration, *split.holdout)]
        self.assertEqual(times, sorted(times))


class EligibilityTests(unittest.TestCase):
    def test_the_rule_needs_holdout_size_and_skill_over_the_base_rate(self):
        self.assertEqual(live_training.eligibility(dict(samples=200, brier_skill=0.02)), (True, []))
        self.assertEqual(live_training.eligibility(dict(samples=200, brier_skill=0.0))[1], ["NO_HOLDOUT_SKILL_OVER_BASE_RATE"])
        self.assertEqual(live_training.eligibility(dict(samples=200, brier_skill=None))[1], ["NO_HOLDOUT_SKILL_OVER_BASE_RATE"])
        self.assertIn("HOLDOUT_TOO_SMALL", live_training.eligibility(dict(samples=10, brier_skill=0.5))[1])


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, rows, instrument="AAPL"):
        now = max(e.label_available_time_ns for e in rows) + 1
        return live_training.build_instrument(instrument, list(rows), output_dir=self.root, decision_time_ns=now)

    def test_a_learnable_corpus_builds_through_the_governed_path_and_is_scored_on_the_holdout(self):
        record = self.build(examples(600))
        self.assertEqual(record["status"], "BUILT", record)
        self.assertTrue(record["model_id"].startswith("PSMOD-"))
        self.assertTrue(record["calibration_model_id"])
        scores = record["holdout_scores"]
        self.assertEqual(scores["samples"], record["holdout"])
        self.assertGreater(scores["brier_skill"], 0)
        self.assertTrue(record["eligible"])
        self.assertTrue((self.root / "AAPL" / "evaluation.json").is_file())

    def test_the_holdout_never_enters_the_training_manifest(self):
        rows = examples(400)
        record = self.build(rows)
        manifest = json.loads((self.root / "AAPL" / "training-manifest.json").read_text(encoding="utf-8"))
        used = {row["snapshot_id"] for row in (*manifest["examples"], *manifest["calibration_examples"])}
        split = live_training.time_ordered_split(rows)
        self.assertFalse(used & {e.snapshot.snapshot_id for e in split.holdout})
        self.assertTrue(manifest["source"]["holdout_excluded"])
        self.assertEqual(manifest["corpus_evidence_authority"], "PROSPECTIVE_FEATURE_EVIDENCE")
        self.assertEqual(record["holdout"], len(split.holdout))

    def test_noise_is_not_made_eligible(self):
        record = self.build(examples(600, signal=False, seed=11))
        if record["status"] == "BUILT":
            self.assertEqual(record["eligible"], record["holdout_scores"]["brier_skill"] > 0 and record["holdout"] >= 60)
        else:
            self.assertFalse(record["eligible"])

    def test_too_little_corpus_is_refused_with_a_reason(self):
        record = self.build(examples(12))
        self.assertNotEqual(record["status"], "BUILT")
        self.assertFalse(record["eligible"])
        self.assertTrue(record["reason_codes"])

    def test_calibration_labels_must_already_be_available_at_build_time(self):
        rows = examples(300)
        record = live_training.build_instrument("AAPL", list(rows), output_dir=self.root, decision_time_ns=START_NS)
        self.assertEqual(record["reason_codes"], ["CALIBRATION_LABELS_NOT_YET_AVAILABLE"])


if __name__ == "__main__":
    unittest.main()
