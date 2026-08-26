"""Matched candidate/control comparison (BUILD 16)."""

from __future__ import annotations

from ..fusion.types import ForecastContributorRole
from .cohort import predictive_rows
from .metrics import compute_predictive_metrics
from .provenance import probability_for_view
from .types import (
    ControlComparisonSummary,
    EvaluationCohortRow,
    EvaluationSpec,
    PairedComparisonMetrics,
    PredictionDiagnosticState,
    ProbabilityView,
    ProbabilityViewComparison,
    forecast_role,
    instrument_id_for_forecast,
)


MATCH_KEY_FIELDS = (
    "snapshot_id",
    "instrument_id",
    "target_kind",
    "horizon_ns",
    "mode",
    "scenario_id",
)


def match_key(row: EvaluationCohortRow) -> tuple[str, ...]:
    instrument = instrument_id_for_forecast(row.forecast) or ""
    return (
        row.forecast.snapshot_id,
        instrument,
        row.forecast.target.target_kind,
        str(row.forecast.horizon.duration_ns),
        row.ledger_entry.mode,
        row.ledger_entry.scenario_id or "",
    )


def is_control_row(row: EvaluationCohortRow) -> bool:
    return forecast_role(row.forecast) == ForecastContributorRole.CONTROL.value


def compute_control_comparison(
    rows: tuple[EvaluationCohortRow, ...],
    spec: EvaluationSpec,
) -> ControlComparisonSummary | None:
    labelable = tuple(
        row
        for row in rows
        if row.binary_label is not None
        and row.diagnostic_state not in {
            PredictionDiagnosticState.FUTURE_LABEL,
            PredictionDiagnosticState.NOT_SETTLED,
            PredictionDiagnosticState.UNLABELABLE,
        }
    )
    if not labelable:
        return None

    candidates: dict[tuple[str, ...], EvaluationCohortRow] = {}
    controls: dict[tuple[str, ...], EvaluationCohortRow] = {}
    for row in labelable:
        key = match_key(row)
        if is_control_row(row):
            controls[key] = row
        else:
            candidates[key] = row

    matched_keys = sorted(set(candidates) & set(controls))
    candidate_only = len(set(candidates) - set(controls))
    control_only = len(set(controls) - set(candidates))

    paired: list[PairedComparisonMetrics] = []
    for key in matched_keys:
        candidate = candidates[key]
        control = controls[key]
        candidate_metrics = compute_predictive_metrics((candidate,), spec)
        control_metrics = compute_predictive_metrics((control,), spec)
        paired.append(
            PairedComparisonMetrics(
                candidate_forecast_id=candidate.forecast.forecast_id,
                control_forecast_id=control.forecast.forecast_id,
                candidate_brier=candidate_metrics.brier_score,
                control_brier=control_metrics.brier_score,
                brier_delta=_delta(candidate_metrics.brier_score, control_metrics.brier_score),
                candidate_log_loss=candidate_metrics.log_loss,
                control_log_loss=control_metrics.log_loss,
                log_loss_delta=_delta(candidate_metrics.log_loss, control_metrics.log_loss),
                candidate_hit_rate=candidate_metrics.directional_hit_rate,
                control_hit_rate=control_metrics.directional_hit_rate,
                hit_rate_delta=_delta(
                    candidate_metrics.directional_hit_rate,
                    control_metrics.directional_hit_rate,
                ),
            )
        )

    return ControlComparisonSummary(
        match_key_fields=MATCH_KEY_FIELDS,
        matched_count=len(matched_keys),
        candidate_only_count=candidate_only,
        control_only_count=control_only,
        paired_metrics=tuple(paired),
        aggregate_brier_delta=_mean_delta([item.brier_delta for item in paired]),
        aggregate_log_loss_delta=_mean_delta([item.log_loss_delta for item in paired]),
        aggregate_hit_rate_delta=_mean_delta([item.hit_rate_delta for item in paired]),
    )


def compute_probability_view_comparison(
    rows: tuple[EvaluationCohortRow, ...],
    spec: EvaluationSpec,
) -> ProbabilityViewComparison | None:
    from .calibration_diag import compute_calibration_diagnostics

    predictive = predictive_rows(rows, spec)
    if not predictive:
        return None

    raw_spec = _with_view(spec, ProbabilityView.RAW)
    calibrated_spec = _with_view(spec, ProbabilityView.CALIBRATED)
    raw_metrics = compute_predictive_metrics(predictive, raw_spec)
    calibrated_rows = tuple(
        row for row in predictive if row.probability_calibrated is not None
    )
    if not calibrated_rows:
        return ProbabilityViewComparison(
            matched_count=len(predictive),
            raw_brier=raw_metrics.brier_score,
            calibrated_brier=None,
            brier_delta=None,
            raw_log_loss=raw_metrics.log_loss,
            calibrated_log_loss=None,
            log_loss_delta=None,
            raw_ece=compute_calibration_diagnostics(predictive, raw_spec).ece
            if compute_calibration_diagnostics(predictive, raw_spec)
            else None,
            calibrated_ece=None,
            ece_delta=None,
        )

    calibrated_metrics = compute_predictive_metrics(calibrated_rows, calibrated_spec)
    raw_cal = compute_calibration_diagnostics(predictive, raw_spec)
    cal_cal = compute_calibration_diagnostics(calibrated_rows, calibrated_spec)
    return ProbabilityViewComparison(
        matched_count=len(calibrated_rows),
        raw_brier=raw_metrics.brier_score,
        calibrated_brier=calibrated_metrics.brier_score,
        brier_delta=_delta(raw_metrics.brier_score, calibrated_metrics.brier_score),
        raw_log_loss=raw_metrics.log_loss,
        calibrated_log_loss=calibrated_metrics.log_loss,
        log_loss_delta=_delta(raw_metrics.log_loss, calibrated_metrics.log_loss),
        raw_ece=raw_cal.ece if raw_cal else None,
        calibrated_ece=cal_cal.ece if cal_cal else None,
        ece_delta=_delta(raw_cal.ece if raw_cal else None, cal_cal.ece if cal_cal else None),
    )


def _with_view(spec: EvaluationSpec, view: ProbabilityView) -> EvaluationSpec:
    return EvaluationSpec(
        evaluation_as_of_ns=spec.evaluation_as_of_ns,
        decision_start_ns=spec.decision_start_ns,
        decision_end_ns=spec.decision_end_ns,
        target_kind=spec.target_kind,
        horizon_ns=spec.horizon_ns,
        mode=spec.mode,
        probability_view=view,
        calibration_bin_count=spec.calibration_bin_count,
        log_loss_epsilon=spec.log_loss_epsilon,
        minimum_slice_size=spec.minimum_slice_size,
        high_confidence_threshold=spec.high_confidence_threshold,
        scenario_id=spec.scenario_id,
        slice_dimensions=spec.slice_dimensions,
        implementation_version=spec.implementation_version,
    )


def _delta(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return left - right


def _mean_delta(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present) / len(present)


__all__ = [
    "compute_control_comparison",
    "compute_probability_view_comparison",
    "is_control_row",
    "match_key",
    "MATCH_KEY_FIELDS",
]
