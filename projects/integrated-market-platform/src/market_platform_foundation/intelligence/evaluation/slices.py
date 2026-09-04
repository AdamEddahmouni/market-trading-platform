"""Deterministic slice aggregation (BUILD 16)."""

from __future__ import annotations

from .calibration_diag import compute_calibration_diagnostics
from .metrics import compute_predictive_metrics
from .types import (
    EvaluationCohortRow,
    EvaluationSpec,
    SliceResult,
    SliceStatus,
    forecast_role,
    instrument_id_for_forecast,
)


def slice_value(row: EvaluationCohortRow, dimension: str) -> str | None:
    forecast = row.forecast
    if dimension == "horizon":
        return str(forecast.horizon.duration_ns)
    if dimension == "target":
        return forecast.target.target_kind
    if dimension == "instrument":
        return instrument_id_for_forecast(forecast)
    if dimension == "model":
        lineage = forecast.component_lineage
        return lineage.model_id if lineage is not None else forecast.metadata.get("baseline_model_kind")
    if dimension == "role":
        return forecast_role(forecast)
    if dimension == "quality":
        return forecast.quality.state.value
    if dimension == "mode":
        return row.ledger_entry.mode
    if dimension == "scenario":
        return row.ledger_entry.scenario_id or ""
    if dimension == "regime":
        return None
    if dimension == "ood":
        uncertainty = forecast.uncertainty or forecast.metadata.get("uncertainty_receipt") or {}
        reasons = uncertainty.get("ood_reasons") if isinstance(uncertainty, dict) else None
        if not reasons:
            return "NONE"
        return ",".join(sorted(str(item) for item in reasons))
    if dimension == "fusion_lineage":
        return forecast.metadata.get("fusion_manifest_id")
    if dimension == "hypothesis_lineage":
        refs = forecast.source_hypothesis_refs
        return refs[0].id if refs else None
    return None


def compute_slices(
    rows: tuple[EvaluationCohortRow, ...],
    spec: EvaluationSpec,
) -> tuple[SliceResult, ...]:
    if not spec.slice_dimensions:
        return ()
    results: list[SliceResult] = []
    for dimension in spec.slice_dimensions:
        groups: dict[str, list[EvaluationCohortRow]] = {}
        unsupported = dimension == "regime"
        for row in rows:
            if unsupported:
                continue
            value = slice_value(row, dimension)
            if value is None:
                continue
            groups.setdefault(str(value), []).append(row)
        if unsupported:
            results.append(
                SliceResult(
                    dimension=dimension,
                    value="UNSUPPORTED",
                    status=SliceStatus.UNSUPPORTED,
                    sample_count=0,
                    metrics=compute_predictive_metrics(tuple(), spec),
                )
            )
            continue
        for value in sorted(groups):
            group_rows = tuple(groups[value])
            metrics = compute_predictive_metrics(group_rows, spec)
            status = SliceStatus.OK
            if len(group_rows) < spec.minimum_slice_size:
                status = SliceStatus.INSUFFICIENT_SAMPLE
            calibration = compute_calibration_diagnostics(group_rows, spec)
            results.append(
                SliceResult(
                    dimension=dimension,
                    value=value,
                    status=status,
                    sample_count=len(group_rows),
                    metrics=metrics,
                    calibration=calibration,
                )
            )
    return tuple(results)


__all__ = ["compute_slices", "slice_value"]
