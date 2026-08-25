"""Baseline training hygiene tests (BUILD 08)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.baselines import (  # noqa: E402
    BaselineClassLabel,
    BaselineFeatureVector,
    BaselineTrainingError,
    BaselineTrainingExample,
    build_training_dataset,
)
from market_platform_foundation.intelligence.baselines.features import BaselineFeatureSchema  # noqa: E402
from tests.intelligence.test_baseline_fixtures import default_target  # noqa: E402


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


class BaselineTrainingTests(unittest.TestCase):
    def test_future_label_rejected(self) -> None:
        target = default_target()
        schema = BaselineFeatureSchema(selectors=())
        with self.assertRaises(BaselineTrainingError):
            build_training_dataset(
                raw_examples=[
                    _example(
                        snapshot_id="s1",
                        label=BaselineClassLabel.UP,
                        label_available_time_ns=200,
                    )
                ],
                feature_schema=schema,
                target=target,
                training_cutoff_ns=100,
            )

    def test_label_equality_boundary_allowed(self) -> None:
        target = default_target()
        schema = BaselineFeatureSchema(selectors=())
        dataset = build_training_dataset(
            raw_examples=[
                _example(
                    snapshot_id="s1",
                    label=BaselineClassLabel.UP,
                    label_available_time_ns=100,
                )
            ],
            feature_schema=schema,
            target=target,
            training_cutoff_ns=100,
        )
        self.assertEqual(len(dataset.examples), 1)

    def test_dataset_fingerprint_order_independent(self) -> None:
        target = default_target()
        schema = BaselineFeatureSchema(selectors=())
        examples = [
            _example(snapshot_id="s2", label=BaselineClassLabel.DOWN, label_available_time_ns=50),
            _example(snapshot_id="s1", label=BaselineClassLabel.UP, label_available_time_ns=40),
        ]
        first = build_training_dataset(
            raw_examples=list(examples),
            feature_schema=schema,
            target=target,
            training_cutoff_ns=100,
        )
        second = build_training_dataset(
            raw_examples=list(reversed(examples)),
            feature_schema=schema,
            target=target,
            training_cutoff_ns=100,
        )
        self.assertEqual(first.fingerprint, second.fingerprint)

    def test_conflicting_labels_rejected(self) -> None:
        target = default_target()
        schema = BaselineFeatureSchema(selectors=())
        with self.assertRaises(BaselineTrainingError):
            build_training_dataset(
                raw_examples=[
                    _example(snapshot_id="s1", label=BaselineClassLabel.UP, label_available_time_ns=50),
                    _example(snapshot_id="s1", label=BaselineClassLabel.DOWN, label_available_time_ns=50),
                ],
                feature_schema=schema,
                target=target,
                training_cutoff_ns=100,
            )


if __name__ == "__main__":
    unittest.main()
