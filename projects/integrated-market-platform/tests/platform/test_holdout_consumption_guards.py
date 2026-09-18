"""Holdout / protected corpus consumption guards across training surfaces."""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.baselines.controls.logistic import (  # noqa: E402
    LogisticRegressionBaseline,
)
from market_platform_foundation.intelligence.baselines.features import (  # noqa: E402
    DEFAULT_STATISTICAL_FEATURE_SCHEMA,
)
from market_platform_foundation.intelligence.baselines.training import (  # noqa: E402
    BaselineClassLabel,
    BaselineTrainingDataset,
    BaselineTrainingExample,
    build_training_dataset,
)
from market_platform_foundation.intelligence.baselines.types import BaselineFeatureVector  # noqa: E402
from market_platform_foundation.intelligence.contracts.common import (  # noqa: E402
    ForecastTarget,
    IntelligenceScope,
)
from market_platform_foundation.intelligence.fusion.calibrators import CalibrationTrainer  # noqa: E402
from market_platform_foundation.intelligence.fusion.policy import (  # noqa: E402
    DEFAULT_PRODUCTION_FUSION_POLICY,
)
from market_platform_foundation.intelligence.fusion.types import (  # noqa: E402
    CalibrationDataset,
    CalibrationExample,
    CalibrationMethod,
)
from market_platform_foundation.intelligence.production.calibrator import (  # noqa: E402
    train_production_calibration,
)
from market_platform_foundation.intelligence.production.identity import (  # noqa: E402
    path_a_direction_target,
    path_a_horizon,
)
from market_platform_foundation.intelligence.production.model import (  # noqa: E402
    fit_production_specialist,
)
from market_platform_foundation.intelligence.training.errors import TrainingFactoryError  # noqa: E402
from market_platform_foundation.intelligence.training.search import expand_candidate_specs  # noqa: E402
from market_platform_foundation.intelligence.training.types import TrainerKind  # noqa: E402
from market_platform_foundation.paper.calibration.dual_corpus.consumption import (  # noqa: E402
    CONSUMPTION_REFUSED_PROTECTED_CORPUS,
    ProtectedCorpusConsumptionError,
    TRAINING_OR_SELECTION_USE_REFUSED,
    assert_corpus_consumable_for_selection_or_training,
    assert_metadata_consumable_for_selection_or_training,
    is_protected_corpus_authority,
    protected_corpus_authorities_for_selection_training,
)
from market_platform_foundation.paper.calibration.dual_corpus.evidence_authority import (  # noqa: E402
    CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
    CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION,
)
from tests.intelligence.test_training_factory import _experiment_manifest  # noqa: E402


def _target() -> ForecastTarget:
    return ForecastTarget(
        target_kind="direction_up_down",
        instrument_id="AAPL",
        parameters={"positive_direction": "UP", "negative_direction": "DOWN"},
    )


def _training_examples() -> list[BaselineTrainingExample]:
    rows: list[BaselineTrainingExample] = []
    for idx, label in enumerate((BaselineClassLabel.UP, BaselineClassLabel.DOWN)):
        rows.append(
            BaselineTrainingExample(
                snapshot_id=f"snap-{idx}",
                decision_time_ns=idx + 1,
                feature_vector=BaselineFeatureVector(
                    feature_keys=("f0",),
                    values=(float(idx),),
                    source_signals=(),
                ),
                label=label,
                label_available_time_ns=idx + 2,
            )
        )
    return rows


