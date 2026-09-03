"""Forward qualification report builder (BUILD 26)."""

from __future__ import annotations

from typing import Any

from ..contracts.prediction_ledger import PredictionLedgerEntryV1
from ..evaluation.types import AggregateStatus
from ..persistence.repository import IntelligenceRepository
from .identity import derive_forward_cohort_fingerprint, derive_qualification_report_id
from .provider_capabilities import provider_capability_matrix
from .types import (
    FORWARD_QUALIFICATION_IMPLEMENTATION_VERSION,
    FORWARD_QUALIFICATION_SCHEMA_VERSION,
    ForwardIntegrityStatus,
    ForwardPredictionReceiptV1,
    ForwardQualificationReportV1,
    ForwardQualificationRunV1,
    ForwardQualificationSpecV1,
    QualificationDisposition,
)


def _count_receipts(receipts: tuple[ForwardPredictionReceiptV1, ...]) -> dict[str, int]:
    valid = sum(1 for r in receipts if r.forward_integrity_status == ForwardIntegrityStatus.VALID)
    invalid = sum(1 for r in receipts if r.forward_integrity_status == ForwardIntegrityStatus.INVALID)
    return {
        "total_registered": len(receipts),
        "valid_forward": valid,
        "invalid_forward": invalid,
        "pending": 0,
    }


def _settlement_counts(
    repository: IntelligenceRepository,
    receipts: tuple[ForwardPredictionReceiptV1, ...],
    *,
    evaluation_as_of_ns: int,
) -> tuple[dict[str, int], dict[str, int]]:
    settled = 0
    pending = 0
    labelable = 0
    unlabelable = 0
    for receipt in receipts:
        outcomes = repository.get_outcomes_by_forecast(receipt.forecast_id)
        matched = [
            outcome
            for outcome in outcomes
            if outcome.metadata.get("ledger_entry_id") == receipt.ledger_entry_id
        ]
        if not matched:
            if evaluation_as_of_ns < receipt.target_time_ns:
                pending += 1
            else:
                pending += 1
            continue
        outcome = matched[0]
        label_time = outcome.metadata.get("label_available_time_ns")
        if label_time is not None and int(label_time) > evaluation_as_of_ns:
            pending += 1
            continue
        settled += 1
        if outcome.resolution_status.value in {"SETTLED", "PARTIAL"}:
            labelable += 1
        else:
            unlabelable += 1
    settlement = {
        "settled": settled,
        "pending": pending,
        "total_registered": len(receipts),
    }
    labelability = {
        "labelable": labelable,
        "unlabelable": unlabelable,
        "pending": pending,
    }
    return settlement, labelability


