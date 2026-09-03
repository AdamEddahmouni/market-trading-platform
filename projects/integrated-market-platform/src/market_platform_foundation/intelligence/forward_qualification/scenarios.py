"""Forward qualification adversarial scenarios (BUILD 26)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable

from ..persistence import InMemoryIntelligenceRepository
from .receipt import build_forward_prediction_receipt, validate_forward_integrity
from .types import EvidenceClass, ForwardIntegrityStatus, IntegrityFailureCode

from tests.intelligence.outcome_fixtures import HORIZON_5M, T, synthetic_final_forecast
from market_platform_foundation.intelligence.outcomes.ledger import build_prediction_ledger_entry
from market_platform_foundation.intelligence.outcomes.types import SettlementMode


class ScenarioStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(frozen=True)
class ScenarioResultV1:
    scenario_id: str
    status: ScenarioStatus
    expected: str
    observed: str
    details: dict[str, Any]


REQUIRED_SCENARIOS: tuple[str, ...] = (
    "F01",
    "F02",
    "F03",
    "F04",
    "F05",
    "F06",
    "F07",
    "F08",
    "F09",
    "F10",
)


def _scenario_f01_replay_masquerading() -> ScenarioResultV1:
    repo = InMemoryIntelligenceRepository()
    forecast = synthetic_final_forecast(repo)
    entry = build_prediction_ledger_entry(
        forecast,
        repo,
        mode=SettlementMode.ACTUAL_LIVE,
        registered_at_ns=forecast.decision_time_ns,
    )
    status, codes = validate_forward_integrity(
        forecast=forecast,
        ledger_entry=entry,
        evidence_class=EvidenceClass.REPLAY,
    )
    ok = status == ForwardIntegrityStatus.INVALID and IntegrityFailureCode.REPLAY_MASQUERADING_AS_FORWARD.value in codes
    return ScenarioResultV1(
        scenario_id="F01",
        status=ScenarioStatus.PASS if ok else ScenarioStatus.FAIL,
        expected="INVALID_FORWARD_INTEGRITY",
        observed=status.value,
        details={"codes": list(codes)},
    )


def _scenario_f02_counterfactual_masquerading() -> ScenarioResultV1:
    repo = InMemoryIntelligenceRepository()
    forecast = synthetic_final_forecast(repo)
    entry = build_prediction_ledger_entry(
        forecast,
        repo,
        mode=SettlementMode.COUNTERFACTUAL,
        registered_at_ns=forecast.decision_time_ns,
    )
    status, codes = validate_forward_integrity(
        forecast=forecast,
        ledger_entry=entry,
        evidence_class=EvidenceClass.COUNTERFACTUAL,
    )
    ok = (
        status == ForwardIntegrityStatus.INVALID
        and IntegrityFailureCode.COUNTERFACTUAL_MASQUERADING_AS_FORWARD.value in codes
    )
    return ScenarioResultV1(
        scenario_id="F02",
        status=ScenarioStatus.PASS if ok else ScenarioStatus.FAIL,
        expected="INVALID_FORWARD_INTEGRITY",
        observed=status.value,
        details={"codes": list(codes)},
    )


def _scenario_f03_ledger_after_target() -> ScenarioResultV1:
    repo = InMemoryIntelligenceRepository()
    forecast = synthetic_final_forecast(repo)
    late_ns = forecast.decision_time_ns + HORIZON_5M + 1
    entry = build_prediction_ledger_entry(
        forecast,
        repo,
        mode=SettlementMode.ACTUAL_LIVE,
        registered_at_ns=late_ns,
        reject_late_registration=False,
    )
    status, codes = validate_forward_integrity(
        forecast=forecast,
        ledger_entry=entry,
        evidence_class=EvidenceClass.ACTUAL_FORWARD,
    )
    ok = status == ForwardIntegrityStatus.INVALID and IntegrityFailureCode.LEDGER_AFTER_TARGET.value in codes
    return ScenarioResultV1(
        scenario_id="F03",
        status=ScenarioStatus.PASS if ok else ScenarioStatus.FAIL,
        expected="LEDGER_AFTER_TARGET",
        observed=status.value,
        details={"codes": list(codes)},
    )


def _scenario_f04_retroactive_forecast() -> ScenarioResultV1:
    repo = InMemoryIntelligenceRepository()
    forecast = synthetic_final_forecast(repo)
    entry = build_prediction_ledger_entry(
        forecast,
        repo,
        mode=SettlementMode.ACTUAL_LIVE,
        registered_at_ns=forecast.decision_time_ns,
    )
    outcome_known_ns = forecast.decision_time_ns
    status, codes = validate_forward_integrity(
        forecast=forecast,
        ledger_entry=entry,
        evidence_class=EvidenceClass.ACTUAL_FORWARD,
        outcome_known_at_ns=outcome_known_ns,
    )
    ok = status == ForwardIntegrityStatus.INVALID and IntegrityFailureCode.RETROACTIVE_FORECAST.value in codes
    return ScenarioResultV1(
        scenario_id="F04",
        status=ScenarioStatus.PASS if ok else ScenarioStatus.FAIL,
        expected="RETROACTIVE_FORECAST",
        observed=status.value,
        details={"codes": list(codes)},
    )


def _scenario_f05_valid_forward_receipt() -> ScenarioResultV1:
    repo = InMemoryIntelligenceRepository()
    forecast = synthetic_final_forecast(repo)
    entry = build_prediction_ledger_entry(
        forecast,
        repo,
        mode=SettlementMode.ACTUAL_LIVE,
        registered_at_ns=forecast.decision_time_ns,
    )
    receipt = build_forward_prediction_receipt(
        forecast=forecast,
        ledger_entry=entry,
        qualification_run_ref="FQRUN-test",
        recorded_at_ns=forecast.decision_time_ns,
    )
    ok = receipt.forward_integrity_status == ForwardIntegrityStatus.VALID
    return ScenarioResultV1(
        scenario_id="F05",
        status=ScenarioStatus.PASS if ok else ScenarioStatus.FAIL,
        expected="VALID",
        observed=receipt.forward_integrity_status.value,
        details={"receipt_id": receipt.receipt_id},
    )


def _scenario_f06_future_event_rejected() -> ScenarioResultV1:
    from market_platform_foundation.intelligence.temporal import inspect_temporal_integrity
    from tests.intelligence.test_signal_fixtures import trade_event

    decision_ns = T
    future_ns = decision_ns + 1
    event = trade_event(
        "future-trade",
        event_time_ns=future_ns,
        available_time_ns=future_ns,
        price=100.0,
        quantity=10,
    )
    report = inspect_temporal_integrity(event, decision_time_ns=decision_ns)
    ok = not report.eligible
    return ScenarioResultV1(
        scenario_id="F06",
        status=ScenarioStatus.PASS if ok else ScenarioStatus.FAIL,
        expected="FUTURE_EVENT_REJECTED",
        observed="eligible" if report.eligible else "rejected",
        details={"violations": [v.code for v in report.violations]},
    )


def _scenario_f07_execution_mode_none_required() -> ScenarioResultV1:
    from .run import build_forward_qualification_run
    from .spec import build_forward_qualification_spec

    spec = build_forward_qualification_spec(
        release_candidate_ref="abc",
        source_head="abc",
        qualification_start_ns=T,
    )
    try:
        build_forward_qualification_run(
            spec=spec,
            source_head="abc",
            run_start_ns=T,
            execution_mode="LIVE",
        )
        ok = False
    except ValueError:
        ok = True
    return ScenarioResultV1(
        scenario_id="F07",
        status=ScenarioStatus.PASS if ok else ScenarioStatus.FAIL,
        expected="EXECUTION_MODE_REJECTED",
        observed="rejected" if ok else "accepted",
        details={},
    )


def _scenario_f08_zero_training() -> ScenarioResultV1:
    from unittest import mock

    with mock.patch(
        "market_platform_foundation.intelligence.training.factory.TrainingFactory.generate_candidates"
    ) as generate:
        _scenario_f05_valid_forward_receipt()
        generate.assert_not_called()
    return ScenarioResultV1(
        scenario_id="F08",
        status=ScenarioStatus.PASS,
        expected="ZERO_TRAINING",
        observed="no_trainer_calls",
        details={},
    )


def _scenario_f09_zero_promotion() -> ScenarioResultV1:
    from unittest import mock

    with mock.patch(
        "market_platform_foundation.intelligence.promotion.engine.PromotionEngine.evaluate_promotion"
    ) as promote:
        _scenario_f05_valid_forward_receipt()
        promote.assert_not_called()
    return ScenarioResultV1(
        scenario_id="F09",
        status=ScenarioStatus.PASS,
        expected="ZERO_PROMOTION",
        observed="no_promotion_calls",
        details={},
    )


def _scenario_f10_champion_change_invalidates_run() -> ScenarioResultV1:
    from .integrity import detect_run_freeze_violation

    violation = detect_run_freeze_violation(
        initial_champion_ref="CHAMP-1",
        current_champion_ref="CHAMP-2",
        initial_policy_ref="POL-1",
        current_policy_ref="POL-1",
        initial_feature_schema_ref="FS-1",
        current_feature_schema_ref="FS-1",
    )
    ok = violation is not None and violation == IntegrityFailureCode.CHAMPION_CHANGED_MID_RUN.value
    return ScenarioResultV1(
        scenario_id="F10",
        status=ScenarioStatus.PASS if ok else ScenarioStatus.FAIL,
        expected="CHAMPION_CHANGED_MID_RUN",
        observed=violation or "none",
        details={},
    )


SCENARIO_REGISTRY: dict[str, Callable[[], ScenarioResultV1]] = {
    "F01": _scenario_f01_replay_masquerading,
    "F02": _scenario_f02_counterfactual_masquerading,
    "F03": _scenario_f03_ledger_after_target,
    "F04": _scenario_f04_retroactive_forecast,
    "F05": _scenario_f05_valid_forward_receipt,
    "F06": _scenario_f06_future_event_rejected,
    "F07": _scenario_f07_execution_mode_none_required,
    "F08": _scenario_f08_zero_training,
    "F09": _scenario_f09_zero_promotion,
    "F10": _scenario_f10_champion_change_invalidates_run,
}


def run_scenarios(scenario_ids: tuple[str, ...] | None = None) -> tuple[ScenarioResultV1, ...]:
    ids = scenario_ids or REQUIRED_SCENARIOS
    return tuple(SCENARIO_REGISTRY[sid]() for sid in ids)