class HoldoutConsumptionGuardTests(unittest.TestCase):
    def test_taxonomy_includes_untouched_forward_evaluation(self) -> None:
        self.assertTrue(
            is_protected_corpus_authority(CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION)
        )
        self.assertIn(
            CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION,
            protected_corpus_authorities_for_selection_training(),
        )

    def test_historical_development_not_protected_for_training_guard(self) -> None:
        assert_corpus_consumable_for_selection_or_training(
            corpus_evidence_authority=CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
            purpose="eval_allowed_fixture",
        )

    def test_protected_manifest_refused_with_refused_suffix(self) -> None:
        with self.assertRaises(ProtectedCorpusConsumptionError) as ctx:
            assert_corpus_consumable_for_selection_or_training(
                corpus_evidence_authority=CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION,
                purpose="unit_test",
            )
        self.assertIn(CONSUMPTION_REFUSED_PROTECTED_CORPUS, str(ctx.exception))
        self.assertIn(TRAINING_OR_SELECTION_USE_REFUSED, str(ctx.exception))

    def test_build_training_dataset_refuses_protected_authority(self) -> None:
        with self.assertRaises(ProtectedCorpusConsumptionError):
            build_training_dataset(
                raw_examples=_training_examples(),
                feature_schema=DEFAULT_STATISTICAL_FEATURE_SCHEMA,
                target=_target(),
                training_cutoff_ns=10,
                corpus_evidence_authority=CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION,
            )

    def test_baseline_logistic_fit_refuses_protected_dataset(self) -> None:
        dataset = BaselineTrainingDataset(
            examples=tuple(_training_examples()),
            feature_schema=DEFAULT_STATISTICAL_FEATURE_SCHEMA,
            target=_target(),
            training_cutoff_ns=10,
            corpus_evidence_authority=CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION,
        )
        with self.assertRaises(ProtectedCorpusConsumptionError):
            LogisticRegressionBaseline().fit(dataset)

    def test_fit_production_specialist_refuses_protected_corpus(self) -> None:
        with self.assertRaises(ProtectedCorpusConsumptionError):
            fit_production_specialist(
                [],
                target=path_a_direction_target("AAPL"),
                horizon=path_a_horizon(),
                training_cutoff_ns=10,
                corpus_evidence_authority=CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION,
            )

    def test_train_production_calibration_refuses_protected_corpus(self) -> None:
        target = path_a_direction_target("AAPL")
        horizon = path_a_horizon()
        policy = DEFAULT_PRODUCTION_FUSION_POLICY.policy_identity
        example = CalibrationExample(
            raw_fusion_id="r1",
            raw_probability=0.55,
            target=target,
            horizon=horizon,
            scope=IntelligenceScope(instrument_ids=("AAPL",), context_id="t"),
            forecast_decision_time_ns=1,
            label=1,
            label_available_time_ns=10,
            fusion_policy_identity=policy,
        )
        with self.assertRaises(ProtectedCorpusConsumptionError):
            train_production_calibration(
                [example],
                method=CalibrationMethod.LOGISTIC_PROBABILITY,
                available_time_ns=20,
                decision_time_ns=20,
                target=target,
                horizon=horizon,
                fusion_policy_identity=policy,
                calibration_cutoff_ns=10,
                mode="paper",
                corpus_evidence_authority=CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION,
            )

    def test_calibration_trainer_fit_refuses_protected_corpus(self) -> None:
        target = path_a_direction_target("AAPL")
        horizon = path_a_horizon()
        policy = DEFAULT_PRODUCTION_FUSION_POLICY.policy_identity
        dataset = CalibrationDataset(
            dataset_id="ds-1",
            examples=(),
            target=target,
            horizon=horizon,
            fusion_policy_identity=policy,
            calibration_cutoff_ns=10,
        )
        with self.assertRaises(ProtectedCorpusConsumptionError):
            CalibrationTrainer().fit(
                dataset,
                method=CalibrationMethod.LOGISTIC_PROBABILITY,
                available_time_ns=20,
                corpus_evidence_authority=CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION,
            )

    def test_hyperparameter_search_refuses_protected_experiment_metadata(self) -> None:
        manifest = _experiment_manifest()
        protected = replace(
            manifest,
            metadata={
                **manifest.metadata,
                "corpus_evidence_authority": CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION,
            },
        )
        with self.assertRaises(TrainingFactoryError) as ctx:
            expand_candidate_specs(
                protected,
                training_dataset_id="ds",
                dataset_fingerprint="fp",
                trainer_kind=TrainerKind.LOGISTIC_REGRESSION,
                trainer_version="1",
                target_kind=protected.data_spec.target_kind,
                horizon_ns=protected.data_spec.horizon_ns,
                mode=protected.data_spec.mode,
                base_hyperparameters={},
                authorized_mutation_surface=protected.allowed_changes or (protected.treatment.component,),
            )
        self.assertIn(CONSUMPTION_REFUSED_PROTECTED_CORPUS, str(ctx.exception))

    def test_metadata_guard_allows_empty_metadata(self) -> None:
        assert_metadata_consumable_for_selection_or_training(None, purpose="noop")
        assert_metadata_consumable_for_selection_or_training({}, purpose="noop")


if __name__ == "__main__":
    unittest.main()
