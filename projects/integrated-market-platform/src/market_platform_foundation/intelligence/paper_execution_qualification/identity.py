"""Deterministic paper execution qualification identities (BUILD 27)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .types import (
    InitialPaperPortfolioStateV1,
    PAPER_EXECUTION_QUALIFICATION_IMPLEMENTATION_VERSION,
    PaperExecutionQualificationRunV1,
    PaperExecutionQualificationSpecV1,
    PaperExecutionReceiptV1,
)


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_prefix(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest}"


def initial_portfolio_identity_payload(state: InitialPaperPortfolioStateV1) -> dict[str, Any]:
    return {
        "schema_version": state.schema_version,
        "initial_cash_minor": state.initial_cash_minor,
        "initial_equity_minor": state.initial_equity_minor,
        "currency": state.currency,
        "price_scale": state.price_scale,
        "allow_short": state.allow_short,
        "margin_policy": state.margin_policy,
        "initial_positions": list(state.initial_positions),
        "initial_open_orders": list(state.initial_open_orders),
        "implementation_version": PAPER_EXECUTION_QUALIFICATION_IMPLEMENTATION_VERSION,
    }


def derive_initial_portfolio_state_id(state: InitialPaperPortfolioStateV1) -> str:
    return _sha256_prefix("PEQPORT", initial_portfolio_identity_payload(state))


def qualification_spec_identity_payload(spec: PaperExecutionQualificationSpecV1) -> dict[str, Any]:
    return {
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
    }


def derive_qualification_spec_id(spec: PaperExecutionQualificationSpecV1) -> str:
    return _sha256_prefix("PEQSPEC", qualification_spec_identity_payload(spec))


def qualification_run_identity_payload(run: PaperExecutionQualificationRunV1) -> dict[str, Any]:
    return {
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
        "data_mode": run.data_mode,
        "execution_mode": run.execution_mode,
        "execution_authority": run.execution_authority,
        "implementation_version": run.implementation_version,
    }


def derive_qualification_run_id(run: PaperExecutionQualificationRunV1) -> str:
    return _sha256_prefix("PEQRUN", qualification_run_identity_payload(run))


def receipt_identity_payload(receipt: PaperExecutionReceiptV1) -> dict[str, Any]:
    return {
        "schema_version": receipt.schema_version,
        "opportunity_id": receipt.opportunity_id,
        "forecast_id": receipt.forecast_id,
        "forward_receipt_ref": receipt.forward_receipt_ref,
        "trade_proposal_id": receipt.trade_proposal_id,
        "risk_decision_id": receipt.risk_decision_id,
        "paper_order_id": receipt.paper_order_id,
        "fill_id": receipt.fill_id,
        "decision_time_ns": receipt.decision_time_ns,
        "fill_time_ns": receipt.fill_time_ns,
        "qualification_run_ref": receipt.qualification_run_ref,
        "evidence_class": receipt.evidence_class.value,
        "implementation_version": PAPER_EXECUTION_QUALIFICATION_IMPLEMENTATION_VERSION,
    }


def derive_receipt_id(receipt: PaperExecutionReceiptV1) -> str:
    return _sha256_prefix("PEQPRCPT", receipt_identity_payload(receipt))


def derive_execution_cohort_fingerprint(
    *,
    opportunity_ids: tuple[str, ...],
    risk_decision_ids: tuple[str, ...],
    fill_ids: tuple[str, ...],
) -> str:
    payload = {
        "opportunity_ids": list(opportunity_ids),
        "risk_decision_ids": list(risk_decision_ids),
        "fill_ids": list(fill_ids),
    }
    return _sha256_prefix("PEQCOHORT", payload)


def derive_qualification_report_id(
    *,
    qualification_spec_id: str,
    qualification_run_id: str,
    cohort_fingerprint: str,
    evaluation_as_of_ns: int,
    implementation_version: str,
) -> str:
    payload = {
        "qualification_spec_id": qualification_spec_id,
        "qualification_run_id": qualification_run_id,
        "cohort_fingerprint": cohort_fingerprint,
        "evaluation_as_of_ns": evaluation_as_of_ns,
        "implementation_version": implementation_version,
    }
    return _sha256_prefix("PEQREP", payload)
