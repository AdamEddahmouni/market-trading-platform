"""Deterministic prospective fixture lifecycle (BUILD 26)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..evaluation.service import EvaluationService
from ..evaluation.types import EvaluationSpec, ProbabilityView
from ..outcomes.service import OutcomeSettlementService, PredictionLedgerService
from ..outcomes.types import SettlementMode, SettlementStatus
from ..persistence import InMemoryIntelligenceRepository
from .receipt import build_forward_prediction_receipt
from .report import build_forward_qualification_report
from .run import build_forward_qualification_run
from .spec import build_forward_qualification_spec
from .types import EvidenceClass, ForwardIntegrityStatus

from tests.intelligence.outcome_fixtures import (
    HORIZON_5M,
    ONE_MIN,
    T,
    cutoff_for,
    seed_terminal_trade,
    synthetic_final_forecast,
    target_time_for,
)


@dataclass(frozen=True)
class FixtureLifecycleResult:
    spec_id: str
    run_id: str
    report_id: str
    forecast_id: str
    ledger_entry_id: str
    outcome_id: str | None
    pending_before_horizon: bool
    settled_after_horizon: bool
    integrity_status: ForwardIntegrityStatus
    metadata: dict[str, Any]


def run_prospective_fixture_lifecycle(
    *,
    release_candidate_ref: str,
    source_head: str,
    qualification_start_ns: int = T,
) -> FixtureLifecycleResult:
    repo = InMemoryIntelligenceRepository()
    forecast = synthetic_final_forecast(repo, forecast_id="fc-forward-fixture")
    spec = build_forward_qualification_spec(
        release_candidate_ref=release_candidate_ref,
        source_head=source_head,
        qualification_start_ns=qualification_start_ns,
        minimum_prediction_count=1,
        minimum_labelable_count=1,
        minimum_duration_ns=HORIZON_5M,
    )
    run = build_forward_qualification_run(
        spec=spec,
        source_head=source_head,
        run_start_ns=qualification_start_ns,
        data_mode="FIXTURE_REPLAY",
    )

    ledger_service = PredictionLedgerService(repo)
    settlement_service = OutcomeSettlementService(repo)
    register_result = ledger_service.register_forecast(
        forecast,
        now_ns=forecast.decision_time_ns,
        mode=SettlementMode.ACTUAL_LIVE,
        scenario_id="BUILD26_FORWARD_FIXTURE",
    )
    if not hasattr(register_result, "ledger_entry_id"):
        raise AssertionError(f"ledger registration failed: {register_result}")
    ledger_entry = register_result

    receipt = build_forward_prediction_receipt(
        forecast=forecast,
        ledger_entry=ledger_entry,
        qualification_run_ref=run.qualification_run_id,
        recorded_at_ns=forecast.decision_time_ns,
        evidence_class=EvidenceClass.ACTUAL_FORWARD,
    )

    target_time = target_time_for(forecast)
    mid_horizon_ns = forecast.decision_time_ns + (HORIZON_5M // 2)
    pending_status = settlement_service.inspect_settlement(ledger_entry, now_ns=mid_horizon_ns)
    pending_before_horizon = pending_status == SettlementStatus.NOT_DUE

    terminal_time = target_time
    seed_terminal_trade(
        repo,
        price=101.0,
        event_time_ns=terminal_time,
        available_time_ns=terminal_time,
        event_id="terminal-forward-fixture",
    )
    settle_ns = cutoff_for(forecast) + ONE_MIN
    settle_result = settlement_service.settle(ledger_entry, now_ns=settle_ns)
    settled_after_horizon = settle_result.status == SettlementStatus.SETTLED

    evaluation_service = EvaluationService(repo)
    eval_spec = EvaluationSpec(
        evaluation_as_of_ns=settle_ns,
        decision_start_ns=forecast.decision_time_ns - 1,
        decision_end_ns=forecast.decision_time_ns + 1,
        target_kind=forecast.target.target_kind,
        horizon_ns=forecast.horizon.duration_ns,
        mode=SettlementMode.ACTUAL_LIVE.value,
        probability_view=ProbabilityView.OPERATIONAL,
        scenario_id="BUILD26_FORWARD_FIXTURE",
    )
    evaluation_report = evaluation_service.evaluate(eval_spec)
    qualification_report = build_forward_qualification_report(
        spec=spec,
        run=run,
        repository=repo,
        receipts=(receipt,),
        evaluation_as_of_ns=settle_ns,
        evaluation_report_id=evaluation_report.report_id,
    )

    return FixtureLifecycleResult(
        spec_id=spec.qualification_spec_id,
        run_id=run.qualification_run_id,
        report_id=qualification_report.qualification_report_id,
        forecast_id=forecast.forecast_id,
        ledger_entry_id=ledger_entry.ledger_entry_id,
        outcome_id=settle_result.outcome_id,
        pending_before_horizon=pending_before_horizon,
        settled_after_horizon=settled_after_horizon,
        integrity_status=receipt.forward_integrity_status,
        metadata={
            "evaluation_report_id": evaluation_report.report_id,
            "disposition": qualification_report.qualification_disposition.value,
        },
    )
