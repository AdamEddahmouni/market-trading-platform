"""PIT dataset-manifest wrap over BUILD 19 walk-forward (not a second engine)."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.validation import (
    ValidationEngine,
    ValidationError,
    ValidationExample,
    ValidationRunContext,
    WalkForwardMode,
    build_validation_dataset_manifest,
    build_validation_plan,
    derive_validation_report_id,
    generate_walk_forward_folds,
    require_clean_validation_dataset_manifest,
    statistical_candidate_profile,
    validation_dataset_manifest_v1_from_dict,
    validation_dataset_manifest_v1_to_dict,
)
from tests.intelligence.outcome_fixtures import HORIZON_5M, T
from tests.intelligence.test_validation_temporal_firewall import (
    _holdout_examples,
    _manifest_with_holdout,
    _trained_candidate,
)


def _in_window_example(*, decision_time_ns: int, example_id: str = "ex-in") -> ValidationExample:
    return ValidationExample(
        example_id=example_id,
        snapshot_id=f"snap-{example_id}",
        decision_time_ns=decision_time_ns,
        label_available_time_ns=decision_time_ns + HORIZON_5M,
        binary_label=1,
        candidate_probability=0.7,
        control_probability=0.6,
        forecast_id=f"fc-{example_id}",
        outcome_id=f"out-{example_id}",
    )


def _engine_report(*, fold_examples: dict[str, tuple[ValidationExample, ...]]):
    repo = InMemoryIntelligenceRepository()
    experiment = _manifest_with_holdout(T + 8)
    candidate, _dataset, artifact_bytes = _trained_candidate(repo, experiment)
    plan = build_validation_plan(
        experiment,
        (candidate,),
        control_ref="baseline_control",
        fold_boundaries_ns=(T, T + 4, T + 8),
        minimum_paired_sample=3,
    )
    report = ValidationEngine(repo).validate(
        ValidationRunContext(
            plan=plan,
            experiment=experiment,
            candidates=(candidate,),
            training_dataset=None,
            holdout_examples=_holdout_examples(candidate_better=True),
            fold_examples=fold_examples,
            knowledge_profiles={candidate.candidate_id: statistical_candidate_profile(candidate.candidate_id)},
            artifact_bytes_by_candidate={candidate.candidate_id: artifact_bytes},
            guardrail_thresholds={},
        ),
        persist=False,
    )
    return plan, report


class ValidationDatasetManifestTests(unittest.TestCase):
    def test_fingerprint_stable_and_cutoff_changes_dataset_id(self) -> None:
        manifest = _manifest_with_holdout(T + 8)
        candidate = type("C", (), {"candidate_id": "c1", "artifact_hash": "h1"})()
        plan = build_validation_plan(
            manifest,
            (candidate,),  # type: ignore[arg-type]
            control_ref="control",
            fold_boundaries_ns=(T, T + 4, T + 8),
        )
        example = _in_window_example(decision_time_ns=T)
        first = build_validation_dataset_manifest(
            plan,
            fold_or_holdout_ref="fold-1",
            examples=(example,),
            decision_start_ns=T,
            decision_end_ns=T + 4,
            training_cutoff_ns=T,
            training_start_ns=None,
        )
        second = build_validation_dataset_manifest(
            plan,
            fold_or_holdout_ref="fold-1",
            examples=(example,),
            decision_start_ns=T,
            decision_end_ns=T + 4,
            training_cutoff_ns=T,
            training_start_ns=None,
        )
        shifted_cutoff = build_validation_dataset_manifest(
            plan,
            fold_or_holdout_ref="fold-1",
            examples=(example,),
            decision_start_ns=T,
            decision_end_ns=T + 4,
            training_cutoff_ns=T - 1,
            training_start_ns=None,
        )
        self.assertEqual(first.dataset_fingerprint, second.dataset_fingerprint)
        self.assertEqual(first.validation_dataset_id, second.validation_dataset_id)
        self.assertEqual(first.dataset_fingerprint, shifted_cutoff.dataset_fingerprint)
        self.assertNotEqual(first.validation_dataset_id, shifted_cutoff.validation_dataset_id)
        self.assertEqual(first.metadata["source_kind"], "WALK_FORWARD_FOLD")
        self.assertEqual(first.metadata["replay_mode"], plan.mode)
        restored = validation_dataset_manifest_v1_from_dict(validation_dataset_manifest_v1_to_dict(first))
        self.assertEqual(first, restored)

    def test_ftep_campaign_binding_rejected(self) -> None:
        manifest = _manifest_with_holdout(T + 8)
        candidate = type("C", (), {"candidate_id": "c1", "artifact_hash": "h1"})()
        plan = build_validation_plan(
            manifest,
            (candidate,),  # type: ignore[arg-type]
            control_ref="control",
            fold_boundaries_ns=(T, T + 4, T + 8),
        )
        with self.assertRaises(ValidationError) as ctx:
            build_validation_dataset_manifest(
                plan,
                fold_or_holdout_ref="fold-1",
                examples=(),
                decision_start_ns=T,
                decision_end_ns=T + 4,
                extra_metadata={"campaign_slug": "FTEP-V1-002"},
            )
        self.assertEqual(ctx.exception.code, "FTEP_BINDING_FORBIDDEN")

    def test_window_mismatch_is_recorded_and_fail_closed_on_require(self) -> None:
        manifest = _manifest_with_holdout(T + 8)
        candidate = type("C", (), {"candidate_id": "c1", "artifact_hash": "h1"})()
        plan = build_validation_plan(
            manifest,
            (candidate,),  # type: ignore[arg-type]
            control_ref="control",
            fold_boundaries_ns=(T, T + 4, T + 8),
        )
        leaked = _in_window_example(decision_time_ns=T + 100, example_id="leak")
        wrapped = build_validation_dataset_manifest(
            plan,
            fold_or_holdout_ref="fold-1",
            examples=(leaked,),
            decision_start_ns=T,
            decision_end_ns=T + 4,
            training_cutoff_ns=T,
        )
        self.assertIn("VALIDATION_WINDOW_MISMATCH", wrapped.metadata["pit_violations"])
        with self.assertRaises(ValidationError) as ctx:
            require_clean_validation_dataset_manifest(wrapped)
        self.assertEqual(ctx.exception.code, "INVALID_TEMPORAL_LEAKAGE")

    def test_rolling_fold_records_training_start(self) -> None:
        manifest = _manifest_with_holdout(T + 8)
        candidate = type("C", (), {"candidate_id": "c1", "artifact_hash": "h1"})()
        plan = build_validation_plan(
            manifest,
            (candidate,),  # type: ignore[arg-type]
            control_ref="control",
            fold_boundaries_ns=(T, T + 4, T + 8),
            walk_forward_mode=WalkForwardMode.ROLLING,
            rolling_window_ns=5,
        )
        fold = generate_walk_forward_folds(plan.walk_forward_spec, purge_ns=plan.purge_ns)[0]
        wrapped = build_validation_dataset_manifest(
            plan,
            fold_or_holdout_ref=fold.fold_id,
            examples=(_in_window_example(decision_time_ns=T),),
            decision_start_ns=fold.validation_start_ns,
            decision_end_ns=fold.validation_end_ns,
            training_cutoff_ns=fold.training_cutoff_ns,
            training_start_ns=fold.training_start_ns,
        )
        self.assertEqual(wrapped.metadata["walk_forward_mode"], "ROLLING")
        self.assertEqual(wrapped.metadata["training_start_ns"], fold.training_start_ns)
        self.assertIsNone(
            require_clean_validation_dataset_manifest(wrapped)
        )

    def test_engine_emits_fold_and_holdout_wraps(self) -> None:
        repo = InMemoryIntelligenceRepository()
        experiment = _manifest_with_holdout(T + 8)
        candidate, _dataset, artifact_bytes = _trained_candidate(repo, experiment)
        plan = build_validation_plan(
            experiment,
            (candidate,),
            control_ref="baseline_control",
            fold_boundaries_ns=(T, T + 4, T + 8),
            minimum_paired_sample=3,
        )
        report = ValidationEngine(repo).validate(
            ValidationRunContext(
                plan=plan,
                experiment=experiment,
                candidates=(candidate,),
                training_dataset=None,
                holdout_examples=_holdout_examples(candidate_better=True),
                fold_examples={
                    "fold-1": (_in_window_example(decision_time_ns=T, example_id="f1"),),
                    "fold-2": (_in_window_example(decision_time_ns=T + 4, example_id="f2"),),
                },
                knowledge_profiles={candidate.candidate_id: statistical_candidate_profile(candidate.candidate_id)},
                artifact_bytes_by_candidate={candidate.candidate_id: artifact_bytes},
                guardrail_thresholds={},
            ),
            persist=False,
        )
        wraps = report.metadata["validation_dataset_manifests"]
        refs = [row["fold_or_holdout_ref"] for row in wraps]
        self.assertEqual(refs, ["fold-1", "fold-2", "holdout"])
        self.assertTrue(all(row["dataset_fingerprint"].startswith("VALDS-") for row in wraps))
        self.assertTrue(all(row["validation_dataset_id"].startswith("VALSET-") for row in wraps))
        self.assertEqual(wraps[0]["metadata"]["pit_violations"], [])
        self.assertIn("VALIDATION_WINDOW_MISMATCH", wraps[-1]["metadata"]["pit_violations"])

    def test_fold_membership_binds_validation_report_id(self) -> None:
        fold_a = {
            "fold-1": (_in_window_example(decision_time_ns=T, example_id="f1a"),),
            "fold-2": (_in_window_example(decision_time_ns=T + 4, example_id="f2"),),
        }
        fold_b = {
            "fold-1": (_in_window_example(decision_time_ns=T, example_id="f1b"),),
            "fold-2": fold_a["fold-2"],
        }
        plan, first = _engine_report(fold_examples=fold_a)
        _, same = _engine_report(fold_examples=fold_a)
        _, mutated = _engine_report(fold_examples=fold_b)
        wraps = first.metadata["validation_dataset_manifests"]
        self.assertEqual([row["fold_or_holdout_ref"] for row in wraps], ["fold-1", "fold-2", "holdout"])
        bound = derive_validation_report_id(
            validation_plan_id=first.validation_plan_id,
            candidate_artifact_hashes=first.candidate_artifact_hashes,
            control_ref=first.control_ref,
            holdout_commitment_id=first.holdout_commitment_id,
            validation_dataset_fingerprints=tuple(row["dataset_fingerprint"] for row in wraps),
            knowledge_assessment_status=first.knowledge_assessment_status.value,
            contamination_disposition=first.contamination_disposition.value,
            implementation_version=plan.implementation_version,
        )
        self.assertEqual(first.validation_report_id, bound)
        self.assertEqual(first.validation_report_id, same.validation_report_id)
        self.assertNotEqual(first.validation_report_id, mutated.validation_report_id)
        self.assertNotEqual(
            wraps[0]["dataset_fingerprint"],
            mutated.metadata["validation_dataset_manifests"][0]["dataset_fingerprint"],
        )
        self.assertEqual(
            wraps[1]["dataset_fingerprint"],
            mutated.metadata["validation_dataset_manifests"][1]["dataset_fingerprint"],
        )
        self.assertEqual(
            wraps[2]["dataset_fingerprint"],
            mutated.metadata["validation_dataset_manifests"][2]["dataset_fingerprint"],
        )


if __name__ == "__main__":
    unittest.main()
