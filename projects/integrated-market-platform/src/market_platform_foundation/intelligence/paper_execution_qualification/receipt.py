"""Paper execution receipt builder (BUILD 27)."""

from __future__ import annotations

from dataclasses import replace

from .identity import derive_receipt_id
from .integrity import validate_forward_lineage
from .types import (
    PAPER_EXECUTION_QUALIFICATION_SCHEMA_VERSION,
    ExecutionIntegrityStatus,
    PaperEvidenceClass,
    PaperExecutionReceiptV1,
)


def build_paper_execution_receipt(
    *,
    opportunity_id: str,
    forecast_id: str,
    forward_receipt_ref: str | None,
    trade_proposal_id: str,
    risk_decision_id: str,
    paper_order_id: str | None,
    fill_id: str | None,
    decision_time_ns: int,
    fill_time_ns: int | None,
    qualification_run_ref: str,
    evidence_class: PaperEvidenceClass = PaperEvidenceClass.FORWARD_PAPER,
) -> PaperExecutionReceiptV1:
    integrity_status, failure_codes = validate_forward_lineage(
        evidence_class=evidence_class,
        forward_receipt_ref=forward_receipt_ref,
        forecast_id=forecast_id,
    )
    if paper_order_id and not risk_decision_id:
        integrity_status = ExecutionIntegrityStatus.INVALID
        failure_codes = tuple(failure_codes) + ("RISK_WITHOUT_DECISION",)

    receipt = PaperExecutionReceiptV1(
        receipt_id="pending",
        schema_version=PAPER_EXECUTION_QUALIFICATION_SCHEMA_VERSION,
        opportunity_id=opportunity_id,
        forecast_id=forecast_id,
        forward_receipt_ref=forward_receipt_ref,
        trade_proposal_id=trade_proposal_id,
        risk_decision_id=risk_decision_id,
        paper_order_id=paper_order_id,
        fill_id=fill_id,
        decision_time_ns=decision_time_ns,
        fill_time_ns=fill_time_ns,
        qualification_run_ref=qualification_run_ref,
        evidence_class=evidence_class,
        execution_integrity_status=integrity_status,
        integrity_failure_codes=failure_codes,
        metadata={},
    )
    return replace(receipt, receipt_id=derive_receipt_id(receipt))
