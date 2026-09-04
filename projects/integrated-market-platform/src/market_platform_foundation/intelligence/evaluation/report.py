"""Evaluation report assembly and serialization (BUILD 16)."""

from __future__ import annotations

from typing import Any

from .types import (
    CalibrationDiagnostics,
    ControlComparisonSummary,
    ErrorSummary,
    EvaluationReportV1,
    EvaluationSpec,
    PairedComparisonMetrics,
    PredictiveMetrics,
    ProbabilityViewComparison,
    ReliabilityBin,
    SettlementDiagnostics,
    SliceResult,
)


def build_settlement_diagnostics(
    rows: tuple[Any, ...],
    *,
    evaluation_as_of_ns: int,
    true_prediction_coverage_status: str,
) -> SettlementDiagnostics:
    from .types import EvaluationCohortRow, PredictionDiagnosticState

    registered = len(rows)
    outcome_available = 0
    labelable = 0
    unlabelable = 0
    not_settled = 0
    future_label = 0
    lags: list[tuple[str, int]] = []

    for row in rows:
        if not isinstance(row, EvaluationCohortRow):
            continue
        if row.outcome is None:
            not_settled += 1
            continue
        if row.label_available_time_ns is not None and row.label_available_time_ns > evaluation_as_of_ns:
            future_label += 1
            continue
        outcome_available += 1
        if row.diagnostic_state == PredictionDiagnosticState.UNLABELABLE:
            unlabelable += 1
        elif row.binary_label is not None:
            labelable += 1
        if row.outcome is not None and row.label_available_time_ns is not None:
            lag = row.outcome.adjudicated_at_ns - row.label_available_time_ns
            lags.append((row.forecast.forecast_id, lag))

    eligible = registered
    settlement_coverage = outcome_available / eligible if eligible else None
    labelable_fraction = labelable / outcome_available if outcome_available else None

    return SettlementDiagnostics(
        registered_count=registered,
        outcome_available_count=outcome_available,
        labelable_count=labelable,
        unlabelable_count=unlabelable,
        not_settled_count=not_settled,
        future_label_count=future_label,
        settlement_coverage=settlement_coverage,
        labelable_fraction=labelable_fraction,
        true_prediction_coverage_status=true_prediction_coverage_status,
        adjudication_lag_ns=tuple(sorted(lags, key=lambda item: item[0])),
    )


def build_error_summary(
    rows: tuple[Any, ...],
    metrics: PredictiveMetrics,
    spec: EvaluationSpec,
) -> ErrorSummary:
    from .types import EvaluationCohortRow, PredictionDiagnosticState

    correct = false_up = false_down = unlabelable = not_settled = high_conf_wrong = 0
    wrong_high_conf: list[tuple[str, float]] = []

    for row in rows:
        if not isinstance(row, EvaluationCohortRow):
            continue
        state = row.diagnostic_state
        if state == PredictionDiagnosticState.CORRECT:
            correct += 1
        elif state == PredictionDiagnosticState.FALSE_UP:
            false_up += 1
        elif state == PredictionDiagnosticState.FALSE_DOWN:
            false_down += 1
        elif state == PredictionDiagnosticState.UNLABELABLE:
            unlabelable += 1
        elif state == PredictionDiagnosticState.NOT_SETTLED:
            not_settled += 1
        if state in {PredictionDiagnosticState.FALSE_UP, PredictionDiagnosticState.FALSE_DOWN}:
            if "HIGH_CONFIDENCE" in row.flags:
                high_conf_wrong += 1
                from .provenance import probability_for_view

                p = probability_for_view(row.forecast, spec.probability_view)
                if p is not None:
                    wrong_high_conf.append((row.forecast.forecast_id, max(p, 1.0 - p)))

    return ErrorSummary(
        correct_count=correct,
        false_up_count=false_up,
        false_down_count=false_down,
        unlabelable_count=unlabelable,
        not_settled_count=not_settled,
        high_confidence_wrong_count=high_conf_wrong,
        largest_brier_contributions=metrics.per_row_brier[:10],
        largest_log_loss_contributions=metrics.per_row_log_loss[:10],
        highest_confidence_wrong=tuple(
            sorted(wrong_high_conf, key=lambda item: (-item[1], item[0]))[:10]
        ),
    )


