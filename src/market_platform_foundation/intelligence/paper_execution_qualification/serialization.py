"""Paper execution qualification serialization (BUILD 27)."""

from __future__ import annotations

from typing import Any

from .types import (
    ExecutionFunnelCountsV1,
    InitialPaperPortfolioStateV1,
    PaperExecutionQualificationReportV1,
    PaperExecutionQualificationRunV1,
    PaperExecutionQualificationSpecV1,
    PaperExecutionReceiptV1,
)


def initial_paper_portfolio_state_v1_to_dict(state: InitialPaperPortfolioStateV1) -> dict[str, Any]:
    return {
        "state_id": state.state_id,
        "schema_version": state.schema_version,
        "initial_cash_minor": state.initial_cash_minor,
        "initial_equity_minor": state.initial_equity_minor,
        "currency": state.currency,
        "price_scale": state.price_scale,
        "allow_short": state.allow_short,
        "margin_policy": state.margin_policy,
        "initial_positions": list(state.initial_positions),
        "initial_open_orders": list(state.initial_open_orders),
        "metadata": dict(state.metadata),
    }


def paper_execution_qualification_spec_v1_to_dict(spec: PaperExecutionQualificationSpecV1) -> dict[str, Any]:
    return {
        "qualification_spec_id": spec.qualification_spec_id,
        "schema_version": spec.schema_version,
        "source_build26_ref": spec.source_build26_ref,
        "source_release_candidate_ref": spec.source_release_candidate_ref,
        "source_head": spec.source_head,
        "contract_inventory_hash": spec.contract_inventory_hash,
        "qualification_kind": spec.qualification_kind.value,
        "allowed_forward_qualification_runs": list(spec.allowed_forward_qualification_runs),
        "instrument_universe": list(spec.instrument_universe),
        "target_kind": spec.target_kind,
        "horizon_ns": spec.horizon_ns,
        "opportunity_policy_ref": spec.opportunity_policy_ref,
        "execution_policy_ref": spec.execution_policy_ref,
        "fill_policy_ref": spec.fill_policy_ref,
        "fee_policy_ref": spec.fee_policy_ref,
        "initial_portfolio_state_ref": spec.initial_portfolio_state_ref,
        "minimum_opportunities": spec.minimum_opportunities,
        "minimum_risk_decisions": spec.minimum_risk_decisions,
        "minimum_orders": spec.minimum_orders,
        "minimum_fills": spec.minimum_fills,
        "minimum_duration_ns": spec.minimum_duration_ns,
        "required_data_mode": spec.required_data_mode,
        "required_execution_mode": spec.required_execution_mode,
        "required_execution_authority": spec.required_execution_authority,
        "implementation_version": spec.implementation_version,
        "metadata": dict(spec.metadata),
    }


def paper_execution_qualification_run_v1_to_dict(run: PaperExecutionQualificationRunV1) -> dict[str, Any]:
    return {
        "qualification_run_id": run.qualification_run_id,
        "schema_version": run.schema_version,
        "qualification_spec_ref": run.qualification_spec_ref,
        "source_build26_ref": run.source_build26_ref,
        "source_release_candidate_ref": run.source_release_candidate_ref,
        "source_head": run.source_head,
        "forward_qualification_run_ref": run.forward_qualification_run_ref,
        "opportunity_policy_ref": run.opportunity_policy_ref,
        "execution_policy_ref": run.execution_policy_ref,
        "fill_policy_ref": run.fill_policy_ref,
        "initial_portfolio_state_ref": run.initial_portfolio_state_ref,
        "instrument_universe": list(run.instrument_universe),
        "run_start_ns": run.run_start_ns,
        "run_end_ns": run.run_end_ns,
        "data_mode": run.data_mode,
        "execution_mode": run.execution_mode,
        "execution_authority": run.execution_authority,
        "implementation_version": run.implementation_version,
        "lineage": dict(run.lineage),
        "metadata": dict(run.metadata),
    }


def funnel_counts_v1_to_dict(counts: ExecutionFunnelCountsV1) -> dict[str, Any]:
    return {
        "forecasts_evaluated": counts.forecasts_evaluated,
        "opportunity_assessments": counts.opportunity_assessments,
        "opportunities_emitted": counts.opportunities_emitted,
        "trade_proposals": counts.trade_proposals,
        "risk_approvals": counts.risk_approvals,
        "risk_reductions": counts.risk_reductions,
        "risk_rejections": counts.risk_rejections,
        "orders_submitted": counts.orders_submitted,
        "orders_filled": counts.orders_filled,
        "orders_cancelled": counts.orders_cancelled,
        "orders_expired": counts.orders_expired,
        "no_fill_count": counts.no_fill_count,
        "attrition_reasons": dict(counts.attrition_reasons),
    }


def paper_execution_qualification_report_v1_to_dict(report: PaperExecutionQualificationReportV1) -> dict[str, Any]:
    return {
        "qualification_report_id": report.qualification_report_id,
        "schema_version": report.schema_version,
        "qualification_spec_ref": report.qualification_spec_ref,
        "qualification_run_ref": report.qualification_run_ref,
        "source_forward_qualification_refs": list(report.source_forward_qualification_refs),
        "source_release_candidate_ref": report.source_release_candidate_ref,
        "evaluation_as_of_ns": report.evaluation_as_of_ns,
        "funnel_counts": funnel_counts_v1_to_dict(report.funnel_counts),
        "execution_realism_assessment": dict(report.execution_realism_assessment),
        "accounting_integrity_assessment": dict(report.accounting_integrity_assessment),
        "risk_integrity_assessment": dict(report.risk_integrity_assessment),
        "idempotency_assessment": dict(report.idempotency_assessment),
        "paper_pnl_diagnostics": dict(report.paper_pnl_diagnostics),
        "qualification_disposition": report.qualification_disposition.value,
        "disposition_reason_codes": list(report.disposition_reason_codes),
        "limitations": list(report.limitations),
        "execution_integrity_status": report.execution_integrity_status.value,
        "implementation_version": report.implementation_version,
        "metadata": dict(report.metadata),
    }
