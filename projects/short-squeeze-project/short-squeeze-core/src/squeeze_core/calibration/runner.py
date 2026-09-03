"""Orchestrate calibration experiments and Phase 3C analysis."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from squeeze_core.analysis.models import (
    AnalysisCohortDefinition,
    AnalysisCohortType,
    AnalysisProvenanceClassification,
    AnalysisUnit,
    BoundarySelectionPolicy,
    ResearchAnalysisRequest,
)
from squeeze_core.analysis.runner import run_research_analysis
from squeeze_core.research.models import ResearchDataset, ResearchDatasetRow

from .detection_ablation import apply_detection_policy, detection_policy_from_spec
from .experiments import CalibrationExperimentError, load_experiment, load_source_dataset
from .models import (
    CalibrationExperiment,
    CalibrationExperimentType,
    CalibrationLimitation,
    CalibrationReport,
    CalibrationVariant,
    ClassificationFlip,
    VariantResult,
    fixture_classification_for_cohort,
)
from .outcome_sensitivity import apply_outcome_policy, outcome_policy_from_spec


CALIBRATION_LIMITATIONS = (
    CalibrationLimitation(
        code="COUNTERFACTUAL_EXPLORATION_ONLY",
        statement="Calibration results are counterfactual explorations, not predictive validation.",
    ),
    CalibrationLimitation(
        code="NO_THRESHOLD_AUTO_PROMOTION",
        statement="No variant in this report is authorized for automatic promotion to production policy.",
    ),
    CalibrationLimitation(
        code="SMALL_SAMPLE_WARNING",
        statement="Small labeled cohorts limit interpretability; intervals do not repair representativeness.",
    ),
    CalibrationLimitation(
        code="OUTCOME_BLIND_BOUNDARY_SELECTION",
        statement="Boundary selection reuses Phase 3C outcome-blind cohort policies.",
    ),
)


def _filter_cohort_rows(
    dataset: ResearchDataset,
    cohort_type: AnalysisCohortType,
) -> tuple[ResearchDatasetRow, ...]:
    target = fixture_classification_for_cohort(cohort_type)
    return tuple(row for row in dataset.rows if row.fixture_classification is target)


def _dataset_from_rows(
    rows: tuple[ResearchDatasetRow, ...],
    source: ResearchDataset,
) -> ResearchDataset:
    if not rows:
        raise CalibrationExperimentError("CALIBRATION_COHORT_EMPTY")
    provenance = source.provenance.model_copy(
        update={
            "case_ids": tuple(row.case_id for row in rows),
            "row_ids": tuple(row.row_id for row in rows),
            "source_fixture_ids": tuple(source for row in rows for source in row.source_ids),
        }
    )
    return ResearchDataset(
        dataset_version=source.dataset_version,
        rows=rows,
        provenance=provenance,
    )


def _apply_variant(
    rows: tuple[ResearchDatasetRow, ...],
    variant: CalibrationVariant,
    experiment_type: CalibrationExperimentType,
) -> tuple[ResearchDatasetRow, ...]:
    updated: list[ResearchDatasetRow] = []
    for row in rows:
        if experiment_type is CalibrationExperimentType.DETECTION_ABLATION:
            assert variant.detection_policy is not None
            policy = detection_policy_from_spec(variant.detection_policy)
            updated.append(apply_detection_policy(row, policy))
        else:
            assert variant.outcome_policy is not None
            policy = outcome_policy_from_spec(variant.outcome_policy)
            updated.append(apply_outcome_policy(row, policy))
    return tuple(updated)


def _analysis_request(
    experiment: CalibrationExperiment,
    dataset: ResearchDataset,
) -> ResearchAnalysisRequest:
    boundary_policy = (
        BoundarySelectionPolicy.EARLIEST_DETECTION_BOUNDARY_PER_SYMBOL
        if experiment.analysis_unit is AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY
        else BoundarySelectionPolicy.ALL_CASE_BOUNDARIES
    )
    provenance = (
        AnalysisProvenanceClassification.SANITIZED_PUBLIC_HISTORICAL_DATA
        if experiment.cohort_type is AnalysisCohortType.HISTORICAL_COMPLETED_CASES
        else AnalysisProvenanceClassification.SYNTHETIC_EDGE_CASE
    )
    definition = AnalysisCohortDefinition(
        cohort_type=experiment.cohort_type,
        analysis_unit=experiment.analysis_unit,
        boundary_selection_policy_version=boundary_policy,
        provenance_classifications=(provenance,),
        required_complete_cases=True,
    )
    return ResearchAnalysisRequest(
        source_dataset_id=str(dataset.deterministic_id),
        cohort_definition=definition,
        analysis_unit=experiment.analysis_unit,
        boundary_selection_policy_version=boundary_policy,
        confidence_level=Decimal("0.95"),
        included_statistics=(
            "CONFUSION_MATRIX",
            "DETECTION_PREVALENCE",
            "RESEARCH_CLASSIFICATION_PREVALENCE",
        ),
        excluded_statistics=("PREDICTIVE_VALIDATION", "THRESHOLD_OPTIMIZATION"),
    )


def _flips(
    baseline_rows: dict[str, ResearchDatasetRow],
    variant_rows: tuple[ResearchDatasetRow, ...],
) -> tuple[ClassificationFlip, ...]:
    flips: list[ClassificationFlip] = []
    for row in variant_rows:
        base = baseline_rows[row.case_id]
        if base.research_classification is row.research_classification:
            continue
        flips.append(
            ClassificationFlip(
                case_id=row.case_id,
                symbol=row.symbol,
                baseline=base.research_classification,
                variant=row.research_classification,
                baseline_detection=base.research_detection_status,
                variant_detection=row.research_detection_status,
                baseline_outcome=base.outcome_label,
                variant_outcome=row.outcome_label,
            )
        )
    return tuple(flips)


def run_calibration_experiment(
    experiment: CalibrationExperiment,
    *,
    source_rows: tuple[ResearchDatasetRow, ...] | None = None,
    source_dataset: ResearchDataset | None = None,
) -> CalibrationReport:
    if source_rows is None or source_dataset is None:
        raise CalibrationExperimentError("CALIBRATION_ROWS_REQUIRED")

    baseline_variant = next(
        variant for variant in experiment.variants if variant.variant_id == experiment.baseline_variant_id
    )
    baseline_rows_list = _apply_variant(source_rows, baseline_variant, experiment.experiment_type)
    baseline_by_id = {row.case_id: row for row in baseline_rows_list}

    variant_results: list[VariantResult] = []
    for variant in experiment.variants:
        variant_rows = _apply_variant(source_rows, variant, experiment.experiment_type)
        dataset = _dataset_from_rows(variant_rows, source_dataset)
        analysis = run_research_analysis(_analysis_request(experiment, dataset), dataset=dataset)
        flips = () if variant.variant_id == experiment.baseline_variant_id else _flips(
            baseline_by_id, variant_rows
        )
        variant_results.append(
            VariantResult(
                variant_id=variant.variant_id,
                description=variant.description,
                case_count=len(variant_rows),
                analysis=analysis,
                flips_from_baseline=flips,
            )
        )

    return CalibrationReport(
        experiment_version=experiment.experiment_version,
        experiment_type=experiment.experiment_type,
        cohort_type=experiment.cohort_type,
        analysis_unit=experiment.analysis_unit,
        source_dataset_path=experiment.source_dataset_path,
        baseline_variant_id=experiment.baseline_variant_id,
        variant_results=tuple(variant_results),
        limitations=CALIBRATION_LIMITATIONS,
    )


def run_calibration_from_path(experiment_path: Path) -> CalibrationReport:
    experiment = load_experiment(experiment_path)
    dataset = load_source_dataset(experiment, experiment_path)
    rows = _filter_cohort_rows(dataset, experiment.cohort_type)
    return run_calibration_experiment(
        experiment,
        source_rows=rows,
        source_dataset=dataset,
    )


__all__ = [
    "CALIBRATION_LIMITATIONS",
    "run_calibration_experiment",
    "run_calibration_from_path",
]