def evaluation_report_v1_to_dict(report: EvaluationReportV1) -> dict[str, Any]:
    return {
        "report_id": report.report_id,
        "evaluation_spec_id": report.evaluation_spec_id,
        "evaluation_as_of_ns": report.evaluation_as_of_ns,
        "cohort_fingerprint": report.cohort_fingerprint,
        "probability_view": report.probability_view.value,
        "implementation_version": report.implementation_version,
        "settlement": _settlement_to_dict(report.settlement),
        "aggregate_metrics": _metrics_to_dict(report.aggregate_metrics),
        "calibration": _calibration_to_dict(report.calibration),
        "probability_view_comparison": _view_comparison_to_dict(report.probability_view_comparison),
        "slice_results": [_slice_to_dict(item) for item in report.slice_results],
        "error_summary": _error_summary_to_dict(report.error_summary),
        "control_comparison": _control_comparison_to_dict(report.control_comparison),
        "limitations": list(report.limitations),
        "lineage": dict(report.lineage),
        "row_diagnostics": list(report.row_diagnostics),
    }


def evaluation_report_v1_from_dict(payload: dict[str, Any]) -> EvaluationReportV1:
    from .types import ProbabilityView

    return EvaluationReportV1(
        report_id=str(payload["report_id"]),
        evaluation_spec_id=str(payload["evaluation_spec_id"]),
        evaluation_as_of_ns=int(payload["evaluation_as_of_ns"]),
        cohort_fingerprint=str(payload["cohort_fingerprint"]),
        probability_view=ProbabilityView(str(payload["probability_view"])),
        implementation_version=str(payload["implementation_version"]),
        settlement=_settlement_from_dict(payload["settlement"]),
        aggregate_metrics=_metrics_from_dict(payload["aggregate_metrics"]),
        calibration=_calibration_from_dict(payload.get("calibration")),
        probability_view_comparison=_view_comparison_from_dict(payload.get("probability_view_comparison")),
        slice_results=tuple(_slice_from_dict(item) for item in payload.get("slice_results") or []),
        error_summary=_error_summary_from_dict(payload.get("error_summary")),
        control_comparison=_control_comparison_from_dict(payload.get("control_comparison")),
        limitations=tuple(payload.get("limitations") or []),
        lineage=dict(payload.get("lineage") or {}),
        row_diagnostics=tuple(payload.get("row_diagnostics") or []),
    )


def _settlement_to_dict(item: SettlementDiagnostics) -> dict[str, Any]:
    return {
        "registered_count": item.registered_count,
        "outcome_available_count": item.outcome_available_count,
        "labelable_count": item.labelable_count,
        "unlabelable_count": item.unlabelable_count,
        "not_settled_count": item.not_settled_count,
        "future_label_count": item.future_label_count,
        "settlement_coverage": item.settlement_coverage,
        "labelable_fraction": item.labelable_fraction,
        "true_prediction_coverage_status": item.true_prediction_coverage_status,
        "adjudication_lag_ns": list(item.adjudication_lag_ns),
    }


def _settlement_from_dict(payload: dict[str, Any]) -> SettlementDiagnostics:
    return SettlementDiagnostics(
        registered_count=int(payload["registered_count"]),
        outcome_available_count=int(payload["outcome_available_count"]),
        labelable_count=int(payload["labelable_count"]),
        unlabelable_count=int(payload["unlabelable_count"]),
        not_settled_count=int(payload["not_settled_count"]),
        future_label_count=int(payload["future_label_count"]),
        settlement_coverage=payload.get("settlement_coverage"),
        labelable_fraction=payload.get("labelable_fraction"),
        true_prediction_coverage_status=str(payload["true_prediction_coverage_status"]),
        adjudication_lag_ns=tuple(tuple(item) for item in payload.get("adjudication_lag_ns") or []),
    )


def _metrics_to_dict(item: PredictiveMetrics) -> dict[str, Any]:
    return {
        "status": item.status.value,
        "sample_count": item.sample_count,
        "brier_score": item.brier_score,
        "log_loss": item.log_loss,
        "directional_hit_rate": item.directional_hit_rate,
        "mean_confidence": item.mean_confidence,
        "boundary_clip_count": item.boundary_clip_count,
        "per_row_brier": list(item.per_row_brier),
        "per_row_log_loss": list(item.per_row_log_loss),
    }


