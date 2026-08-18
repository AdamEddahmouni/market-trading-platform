"""SS P3 baseline model and calibration tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.research.squeeze_models import (  # noqa: E402
    calibration_report,
    load_mechanism_dataset,
    predict_squeeze_probability,
    run_squeeze_walk_forward_harness,
)


class SqueezeP3ModelTests(unittest.TestCase):
    def test_mechanism_dataset_loads(self) -> None:
        rows = load_mechanism_dataset()
        self.assertGreaterEqual(len(rows), 3)

    def test_predict_squeeze_probability(self) -> None:
        pred = predict_squeeze_probability([0.8, 0.6, 0.4], horizon_days=5)
        self.assertIn("occurrence_probability", pred)
        self.assertIn("hazard_probability", pred)

    def test_walk_forward_harness(self) -> None:
        report = run_squeeze_walk_forward_harness()
        self.assertGreater(report["sample_count"], 0)
        self.assertIn("brier_score", report["calibration"])

    def test_calibration_report(self) -> None:
        preds = [0.9, 0.2, 0.7, 0.1]
        labels = [True, False, True, False]
        report = calibration_report(preds, labels)
        self.assertLess(report["brier_score"], 1.0)


if __name__ == "__main__":
    unittest.main()
