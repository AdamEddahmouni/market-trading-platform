"""BUILD 32 operational reliability tests."""

from __future__ import annotations

import json
import unittest
from unittest import mock

from market_platform_foundation.intelligence.live_canary import (
    build_default_canary_policy,
    build_default_program_policy,
)
from market_platform_foundation.intelligence.live_canary.types import ProgramGovernanceState
from market_platform_foundation.intelligence.live_canary.operator_control import OperatorControlContext
from market_platform_foundation.intelligence.live_canary.operational_reliability import (
    ALLOWED_METRIC_DIMENSIONS,
    ConsoleAlertDeliveryAdapter,
    acknowledge_alert,
    assess_operational_slos,
    assess_persistence_health,
    build_component_heartbeat,
    build_default_alert_policy,
    build_default_slo_policy,
    build_operational_health_matrix,
    build_operational_reliability_qualification_report,
    create_backup_manifest,
    deliver_alert,
    evaluate_heartbeat_staleness,
    evaluate_operational_readiness_blocks_live,
    raise_alert,
    recovered_runtime_blocks_live,
    run_all_dr_drills,
    run_virtual_soak_endurance,
    sanitize_alert_payload,
    should_dedup_alert,
    verify_backup_integrity,
)
from market_platform_foundation.intelligence.live_canary.operational_reliability.alerts import (
    alerts_from_slo_assessment,
)
from market_platform_foundation.intelligence.live_canary.operational_reliability.backup import (
    canonical_backup_content,
    collect_backup_scope,
)
from market_platform_foundation.intelligence.live_canary.operational_reliability.delivery import (
    NotConfiguredDeliveryAdapter,
)
from market_platform_foundation.intelligence.live_canary.operational_reliability.identity import (
    derive_slo_policy_id,
)
from market_platform_foundation.intelligence.live_canary.operational_reliability.types import (
    AlertSeverity,
    AlertState,
    ComponentSignalState,
    DeliveryResult,
    DrillResult,
    SLOObjectiveStatus,
)
from market_platform_foundation.intelligence.live_canary.types import ProgramGovernanceState
from market_platform_foundation.intelligence.live_execution_safety.types import (
    LiveGateReasonCode,
)
from market_platform_foundation.ui_api import canary_projections

T = 1_700_000_000_000_000_000
INTERVAL = 30_000_000_000
STALE = 90_000_000_000


def _ctx() -> OperatorControlContext:
    ctx = OperatorControlContext(
        program_policy=build_default_program_policy(program_effective_from_ns=T),
        canary_policy=build_default_canary_policy(broker="tradier.paper", account_ref="fp-test"),
        governance_state=ProgramGovernanceState.PROGRAM_ACTIVE,
        session_ref="session-1",
        broker_health="HEALTHY",
        reconciliation_health="CLEAN",
    )
    ctx.kill_switch.permit_program("TEST")
    return ctx


class HeartbeatTests(unittest.TestCase):
    def test_fresh_heartbeat(self) -> None:
        state = evaluate_heartbeat_staleness(observed_at_ns=T, as_of_ns=T + INTERVAL)
        self.assertEqual(state, ComponentSignalState.HEALTHY)

    def test_exact_stale_boundary(self) -> None:
        state = evaluate_heartbeat_staleness(observed_at_ns=T, as_of_ns=T + STALE)
        self.assertEqual(state, ComponentSignalState.STALE)

    def test_never_observed_not_healthy(self) -> None:
        hb = build_component_heartbeat(component="broker_adapter", as_of_ns=T, observed_at_ns=None)
        self.assertEqual(hb.liveness, ComponentSignalState.NEVER_OBSERVED.value)
        self.assertTrue(hb.blocking_live)

    def test_stale_blocks_execution_critical(self) -> None:
        hb = build_component_heartbeat(
            component="broker_adapter",
            as_of_ns=T + STALE + 1,
            observed_at_ns=T,
        )
        self.assertTrue(hb.blocking_live)


