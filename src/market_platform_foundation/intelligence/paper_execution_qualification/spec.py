"""Paper execution qualification spec builder (BUILD 27)."""

from __future__ import annotations

from market_platform_foundation.intelligence.execution import build_execution_policy
from market_platform_foundation.intelligence.opportunity import build_opportunity_policy
from market_platform_foundation.intelligence.system_acceptance import contract_inventory_hash
from tests.intelligence.promotion_fixtures import DEFAULT_SCOPE

from .identity import derive_qualification_spec_id
from .initial_portfolio import build_initial_paper_portfolio_state
from .types import (
    DEFAULT_HORIZON_NS,
    DEFAULT_INSTRUMENT_UNIVERSE,
    DEFAULT_MINIMUM_DURATION_NS,
    DEFAULT_MINIMUM_FILLS,
    DEFAULT_MINIMUM_OPPORTUNITIES,
    DEFAULT_MINIMUM_ORDERS,
    DEFAULT_MINIMUM_RISK_DECISIONS,
    DEFAULT_TARGET_KIND,
    PAPER_EXECUTION_QUALIFICATION_IMPLEMENTATION_VERSION,
    PAPER_EXECUTION_QUALIFICATION_SCHEMA_VERSION,
    PaperExecutionQualificationSpecV1,
    QualificationKind,
)

BUILD26_BRANCH = "build-26-forward-shadow-qualification"
FILL_POLICY_REF = "BarConservativeSimulator/phase7.bar-conservative/1.1.0"
FEE_POLICY_REF = "ZERO_FEE_PAPER"


def build_paper_execution_qualification_spec(
    *,
    source_build26_ref: str,
    source_release_candidate_ref: str,
    source_head: str,
    qualification_start_ns: int,
    qualification_end_ns: int | None = None,
    allowed_forward_qualification_runs: tuple[str, ...] = (),
    instrument_universe: tuple[str, ...] = DEFAULT_INSTRUMENT_UNIVERSE,
    target_kind: str = DEFAULT_TARGET_KIND,
    horizon_ns: int = DEFAULT_HORIZON_NS,
    minimum_opportunities: int = DEFAULT_MINIMUM_OPPORTUNITIES,
    minimum_risk_decisions: int = DEFAULT_MINIMUM_RISK_DECISIONS,
    minimum_orders: int = DEFAULT_MINIMUM_ORDERS,
    minimum_fills: int = DEFAULT_MINIMUM_FILLS,
    minimum_duration_ns: int = DEFAULT_MINIMUM_DURATION_NS,
    opportunity_policy: object | None = None,
    execution_policy: object | None = None,
    initial_portfolio: object | None = None,
) -> PaperExecutionQualificationSpecV1:
    opp_policy = opportunity_policy or build_opportunity_policy(champion_scope=DEFAULT_SCOPE)
    exec_policy = execution_policy or build_execution_policy()
    portfolio_state = initial_portfolio or build_initial_paper_portfolio_state()

    spec = PaperExecutionQualificationSpecV1(
        qualification_spec_id="pending",
        schema_version=PAPER_EXECUTION_QUALIFICATION_SCHEMA_VERSION,
        source_build26_ref=source_build26_ref,
        source_release_candidate_ref=source_release_candidate_ref,
        source_head=source_head,
        contract_inventory_hash=contract_inventory_hash(),
        qualification_kind=QualificationKind.PROSPECTIVE_PAPER_EXECUTION,
        allowed_forward_qualification_runs=allowed_forward_qualification_runs,
        instrument_universe=instrument_universe,
        target_kind=target_kind,
        horizon_ns=horizon_ns,
        opportunity_policy_ref=opp_policy.opportunity_policy_id,
        execution_policy_ref=exec_policy.execution_policy_id,
        fill_policy_ref=FILL_POLICY_REF,
        fee_policy_ref=FEE_POLICY_REF,
        initial_portfolio_state_ref=portfolio_state.state_id,
        minimum_opportunities=minimum_opportunities,
        minimum_risk_decisions=minimum_risk_decisions,
        minimum_orders=minimum_orders,
        minimum_fills=minimum_fills,
        minimum_duration_ns=minimum_duration_ns,
        required_data_mode="LIVE_OBSERVATIONAL",
        required_execution_mode="PAPER",
        required_execution_authority="PAPER_ONLY",
        implementation_version=PAPER_EXECUTION_QUALIFICATION_IMPLEMENTATION_VERSION,
        metadata={
            "build": "BUILD_27_PAPER_EXECUTION_QUALIFICATION",
            "qualification_start_ns": qualification_start_ns,
            "qualification_end_ns": qualification_end_ns,
        },
    )
    spec_id = derive_qualification_spec_id(spec)
    return PaperExecutionQualificationSpecV1(
        qualification_spec_id=spec_id,
        schema_version=spec.schema_version,
        source_build26_ref=spec.source_build26_ref,
        source_release_candidate_ref=spec.source_release_candidate_ref,
        source_head=spec.source_head,
        contract_inventory_hash=spec.contract_inventory_hash,
        qualification_kind=spec.qualification_kind,
        allowed_forward_qualification_runs=spec.allowed_forward_qualification_runs,
        instrument_universe=spec.instrument_universe,
        target_kind=spec.target_kind,
        horizon_ns=spec.horizon_ns,
        opportunity_policy_ref=spec.opportunity_policy_ref,
        execution_policy_ref=spec.execution_policy_ref,
        fill_policy_ref=spec.fill_policy_ref,
        fee_policy_ref=spec.fee_policy_ref,
        initial_portfolio_state_ref=spec.initial_portfolio_state_ref,
        minimum_opportunities=spec.minimum_opportunities,
        minimum_risk_decisions=spec.minimum_risk_decisions,
        minimum_orders=spec.minimum_orders,
        minimum_fills=spec.minimum_fills,
        minimum_duration_ns=spec.minimum_duration_ns,
        required_data_mode=spec.required_data_mode,
        required_execution_mode=spec.required_execution_mode,
        required_execution_authority=spec.required_execution_authority,
        implementation_version=spec.implementation_version,
        metadata=spec.metadata,
    )
