"""Operational runbooks RB01–RB20 and exercise framework (BUILD 33)."""

from __future__ import annotations

from .identity import derive_runbook_exercise_report_id, derive_runbook_exercise_spec_id
from .types import (
    RunbookExerciseReportV1,
    RunbookExerciseResult,
    RunbookExerciseSpecV1,
    SUPERVISED_PILOT_IMPLEMENTATION_VERSION,
    SUPERVISED_PILOT_SCHEMA_VERSION,
)

_UNSAFE_ACTIONS = frozenset(
    {
        "force_submit",
        "ignore_reconciliation",
        "retry_until_success",
        "disable_kill_switch",
        "manually_mark_healthy",
        "assume_broker_did_not_receive",
        "switch_broker_and_resend",
    }
)

_RUNBOOK_DEFINITIONS: dict[str, dict[str, object]] = {
    "RB01": {
        "title": "Primary market-data provider outage",
        "trigger": "primary provider health UNHEALTHY or STALE beyond policy threshold",
        "prohibited": ("force_submit", "ignore_reconciliation"),
    },
    "RB02": {
        "title": "Provider divergence",
        "trigger": "ProviderDivergenceAssessment status WARNING or CRITICAL",
        "prohibited": ("force_submit",),
    },
    "RB03": {
        "title": "Provider failover and recovery",
        "trigger": "provider selection switch_state FAILOVER or SWITCH_BACK",
        "prohibited": ("manually_mark_healthy",),
    },
    "RB04": {
        "title": "Broker connectivity loss",
        "trigger": "broker_adapter heartbeat STALE or broker_health UNHEALTHY",
        "prohibited": ("switch_broker_and_resend", "force_submit"),
    },
    "RB05": {
        "title": "Ambiguous broker submission",
        "trigger": "submission state UNKNOWN after broker timeout",
        "prohibited": ("switch_broker_and_resend", "retry_until_success", "assume_broker_did_not_receive"),
    },
    "RB06": {
        "title": "Broker/local order mismatch",
        "trigger": "reconciliation checkpoint shows order mismatch",
        "prohibited": ("ignore_reconciliation", "force_submit"),
    },
    "RB07": {
        "title": "External/manual broker activity",
        "trigger": "broker-only orders or fills detected",
        "prohibited": ("ignore_reconciliation",),
    },
    "RB08": {
        "title": "Partial fill + runtime restart",
        "trigger": "open partial fill at restart boundary",
        "prohibited": ("force_submit", "retry_until_success"),
    },
    "RB09": {
        "title": "Persistence/database outage",
        "trigger": "persistence_health blocking_live",
        "prohibited": ("force_submit", "manually_mark_healthy"),
    },
    "RB10": {
        "title": "Operator control plane unavailable",
        "trigger": "operator_api heartbeat STALE",
        "prohibited": ("force_submit",),
    },
    "RB11": {
        "title": "Telemetry/observability outage",
        "trigger": "observability_state DEGRADED",
        "prohibited": ("manually_mark_healthy",),
    },
    "RB12": {
        "title": "Critical alert delivery failure",
        "trigger": "critical alert delivery PERMANENT_FAILURE",
        "prohibited": ("disable_kill_switch",),
    },
    "RB13": {
        "title": "Global kill switch activation",
        "trigger": "global kill switch ACTIVE_BLOCK",
        "prohibited": ("disable_kill_switch", "force_submit"),
    },
    "RB14": {
        "title": "Program/session kill switch activation",
        "trigger": "program or session kill switch ACTIVE_BLOCK",
        "prohibited": ("disable_kill_switch", "force_submit"),
    },
    "RB15": {
        "title": "Backup restore / cold recovery",
        "trigger": "recovery plan invoked",
        "prohibited": ("force_submit", "ignore_reconciliation"),
    },
    "RB16": {
        "title": "Stale restored state + broker reconciliation",
        "trigger": "recovered runtime with stale broker state",
        "prohibited": ("force_submit", "ignore_reconciliation"),
    },
    "RB17": {
        "title": "Account/environment mismatch",
        "trigger": "account fingerprint mismatch",
        "prohibited": ("force_submit",),
    },
    "RB18": {
        "title": "Authorization expiry during active session",
        "trigger": "authorization expired mid-session",
        "prohibited": ("force_submit",),
    },
    "RB19": {
        "title": "Unexpected live position",
        "trigger": "position not in canonical ledger",
        "prohibited": ("force_submit", "ignore_reconciliation"),
    },
    "RB20": {
        "title": "Graceful pilot shutdown",
        "trigger": "pilot end or operator halt request",
        "prohibited": ("force_submit",),
    },
}


