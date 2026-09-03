"""Paper execution qualification report builder (BUILD 27)."""

from __future__ import annotations

from typing import Any

from .fill_realism import bar_conservative_limitations
from .funnel import reconcile_funnel
from .identity import derive_execution_cohort_fingerprint, derive_qualification_report_id
from .types import (
    PAPER_EXECUTION_QUALIFICATION_IMPLEMENTATION_VERSION,
    PAPER_EXECUTION_QUALIFICATION_SCHEMA_VERSION,
    ExecutionFunnelCountsV1,
    ExecutionIntegrityStatus,
    PaperExecutionQualificationReportV1,
    PaperExecutionQualificationRunV1,
    PaperExecutionQualificationSpecV1,
    PaperExecutionReceiptV1,
    PaperQualificationDisposition,
)


def _derive_disposition(
    *,
    spec: PaperExecutionQualificationSpecV1,
    integrity_status: ExecutionIntegrityStatus,
    funnel: ExecutionFunnelCountsV1,
    fixture_ok: bool,
) -> tuple[PaperQualificationDisposition, tuple[str, ...], tuple[str, ...]]:
    limitations = list(bar_conservative_limitations())
    reason_codes: list[str] = []

    if integrity_status == ExecutionIntegrityStatus.INVALID:
        return (
            PaperQualificationDisposition.INVALID_EXECUTION_INTEGRITY,
            ("EXECUTION_INTEGRITY_INVALID",),
            tuple(limitations),
        )

    if funnel.opportunities_emitted < spec.minimum_opportunities:
        reason_codes.append("INSUFFICIENT_FORWARD_OPPORTUNITIES")
        limitations.append("FORWARD_SAMPLE_INSUFFICIENT")
        return (
            PaperQualificationDisposition.INSUFFICIENT_PAPER_EXECUTION_EVIDENCE,
            tuple(reason_codes),
            tuple(limitations),
        )

    if funnel.orders_filled < spec.minimum_fills:
        reason_codes.append("INSUFFICIENT_FILLS")
        limitations.append("FORWARD_SAMPLE_INSUFFICIENT")
        return (
            PaperQualificationDisposition.INSUFFICIENT_PAPER_EXECUTION_EVIDENCE,
            tuple(reason_codes),
            tuple(limitations),
        )

    if not fixture_ok:
        return (
            PaperQualificationDisposition.PAPER_EXECUTION_QUALIFIED_WITH_LIMITATIONS,
            ("FIXTURE_LIFECYCLE_INCOMPLETE",),
            tuple(limitations),
        )

    if limitations:
        return (
            PaperQualificationDisposition.PAPER_EXECUTION_QUALIFIED_WITH_LIMITATIONS,
            ("KNOWN_SIMULATOR_LIMITATIONS",),
            tuple(limitations),
        )

    return (
        PaperQualificationDisposition.PAPER_EXECUTION_QUALIFIED,
        ("PAPER_EXECUTION_LOGIC_VALIDATED",),
        tuple(limitations),
    )


def build_paper_execution_qualification_report(
    *,
    spec: PaperExecutionQualificationSpecV1,
    run: PaperExecutionQualificationRunV1,
    receipts: tuple[PaperExecutionReceiptV1, ...],
    funnel_counts: ExecutionFunnelCountsV1,
    evaluation_as_of_ns: int,
    forward_qualification_refs: tuple[str, ...] = (),
    fill_realism_notes: dict[str, Any] | None = None,
    ending_portfolio: Any | None = None,
    fixture_ok: bool = True,
) -> PaperExecutionQualificationReportV1:
    integrity_failures = sorted(
        {code for receipt in receipts for code in receipt.integrity_failure_codes}
    )
    integrity_status = (
        ExecutionIntegrityStatus.INVALID if integrity_failures else ExecutionIntegrityStatus.VALID
    )
    funnel_ok, funnel_issues = reconcile_funnel(funnel_counts)

    opportunity_ids = tuple(sorted(r.opportunity_id for r in receipts))
    risk_ids = tuple(sorted(r.risk_decision_id for r in receipts))
    fill_ids = tuple(sorted(r.fill_id for r in receipts if r.fill_id))
    cohort = derive_execution_cohort_fingerprint(
        opportunity_ids=opportunity_ids,
        risk_decision_ids=risk_ids,
        fill_ids=fill_ids,
    )

    disposition, reason_codes, limitations = _derive_disposition(
        spec=spec,
        integrity_status=integrity_status,
        funnel=funnel_counts,
        fixture_ok=fixture_ok and funnel_ok,
    )

    report_id = derive_qualification_report_id(
        qualification_spec_id=spec.qualification_spec_id,
        qualification_run_id=run.qualification_run_id,
        cohort_fingerprint=cohort,
        evaluation_as_of_ns=evaluation_as_of_ns,
        implementation_version=PAPER_EXECUTION_QUALIFICATION_IMPLEMENTATION_VERSION,
    )

    paper_pnl: dict[str, Any] = {"simulator_dependent": True, "not_live_pnl": True}
    if ending_portfolio is not None:
        paper_pnl["ending_cash_minor"] = ending_portfolio.cash_minor
        paper_pnl["ending_equity_minor"] = ending_portfolio.equity_minor

    return PaperExecutionQualificationReportV1(
        qualification_report_id=report_id,
        schema_version=PAPER_EXECUTION_QUALIFICATION_SCHEMA_VERSION,
        qualification_spec_ref=spec.qualification_spec_id,
        qualification_run_ref=run.qualification_run_id,
        source_forward_qualification_refs=forward_qualification_refs,
        source_release_candidate_ref=spec.source_release_candidate_ref,
        evaluation_as_of_ns=evaluation_as_of_ns,
        funnel_counts=funnel_counts,
        execution_realism_assessment={
            "fill_model": spec.fill_policy_ref,
            "fee_policy": spec.fee_policy_ref,
            "notes": fill_realism_notes or {},
            "funnel_reconciliation_ok": funnel_ok,
            "funnel_issues": funnel_issues,
        },
        accounting_integrity_assessment={"ledger_authority": "BUILD22_PAPER_LEDGER"},
        risk_integrity_assessment={"pre_trade_required": True},
        idempotency_assessment={"risk_decision_idempotency": True},
        paper_pnl_diagnostics=paper_pnl,
        provider_data_quality_summary={},
        governance_incident_summary={},
        execution_integrity_status=integrity_status,
        execution_integrity_failures=tuple(integrity_failures),
        qualification_disposition=disposition,
        disposition_reason_codes=reason_codes,
        limitations=limitations,
        lineage={
            "source_build26_ref": spec.source_build26_ref,
            "cohort_fingerprint": cohort,
        },
        implementation_version=PAPER_EXECUTION_QUALIFICATION_IMPLEMENTATION_VERSION,
        metadata={"build": "BUILD_27"},
    )
