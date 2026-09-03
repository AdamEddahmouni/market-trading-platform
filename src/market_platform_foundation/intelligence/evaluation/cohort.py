"""Deterministic evaluation cohort materialization (BUILD 16)."""

from __future__ import annotations

from ..contracts.common import Direction, OutcomeResolutionStatus, QualityState
from ..contracts.forecast import ForecastV1
from ..contracts.outcome import OutcomeV1
from ..contracts.prediction_ledger import PredictionLedgerEntryV1
from ..outcomes.identity import derive_outcome_id
from ..persistence.repository import IntelligenceRepository
from .errors import EvaluationError
from .provenance import (
    binary_label_from_outcome,
    extract_probabilities,
    label_available_time_ns,
    predicted_direction_from_forecast,
)
from .types import EvaluationCohortRow, EvaluationSpec, PredictionDiagnosticState


def materialize_cohort(
    repository: IntelligenceRepository,
    spec: EvaluationSpec,
) -> tuple[EvaluationCohortRow, ...]:
    entries = _query_ledger_entries(repository, spec)
    rows: list[EvaluationCohortRow] = []
    for entry in entries:
        row = _build_row(repository, entry, spec)
        rows.append(row)
    return tuple(sorted(rows, key=lambda item: item.ledger_entry.ledger_entry_id))


def _query_ledger_entries(
    repository: IntelligenceRepository,
    spec: EvaluationSpec,
) -> tuple[PredictionLedgerEntryV1, ...]:
    return repository.query_prediction_ledger_entries(
        decision_start_ns=spec.decision_start_ns,
        decision_end_ns=spec.decision_end_ns,
        mode=spec.mode,
        scenario_id=spec.scenario_id,
        target_kind=spec.target_kind,
        horizon_ns=spec.horizon_ns,
    )


def _build_row(
    repository: IntelligenceRepository,
    entry: PredictionLedgerEntryV1,
    spec: EvaluationSpec,
) -> EvaluationCohortRow:
    forecast = repository.get_forecast(entry.forecast_id)
    if forecast is None:
        raise EvaluationError(
            "FORECAST_NOT_FOUND",
            details={"forecast_id": entry.forecast_id, "ledger_entry_id": entry.ledger_entry_id},
        )
    if forecast.forecast_id != entry.forecast_id:
        raise EvaluationError("FORECAST_LEDGER_MISMATCH", details={"forecast_id": forecast.forecast_id})
    if forecast.target.target_kind != spec.target_kind:
        raise EvaluationError("TARGET_MISMATCH", details={"forecast_id": forecast.forecast_id})
    if forecast.horizon.duration_ns != spec.horizon_ns:
        raise EvaluationError("HORIZON_MISMATCH", details={"forecast_id": forecast.forecast_id})
    if entry.mode != spec.mode:
        raise EvaluationError("MODE_MISMATCH", details={"ledger_entry_id": entry.ledger_entry_id})
    if spec.scenario_id is not None and entry.scenario_id != spec.scenario_id:
        raise EvaluationError("SCENARIO_MISMATCH", details={"ledger_entry_id": entry.ledger_entry_id})

    outcome = _resolve_outcome(repository, entry)
    label_time = label_available_time_ns(outcome, entry)
    state, flags = _classify_row(outcome, label_time, spec.evaluation_as_of_ns, forecast)
    raw, calibrated, operational = extract_probabilities(forecast)
    binary_label = binary_label_from_outcome(outcome) if outcome is not None else None
    evaluated_p = operational if operational is not None else raw
    predicted_dir = (
        predicted_direction_from_forecast(forecast, evaluated_p)
        if evaluated_p is not None
        else None
    )
    return EvaluationCohortRow(
        forecast=forecast,
        ledger_entry=entry,
        outcome=outcome,
        label_available_time_ns=label_time,
        diagnostic_state=state,
        probability_raw=raw,
        probability_calibrated=calibrated,
        probability_operational=operational,
        binary_label=binary_label,
        predicted_direction=predicted_dir,
        flags=flags,
    )


def _resolve_outcome(
    repository: IntelligenceRepository,
    entry: PredictionLedgerEntryV1,
) -> OutcomeV1 | None:
    expected_id = derive_outcome_id(
        forecast_id=entry.forecast_id,
        ledger_entry_id=entry.ledger_entry_id,
        settlement_policy_identity=entry.settlement_policy_identity,
        mode=entry.mode,
        scenario_id=entry.scenario_id,
    )
    outcome = repository.get_outcome(expected_id)
    if outcome is not None:
        if outcome.forecast_id != entry.forecast_id:
            raise EvaluationError("OUTCOME_FORECAST_MISMATCH", details={"outcome_id": expected_id})
        return outcome
    for candidate in repository.get_outcomes_by_forecast(entry.forecast_id):
        if candidate.outcome_id == expected_id:
            return candidate
    return None


