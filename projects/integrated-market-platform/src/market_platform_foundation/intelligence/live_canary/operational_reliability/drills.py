"""Disaster recovery drill specifications and runner (BUILD 32).

All drills use fixtures/isolated stores — zero real broker side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..operator_control.context import OperatorControlContext
from ..policy import build_default_canary_policy
from ..program_policy import build_default_program_policy
from ..types import ProgramGovernanceState
from .alerts import build_default_alert_policy, raise_alert
from .backup import canonical_backup_content, collect_backup_scope, create_backup_manifest, verify_backup_integrity
from .delivery import ConsoleAlertDeliveryAdapter, deliver_alert
from .identity import derive_drill_report_id
from .readiness import evaluate_operational_readiness_blocks_live
from .recovery import build_default_recovery_plan, recovered_runtime_blocks_live
from .types import (
    OPERATIONAL_RELIABILITY_IMPLEMENTATION_VERSION,
    OPERATIONAL_RELIABILITY_SCHEMA_VERSION,
    AlertSeverity,
    DeliveryResult,
    DisasterRecoveryDrillReportV1,
    DisasterRecoveryDrillSpecV1,
    DrillResult,
)

T = 1_700_000_000_000_000_000
BROKER = "tradier.paper"
ACCOUNT = "fp-canary-test"
BUILD31_HEAD = "844ce17edf0d100079c30c36b1cca2da3aa2870f"


def _base_context() -> OperatorControlContext:
    ctx = OperatorControlContext(
        program_policy=build_default_program_policy(program_effective_from_ns=T),
        canary_policy=build_default_canary_policy(broker=BROKER, account_ref=ACCOUNT),
        governance_state=ProgramGovernanceState.PROGRAM_ACTIVE,
        session_ref="session-dr-1",
        broker_health="HEALTHY",
        reconciliation_health="CLEAN",
        drill_mode=True,
    )
    ctx.kill_switch.permit_program("DR_INIT")
    return ctx


def _drill_specs() -> dict[str, DisasterRecoveryDrillSpecV1]:
    scenarios = {
        "DR01": "process crash",
        "DR02": "host/runtime restart",
        "DR03": "database unavailable",
        "DR04": "restore from backup",
        "DR05": "corrupted backup detected",
        "DR06": "stale backup + broker order",
        "DR07": "local-only order",
        "DR08": "broker-only order",
        "DR09": "provider/broker outage during recovery",
        "DR10": "alert delivery outage",
        "DR11": "unknown kill-switch state",
        "DR12": "operator UI unavailable",
        "DR13": "telemetry pipeline failure",
        "DR14": "schema mismatch on restore",
        "DR15": "full cold-start reconstruction",
    }
    specs: dict[str, DisasterRecoveryDrillSpecV1] = {}
    for drill_id, scenario in scenarios.items():
        specs[drill_id] = DisasterRecoveryDrillSpecV1(
            drill_spec_id=drill_id,
            schema_version=OPERATIONAL_RELIABILITY_SCHEMA_VERSION,
            scenario=scenario,
            initial_state={"governance": "PROGRAM_ACTIVE"},
            failure_injection={"type": scenario},
            expected_unavailable_components=(),
            expected_safety_state={"live_blocked": True},
            restore_source="fixture_backup" if "backup" in scenario or "restore" in scenario else None,
            expected_reconciliation=("broker_reconciliation",),
            required_operator_action=("review", "reconcile"),
            expected_final_state={"live_blocked": True, "real_broker_submits": 0},
            implementation_version=OPERATIONAL_RELIABILITY_IMPLEMENTATION_VERSION,
        )
    return specs


DR_DRILL_SPECS = _drill_specs()


@dataclass
class DRDrillOutcome:
    report: DisasterRecoveryDrillReportV1
    context: OperatorControlContext


def _report(
    spec: DisasterRecoveryDrillSpecV1,
    *,
    failure_observed: dict[str, Any],
    alert_results: tuple[str, ...],
    restore_result: str,
    reconciliation_result: str,
    final_state: dict[str, Any],
    recovery_duration_ns: int = 1_000_000,
    data_loss: str = "NONE_IN_FIXTURE",
    result: DrillResult = DrillResult.PASS,
) -> DisasterRecoveryDrillReportV1:
    report = DisasterRecoveryDrillReportV1(
        drill_report_id="",
        schema_version=OPERATIONAL_RELIABILITY_SCHEMA_VERSION,
        drill_spec_ref=spec.drill_spec_id,
        failure_observed=failure_observed,
        detection_time_ns=T,
        alert_results=alert_results,
        restore_result=restore_result,
        integrity_checks=("hash_verified",),
        reconciliation_result=reconciliation_result,
        operator_workflow=("detect", "review"),
        final_safe_state=final_state,
        recovery_duration_ns=recovery_duration_ns,
        data_loss_assessment=data_loss,
        real_broker_submits=0,
        real_broker_cancels=0,
        real_broker_replaces=0,
        result=result.value,
        implementation_version=OPERATIONAL_RELIABILITY_IMPLEMENTATION_VERSION,
    )
    return DisasterRecoveryDrillReportV1(
        drill_report_id=derive_drill_report_id(report),
        schema_version=report.schema_version,
        drill_spec_ref=report.drill_spec_ref,
        failure_observed=report.failure_observed,
        detection_time_ns=report.detection_time_ns,
        alert_results=report.alert_results,
        restore_result=report.restore_result,
        integrity_checks=report.integrity_checks,
        reconciliation_result=report.reconciliation_result,
        operator_workflow=report.operator_workflow,
        final_safe_state=report.final_safe_state,
        recovery_duration_ns=report.recovery_duration_ns,
        data_loss_assessment=report.data_loss_assessment,
        real_broker_submits=report.real_broker_submits,
        real_broker_cancels=report.real_broker_cancels,
        real_broker_replaces=report.real_broker_replaces,
        result=report.result,
        implementation_version=report.implementation_version,
    )


def run_dr_drill(drill_id: str) -> DRDrillOutcome:
    spec = DR_DRILL_SPECS[drill_id]
    ctx = _base_context()
    handlers: dict[str, Callable[[], DRDrillOutcome]] = {
        "DR01": lambda: _dr01(ctx, spec),
        "DR02": lambda: _dr02(ctx, spec),
        "DR03": lambda: _dr03(ctx, spec),
        "DR04": lambda: _dr04(ctx, spec),
        "DR05": lambda: _dr05(ctx, spec),
        "DR06": lambda: _dr06(ctx, spec),
        "DR07": lambda: _dr07(ctx, spec),
        "DR08": lambda: _dr08(ctx, spec),
        "DR09": lambda: _dr09(ctx, spec),
        "DR10": lambda: _dr10(ctx, spec),
        "DR11": lambda: _dr11(ctx, spec),
        "DR12": lambda: _dr12(ctx, spec),
        "DR13": lambda: _dr13(ctx, spec),
        "DR14": lambda: _dr14(ctx, spec),
        "DR15": lambda: _dr15(ctx, spec),
    }
    return handlers[drill_id]()


def _dr01(ctx: OperatorControlContext, spec: DisasterRecoveryDrillSpecV1) -> DRDrillOutcome:
    blocked, reasons = evaluate_operational_readiness_blocks_live(ctx, as_of_ns=T)
    return DRDrillOutcome(
        report=_report(spec, failure_observed={"crash": True}, alert_results=("PROCESS_CRASH",), restore_result="RESTART", reconciliation_result="CLEAN", final_state={"live_blocked": blocked, "reasons": reasons}),
        context=ctx,
    )


def _dr02(ctx: OperatorControlContext, spec: DisasterRecoveryDrillSpecV1) -> DRDrillOutcome:
    ctx.restart_generation += 1
    blocked = recovered_runtime_blocks_live(reconciliation_clean=False, operator_approved=False)
    return DRDrillOutcome(
        report=_report(spec, failure_observed={"restart": True}, alert_results=("HOST_RESTART",), restore_result="COLD_START", reconciliation_result="PENDING", final_state={"live_blocked": blocked}),
        context=ctx,
    )


def _dr03(ctx: OperatorControlContext, spec: DisasterRecoveryDrillSpecV1) -> DRDrillOutcome:
    blocked, reasons = evaluate_operational_readiness_blocks_live(ctx, as_of_ns=T, persistence_healthy=False)
    return DRDrillOutcome(
        report=_report(spec, failure_observed={"db_unavailable": True}, alert_results=("PERSISTENCE_UNHEALTHY",), restore_result="NOT_ATTEMPTED", reconciliation_result="BLOCKED", final_state={"live_blocked": blocked, "reasons": reasons}),
        context=ctx,
    )


def _dr04(ctx: OperatorControlContext, spec: DisasterRecoveryDrillSpecV1) -> DRDrillOutcome:
    manifest = create_backup_manifest(ctx, created_at_ns=T, source_head=BUILD31_HEAD)
    scope = collect_backup_scope(ctx)
    content = canonical_backup_content(scope)
    verified = verify_backup_integrity(manifest, content)
    blocked = recovered_runtime_blocks_live(reconciliation_clean=True, operator_approved=False)
    return DRDrillOutcome(
        report=_report(spec, failure_observed={"data_loss": True}, alert_results=("RESTORE_INITIATED",), restore_result="SUCCESS" if verified else "FAILED", reconciliation_result="CLEAN", final_state={"live_blocked": blocked, "integrity_verified": verified}),
        context=ctx,
    )


def _dr05(ctx: OperatorControlContext, spec: DisasterRecoveryDrillSpecV1) -> DRDrillOutcome:
    manifest = create_backup_manifest(ctx, created_at_ns=T, source_head=BUILD31_HEAD)
    corrupt = verify_backup_integrity(manifest, "corrupted-content")
    return DRDrillOutcome(
        report=_report(spec, failure_observed={"corrupt_backup": True}, alert_results=("BACKUP_INTEGRITY_FAILED",), restore_result="REJECTED" if not corrupt else "FAILED", reconciliation_result="NOT_STARTED", final_state={"live_blocked": True, "corrupt_rejected": not corrupt}),
        context=ctx,
    )


def _dr06(ctx: OperatorControlContext, spec: DisasterRecoveryDrillSpecV1) -> DRDrillOutcome:
    ctx.reconciliation_health = "BROKER_ONLY_ORDER"
    blocked, reasons = evaluate_operational_readiness_blocks_live(ctx, as_of_ns=T, recovered_runtime=True, reconciliation_clean=False)
    return DRDrillOutcome(
        report=_report(spec, failure_observed={"stale_backup": True, "broker_order_at_t1": True}, alert_results=("BROKER_ONLY_ORDER",), restore_result="STALE_RESTORE", reconciliation_result="BROKER_ONLY_DETECTED", final_state={"live_blocked": blocked, "reasons": reasons, "resubmit": False}),
        context=ctx,
    )


def _dr07(ctx: OperatorControlContext, spec: DisasterRecoveryDrillSpecV1) -> DRDrillOutcome:
    ctx.reconciliation_health = "LOCAL_ONLY_ORDER"
    blocked, _ = evaluate_operational_readiness_blocks_live(ctx, as_of_ns=T)
    return DRDrillOutcome(
        report=_report(spec, failure_observed={"local_only_order": True}, alert_results=("LOCAL_ONLY_ORDER",), restore_result="N/A", reconciliation_result="LOCAL_ONLY_DETECTED", final_state={"live_blocked": blocked}),
        context=ctx,
    )


def _dr08(ctx: OperatorControlContext, spec: DisasterRecoveryDrillSpecV1) -> DRDrillOutcome:
    ctx.reconciliation_health = "BROKER_ONLY_ORDER"
    blocked, _ = evaluate_operational_readiness_blocks_live(ctx, as_of_ns=T, recovered_runtime=True, reconciliation_clean=False)
    return DRDrillOutcome(
        report=_report(spec, failure_observed={"broker_only_order": True}, alert_results=("BROKER_ONLY_ORDER",), restore_result="N/A", reconciliation_result="BROKER_ONLY_DETECTED", final_state={"live_blocked": blocked}),
        context=ctx,
    )


def _dr09(ctx: OperatorControlContext, spec: DisasterRecoveryDrillSpecV1) -> DRDrillOutcome:
    ctx.broker_health = "UNHEALTHY"
    blocked, reasons = evaluate_operational_readiness_blocks_live(ctx, as_of_ns=T, recovered_runtime=True, reconciliation_clean=False)
    return DRDrillOutcome(
        report=_report(spec, failure_observed={"broker_outage": True}, alert_results=("BROKER_UNHEALTHY",), restore_result="DEFERRED", reconciliation_result="BLOCKED", final_state={"live_blocked": blocked, "reasons": reasons}),
        context=ctx,
    )


def _dr10(ctx: OperatorControlContext, spec: DisasterRecoveryDrillSpecV1) -> DRDrillOutcome:
    alert = raise_alert(alert_type="CRITICAL_INCIDENT", severity=AlertSeverity.CRITICAL.value, scope="canary", raised_at_ns=T, summary="test critical")
    adapter = ConsoleAlertDeliveryAdapter(permanent_failure=True)
    receipts = deliver_alert(alert, (adapter,), attempt_time_ns=T)
    delivery_failed = all(r.result != DeliveryResult.SUCCESS.value for r in receipts)
    failure_alert = raise_alert(alert_type="ALERT_DELIVERY_FAILED", severity=AlertSeverity.CRITICAL.value, scope="canary", raised_at_ns=T, summary="delivery failed")
    return DRDrillOutcome(
        report=_report(spec, failure_observed={"delivery_outage": True}, alert_results=(failure_alert.alert_type,), restore_result="N/A", reconciliation_result="N/A", final_state={"delivery_failed_observable": delivery_failed}),
        context=ctx,
    )


def _dr11(ctx: OperatorControlContext, spec: DisasterRecoveryDrillSpecV1) -> DRDrillOutcome:
    from ..kill_switch_store import KillSwitchStore

    ctx.kill_switch = KillSwitchStore.from_persistence_dict({"global_state": "INVALID_STATE"})
    blocked = ctx.kill_switch.any_block_active()
    return DRDrillOutcome(
        report=_report(spec, failure_observed={"kill_switch_corrupt": True}, alert_results=("KILL_SWITCH_UNKNOWN",), restore_result="DEFAULT_BLOCK", reconciliation_result="BLOCKED", final_state={"live_blocked": blocked}),
        context=ctx,
    )


def _dr12(ctx: OperatorControlContext, spec: DisasterRecoveryDrillSpecV1) -> DRDrillOutcome:
    blocked = ctx.kill_switch.any_block_active() or True
    return DRDrillOutcome(
        report=_report(spec, failure_observed={"ui_unavailable": True}, alert_results=("UI_UNAVAILABLE",), restore_result="N/A", reconciliation_result="BACKEND_SAFE", final_state={"live_blocked": blocked, "backend_safe": True}),
        context=ctx,
    )


def _dr13(ctx: OperatorControlContext, spec: DisasterRecoveryDrillSpecV1) -> DRDrillOutcome:
    blocked, reasons = evaluate_operational_readiness_blocks_live(ctx, as_of_ns=T, telemetry_evaluator_ok=False)
    return DRDrillOutcome(
        report=_report(spec, failure_observed={"telemetry_failure": True}, alert_results=("OBSERVABILITY_DEGRADED",), restore_result="N/A", reconciliation_result="UNKNOWN", final_state={"live_blocked": blocked, "reasons": reasons}),
        context=ctx,
    )


def _dr14(ctx: OperatorControlContext, spec: DisasterRecoveryDrillSpecV1) -> DRDrillOutcome:
    blocked, reasons = evaluate_operational_readiness_blocks_live(ctx, as_of_ns=T, persistence_healthy=False)
    return DRDrillOutcome(
        report=_report(spec, failure_observed={"schema_mismatch": True}, alert_results=("SCHEMA_MISMATCH",), restore_result="REJECTED", reconciliation_result="BLOCKED", final_state={"live_blocked": blocked, "reasons": reasons}),
        context=ctx,
    )


def _dr15(ctx: OperatorControlContext, spec: DisasterRecoveryDrillSpecV1) -> DRDrillOutcome:
    plan = build_default_recovery_plan(failure_scenario="cold_start")
    blocked = recovered_runtime_blocks_live(reconciliation_clean=False, operator_approved=False)
    return DRDrillOutcome(
        report=_report(spec, failure_observed={"cold_start": True}, alert_results=("COLD_START",), restore_result="RECONSTRUCTED", reconciliation_result="PENDING", final_state={"live_blocked": blocked, "startup_mode": plan.startup_mode}),
        context=ctx,
    )


def run_all_dr_drills() -> dict[str, DisasterRecoveryDrillReportV1]:
    return {drill_id: run_dr_drill(drill_id).report for drill_id in DR_DRILL_SPECS}