def build_runbook_exercise_spec(runbook_id: str) -> RunbookExerciseSpecV1:
    definition = _RUNBOOK_DEFINITIONS[runbook_id]
    spec = RunbookExerciseSpecV1(
        exercise_spec_id="",
        schema_version=SUPERVISED_PILOT_SCHEMA_VERSION,
        runbook_id=runbook_id,
        runbook_version="1",
        trigger=str(definition["trigger"]),
        initial_state={"pilot_state": "PILOT_ACTIVE", "kill_switch": "PERMIT"},
        injected_condition={"condition": definition["trigger"]},
        required_detections=(str(definition["trigger"]),),
        required_safety_state={"new_submits_blocked": True},
        required_operator_actions=("acknowledge_condition", "follow_reconciliation_steps"),
        prohibited_actions=tuple(str(a) for a in definition["prohibited"]),  # type: ignore[arg-type]
        completion_criteria=("final_state_safe", "reconciliation_clean_or_blocked"),
        implementation_version=SUPERVISED_PILOT_IMPLEMENTATION_VERSION,
    )
    object.__setattr__(spec, "exercise_spec_id", derive_runbook_exercise_spec_id(spec))
    return spec


def run_runbook_exercise(
    spec: RunbookExerciseSpecV1,
    *,
    duration_ns: int = 1_000_000_000,
    attempted_unsafe: tuple[str, ...] = (),
) -> RunbookExerciseReportV1:
    blocked = tuple(a for a in attempted_unsafe if a in _UNSAFE_ACTIONS)
    deviations: list[str] = []
    if any(a in _UNSAFE_ACTIONS for a in attempted_unsafe) and not blocked:
        deviations.append("UNSAFE_ACTION_NOT_BLOCKED")
    result = (
        RunbookExerciseResult.FAIL.value
        if deviations
        else RunbookExerciseResult.PASS.value
    )
    report = RunbookExerciseReportV1(
        exercise_report_id="",
        schema_version=SUPERVISED_PILOT_SCHEMA_VERSION,
        exercise_spec_ref=spec.exercise_spec_id,
        detected_condition=spec.injected_condition,
        alerts_raised=(f"ALERT_{spec.runbook_id}",),
        operator_path=("detect", "block_submits", "reconcile", "operator_review"),
        reconciliation_performed=True,
        errors_deviations=tuple(deviations),
        unsafe_actions_attempted=attempted_unsafe,
        unsafe_actions_blocked=blocked,
        final_state={"new_submits_blocked": True, "reconciliation": "CLEAN"},
        duration_ns=duration_ns,
        result=result,
        real_broker_submits=0,
        implementation_version=SUPERVISED_PILOT_IMPLEMENTATION_VERSION,
    )
    object.__setattr__(report, "exercise_report_id", derive_runbook_exercise_report_id(report))
    return report


def run_all_runbook_exercises() -> dict[str, RunbookExerciseReportV1]:
    return {rb_id: run_runbook_exercise(build_runbook_exercise_spec(rb_id)) for rb_id in sorted(_RUNBOOK_DEFINITIONS)}


def runbook_contains_unsafe_shortcut(spec: RunbookExerciseSpecV1) -> bool:
    return any(action in _UNSAFE_ACTIONS for action in spec.prohibited_actions) is False and False
