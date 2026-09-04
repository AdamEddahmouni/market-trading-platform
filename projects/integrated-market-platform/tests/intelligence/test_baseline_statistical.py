"""Statistical baseline tests (BUILD 08)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.baselines import (  # noqa: E402
    BaselineClassLabel,
    BaselineFeatureVector,
    BaselinePredictionContext,
    BaselineTrainingError,
    BaselineTrainingExample,
    EmpiricalPriorBaseline,
    GradientBoostingBaseline,
    LogisticRegressionBaseline,
    RegimeConditionedPriorBaseline,
    UnseenRegimePolicy,
    build_training_dataset,
)
from market_platform_foundation.intelligence.baselines.features import BaselineFeatureSchema  # noqa: E402
from market_platform_foundation.intelligence.contracts import TimeHorizonNs  # noqa: E402
from tests.intelligence.test_baseline_fixtures import (  # noqa: E402
    HORIZON_5M,
    T,
    default_target,
    sample_snapshot,
)


def _example(
    *,
    snapshot_id: str,
    label: BaselineClassLabel,
    label_available_time_ns: int,
    values: tuple[float, ...] = (1.0,),
    regime_key: str | None = None,
) -> BaselineTrainingExample:
    keys = tuple(f"f{i}" for i in range(len(values)))
    return BaselineTrainingExample(
        snapshot_id=snapshot_id,
        decision_time_ns=label_available_time_ns - 1,
        feature_vector=BaselineFeatureVector(values=values, source_signals=(), feature_keys=keys),
        label=label,
        label_available_time_ns=label_available_time_ns,
        regime_key=regime_key,
    )


class BaselineStatisticalTests(unittest.TestCase):
    def test_empirical_prior(self) -> None:
        target = default_target()
        schema = BaselineFeatureSchema(selectors=())
        dataset = build_training_dataset(
            raw_examples=[
                _example(snapshot_id="s1", label=BaselineClassLabel.UP, label_available_time_ns=T),
                _example(snapshot_id="s2", label=BaselineClassLabel.UP, label_available_time_ns=T),
                _example(snapshot_id="s3", label=BaselineClassLabel.UP, label_available_time_ns=T),
                _example(snapshot_id="s4", label=BaselineClassLabel.DOWN, label_available_time_ns=T),
            ],
            feature_schema=schema,
            target=target,
            training_cutoff_ns=T + 1000,
        )
        model = EmpiricalPriorBaseline()
        model.fit(dataset)
        context = BaselinePredictionContext(
            snapshot=sample_snapshot(),
            target=target,
            horizon=TimeHorizonNs(duration_ns=HORIZON_5M),
        )
        output = model.predict(
            BaselineFeatureVector(values=(), source_signals=(), feature_keys=()),
            context,
        )
        self.assertAlmostEqual(output.raw_probability_up, 0.75)

    def test_empirical_prior_empty_dataset_fails(self) -> None:
        target = default_target()
        schema = BaselineFeatureSchema(selectors=())
        with self.assertRaises(BaselineTrainingError):
            build_training_dataset(
                raw_examples=[],
                feature_schema=schema,
                target=target,
                training_cutoff_ns=T,
            )

    def test_logistic_single_class_fails(self) -> None:
        target = default_target()
        schema = BaselineFeatureSchema(selectors=())
        dataset = build_training_dataset(
            raw_examples=[
                _example(snapshot_id="s1", label=BaselineClassLabel.UP, label_available_time_ns=T),
                _example(snapshot_id="s2", label=BaselineClassLabel.UP, label_available_time_ns=T),
            ],
            feature_schema=schema,
            target=target,
            training_cutoff_ns=T + 1000,
        )
        model = LogisticRegressionBaseline(feature_schema=schema)
        with self.assertRaises(BaselineTrainingError):
            model.fit(dataset)

    def test_logistic_determinism(self) -> None:
        target = default_target()
        schema = BaselineFeatureSchema(selectors=())
        examples = []
        for index in range(8):
            label = BaselineClassLabel.UP if index % 2 == 0 else BaselineClassLabel.DOWN
            values = (float(index), float(index % 3))
            examples.append(
                _example(
                    snapshot_id=f"s{index}",
                    label=label,
                    label_available_time_ns=T,
                    values=values,
                )
            )
        dataset = build_training_dataset(
            raw_examples=examples,
            feature_schema=schema,
            target=target,
            training_cutoff_ns=T + 1000,
        )
        first = LogisticRegressionBaseline(feature_schema=schema)
        second = LogisticRegressionBaseline(feature_schema=schema)
        first.fit(dataset)
        second.fit(dataset)
        self.assertEqual(first.descriptor.model_id, second.descriptor.model_id)
        self.assertEqual(first.descriptor.parameter_fingerprint, second.descriptor.parameter_fingerprint)

    def test_regime_prior_and_unseen_fallback(self) -> None:
        target = default_target()
        schema = BaselineFeatureSchema(selectors=())
        dataset = build_training_dataset(
            raw_examples=[
                _example(
                    snapshot_id="r1",
                    label=BaselineClassLabel.UP,
                    label_available_time_ns=T,
                    regime_key="risk_on",
                ),
                _example(
                    snapshot_id="r2",
                    label=BaselineClassLabel.DOWN,
                    label_available_time_ns=T,
                    regime_key="risk_on",
                ),
                _example(
                    snapshot_id="r3",
                    label=BaselineClassLabel.UP,
                    label_available_time_ns=T,
                    regime_key="risk_off",
                ),
            ],
            feature_schema=schema,
            target=target,
            training_cutoff_ns=T + 1000,
        )
        model = RegimeConditionedPriorBaseline(unseen_regime_policy=UnseenRegimePolicy.GLOBAL_FALLBACK)
        model.fit(dataset)
        context = BaselinePredictionContext(
            snapshot=sample_snapshot(),
            target=target,
            horizon=TimeHorizonNs(duration_ns=HORIZON_5M),
            regime_key="unknown",
        )
        output = model.predict(
            BaselineFeatureVector(values=(), source_signals=(), feature_keys=()),
            context,
        )
        self.assertAlmostEqual(output.raw_probability_up, 2 / 3)

    def test_gbm_fit_summary(self) -> None:
        target = default_target()
        schema = BaselineFeatureSchema(selectors=())
        examples = []
        for index in range(10):
            label = BaselineClassLabel.UP if index < 5 else BaselineClassLabel.DOWN
            examples.append(
                _example(
                    snapshot_id=f"g{index}",
                    label=label,
                    label_available_time_ns=T,
                    values=(float(index), float(index % 4)),
                )
            )
        dataset = build_training_dataset(
            raw_examples=examples,
            feature_schema=schema,
            target=target,
            training_cutoff_ns=T + 1000,
        )
        model = GradientBoostingBaseline(feature_schema=schema)
        summary = model.fit(dataset)
        self.assertEqual(summary.example_count, 10)


if __name__ == "__main__":
    unittest.main()
