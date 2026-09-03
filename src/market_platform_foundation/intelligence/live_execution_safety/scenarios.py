"""Adversarial safety scenarios for BUILD 28."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION, ContractKind, ContractReference, IntelligenceScope, OpportunitySide, QualityState, QualitySummary
from ..contracts.opportunity import OpportunityV1
from ..contracts.trade_proposal import TradeProposalV1
from ..execution.types import ExposureSnapshot, RiskDecisionKind, RiskDecisionV1, RiskReasonCode
from .authorization import build_design_only_authorization, build_test_enabled_authorization_fixture
from .certification import certify_broker
from .broker_inventory import inventory_by_broker
from .dry_run import DryRunExecutionAdapter, LiveSubmitForbiddenError, ZeroSubmitGuard
from .gate import evaluate_live_execution_gate
from .health import build_broker_execution_health
from .kill_switch import build_production_kill_switch, build_test_inactive_kill_switch
from .order_intent import build_broker_order_intent
from .reconciliation import build_reconciliation_snapshot
from .translation import translate_broker_payload
from .types import (
    AccountEnvironment,
    LiveGateDecisionKind,
    LiveGateReasonCode,
)

T = 1_700_000_000_000_000_000
BROKER = "tradier.paper"
ACCOUNT_ENV = AccountEnvironment.SANDBOX
INSTRUMENT_ID = "inst-aapl"
SCOPE = IntelligenceScope(instrument_ids=(INSTRUMENT_ID,))


class ScenarioStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(frozen=True)
class ScenarioResultV1:
    scenario_id: str
    status: ScenarioStatus
    message: str = ""


def _fixture_opportunity(*, valid_until_ns: int | None = None) -> OpportunityV1:
    return OpportunityV1(
        opportunity_id="OPP-BUILD28-001",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        scope=SCOPE,
        created_at_ns=T,
        quality=QualitySummary(state=QualityState.GOOD),
        side=OpportunitySide.LONG,
        valid_until_ns=valid_until_ns or T + 60_000_000_000,
        source_forecast_refs=(ContractReference(kind=ContractKind.FORECAST.value, id="FCST-BUILD28-001"),),
    )


def _fixture_proposal(*, expires_at_ns: int | None = None) -> TradeProposalV1:
    return TradeProposalV1(
        proposal_id="TP-BUILD28-001",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        opportunity_id="OPP-BUILD28-001",
        execution_policy_id="EXECPOL-BUILD28",
        instrument_id=INSTRUMENT_ID,
        side="BUY",
        requested_quantity=10,
        requested_notional_minor=150_000,
        reference_price_minor=150_00,
        proposal_time_ns=T,
        expires_at_ns=expires_at_ns or T + 60_000_000_000,
        execution_mode="PAPER",
        opportunity_ref=ContractReference(
            kind=ContractKind.OPPORTUNITY.value,
            id="OPP-BUILD28-001",
        ),
    )


def _fixture_risk(*, approved_quantity: int = 8) -> RiskDecisionV1:
    return RiskDecisionV1(
        risk_decision_id="RISK-BUILD28-001",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        trade_proposal_id="TP-BUILD28-001",
        opportunity_id="OPP-BUILD28-001",
        execution_policy_id="EXECPOL-BUILD28",
        portfolio_snapshot_id="PORT-BUILD28",
        decision_time_ns=T,
        requested_quantity=10,
        requested_notional_minor=150_000,
        approved_quantity=approved_quantity,
        approved_notional_minor=120_000,
        decision=RiskDecisionKind.REDUCE if approved_quantity < 10 else RiskDecisionKind.APPROVE,
        reason_codes=(RiskReasonCode.SIZE_REDUCED,) if approved_quantity < 10 else (RiskReasonCode.RISK_APPROVED,),
        pre_trade_exposure=ExposureSnapshot(gross_exposure_minor=0, net_exposure_minor=0),
    )


def _full_gate_eval(**overrides):
    entry = inventory_by_broker(BROKER)
    cert = certify_broker(entry) if entry else None
    opp = _fixture_opportunity()
    prop = _fixture_proposal()
    risk = _fixture_risk()
    intent = build_broker_order_intent(
        trade_proposal=prop,
        risk_decision=risk,
        execution_policy_ref="EXECPOL-BUILD28",
        broker_target=BROKER,
        account_environment=ACCOUNT_ENV,
        decision_time_ns=T,
    )
    health = build_broker_execution_health(
        broker=BROKER,
        account_environment=ACCOUNT_ENV,
        as_of_ns=T,
    )
    auth = build_test_enabled_authorization_fixture(
        broker=BROKER,
        account_ref="acct-fp-test",
        effective_from_ns=T - 1,
        effective_until_ns=T + 3600_000_000_000,
    )
    defaults = dict(
        decision_time_ns=T,
        broker=BROKER,
        account_environment=ACCOUNT_ENV,
        runtime_activation_ref="TEST_RUNTIME",
        runtime_allows_live=True,
        authorization=auth,
        broker_certification=cert,
        opportunity=opp,
        trade_proposal=prop,
        risk_decision=risk,
        order_intent=intent,
        broker_health=health,
        reconciliation=None,
        kill_switch=build_test_inactive_kill_switch(effective_from_ns=T),
        production_config=False,
        allow_dry_run_in_test=True,
    )
    defaults.update(overrides)
    return evaluate_live_execution_gate(**defaults)


REQUIRED_SCENARIOS: tuple[str, ...] = (
    "missing_authorization",
    "disabled_authorization",
    "expired_authorization",
    "wrong_broker",
    "kill_switch_active",
    "unknown_environment",
    "risk_rejected",
    "reduced_risk_quantity",
    "duplicate_client_order_id",
    "reconciliation_unhealthy",
    "ambiguous_timeout_no_resubmit",
    "production_config_blocks",
    "idempotency_deterministic",
    "payload_deterministic",
    "zero_submit_guard",
)


def run_scenario(scenario_id: str) -> ScenarioResultV1:
    try:
        if scenario_id == "missing_authorization":
            decision = _full_gate_eval(authorization=None)
            if LiveGateReasonCode.LIVE_AUTHORIZATION_MISSING not in decision.reason_codes:
                return ScenarioResultV1(scenario_id, ScenarioStatus.FAIL, "expected missing auth block")
        elif scenario_id == "disabled_authorization":
            auth = build_design_only_authorization(
                broker=BROKER, account_ref="acct", effective_from_ns=T - 1, effective_until_ns=T + 1
            )
            decision = _full_gate_eval(authorization=auth)
            if LiveGateReasonCode.LIVE_AUTHORIZATION_DISABLED not in decision.reason_codes:
                return ScenarioResultV1(scenario_id, ScenarioStatus.FAIL, "expected disabled auth block")
        elif scenario_id == "expired_authorization":
            auth = build_test_enabled_authorization_fixture(
                broker=BROKER, account_ref="acct", effective_from_ns=T - 100, effective_until_ns=T - 1
            )
            decision = _full_gate_eval(authorization=auth)
            if LiveGateReasonCode.AUTHORIZATION_EXPIRED not in decision.reason_codes:
                return ScenarioResultV1(scenario_id, ScenarioStatus.FAIL, "expected expired auth block")
        elif scenario_id == "wrong_broker":
            auth = build_test_enabled_authorization_fixture(
                broker="other.broker", account_ref="acct", effective_from_ns=T - 1, effective_until_ns=T + 1
            )
            decision = _full_gate_eval(authorization=auth)
            if LiveGateReasonCode.AUTHORIZATION_SCOPE_MISMATCH not in decision.reason_codes:
                return ScenarioResultV1(scenario_id, ScenarioStatus.FAIL, "expected broker mismatch block")
        elif scenario_id == "kill_switch_active":
            decision = _full_gate_eval(kill_switch=build_production_kill_switch(effective_from_ns=T))
            if LiveGateReasonCode.KILL_SWITCH_ACTIVE not in decision.reason_codes:
                return ScenarioResultV1(scenario_id, ScenarioStatus.FAIL, "expected kill switch block")
        elif scenario_id == "unknown_environment":
            decision = _full_gate_eval(account_environment=AccountEnvironment.UNKNOWN)
            if LiveGateReasonCode.BROKER_ENVIRONMENT_UNKNOWN not in decision.reason_codes:
                return ScenarioResultV1(scenario_id, ScenarioStatus.FAIL, "expected unknown env fail closed")
        elif scenario_id == "risk_rejected":
            risk = RiskDecisionV1(
                risk_decision_id="RISK-BUILD28-REJECT",
                schema_version=INTELLIGENCE_SCHEMA_VERSION,
                trade_proposal_id="TP-BUILD28-001",
                opportunity_id="OPP-BUILD28-001",
                execution_policy_id="EXECPOL-BUILD28",
                portfolio_snapshot_id="PORT-BUILD28",
                decision_time_ns=T,
                requested_quantity=10,
                requested_notional_minor=150_000,
                approved_quantity=0,
                approved_notional_minor=0,
                decision=RiskDecisionKind.REJECT,
                reason_codes=(RiskReasonCode.RISK_REJECTED,),
            )
            decision = _full_gate_eval(risk_decision=risk, order_intent=None)
            if LiveGateReasonCode.RISK_NOT_APPROVED not in decision.reason_codes:
                return ScenarioResultV1(scenario_id, ScenarioStatus.FAIL, "expected risk reject block")
        elif scenario_id == "reduced_risk_quantity":
            prop = _fixture_proposal()
            risk = _fixture_risk(approved_quantity=8)
            intent = build_broker_order_intent(
                trade_proposal=prop,
                risk_decision=risk,
                execution_policy_ref="EXECPOL",
                broker_target=BROKER,
                account_environment=ACCOUNT_ENV,
                decision_time_ns=T,
            )
            if intent.quantity != 8:
                return ScenarioResultV1(scenario_id, ScenarioStatus.FAIL, "intent must use approved qty")
        elif scenario_id == "duplicate_client_order_id":
            prop = _fixture_proposal()
            risk = _fixture_risk()
            intent = build_broker_order_intent(
                trade_proposal=prop,
                risk_decision=risk,
                execution_policy_ref="EXECPOL",
                broker_target=BROKER,
                account_environment=ACCOUNT_ENV,
                decision_time_ns=T,
            )
            decision = _full_gate_eval(
                order_intent=intent,
                used_client_order_ids=frozenset({intent.client_order_id}),
            )
            if LiveGateReasonCode.DUPLICATE_CLIENT_ORDER_ID not in decision.reason_codes:
                return ScenarioResultV1(scenario_id, ScenarioStatus.FAIL, "expected duplicate client id block")
        elif scenario_id == "reconciliation_unhealthy":
            recon = build_reconciliation_snapshot(
                broker=BROKER,
                account_environment=ACCOUNT_ENV,
                as_of_ns=T,
                local_open_intents=("local-1",),
                broker_open_orders=(),
            )
            decision = _full_gate_eval(reconciliation=recon)
            if LiveGateReasonCode.RECONCILIATION_UNHEALTHY not in decision.reason_codes:
                return ScenarioResultV1(scenario_id, ScenarioStatus.FAIL, "expected reconciliation block")
        elif scenario_id == "ambiguous_timeout_no_resubmit":
            guard = ZeroSubmitGuard()
            adapter = DryRunExecutionAdapter(guard=guard)
            prop = _fixture_proposal()
            risk = _fixture_risk()
            intent = build_broker_order_intent(
                trade_proposal=prop,
                risk_decision=risk,
                execution_policy_ref="EXECPOL",
                broker_target=BROKER,
                account_environment=ACCOUNT_ENV,
                decision_time_ns=T,
            )
            result = adapter.simulate_ambiguous_submission(intent, broker_symbol="AAPL", decision_time_ns=T)
            if "RECONCILE_REQUIRED" not in result.reason_codes:
                return ScenarioResultV1(scenario_id, ScenarioStatus.FAIL, "expected reconcile required")
            guard.assert_zero()
        elif scenario_id == "production_config_blocks":
            decision = _full_gate_eval(
                production_config=True,
                kill_switch=build_test_inactive_kill_switch(effective_from_ns=T),
            )
            if decision.decision != LiveGateDecisionKind.BLOCK:
                return ScenarioResultV1(scenario_id, ScenarioStatus.FAIL, "production must block")
        elif scenario_id == "idempotency_deterministic":
            prop = _fixture_proposal()
            risk = _fixture_risk()
            ids = set()
            for _ in range(100):
                intent = build_broker_order_intent(
                    trade_proposal=prop,
                    risk_decision=risk,
                    execution_policy_ref="EXECPOL",
                    broker_target=BROKER,
                    account_environment=ACCOUNT_ENV,
                    decision_time_ns=T,
                )
                ids.add(intent.client_order_id)
            if len(ids) != 1:
                return ScenarioResultV1(scenario_id, ScenarioStatus.FAIL, "client order id not deterministic")
        elif scenario_id == "payload_deterministic":
            prop = _fixture_proposal()
            risk = _fixture_risk()
            intent = build_broker_order_intent(
                trade_proposal=prop,
                risk_decision=risk,
                execution_policy_ref="EXECPOL",
                broker_target=BROKER,
                account_environment=ACCOUNT_ENV,
                decision_time_ns=T,
            )
            hashes = set()
            for _ in range(10):
                _, h = translate_broker_payload(intent, broker_symbol="AAPL", decision_time_ns=T)
                hashes.add(h)
            if len(hashes) != 1:
                return ScenarioResultV1(scenario_id, ScenarioStatus.FAIL, "payload hash not deterministic")
        elif scenario_id == "zero_submit_guard":
            guard = ZeroSubmitGuard()
            try:
                guard.record_submit("place_order")
                return ScenarioResultV1(scenario_id, ScenarioStatus.FAIL, "guard should have raised")
            except LiveSubmitForbiddenError:
                if guard.real_submit_count != 1:
                    return ScenarioResultV1(scenario_id, ScenarioStatus.FAIL, "submit should be recorded before raise")
        else:
            return ScenarioResultV1(scenario_id, ScenarioStatus.FAIL, f"unknown scenario {scenario_id}")
        return ScenarioResultV1(scenario_id, ScenarioStatus.PASS)
    except Exception as exc:
        return ScenarioResultV1(scenario_id, ScenarioStatus.FAIL, str(exc))


def run_all_scenarios() -> tuple[ScenarioResultV1, ...]:
    return tuple(run_scenario(sid) for sid in REQUIRED_SCENARIOS)
