"""Deterministic evaluation identity helpers (BUILD 16)."""

from __future__ import annotations

from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from .types import EvaluationCohortRow, EvaluationSpec, ProbabilityView

EVALUATION_SPEC_ID_VERSION = "evaluation-spec-sha256-v1"
COHORT_FINGERPRINT_VERSION = "evaluation-cohort-sha256-v1"
REPORT_ID_VERSION = "evaluation-report-sha256-v1"


def derive_evaluation_spec_id(spec: EvaluationSpec) -> str:
    payload: dict[str, Any] = {
        "identity_version": EVALUATION_SPEC_ID_VERSION,
        "evaluation_as_of_ns": spec.evaluation_as_of_ns,
        "decision_start_ns": spec.decision_start_ns,
        "decision_end_ns": spec.decision_end_ns,
        "target_kind": spec.target_kind,
        "horizon_ns": spec.horizon_ns,
        "mode": spec.mode,
        "scenario_id": spec.scenario_id,
        "probability_view": spec.probability_view.value,
        "calibration_bin_count": spec.calibration_bin_count,
        "log_loss_epsilon": spec.log_loss_epsilon,
        "minimum_slice_size": spec.minimum_slice_size,
        "high_confidence_threshold": spec.high_confidence_threshold,
        "slice_dimensions": list(spec.slice_dimensions),
        "implementation_version": spec.implementation_version,
    }
    return f"EVSPEC-{sha256_bytes(canonical_bytes(payload))}"


def derive_cohort_fingerprint(
    rows: tuple[EvaluationCohortRow, ...],
    *,
    probability_view: ProbabilityView,
) -> str:
    ordered = sorted(
        rows,
        key=lambda row: (
            row.ledger_entry.ledger_entry_id,
            row.forecast.forecast_id,
            row.outcome.outcome_id if row.outcome is not None else "",
        ),
    )
    row_payload = []
    for row in ordered:
        outcome_id = row.outcome.outcome_id if row.outcome is not None else None
        row_payload.append(
            {
                "forecast_id": row.forecast.forecast_id,
                "ledger_entry_id": row.ledger_entry.ledger_entry_id,
                "outcome_id": outcome_id,
                "diagnostic_state": row.diagnostic_state.value,
                "probability_view": probability_view.value,
            }
        )
    payload = {
        "identity_version": COHORT_FINGERPRINT_VERSION,
        "probability_view": probability_view.value,
        "rows": row_payload,
    }
    return f"EVCOH-{sha256_bytes(canonical_bytes(payload))}"


def derive_report_id(
    *,
    evaluation_spec_id: str,
    cohort_fingerprint: str,
    implementation_version: str,
) -> str:
    payload = {
        "identity_version": REPORT_ID_VERSION,
        "evaluation_spec_id": evaluation_spec_id,
        "cohort_fingerprint": cohort_fingerprint,
        "implementation_version": implementation_version,
    }
    return f"EVREP-{sha256_bytes(canonical_bytes(payload))}"


__all__ = [
    "derive_cohort_fingerprint",
    "derive_evaluation_spec_id",
    "derive_report_id",
]
