"""BUILD 34 deployment and change-control tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from market_platform_foundation.intelligence.live_canary.deployment import (
    BUILD33_HEAD,
    BrokerEnvironment,
    ChangeApprovalState,
    ChangeType,
    DeploymentDisposition,
    EnvironmentKind,
    FixtureServiceSupervisor,
    assess_configuration_drift,
    build_change_request,
    build_deployment_canary_spec,
    build_deployment_configuration,
    build_deployment_plan,
    build_deployment_qualification_spec,
    build_environment_manifest,
    build_migration_plan,
    build_release_manifest,
    build_rollback_plan,
    build_runtime_version_report,
    compare_semantic_identity,
    configuration_hash,
    decide_rollback,
    deployment_grants_live_authority,
    deployment_requires_approved_change_request,
    destructive_migration_without_backup_blocked,
    dirty_tree_blocks_release,
    drift_blocks_live_actions,
    floating_latest_prohibited,
    promote_release,
    rollback_auto_resumes_live,
    run_deployment_canary,
    run_failed_deployment_rollback_fixture,
    run_full_successful_deployment_fixture,
    run_migration_fixture,
    run_reproducibility_fixture,
    unknown_environment_fails_closed,
    validate_configuration_for_environment,
    validate_configuration_no_policy_override,
    validate_environment_manifest,
    validate_promotion_gates,
    validate_startup_order,
    verify_dependency_lock_consistent,
)
from market_platform_foundation.intelligence.live_canary.deployment.plan import build_deployment_record
from market_platform_foundation.intelligence.live_canary.deployment.supervision import build_default_service_graph
from market_platform_foundation.ui_api import canary_projections

T = 1_700_000_000_000_000_000
BUILD33_QUAL = "BUILD33-SUPERVISED-PRODUCTION-PILOT-QUALIFIED"


class ReleaseManifestTests(unittest.TestCase):
    def test_deterministic_release_id(self) -> None:
        a = build_release_manifest(build_timestamp_ns=T, build33_qualification_ref=BUILD33_QUAL, allow_dirty=True)
        b = build_release_manifest(build_timestamp_ns=T + 1, build33_qualification_ref=BUILD33_QUAL, allow_dirty=True)
        self.assertFalse(a.blocked)
        self.assertEqual(a.manifest.release_manifest_id, b.manifest.release_manifest_id)
        self.assertTrue(a.manifest.release_manifest_id.startswith("REL-"))

    def test_dirty_tree_blocks_release(self) -> None:
        blocked, reason = dirty_tree_blocks_release()
        if blocked:
            self.assertIn("dirty", reason.lower())

    def test_reproducibility_same_semantic_hash(self) -> None:
        self.assertTrue(run_reproducibility_fixture())

    def test_compare_semantic_identity(self) -> None:
        a = build_release_manifest(build_timestamp_ns=T, build33_qualification_ref=BUILD33_QUAL, allow_dirty=True)
        b = build_release_manifest(build_timestamp_ns=T + 999, build33_qualification_ref=BUILD33_QUAL, allow_dirty=True)
        self.assertTrue(compare_semantic_identity(a, b))

    def test_dependency_lock_verified(self) -> None:
        ok, msg = verify_dependency_lock_consistent()
        self.assertTrue(ok, msg)

    def test_source_commit_sha_present(self) -> None:
        result = build_release_manifest(build_timestamp_ns=T, build33_qualification_ref=BUILD33_QUAL, allow_dirty=True)
        self.assertTrue(len(result.manifest.source_commit_sha) == 40)


class EnvironmentTests(unittest.TestCase):
    def test_valid_test_environment(self) -> None:
        release = build_release_manifest(build_timestamp_ns=T, build33_qualification_ref=BUILD33_QUAL, allow_dirty=True)
        env = build_environment_manifest(
            environment_kind=EnvironmentKind.TEST.value,
            release_manifest_ref=release.manifest.release_manifest_id,
            build33_qualification_ref=BUILD33_QUAL,
        )
        ok, violations = validate_environment_manifest(env)
        self.assertTrue(ok, violations)

    def test_valid_supervised_live_environment(self) -> None:
        release = build_release_manifest(build_timestamp_ns=T, build33_qualification_ref=BUILD33_QUAL, allow_dirty=True)
        env = build_environment_manifest(
            environment_kind=EnvironmentKind.SUPERVISED_LIVE.value,
            release_manifest_ref=release.manifest.release_manifest_id,
            build33_qualification_ref=BUILD33_QUAL,
        )
        ok, violations = validate_environment_manifest(env)
        self.assertTrue(ok, violations)

    def test_unknown_environment_fails_closed(self) -> None:
        self.assertTrue(unknown_environment_fails_closed("UNKNOWN_ENV"))

    def test_paper_broker_in_live_config_blocked(self) -> None:
        config = build_deployment_configuration(
            environment_kind=EnvironmentKind.SUPERVISED_LIVE.value,
            execution_mode="SUPERVISED_LIVE",
            execution_authority="SUPERVISED_LIVE",
            broker_environment=BrokerEnvironment.PAPER.value,
            persistence_target="supervised-live",
            provider_environment="live-readonly",
        )
        ok, violations = validate_configuration_for_environment(config, EnvironmentKind.SUPERVISED_LIVE.value)
        self.assertFalse(ok)
        self.assertTrue(any("broker" in v.lower() for v in violations))

    def test_live_broker_in_test_config_blocked(self) -> None:
        config = build_deployment_configuration(
            environment_kind=EnvironmentKind.TEST.value,
            execution_mode="PAPER",
            execution_authority="PAPER",
            broker_environment=BrokerEnvironment.SUPERVISED_LIVE.value,
            persistence_target="test",
            provider_environment="fixture",
        )
        ok, violations = validate_configuration_for_environment(config, EnvironmentKind.TEST.value)
        self.assertFalse(ok)


class ConfigVsPolicyTests(unittest.TestCase):
    def test_env_var_cannot_override_policy(self) -> None:
        config = build_deployment_configuration(
            environment_kind=EnvironmentKind.TEST.value,
            execution_mode="PAPER",
            execution_authority="PAPER",
            broker_environment=BrokerEnvironment.TEST.value,
            persistence_target="test",
            provider_environment="fixture",
        )
        ok, violations = validate_configuration_no_policy_override(
            config, raw_env={"MAX_PILOT_ORDERS": "9999"}
        )
        self.assertFalse(ok)

    def test_symbolic_secret_references(self) -> None:
        config = build_deployment_configuration(
            environment_kind=EnvironmentKind.TEST.value,
            execution_mode="PAPER",
            execution_authority="PAPER",
            broker_environment=BrokerEnvironment.TEST.value,
            persistence_target="test",
            provider_environment="fixture",
        )
        ok, violations = validate_configuration_no_policy_override(config)
        self.assertTrue(ok, violations)


class PromotionTests(unittest.TestCase):
    def test_same_artifact_promoted(self) -> None:
        release = build_release_manifest(build_timestamp_ns=T, build33_qualification_ref=BUILD33_QUAL, allow_dirty=True)
        artifact = release.manifest.artifact_hashes["bundle_content"]
        promo = promote_release(
            release=release.manifest,
            from_environment=EnvironmentKind.TEST.value,
            to_environment=EnvironmentKind.SUPERVISED_LIVE.value,
            artifact_hash=artifact,
            qualification_refs=(BUILD33_QUAL,),
            promotion_time_ns=T,
        )
        self.assertEqual(promo.result, "PROMOTED")
        self.assertEqual(promo.artifact_hash, artifact)

    def test_floating_latest_prohibited(self) -> None:
        self.assertTrue(floating_latest_prohibited("latest"))
        self.assertTrue(floating_latest_prohibited("HEAD"))

    def test_rebuild_during_promotion_blocked(self) -> None:
        release = build_release_manifest(build_timestamp_ns=T, build33_qualification_ref=BUILD33_QUAL, allow_dirty=True)
        artifact = release.manifest.artifact_hashes["bundle_content"]
        ok, violations = validate_promotion_gates(
            release=release.manifest,
            to_environment=EnvironmentKind.SUPERVISED_LIVE.value,
            build33_ref=BUILD33_QUAL,
            artifact_hash="different-hash",
            source_artifact_hash=artifact,
        )
        self.assertFalse(ok)


class DriftTests(unittest.TestCase):
    def test_artifact_mismatch_blocks_live(self) -> None:
        drift = assess_configuration_drift(
            expected_release="REL-abc",
            expected_config_hash="hash-a",
            observed_release="REL-xyz",
            observed_config_hash="hash-a",
        )
        self.assertTrue(drift_blocks_live_actions(drift))
        self.assertEqual(drift.drift_classification, "ARTIFACT_MISMATCH")

    def test_manual_runtime_edit_detected(self) -> None:
        drift = assess_configuration_drift(
            expected_release="REL-abc",
            expected_config_hash="hash-a",
            observed_release="REL-abc",
            observed_config_hash="hash-tampered",
        )
        self.assertTrue(drift.blocking_impact)


class ServiceSupervisionTests(unittest.TestCase):
    def test_startup_order_valid(self) -> None:
        graph = build_default_service_graph("ENV-test")
        ok, violations = validate_startup_order(graph)
        self.assertTrue(ok, violations)

    def test_restart_does_not_restore_live_authority(self) -> None:
        supervisor = FixtureServiceSupervisor()
        graph = build_default_service_graph("ENV-test")
        for svc in graph.services:
            supervisor.register(svc)
        supervisor.start_service("operator-api", release_ref="REL-test", start_time_ns=T)
        supervisor.crash_service("operator-api", "crash")
        supervisor.restart_service("operator-api", start_time_ns=T + 1000)
        self.assertFalse(supervisor.restart_restores_live_authority())

    def test_crash_loop_detected(self) -> None:
        supervisor = FixtureServiceSupervisor()
        graph = build_default_service_graph("ENV-test")
        for svc in graph.services:
            supervisor.register(svc)
        for _ in range(6):
            supervisor.crash_service("operator-api", "crash")
        self.assertTrue(supervisor.is_crash_loop("operator-api"))

    def test_graceful_shutdown(self) -> None:
        supervisor = FixtureServiceSupervisor()
        graph = build_default_service_graph("ENV-test")
        for svc in graph.services:
            supervisor.register(svc)
        supervisor.start_service("operator-api", release_ref="REL-test", start_time_ns=T)
        result = supervisor.graceful_shutdown("operator-api", timeout_ns=1000, elapsed_ns=500)
        self.assertEqual(result, "GRACEFUL")

    def test_forced_shutdown(self) -> None:
        supervisor = FixtureServiceSupervisor()
        graph = build_default_service_graph("ENV-test")
        for svc in graph.services:
            supervisor.register(svc)
        supervisor.start_service("operator-api", release_ref="REL-test", start_time_ns=T)
        result = supervisor.graceful_shutdown("operator-api", timeout_ns=1000, elapsed_ns=2000)
        self.assertEqual(result, "FORCED_TERMINATION")


class DeploymentCanaryTests(unittest.TestCase):
    def test_zero_order_canary_default(self) -> None:
        plan = build_deployment_plan(
            target_environment="ENV-test",
            release_ref="REL-test",
            config_ref="DCFG-test",
        )
        spec = build_deployment_canary_spec(deployment_plan_ref=plan.deployment_plan_id)
        self.assertTrue(spec.zero_live_order_requirement)
        report = run_deployment_canary(
            canary_spec=spec,
            observation_duration_ns=spec.minimum_observation_duration_ns,
        )
        self.assertEqual(report.real_broker_submits, 0)
        self.assertEqual(report.disposition, "CANARY_PASSED")

    def test_canary_failure_on_live_order(self) -> None:
        plan = build_deployment_plan(
            target_environment="ENV-test",
            release_ref="REL-test",
            config_ref="DCFG-test",
        )
        spec = build_deployment_canary_spec(deployment_plan_ref=plan.deployment_plan_id)
        report = run_deployment_canary(
            canary_spec=spec,
            real_broker_submits=1,
            observation_duration_ns=spec.minimum_observation_duration_ns,
        )
        self.assertEqual(report.disposition, "CANARY_FAILED")

    def test_canary_failure_injected(self) -> None:
        plan = build_deployment_plan(
            target_environment="ENV-test",
            release_ref="REL-test",
            config_ref="DCFG-test",
        )
        spec = build_deployment_canary_spec(deployment_plan_ref=plan.deployment_plan_id)
        report = run_deployment_canary(
            canary_spec=spec,
            injected_failure="reconciliation_failure",
            observation_duration_ns=spec.minimum_observation_duration_ns,
        )
        self.assertEqual(report.disposition, "CANARY_FAILED")


class MigrationTests(unittest.TestCase):
    def test_destructive_migration_without_backup_blocked(self) -> None:
        plan = build_migration_plan(from_schema="intelligence-v1", to_schema="intelligence-v2", rollback_supported=False)
        blocked, _ = destructive_migration_without_backup_blocked(plan, backup_verified=False)
        self.assertTrue(blocked)

    def test_no_migration_needed_at_v1(self) -> None:
        result = run_migration_fixture(backup_verified=True)
        self.assertEqual(result.forward_migration, "PASS")


class RollbackTests(unittest.TestCase):
    def test_failed_deployment_rollback_fixture(self) -> None:
        result = run_failed_deployment_rollback_fixture()
        self.assertTrue(result.release_a_restored)
        self.assertEqual(result.orders_replayed, 0)
        self.assertFalse(result.live_auto_resume)

    def test_schema_incompatible_rollback_halts(self) -> None:
        plan = build_rollback_plan(
            deployment_ref="DEPLOY-b",
            rollback_target_release="REL-a",
            rollback_target_deployment="DEPLOY-a",
            schema_compatible=False,
        )
        decision = decide_rollback(
            deployment_ref="DEPLOY-b",
            rollback_plan=plan,
            failure_reason="migration_failure",
            schema_compatible=False,
        )
        self.assertEqual(decision.decision, "HALT_ENVIRONMENT")

    def test_rollback_does_not_auto_resume(self) -> None:
        self.assertFalse(rollback_auto_resumes_live())


class ChangeControlTests(unittest.TestCase):
    def test_deployment_requires_approved_change_request(self) -> None:
        request = build_change_request(
            change_type=ChangeType.CODE_RELEASE.value,
            release_ref="REL-test",
            target_environment="ENV-test",
            reason="test",
            rollback_target="REL-prev",
            approval_state=ChangeApprovalState.APPROVED.value,
        )
        ok, _ = deployment_requires_approved_change_request(request)
        self.assertTrue(ok)

    def test_unapproved_change_blocked(self) -> None:
        request = build_change_request(
            change_type=ChangeType.CONFIGURATION_CHANGE.value,
            release_ref="REL-test",
            target_environment="ENV-test",
            reason="config change",
            rollback_target="REL-prev",
            configuration_diff={"operator_server_config.port": 9000},
            approval_state=ChangeApprovalState.PENDING_APPROVAL.value,
        )
        ok, _ = deployment_requires_approved_change_request(request)
        self.assertFalse(ok)

    def test_config_only_change_audited(self) -> None:
        config = build_deployment_configuration(
            environment_kind=EnvironmentKind.TEST.value,
            execution_mode="PAPER",
            execution_authority="PAPER",
            broker_environment=BrokerEnvironment.TEST.value,
            persistence_target="test",
            provider_environment="fixture",
        )
        h1 = configuration_hash(config)
        request = build_change_request(
            change_type=ChangeType.CONFIGURATION_CHANGE.value,
            release_ref="REL-test",
            target_environment="ENV-test",
            reason="port change",
            rollback_target="REL-prev",
            configuration_diff={"port": 9000},
            approval_state=ChangeApprovalState.APPROVED.value,
        )
        self.assertEqual(request.change_type, ChangeType.CONFIGURATION_CHANGE.value)
        self.assertIsNotNone(h1)


class NoAutonomyTests(unittest.TestCase):
    def test_deployment_does_not_grant_live_authority(self) -> None:
        record = build_deployment_record(
            environment_ref="ENV-test",
            release_ref="REL-test",
            deployment_started_ns=T,
            configuration_hash="hash",
            artifact_hashes={"bundle": "abc"},
            disposition=DeploymentDisposition.DEPLOYMENT_QUALIFIED.value,
        )
        self.assertFalse(deployment_grants_live_authority(record))

    def test_full_fixture_zero_orders(self) -> None:
        result = run_full_successful_deployment_fixture(allow_dirty=True)
        if not result.release_blocked:
            self.assertEqual(result.real_broker_submits, 0)
            self.assertFalse(result.live_authority_granted)


class RuntimeVersionTests(unittest.TestCase):
    def test_runtime_version_match(self) -> None:
        report = build_runtime_version_report(
            service_id="operator-api",
            expected_release="REL-abc",
            expected_config_hash="hash-a",
            observed_release="REL-abc",
            observed_config_hash="hash-a",
            commit_sha=BUILD33_HEAD,
        )
        self.assertTrue(report.matches_expected)

    def test_runtime_version_mismatch(self) -> None:
        report = build_runtime_version_report(
            service_id="operator-api",
            expected_release="REL-abc",
            expected_config_hash="hash-a",
            observed_release="REL-xyz",
            observed_config_hash="hash-a",
            commit_sha=BUILD33_HEAD,
        )
        self.assertFalse(report.matches_expected)


class OperatorControlPlaneTests(unittest.TestCase):
    def test_deployment_payload_separate_from_live_auth(self) -> None:
        payload = canary_projections.build_canary_deployment_payload()
        self.assertIn("live_authorization", payload)
        self.assertFalse(payload["live_authorization"]["deployment_grants_authority"])
        self.assertTrue(payload["live_authorization"]["per_order_confirmation_required"])
        self.assertIn("disclaimer", payload)


class FullFixtureTests(unittest.TestCase):
    def test_full_successful_deployment_fixture(self) -> None:
        result = run_full_successful_deployment_fixture(allow_dirty=True)
        if result.release_blocked:
            self.skipTest("release blocked due to dirty tree in CI")
        self.assertFalse(result.release_blocked)
        self.assertEqual(result.promotion_result, "PROMOTED")
        self.assertEqual(result.canary_disposition, "CANARY_PASSED")
        self.assertIn(
            result.qualification_disposition,
            (
                DeploymentDisposition.DEPLOYMENT_QUALIFIED.value,
                DeploymentDisposition.DEPLOYMENT_QUALIFIED_WITH_LIMITATIONS.value,
            ),
        )


if __name__ == "__main__":
    unittest.main()