def build_forward_qualification_report(
    *,
    spec: ForwardQualificationSpecV1,
    run: ForwardQualificationRunV1,
    repository: IntelligenceRepository,
    receipts: tuple[ForwardPredictionReceiptV1, ...],
    evaluation_as_of_ns: int,
    evaluation_report_id: str | None = None,
    primary_forward_metrics: dict[str, Any] | None = None,
    control_comparison: dict[str, Any] | None = None,
    calibration_diagnostics: dict[str, Any] | None = None,
    provider_health_summary: dict[str, Any] | None = None,
    data_quality_summary: dict[str, Any] | None = None,
) -> ForwardQualificationReportV1:
    integrity_failures = sorted(
        {
            code
            for receipt in receipts
            for code in receipt.integrity_failure_codes
        }
    )
    integrity_status = (
        ForwardIntegrityStatus.INVALID
        if integrity_failures
        else ForwardIntegrityStatus.VALID
    )

    prediction_counts = _count_receipts(receipts)
    settlement_counts, labelability_counts = _settlement_counts(
        repository,
        receipts,
        evaluation_as_of_ns=evaluation_as_of_ns,
    )

    forecast_ids = tuple(sorted(r.forecast_id for r in receipts))
    ledger_ids = tuple(sorted(r.ledger_entry_id for r in receipts))
    outcome_ids: list[str] = []
    for receipt in receipts:
        for outcome in repository.get_outcomes_by_forecast(receipt.forecast_id):
            if outcome.metadata.get("ledger_entry_id") == receipt.ledger_entry_id:
                outcome_ids.append(outcome.outcome_id)
    cohort_fingerprint = derive_forward_cohort_fingerprint(
        forecast_ids=forecast_ids,
        ledger_entry_ids=ledger_ids,
        outcome_ids=tuple(sorted(outcome_ids)),
    )

    disposition, reason_codes, limitations = _derive_disposition(
        spec=spec,
        integrity_status=integrity_status,
        prediction_counts=prediction_counts,
        labelability_counts=labelability_counts,
        primary_forward_metrics=primary_forward_metrics or {},
    )

    report_id = derive_qualification_report_id(
        qualification_spec_id=spec.qualification_spec_id,
        qualification_run_id=run.qualification_run_id,
        cohort_fingerprint=cohort_fingerprint,
        evaluation_as_of_ns=evaluation_as_of_ns,
        implementation_version=FORWARD_QUALIFICATION_IMPLEMENTATION_VERSION,
    )

    return ForwardQualificationReportV1(
        qualification_report_id=report_id,
        schema_version=FORWARD_QUALIFICATION_SCHEMA_VERSION,
        qualification_spec_ref=spec.qualification_spec_id,
        qualification_run_ref=run.qualification_run_id,
        release_candidate_ref=spec.release_candidate_ref,
        evaluation_as_of_ns=evaluation_as_of_ns,
        provider_capability_summary=provider_capability_matrix(),
        provider_health_summary=provider_health_summary or {"status": "NOT_COLLECTED"},
        data_quality_summary=data_quality_summary or {"status": "NOT_COLLECTED"},
        prediction_counts=prediction_counts,
        settlement_counts=settlement_counts,
        labelability_counts=labelability_counts,
        primary_forward_metrics=primary_forward_metrics or {"status": AggregateStatus.EMPTY_COHORT.value},
        control_comparison=control_comparison or {},
        calibration_diagnostics=calibration_diagnostics or {},
        ood_diagnostics={},
        operational_errors=(),
        runtime_incidents=(),
        forward_integrity_status=integrity_status,
        forward_integrity_failures=tuple(integrity_failures),
        qualification_disposition=disposition,
        disposition_reason_codes=reason_codes,
        limitations=limitations,
        lineage={
            "evaluation_report_id": evaluation_report_id,
            "cohort_fingerprint": cohort_fingerprint,
        },
        implementation_version=FORWARD_QUALIFICATION_IMPLEMENTATION_VERSION,
        metadata={"release_candidate_ref": spec.release_candidate_ref},
    )


def _derive_disposition(
    *,
    spec: ForwardQualificationSpecV1,
    integrity_status: ForwardIntegrityStatus,
    prediction_counts: dict[str, int],
    labelability_counts: dict[str, int],
    primary_forward_metrics: dict[str, Any],
) -> tuple[QualificationDisposition, tuple[str, ...], tuple[str, ...]]:
    limitations: list[str] = []
    if integrity_status == ForwardIntegrityStatus.INVALID:
        return (
            QualificationDisposition.INVALID_FORWARD_INTEGRITY,
            ("FORWARD_INTEGRITY_FAILURE",),
            tuple(limitations),
        )

    total = prediction_counts.get("total_registered", 0)
    labelable = labelability_counts.get("labelable", 0)
    if total < spec.minimum_prediction_count or labelable < spec.minimum_labelable_count:
        limitations.append("INSUFFICIENT_FORWARD_EVIDENCE")
        return (
            QualificationDisposition.INSUFFICIENT_FORWARD_EVIDENCE,
            ("MINIMUM_SAMPLE_NOT_MET",),
            tuple(limitations),
        )

    if primary_forward_metrics.get("status") not in {None, AggregateStatus.OK.value, "OK"}:
        limitations.append("METRICS_INCOMPLETE")
        return (
            QualificationDisposition.QUALIFIED_WITH_LIMITATIONS,
            ("METRICS_INCOMPLETE",),
            tuple(limitations),
        )

    return (
        QualificationDisposition.QUALIFIED_WITH_LIMITATIONS,
        ("FIXTURE_OR_BOUNDED_RUN",),
        ("REAL_FORWARD_SESSION_MAY_NOT_HAVE_EXECUTED",),
    )
