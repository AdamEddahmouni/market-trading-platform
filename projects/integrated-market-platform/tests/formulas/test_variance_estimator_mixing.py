"""Cross-module: population vs sample σ must stay labeled; unlabeled mix is forbidden."""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.physical_distribution import (  # noqa: E402
    physical_distribution_to_dict,
)
from market_platform_foundation.research.distribution import (  # noqa: E402
    VARIANCE_ESTIMATOR_POPULATION,
    VARIANCE_ESTIMATOR_SAMPLE,
    physical_distribution_forecast,
)
from market_platform_foundation.research.distribution.realized_vol import (  # noqa: E402
    realized_volatility_close_to_close,
)

FUSION_PATH = ROOT / "src" / "market_platform_foundation" / "cross_lane" / "fusion.py"
EXTRACTORS_PATH = ROOT / "src" / "market_platform_foundation" / "cross_lane" / "extractors.py"
INTERPRETATION_PATH = ROOT / "src" / "market_platform_foundation" / "strategy" / "interpretation.py"


def _forbid_unlabeled_mix(left: dict, right: dict) -> None:
    left_label = left.get("variance_estimator") or left.get("standard_deviation_policy")
    right_label = right.get("variance_estimator") or right.get("standard_deviation_policy")
    if not left_label or not right_label:
        raise ValueError("unlabeled variance mix is forbidden in fusion/strategy interpretation")
    if left_label != right_label:
        raise ValueError("incompatible variance estimators cannot be mixed as one sigma")


class VarianceEstimatorMixingTests(unittest.TestCase):
    def test_physical_p_stamps_sample_estimator(self) -> None:
        closes = [100.0 + i * 0.2 for i in range(40)]
        forecast = physical_distribution_forecast(
            closes, symbol="NVDA", as_of_time="2026-07-21T20:30:39.000000000Z"
        )
        self.assertIsNotNone(forecast)
        assert forecast is not None
        payload = physical_distribution_to_dict(forecast)
        self.assertEqual(payload["variance_estimator"], VARIANCE_ESTIMATOR_SAMPLE)
        self.assertEqual(forecast.variance_estimator, VARIANCE_ESTIMATOR_SAMPLE)
        rv = realized_volatility_close_to_close(closes)
        self.assertEqual(payload["realized_vol_close_to_close"], rv)

    def test_unlabeled_mix_is_rejected(self) -> None:
        squeeze_like = {"sigma": 0.4}  # population ADR σ without a label
        platform_like = {"sigma": 0.4, "variance_estimator": VARIANCE_ESTIMATOR_SAMPLE}
        with self.assertRaises(ValueError):
            _forbid_unlabeled_mix(squeeze_like, platform_like)

    def test_labeled_population_and_sample_cannot_be_treated_as_one_sigma(self) -> None:
        squeeze_like = {
            "sigma": 0.2,
            "standard_deviation_policy": "population_standard_deviation_decimal.v1",
            "variance_estimator": VARIANCE_ESTIMATOR_POPULATION,
        }
        platform_like = {"sigma": 0.2, "variance_estimator": VARIANCE_ESTIMATOR_SAMPLE}
        with self.assertRaises(ValueError):
            _forbid_unlabeled_mix(squeeze_like, platform_like)

    def test_fusion_and_strategy_do_not_combine_sigmas(self) -> None:
        fusion_src = FUSION_PATH.read_text(encoding="utf-8")
        extractors_src = EXTRACTORS_PATH.read_text(encoding="utf-8")
        interpretation_src = INTERPRETATION_PATH.read_text(encoding="utf-8")
        for source in (fusion_src, extractors_src, interpretation_src):
            tree = ast.parse(source)
            names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
            self.assertNotIn("realized_volatility_close_to_close", names)
            self.assertNotIn("population_standard_deviation", names)


if __name__ == "__main__":
    unittest.main()