def _metrics_from_dict(payload: dict[str, Any]) -> PredictiveMetrics:
    from .types import AggregateStatus

    return PredictiveMetrics(
        status=AggregateStatus(str(payload["status"])),
        sample_count=int(payload["sample_count"]),
        brier_score=payload.get("brier_score"),
        log_loss=payload.get("log_loss"),
        directional_hit_rate=payload.get("directional_hit_rate"),
        mean_confidence=payload.get("mean_confidence"),
        boundary_clip_count=int(payload.get("boundary_clip_count") or 0),
        per_row_brier=tuple(tuple(item) for item in payload.get("per_row_brier") or []),
        per_row_log_loss=tuple(tuple(item) for item in payload.get("per_row_log_loss") or []),
    )


def _calibration_to_dict(item: CalibrationDiagnostics | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "bins": [_bin_to_dict(bin_item) for bin_item in item.bins],
        "ece": item.ece,
        "mce": item.mce,
        "brier_reliability": item.brier_reliability,
        "brier_resolution": item.brier_resolution,
        "brier_uncertainty": item.brier_uncertainty,
    }


def _calibration_from_dict(payload: dict[str, Any] | None) -> CalibrationDiagnostics | None:
    if payload is None:
        return None
    return CalibrationDiagnostics(
        bins=tuple(_bin_from_dict(item) for item in payload.get("bins") or []),
        ece=payload.get("ece"),
        mce=payload.get("mce"),
        brier_reliability=payload.get("brier_reliability"),
        brier_resolution=payload.get("brier_resolution"),
        brier_uncertainty=payload.get("brier_uncertainty"),
    )


def _bin_to_dict(item: ReliabilityBin) -> dict[str, Any]:
    return {
        "lower": item.lower,
        "upper": item.upper,
        "count": item.count,
        "mean_predicted_probability": item.mean_predicted_probability,
        "empirical_positive_rate": item.empirical_positive_rate,
        "calibration_gap": item.calibration_gap,
    }


def _bin_from_dict(payload: dict[str, Any]) -> ReliabilityBin:
    return ReliabilityBin(
        lower=float(payload["lower"]),
        upper=float(payload["upper"]),
        count=int(payload["count"]),
        mean_predicted_probability=payload.get("mean_predicted_probability"),
        empirical_positive_rate=payload.get("empirical_positive_rate"),
        calibration_gap=payload.get("calibration_gap"),
    )


def _slice_to_dict(item: SliceResult) -> dict[str, Any]:
    return {
        "dimension": item.dimension,
        "value": item.value,
        "status": item.status.value,
        "sample_count": item.sample_count,
        "metrics": _metrics_to_dict(item.metrics),
        "calibration": _calibration_to_dict(item.calibration),
    }


def _slice_from_dict(payload: dict[str, Any]) -> SliceResult:
    from .types import SliceStatus

    return SliceResult(
        dimension=str(payload["dimension"]),
        value=str(payload["value"]),
        status=SliceStatus(str(payload["status"])),
        sample_count=int(payload["sample_count"]),
        metrics=_metrics_from_dict(payload["metrics"]),
        calibration=_calibration_from_dict(payload.get("calibration")),
    )


def _error_summary_to_dict(item: ErrorSummary | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "correct_count": item.correct_count,
        "false_up_count": item.false_up_count,
        "false_down_count": item.false_down_count,
        "unlabelable_count": item.unlabelable_count,
        "not_settled_count": item.not_settled_count,
        "high_confidence_wrong_count": item.high_confidence_wrong_count,
        "largest_brier_contributions": list(item.largest_brier_contributions),
        "largest_log_loss_contributions": list(item.largest_log_loss_contributions),
        "highest_confidence_wrong": list(item.highest_confidence_wrong),
    }


def _error_summary_from_dict(payload: dict[str, Any] | None) -> ErrorSummary | None:
    if payload is None:
        return None
    return ErrorSummary(
        correct_count=int(payload["correct_count"]),
        false_up_count=int(payload["false_up_count"]),
        false_down_count=int(payload["false_down_count"]),
        unlabelable_count=int(payload["unlabelable_count"]),
        not_settled_count=int(payload["not_settled_count"]),
        high_confidence_wrong_count=int(payload["high_confidence_wrong_count"]),
        largest_brier_contributions=tuple(tuple(item) for item in payload.get("largest_brier_contributions") or []),
        largest_log_loss_contributions=tuple(
            tuple(item) for item in payload.get("largest_log_loss_contributions") or []
        ),
        highest_confidence_wrong=tuple(tuple(item) for item in payload.get("highest_confidence_wrong") or []),
    )


