"""Validation engine orchestrator (BUILD 19)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from ..persistence.repository import IntelligenceRepository
from ..research_experiments.types import ExperimentManifestV1
from ..training.types import CandidateArtifactV1, TrainingDatasetManifestV1
from .artifacts import verify_candidate_ready_for_validation
from .contamination import ContaminationLedger, assess_holdout_contamination
from .embargo import verify_embargo_for_fold_sequence
from .errors import ValidationError
from .folds import generate_walk_forward_folds
from .holdout import ValidationDataAccessGuard, verify_plan_matches_commitment
from .identity import derive_validation_dataset_fingerprint, derive_validation_report_id
from .metrics import aggregate_metric_values, compute_example_primary_metric, evaluate_guardrails
from .planning import build_validation_plan
from .purge import verify_training_purge_for_fold
from .statistics import evaluate_statistical_criteria, moving_block_bootstrap_ci, paired_metric_deltas
from .temporal_knowledge import (
    aggregate_assessment_status,
    assess_knowledge_cutoff,
    require_historical_inference_allowed,
    statistical_candidate_profile,
)
from .types import (
    ContaminationDisposition,
    FoldMetricResult,
    HoldoutMetricResult,
    KnowledgeAssessmentStatus,
    KnowledgeProfileV1,
    ValidationDisposition,
    ValidationExample,
    ValidationPlanV1,
    ValidationReportV1,
)


@dataclass(frozen=True, slots=True)
class ValidationRunContext:
    plan: ValidationPlanV1
    experiment: ExperimentManifestV1
    candidates: tuple[CandidateArtifactV1, ...]
    training_dataset: TrainingDatasetManifestV1 | None
    holdout_examples: tuple[ValidationExample, ...]
    fold_examples: dict[str, tuple[ValidationExample, ...]]
    knowledge_profiles: dict[str, KnowledgeProfileV1]
    artifact_bytes_by_candidate: dict[str, bytes]
    guardrail_thresholds: dict[str, float]
    prior_holdout_access: bool = False
    provenance_complete: bool = True


class ValidationEngine:
    """Independent validation authority — validates frozen candidates only."""

    def __init__(
        self,
        repository: IntelligenceRepository,
        *,
        artifact_base_dir: Path | None = None,
    ) -> None:
        self.repository = repository
        self.artifact_base_dir = artifact_base_dir or Path("artifacts/intelligence")
        self._access_guard = ValidationDataAccessGuard(repository)

    @property
    def access_guard(self) -> ValidationDataAccessGuard:
        return self._access_guard

    def build_plan(
        self,
        experiment: ExperimentManifestV1,
        candidates: tuple[CandidateArtifactV1, ...],
        **kwargs: Any,
    ) -> ValidationPlanV1:
        return build_validation_plan(experiment, candidates, **kwargs)

    def verify_candidates(
        self,
        candidates: tuple[CandidateArtifactV1, ...],
        *,
        artifact_bytes_by_candidate: dict[str, bytes] | None = None,
    ) -> dict[str, bytes]:
        resolved: dict[str, bytes] = {}
        artifact_bytes_by_candidate = artifact_bytes_by_candidate or {}
        for candidate in candidates:
            content = verify_candidate_ready_for_validation(
                self.repository,
                candidate,
                artifact_bytes=artifact_bytes_by_candidate.get(candidate.candidate_id),
                artifact_base_dir=self.artifact_base_dir,
            )
            resolved[candidate.candidate_id] = content
        return resolved

    def validate(self, context: ValidationRunContext, *, persist: bool = True) -> ValidationReportV1:
        plan = context.plan
        commitment = self._access_guard.commit_holdout(plan)
        contamination_ledger = assess_holdout_contamination(
            footprint=context.experiment.knowledge_footprint,
            training_dataset=context.training_dataset,
            holdout=plan.holdout_spec,
            validation_plan_id=plan.validation_plan_id,
            experiment_id=plan.experiment_id,
            prior_holdout_access=context.prior_holdout_access,
            provenance_complete=context.provenance_complete,
        )

        knowledge_assessments = []
        knowledge_blocked = False
        for candidate in context.candidates:
            profile = context.knowledge_profiles.get(
                candidate.candidate_id,
                statistical_candidate_profile(candidate.candidate_id),
            )
            for example in context.holdout_examples:
                if profile.is_llm:
                    try:
                        require_historical_inference_allowed(
                            profile, example.decision_time_ns, plan.temporal_knowledge_policy
                        )
                    except ValidationError:
                        knowledge_blocked = True
                knowledge_assessments.append(
                    assess_knowledge_cutoff(profile, example.decision_time_ns, plan.temporal_knowledge_policy)
                )
        knowledge_status = aggregate_assessment_status(tuple(knowledge_assessments))
        if knowledge_blocked:
            knowledge_status = KnowledgeAssessmentStatus.FAIL_KNOWLEDGE_CUTOFF

        fold_results: list[FoldMetricResult] = []
        if plan.walk_forward_spec is not None:
            folds = generate_walk_forward_folds(plan.walk_forward_spec, purge_ns=plan.purge_ns)
            datasets_by_fold: dict[str, TrainingDatasetManifestV1] = {}
            if context.training_dataset is not None:
                for fold in folds:
                    datasets_by_fold[fold.fold_id] = context.training_dataset

            embargo_clean, _ = verify_embargo_for_fold_sequence(
                datasets_by_fold, folds, embargo_ns=plan.embargo_ns
            )

            for fold in folds:
                fold_disposition = ValidationDisposition.INCONCLUSIVE
                contamination = ContaminationDisposition.CLEAN
                if fold.candidate_id is None:
                    fold_disposition = ValidationDisposition.MISSING_FOLD_CANDIDATE
                elif context.training_dataset is not None:
                    purge_clean, _ = verify_training_purge_for_fold(
                        context.training_dataset,
                        fold,
                        purge_ns=plan.purge_ns,
                    )
                    if not purge_clean:
                        fold_disposition = ValidationDisposition.INVALID_TEMPORAL_LEAKAGE
                        contamination = ContaminationDisposition.CONTAMINATED
                    elif not embargo_clean:
                        fold_disposition = ValidationDisposition.INVALID_TEMPORAL_LEAKAGE
                        contamination = ContaminationDisposition.CONTAMINATED

                examples = context.fold_examples.get(fold.fold_id, ())
                candidate_id = fold.candidate_id or context.candidates[0].candidate_id
                candidate_values = tuple(
                    compute_example_primary_metric(
                        ex, primary_metric=plan.primary_metric, for_candidate=True
                    )
                    for ex in examples
                )
                control_values = tuple(
                    compute_example_primary_metric(
                        ex, primary_metric=plan.primary_metric, for_candidate=False
                    )
                    for ex in examples
                )
                candidate_metric = aggregate_metric_values(candidate_values)
                control_metric = aggregate_metric_values(control_values)
                delta = (
                    candidate_metric - control_metric
                    if candidate_metric is not None and control_metric is not None
                    else None
                )
                fold_results.append(
                    FoldMetricResult(
                        fold_id=fold.fold_id,
                        candidate_id=candidate_id,
                        control_ref=plan.control_ref,
                        matched_count=len(examples),
                        candidate_primary_metric=candidate_metric,
                        control_primary_metric=control_metric,
                        primary_delta=delta,
                        guardrail_results=evaluate_guardrails(
                            examples,
                            plan.guardrail_metrics,
                            thresholds=context.guardrail_thresholds,
                        ),
                        knowledge_assessment_status=knowledge_status,
                        contamination_disposition=contamination,
                        disposition=fold_disposition,
                    )
                )

        self._access_guard.unlock_holdout(
            unlocked_at_ns=plan.holdout_spec.holdout_end_ns,
            context="canonical_validation_run",
        )

        holdout_results: list[HoldoutMetricResult] = []
        dataset_fingerprints: list[str] = []
        for candidate in context.candidates:
            examples = context.holdout_examples
            candidate_values = tuple(
                compute_example_primary_metric(
                    ex, primary_metric=plan.primary_metric, for_candidate=True
                )
                for ex in examples
            )
            control_values = tuple(
                compute_example_primary_metric(
                    ex, primary_metric=plan.primary_metric, for_candidate=False
                )
                for ex in examples
            )
            candidate_metric = aggregate_metric_values(candidate_values)
            control_metric = aggregate_metric_values(control_values)
            delta = (
                candidate_metric - control_metric
                if candidate_metric is not None and control_metric is not None
                else None
            )
            paired = None
            stat_disposition = ValidationDisposition.INCONCLUSIVE
            if len(candidate_values) == len(control_values) and candidate_values:
                deltas = paired_metric_deltas(candidate_values, control_values)
                paired = moving_block_bootstrap_ci(deltas, plan.statistical_plan)
                stat_outcome = evaluate_statistical_criteria(paired, plan.statistical_plan)
                if stat_outcome == "MEETS_PRE_REGISTERED_CRITERIA":
                    stat_disposition = ValidationDisposition.MEETS_PRE_REGISTERED_CRITERIA
                elif stat_outcome == "DOES_NOT_MEET_PRE_REGISTERED_CRITERIA":
                    stat_disposition = ValidationDisposition.DOES_NOT_MEET_PRE_REGISTERED_CRITERIA
                elif stat_outcome == "INCONCLUSIVE_INSUFFICIENT_SAMPLE":
                    stat_disposition = ValidationDisposition.INCONCLUSIVE_INSUFFICIENT_SAMPLE

            contamination_disp = contamination_ledger.disposition
            holdout_disposition = stat_disposition
            if contamination_disp == ContaminationDisposition.CONTAMINATED:
                holdout_disposition = ValidationDisposition.INVALID_CONTAMINATED
            elif contamination_disp == ContaminationDisposition.UNKNOWN:
                holdout_disposition = ValidationDisposition.INCONCLUSIVE
            elif knowledge_status in {
                KnowledgeAssessmentStatus.FAIL_KNOWLEDGE_CUTOFF,
                KnowledgeAssessmentStatus.BLOCKED_UNKNOWN_KNOWLEDGE_CUTOFF,
                KnowledgeAssessmentStatus.FAIL_TOOL_POLICY,
                KnowledgeAssessmentStatus.FAIL_RETRIEVAL_TIME,
            }:
                holdout_disposition = ValidationDisposition.INVALID_KNOWLEDGE_FIREWALL

            guardrail_results = evaluate_guardrails(
                examples,
                plan.guardrail_metrics,
                thresholds=context.guardrail_thresholds,
            )
            if plan.guardrail_metrics and any(v is False for v in guardrail_results.values()):
                if holdout_disposition == ValidationDisposition.MEETS_PRE_REGISTERED_CRITERIA:
                    holdout_disposition = ValidationDisposition.DOES_NOT_MEET_PRE_REGISTERED_CRITERIA

            forecast_ids = tuple(ex.forecast_id for ex in examples if ex.forecast_id)
            outcome_ids = tuple(ex.outcome_id for ex in examples if ex.outcome_id)
            fingerprint = derive_validation_dataset_fingerprint(
                validation_plan_id=plan.validation_plan_id,
                fold_or_holdout_ref="holdout",
                forecast_ids=forecast_ids,
                outcome_ids=outcome_ids,
                decision_start_ns=plan.holdout_spec.holdout_start_ns,
                decision_end_ns=plan.holdout_spec.holdout_end_ns,
            )
            dataset_fingerprints.append(fingerprint)

            holdout_results.append(
                HoldoutMetricResult(
                    candidate_id=candidate.candidate_id,
                    control_ref=plan.control_ref,
                    matched_count=len(examples),
                    candidate_metrics={plan.primary_metric: candidate_metric},
                    control_metrics={plan.primary_metric: control_metric},
                    primary_delta=delta,
                    paired_delta=paired,
                    guardrail_results=guardrail_results,
                    knowledge_assessment_status=knowledge_status,
                    contamination_disposition=contamination_disp,
                    disposition=holdout_disposition,
                )
            )

        final_disposition = holdout_results[0].disposition if holdout_results else ValidationDisposition.INCONCLUSIVE
        report_id = derive_validation_report_id(
            validation_plan_id=plan.validation_plan_id,
            candidate_artifact_hashes=plan.candidate_artifact_hashes,
            control_ref=plan.control_ref,
            holdout_commitment_id=commitment.holdout_commitment_id,
            validation_dataset_fingerprints=tuple(dataset_fingerprints),
            knowledge_assessment_status=knowledge_status.value,
            contamination_disposition=contamination_ledger.disposition.value,
            implementation_version=plan.implementation_version,
        )
        report = ValidationReportV1(
            validation_report_id=report_id,
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            validation_plan_id=plan.validation_plan_id,
            experiment_id=plan.experiment_id,
            candidate_ids=plan.candidate_ids,
            candidate_artifact_hashes=plan.candidate_artifact_hashes,
            control_ref=plan.control_ref,
            holdout_commitment_id=commitment.holdout_commitment_id,
            fold_results=tuple(fold_results),
            holdout_results=tuple(holdout_results),
            contamination_disposition=contamination_ledger.disposition,
            contamination_record_ids=tuple(r.contamination_record_id for r in contamination_ledger.records),
            knowledge_assessment_status=knowledge_status,
            candidate_family_size=len(context.candidates),
            final_disposition=final_disposition,
        )

        if persist:
            if hasattr(self.repository, "put_validation_plan"):
                self.repository.put_validation_plan(plan)
            if hasattr(self.repository, "put_validation_report"):
                self.repository.put_validation_report(report)
            for record in contamination_ledger.records:
                if hasattr(self.repository, "put_contamination_record"):
                    self.repository.put_contamination_record(record)

        return report

    def detect_plan_deviation(
        self,
        plan: ValidationPlanV1,
        *,
        candidate: CandidateArtifactV1,
        commitment=None,
    ) -> None:
        if candidate.candidate_id not in plan.candidate_ids:
            raise ValidationError("PLAN_DEVIATION_CANDIDATE")
        expected_hash = dict(zip(plan.candidate_ids, plan.candidate_artifact_hashes, strict=True)).get(
            candidate.candidate_id
        )
        if expected_hash != candidate.artifact_hash:
            raise ValidationError("PLAN_DEVIATION_ARTIFACT_HASH")
        if commitment is not None:
            verify_plan_matches_commitment(plan, commitment)


__all__ = ["ValidationEngine", "ValidationRunContext"]
