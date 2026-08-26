"""Evaluation orchestration service (BUILD 16)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..persistence.repository import IntelligenceRepository, RepositoryPutResult
from .calibration_diag import compute_calibration_diagnostics
from .cohort import materialize_cohort, predictive_rows, refine_diagnostic_states
from .comparison import compute_control_comparison, compute_probability_view_comparison
from .identity import derive_cohort_fingerprint, derive_evaluation_spec_id, derive_report_id
from .metrics import compute_predictive_metrics
from .report import (
    build_error_summary,
    build_settlement_diagnostics,
    evaluation_report_v1_from_dict,
    evaluation_report_v1_to_dict,
)
from .slices import compute_slices
from .types import EvaluationReportV1, EvaluationSpec, ProbabilityView

TRUE_PREDICTION_COVERAGE_UNAVAILABLE = "TRUE_PREDICTION_COVERAGE_UNAVAILABLE"


@dataclass
class EvaluationService:
    repository: IntelligenceRepository

    def evaluate(self, spec: EvaluationSpec, *, persist: bool = False) -> EvaluationReportV1:
        raw_rows = materialize_cohort(self.repository, spec)
        rows = refine_diagnostic_states(raw_rows, spec)
        spec_id = derive_evaluation_spec_id(spec)
        fingerprint = derive_cohort_fingerprint(rows, probability_view=spec.probability_view)
        report_id = derive_report_id(
            evaluation_spec_id=spec_id,
            cohort_fingerprint=fingerprint,
            implementation_version=spec.implementation_version,
        )

        predictive = predictive_rows(rows, spec)
        aggregate_metrics = compute_predictive_metrics(predictive, spec)
        calibration = compute_calibration_diagnostics(predictive, spec)
        settlement = build_settlement_diagnostics(
            rows,
            evaluation_as_of_ns=spec.evaluation_as_of_ns,
            true_prediction_coverage_status=TRUE_PREDICTION_COVERAGE_UNAVAILABLE,
        )
        error_summary = build_error_summary(rows, aggregate_metrics, spec)
        slice_results = compute_slices(predictive, spec)
        view_comparison = compute_probability_view_comparison(rows, spec)
        control_comparison = compute_control_comparison(rows, spec)

        limitations: list[str] = [
            TRUE_PREDICTION_COVERAGE_UNAVAILABLE,
            "REGIME_SLICE_UNSUPPORTED_WITHOUT_FROZEN_METADATA",
        ]

        report = EvaluationReportV1(
            report_id=report_id,
            evaluation_spec_id=spec_id,
            evaluation_as_of_ns=spec.evaluation_as_of_ns,
            cohort_fingerprint=fingerprint,
            probability_view=spec.probability_view,
            implementation_version=spec.implementation_version,
            settlement=settlement,
            aggregate_metrics=aggregate_metrics,
            calibration=calibration,
            probability_view_comparison=view_comparison,
            slice_results=slice_results,
            error_summary=error_summary,
            control_comparison=control_comparison,
            limitations=tuple(limitations),
            lineage={"evaluation_spec_id": spec_id},
            row_diagnostics=tuple(_row_diagnostic(row) for row in rows),
        )
        if persist and hasattr(self.repository, "put_evaluation_report"):
            self.repository.put_evaluation_report(report)
        return report

    def get_report(self, report_id: str) -> EvaluationReportV1 | None:
        if hasattr(self.repository, "get_evaluation_report"):
            return self.repository.get_evaluation_report(report_id)
        return None


def _row_diagnostic(row: Any) -> dict[str, Any]:
    return {
        "forecast_id": row.forecast.forecast_id,
        "ledger_entry_id": row.ledger_entry.ledger_entry_id,
        "outcome_id": row.outcome.outcome_id if row.outcome is not None else None,
        "diagnostic_state": row.diagnostic_state.value,
        "flags": sorted(row.flags),
        "label_available_time_ns": row.label_available_time_ns,
    }


__all__ = ["EvaluationService", "TRUE_PREDICTION_COVERAGE_UNAVAILABLE"]