def _classify_row(
    outcome: OutcomeV1 | None,
    label_time: int | None,
    evaluation_as_of_ns: int,
    forecast: ForecastV1,
) -> tuple[PredictionDiagnosticState, frozenset[str]]:
    flags: set[str] = set()
    if forecast.quality.state == QualityState.DEGRADED:
        flags.add("DEGRADED_QUALITY")
    if forecast.quality.state == QualityState.INVALID:
        flags.add("INVALID_QUALITY")
    uncertainty = forecast.uncertainty or forecast.metadata.get("uncertainty_receipt") or {}
    ood_reasons = uncertainty.get("ood_reasons") if isinstance(uncertainty, dict) else None
    if ood_reasons:
        flags.add("OOD")
    if outcome is None:
        return PredictionDiagnosticState.NOT_SETTLED, frozenset(flags)
    if label_time is None:
        return PredictionDiagnosticState.NOT_SETTLED, frozenset(flags)
    if label_time > evaluation_as_of_ns:
        return PredictionDiagnosticState.FUTURE_LABEL, frozenset(flags)
    if outcome.resolution_status == OutcomeResolutionStatus.UNLABELABLE:
        return PredictionDiagnosticState.UNLABELABLE, frozenset(flags)
    if outcome.resolution_status != OutcomeResolutionStatus.SETTLED:
        return PredictionDiagnosticState.INELIGIBLE, frozenset(flags)
    return PredictionDiagnosticState.CORRECT, frozenset(flags)


def labelable_rows(rows: tuple[EvaluationCohortRow, ...]) -> tuple[EvaluationCohortRow, ...]:
    return tuple(
        row
        for row in rows
        if row.diagnostic_state not in {
            PredictionDiagnosticState.NOT_SETTLED,
            PredictionDiagnosticState.FUTURE_LABEL,
            PredictionDiagnosticState.UNLABELABLE,
            PredictionDiagnosticState.INELIGIBLE,
        }
        and row.binary_label is not None
    )


def predictive_rows(
    rows: tuple[EvaluationCohortRow, ...],
    spec: EvaluationSpec,
) -> tuple[EvaluationCohortRow, ...]:
    from .provenance import probability_for_view

    eligible = labelable_rows(rows)
    result: list[EvaluationCohortRow] = []
    for row in eligible:
        probability = probability_for_view(row.forecast, spec.probability_view)
        if probability is None:
            continue
        result.append(row)
    return tuple(result)


def refine_diagnostic_states(
    rows: tuple[EvaluationCohortRow, ...],
    spec: EvaluationSpec,
) -> tuple[EvaluationCohortRow, ...]:
    from .provenance import probability_for_view, validate_evaluated_probability

    refined: list[EvaluationCohortRow] = []
    for row in rows:
        if row.diagnostic_state != PredictionDiagnosticState.CORRECT:
            refined.append(row)
            continue
        probability = probability_for_view(row.forecast, spec.probability_view)
        if probability is None or row.binary_label is None:
            refined.append(
                EvaluationCohortRow(
                    forecast=row.forecast,
                    ledger_entry=row.ledger_entry,
                    outcome=row.outcome,
                    label_available_time_ns=row.label_available_time_ns,
                    diagnostic_state=PredictionDiagnosticState.INELIGIBLE,
                    probability_raw=row.probability_raw,
                    probability_calibrated=row.probability_calibrated,
                    probability_operational=row.probability_operational,
                    binary_label=row.binary_label,
                    predicted_direction=row.predicted_direction,
                    flags=row.flags,
                )
            )
            continue
        p = validate_evaluated_probability(probability)
        flags = set(row.flags)
        if p <= spec.log_loss_epsilon or p >= 1.0 - spec.log_loss_epsilon:
            flags.add("BOUNDARY_PROBABILITY")
        confidence = max(p, 1.0 - p)
        if confidence >= spec.high_confidence_threshold:
            flags.add("HIGH_CONFIDENCE")
        elif confidence <= (1.0 - spec.high_confidence_threshold):
            flags.add("LOW_CONFIDENCE")
        predicted = predicted_direction_from_forecast(row.forecast, p)
        actual = Direction.LONG if row.binary_label == 1 else Direction.SHORT
        if predicted == actual:
            state = PredictionDiagnosticState.CORRECT
        elif predicted == Direction.LONG:
            state = PredictionDiagnosticState.FALSE_UP
        elif predicted == Direction.SHORT:
            state = PredictionDiagnosticState.FALSE_DOWN
        else:
            state = PredictionDiagnosticState.INELIGIBLE
        refined.append(
            EvaluationCohortRow(
                forecast=row.forecast,
                ledger_entry=row.ledger_entry,
                outcome=row.outcome,
                label_available_time_ns=row.label_available_time_ns,
                diagnostic_state=state,
                probability_raw=row.probability_raw,
                probability_calibrated=row.probability_calibrated,
                probability_operational=row.probability_operational,
                binary_label=row.binary_label,
                predicted_direction=predicted,
                flags=frozenset(flags),
            )
        )
    return tuple(refined)


__all__ = [
    "labelable_rows",
    "materialize_cohort",
    "predictive_rows",
    "refine_diagnostic_states",
]