class SLOPolicyTests(unittest.TestCase):
    def test_deterministic_policy_id(self) -> None:
        p1 = build_default_slo_policy()
        p2 = build_default_slo_policy()
        self.assertEqual(p1.slo_policy_id, p2.slo_policy_id)

    def test_semantic_change_changes_id(self) -> None:
        base = build_default_slo_policy()
        from market_platform_foundation.intelligence.live_canary.operational_reliability.types import (
            OperationalSLOPolicyV1,
            SLOObjectiveV1,
        )

        modified = OperationalSLOPolicyV1(
            slo_policy_id="",
            schema_version=base.schema_version,
            scope=base.scope,
            measurement_window_ns=base.measurement_window_ns,
            evaluation_cadence_ns=base.evaluation_cadence_ns,
            objectives=(
                SLOObjectiveV1(
                    objective_id="test_obj",
                    description="changed",
                    warning_threshold=0.5,
                    critical_threshold=0.4,
                    safety_critical=True,
                    missing_data_semantics="INSUFFICIENT_DATA",
                ),
            ),
            minimum_sample=base.minimum_sample,
            missing_data_semantics=base.missing_data_semantics,
            implementation_version=base.implementation_version,
        )
        self.assertNotEqual(base.slo_policy_id, derive_slo_policy_id(modified))

    def test_missing_data_not_success(self) -> None:
        policy = build_default_slo_policy()
        assessment = assess_operational_slos(
            policy,
            window_start_ns=T,
            window_end_ns=T + policy.measurement_window_ns,
            as_of_ns=T + policy.measurement_window_ns,
            samples={obj.objective_id: (0, 0) for obj in policy.objectives},
        )
        for result in assessment.objective_results:
            self.assertEqual(result.status, SLOObjectiveStatus.INSUFFICIENT_DATA.value)
            self.assertIsNone(result.observed_value)


class AlertTests(unittest.TestCase):
    def test_dedup_same_condition(self) -> None:
        policy = build_default_alert_policy()
        a1 = raise_alert(
            alert_type="SLO_BREACH",
            severity=AlertSeverity.WARNING.value,
            scope="canary",
            raised_at_ns=T,
            summary="test",
        )
        a2 = raise_alert(
            alert_type="SLO_BREACH",
            severity=AlertSeverity.WARNING.value,
            scope="canary",
            raised_at_ns=T + 1,
            summary="test",
        )
        self.assertTrue(should_dedup_alert(a1, a2, as_of_ns=T + 2, dedup_window_ns=policy.dedup_window_ns))

    def test_acknowledge_does_not_resolve(self) -> None:
        alert = raise_alert(
            alert_type="TEST",
            severity=AlertSeverity.CRITICAL.value,
            scope="canary",
            raised_at_ns=T,
            summary="test",
        )
        acked = acknowledge_alert(alert, acknowledged_at_ns=T + 1)
        self.assertEqual(acked.state, AlertState.ACKNOWLEDGED.value)
        self.assertIsNone(acked.resolved_at_ns)

    def test_critical_escalation_not_deduped(self) -> None:
        policy = build_default_alert_policy()
        a1 = raise_alert(
            alert_type="SLO_BREACH",
            severity=AlertSeverity.WARNING.value,
            scope="canary",
            raised_at_ns=T,
            summary="test",
        )
        a2 = raise_alert(
            alert_type="SLO_BREACH",
            severity=AlertSeverity.CRITICAL.value,
            scope="canary",
            raised_at_ns=T + 1,
            summary="test",
        )
        self.assertFalse(
            should_dedup_alert(a1, a2, as_of_ns=T + 2, dedup_window_ns=policy.dedup_window_ns)
        )


class AlertDeliveryTests(unittest.TestCase):
    def test_successful_delivery(self) -> None:
        alert = raise_alert(
            alert_type="TEST",
            severity=AlertSeverity.INFO.value,
            scope="canary",
            raised_at_ns=T,
            summary="test",
        )
        receipts = deliver_alert(alert, (ConsoleAlertDeliveryAdapter(),), attempt_time_ns=T)
        self.assertEqual(receipts[0].result, DeliveryResult.SUCCESS.value)

    def test_all_channel_failure_observable(self) -> None:
        alert = raise_alert(
            alert_type="TEST",
            severity=AlertSeverity.CRITICAL.value,
            scope="canary",
            raised_at_ns=T,
            summary="test",
        )
        adapter = ConsoleAlertDeliveryAdapter(permanent_failure=True)
        receipts = deliver_alert(alert, (adapter,), attempt_time_ns=T)
        self.assertTrue(all(r.result != DeliveryResult.SUCCESS.value for r in receipts))

    def test_not_configured_channel(self) -> None:
        alert = raise_alert(
            alert_type="TEST",
            severity=AlertSeverity.INFO.value,
            scope="canary",
            raised_at_ns=T,
            summary="test",
        )
        receipts = deliver_alert(alert, (NotConfiguredDeliveryAdapter(channel="slack"),), attempt_time_ns=T)
        self.assertEqual(receipts[0].result, DeliveryResult.NOT_CONFIGURED.value)


class PersistenceTests(unittest.TestCase):
    def test_unhealthy_blocks_live(self) -> None:
        snap = assess_persistence_health(as_of_ns=T, write_healthy=False)
        self.assertTrue(snap.blocking_live)

    def test_operational_readiness_persistence_block(self) -> None:
        ctx = _ctx()
        blocked, reasons = evaluate_operational_readiness_blocks_live(ctx, as_of_ns=T, persistence_healthy=False)
        self.assertTrue(blocked)
        self.assertIn(LiveGateReasonCode.PERSISTENCE_UNHEALTHY.value, reasons)


