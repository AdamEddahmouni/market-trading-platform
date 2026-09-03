"""Forward prediction integrity receipts and validation (BUILD 26)."""

from __future__ import annotations

from dataclasses import replace

from ..contracts.forecast import ForecastV1
from ..contracts.prediction_ledger import PredictionLedgerEntryV1
from .identity import derive_receipt_content_hash, derive_receipt_id
from .types import (
    FORWARD_QUALIFICATION_SCHEMA_VERSION,
    EvidenceClass,
    ForwardIntegrityStatus,
    ForwardPredictionReceiptV1,
    IntegrityFailureCode,
)


def validate_forward_integrity(
    *,
    forecast: ForecastV1,
    ledger_entry: PredictionLedgerEntryV1 | None,
    evidence_class: EvidenceClass,
    registered_at_ns: int | None = None,
    outcome_known_at_ns: int | None = None,
) -> tuple[ForwardIntegrityStatus, tuple[str, ...]]:
    failures: list[str] = []

    if evidence_class == EvidenceClass.REPLAY:
        failures.append(IntegrityFailureCode.REPLAY_MASQUERADING_AS_FORWARD.value)
    if evidence_class == EvidenceClass.COUNTERFACTUAL:
        failures.append(IntegrityFailureCode.COUNTERFACTUAL_MASQUERADING_AS_FORWARD.value)

    target_time_ns = forecast.decision_time_ns + forecast.horizon.duration_ns
    reg_ns = registered_at_ns
    if ledger_entry is not None:
        reg_ns = ledger_entry.registered_at_ns
        if ledger_entry.registered_at_ns > target_time_ns:
            failures.append(IntegrityFailureCode.LEDGER_AFTER_TARGET.value)

    if outcome_known_at_ns is not None and reg_ns is not None:
        if reg_ns >= outcome_known_at_ns:
            failures.append(IntegrityFailureCode.RETROACTIVE_FORECAST.value)

    if ledger_entry is None:
        failures.append(IntegrityFailureCode.LEDGER_AFTER_TARGET.value)

    if failures:
        return ForwardIntegrityStatus.INVALID, tuple(sorted(set(failures)))
    return ForwardIntegrityStatus.VALID, ()


def build_forward_prediction_receipt(
    *,
    forecast: ForecastV1,
    ledger_entry: PredictionLedgerEntryV1,
    qualification_run_ref: str,
    recorded_at_ns: int,
    evidence_class: EvidenceClass = EvidenceClass.ACTUAL_FORWARD,
    outcome_known_at_ns: int | None = None,
) -> ForwardPredictionReceiptV1:
    target_time_ns = forecast.decision_time_ns + forecast.horizon.duration_ns
    content_hash = derive_receipt_content_hash(
        forecast_id=forecast.forecast_id,
        ledger_entry_id=ledger_entry.ledger_entry_id,
        decision_time_ns=forecast.decision_time_ns,
        target_time_ns=target_time_ns,
        registered_at_ns=ledger_entry.registered_at_ns,
    )
    integrity_status, failure_codes = validate_forward_integrity(
        forecast=forecast,
        ledger_entry=ledger_entry,
        evidence_class=evidence_class,
        registered_at_ns=ledger_entry.registered_at_ns,
        outcome_known_at_ns=outcome_known_at_ns,
    )
    receipt = ForwardPredictionReceiptV1(
        receipt_id="pending",
        schema_version=FORWARD_QUALIFICATION_SCHEMA_VERSION,
        forecast_id=forecast.forecast_id,
        ledger_entry_id=ledger_entry.ledger_entry_id,
        decision_time_ns=forecast.decision_time_ns,
        target_time_ns=target_time_ns,
        registered_at_ns=ledger_entry.registered_at_ns,
        recorded_at_ns=recorded_at_ns,
        qualification_run_ref=qualification_run_ref,
        evidence_class=evidence_class,
        content_hash=content_hash,
        forward_integrity_status=integrity_status,
        integrity_failure_codes=failure_codes,
    )
    return replace(receipt, receipt_id=derive_receipt_id(receipt))