def _control_comparison_to_dict(item: ControlComparisonSummary | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "match_key_fields": list(item.match_key_fields),
        "matched_count": item.matched_count,
        "candidate_only_count": item.candidate_only_count,
        "control_only_count": item.control_only_count,
        "paired_metrics": [_paired_to_dict(row) for row in item.paired_metrics],
        "aggregate_brier_delta": item.aggregate_brier_delta,
        "aggregate_log_loss_delta": item.aggregate_log_loss_delta,
        "aggregate_hit_rate_delta": item.aggregate_hit_rate_delta,
    }


def _control_comparison_from_dict(payload: dict[str, Any] | None) -> ControlComparisonSummary | None:
    if payload is None:
        return None
    return ControlComparisonSummary(
        match_key_fields=tuple(payload.get("match_key_fields") or []),
        matched_count=int(payload["matched_count"]),
        candidate_only_count=int(payload["candidate_only_count"]),
        control_only_count=int(payload["control_only_count"]),
        paired_metrics=tuple(_paired_from_dict(item) for item in payload.get("paired_metrics") or []),
        aggregate_brier_delta=payload.get("aggregate_brier_delta"),
        aggregate_log_loss_delta=payload.get("aggregate_log_loss_delta"),
        aggregate_hit_rate_delta=payload.get("aggregate_hit_rate_delta"),
    )


def _paired_to_dict(item: PairedComparisonMetrics) -> dict[str, Any]:
    return {
        "candidate_forecast_id": item.candidate_forecast_id,
        "control_forecast_id": item.control_forecast_id,
        "candidate_brier": item.candidate_brier,
        "control_brier": item.control_brier,
        "brier_delta": item.brier_delta,
        "candidate_log_loss": item.candidate_log_loss,
        "control_log_loss": item.control_log_loss,
        "log_loss_delta": item.log_loss_delta,
        "candidate_hit_rate": item.candidate_hit_rate,
        "control_hit_rate": item.control_hit_rate,
        "hit_rate_delta": item.hit_rate_delta,
    }


def _paired_from_dict(payload: dict[str, Any]) -> PairedComparisonMetrics:
    return PairedComparisonMetrics(
        candidate_forecast_id=str(payload["candidate_forecast_id"]),
        control_forecast_id=str(payload["control_forecast_id"]),
        candidate_brier=payload.get("candidate_brier"),
        control_brier=payload.get("control_brier"),
        brier_delta=payload.get("brier_delta"),
        candidate_log_loss=payload.get("candidate_log_loss"),
        control_log_loss=payload.get("control_log_loss"),
        log_loss_delta=payload.get("log_loss_delta"),
        candidate_hit_rate=payload.get("candidate_hit_rate"),
        control_hit_rate=payload.get("control_hit_rate"),
        hit_rate_delta=payload.get("hit_rate_delta"),
    )


def _view_comparison_to_dict(item: ProbabilityViewComparison | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "matched_count": item.matched_count,
        "raw_brier": item.raw_brier,
        "calibrated_brier": item.calibrated_brier,
        "brier_delta": item.brier_delta,
        "raw_log_loss": item.raw_log_loss,
        "calibrated_log_loss": item.calibrated_log_loss,
        "log_loss_delta": item.log_loss_delta,
        "raw_ece": item.raw_ece,
        "calibrated_ece": item.calibrated_ece,
        "ece_delta": item.ece_delta,
    }


def _view_comparison_from_dict(payload: dict[str, Any] | None) -> ProbabilityViewComparison | None:
    if payload is None:
        return None
    return ProbabilityViewComparison(
        matched_count=int(payload["matched_count"]),
        raw_brier=payload.get("raw_brier"),
        calibrated_brier=payload.get("calibrated_brier"),
        brier_delta=payload.get("brier_delta"),
        raw_log_loss=payload.get("raw_log_loss"),
        calibrated_log_loss=payload.get("calibrated_log_loss"),
        log_loss_delta=payload.get("log_loss_delta"),
        raw_ece=payload.get("raw_ece"),
        calibrated_ece=payload.get("calibrated_ece"),
        ece_delta=payload.get("ece_delta"),
    )


__all__ = [
    "build_error_summary",
    "build_settlement_diagnostics",
    "evaluation_report_v1_from_dict",
    "evaluation_report_v1_to_dict",
]