class ObservabilityLossTests(unittest.TestCase):
    def test_telemetry_failure_blocks(self) -> None:
        ctx = _ctx()
        blocked, reasons = evaluate_operational_readiness_blocks_live(
            ctx, as_of_ns=T, telemetry_evaluator_ok=False
        )
        self.assertTrue(blocked)
        self.assertIn(LiveGateReasonCode.OBSERVABILITY_DEGRADED.value, reasons)

    def test_unknown_critical_not_healthy_matrix(self) -> None:
        ctx = _ctx()
        matrix = build_operational_health_matrix(
            ctx, as_of_ns=T, telemetry_evaluator_ok=False
        )
        self.assertEqual(matrix.observability_state, "OBSERVABILITY_DEGRADED")


class BackupRestoreTests(unittest.TestCase):
    def test_backup_integrity(self) -> None:
        ctx = _ctx()
        manifest = create_backup_manifest(ctx, created_at_ns=T, source_head="abc123")
        scope = collect_backup_scope(ctx)
        content = canonical_backup_content(scope)
        self.assertTrue(verify_backup_integrity(manifest, content))

    def test_corrupt_backup_rejected(self) -> None:
        ctx = _ctx()
        manifest = create_backup_manifest(ctx, created_at_ns=T, source_head="abc123")
        self.assertFalse(verify_backup_integrity(manifest, "tampered"))

    def test_recovered_runtime_blocked(self) -> None:
        self.assertTrue(recovered_runtime_blocks_live(reconciliation_clean=False, operator_approved=False))


class DRDrillTests(unittest.TestCase):
    def test_all_drills_pass_zero_broker_effects(self) -> None:
        reports = run_all_dr_drills()
        self.assertEqual(len(reports), 15)
        for report in reports.values():
            self.assertEqual(report.result, DrillResult.PASS.value)
            self.assertEqual(report.real_broker_submits, 0)
            self.assertEqual(report.real_broker_cancels, 0)
            self.assertEqual(report.real_broker_replaces, 0)


class SoakTests(unittest.TestCase):
    def test_virtual_endurance(self) -> None:
        report = run_virtual_soak_endurance(start_ns=T, cycles=50)
        self.assertGreater(report.virtual_duration_ns, 0)
        self.assertEqual(report.actual_duration_ns, 0)


class SecretRedactionTests(unittest.TestCase):
    def test_alert_payload_sanitized(self) -> None:
        alert = raise_alert(
            alert_type="TEST",
            severity=AlertSeverity.INFO.value,
            scope="canary",
            raised_at_ns=T,
            summary="safe summary",
        )
        payload = sanitize_alert_payload(alert)
        self.assertNotIn("password", json.dumps(payload).lower())
        self.assertIn("alert_id", payload)


class CardinalityTests(unittest.TestCase):
    def test_bounded_dimensions(self) -> None:
        self.assertNotIn("order_id", ALLOWED_METRIC_DIMENSIONS)
        self.assertNotIn("forecast_id", ALLOWED_METRIC_DIMENSIONS)


class ApiIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        canary_projections.reset_operator_context_for_tests()

    def test_reliability_endpoint(self) -> None:
        payload = canary_projections.build_canary_reliability_payload()
        self.assertEqual(payload["authority_boundary"], "OPERATIONAL_RELIABILITY_READ_ONLY")
        self.assertIn("health_matrix", payload)


class QualificationTests(unittest.TestCase):
    def test_qualification_report(self) -> None:
        report = build_operational_reliability_qualification_report(build32_source_ref="test-head")
        self.assertEqual(report.real_broker_side_effects_observed, 0)
        self.assertEqual(len(report.dr_drill_results), 15)


class NoAutonomyTests(unittest.TestCase):
    def test_alert_never_trades(self) -> None:
        with mock.patch(
            "market_platform_foundation.intelligence.live_canary.submission.MockBrokerTransport.submit",
            side_effect=AssertionError("broker submit must not be called"),
        ):
            alert = raise_alert(
                alert_type="TEST",
                severity=AlertSeverity.CRITICAL.value,
                scope="canary",
                raised_at_ns=T,
                summary="test",
            )
            deliver_alert(alert, (ConsoleAlertDeliveryAdapter(),), attempt_time_ns=T)
            assessment = assess_operational_slos(
                build_default_slo_policy(),
                window_start_ns=T,
                window_end_ns=T + 300_000_000_000,
                as_of_ns=T + 300_000_000_000,
                samples={"provider_connection_availability": (0, 1)},
            )
            alerts_from_slo_assessment(assessment, build_default_alert_policy())


if __name__ == "__main__":
    unittest.main()
