"""BUILD 35 release governance and full-system acceptance tests."""

from __future__ import annotations

import unittest
from unittest import mock

from market_platform_foundation.intelligence.live_canary.release_governance import (
    BUILD35_KNOWN_LIMITATIONS,
    ChangeClass,
    EligibilityDisposition,
    FullSystemAcceptanceDisposition,
    ProductionReleaseRegistry,
    ReleaseApprovalStatus,
    approval_authorizes_live_session,
    approval_confirms_order,
    assemble_release_candidate_fixture,
    assess_release_eligibility,
    audit_deployment_to_live_authorization,
    audit_direct_forecast_to_broker,
    audit_direct_llm_to_broker,
    audit_direct_research_to_active_model,
    audit_release_approval_to_order_confirmation,
    build_canonical_authority_map,
    build_change_impact_policy,
    build_change_window_policy,
    build_default_release_governance_policy,
    build_environment_promotion_policy,
    build_full_system_acceptance_report,
    build_full_system_acceptance_spec,
    build_production_release_candidate,
    build_release_approval,
    build_release_evidence_bundle,
    classify_changed_path,
    evaluate_change_window,
    false_global_green_blocked,
    find_duplicate_authorities,
    release_approval_creates_live_authority,
    required_requalification_for_change,
    revoke_release_approval,
    run_change_window_deployment_fixture,
    run_full_lifecycle_fixture,
    run_revocation_exercise,
    run_rollback_exercises,
    validate_promotion_edge,
    verify_evidence_lineage,
)
from market_platform_foundation.intelligence.live_canary.release_governance.acceptance import (
    DomainAcceptanceResultV1,
)
from market_platform_foundation.intelligence.live_canary.release_governance.types import (
    RequirementResult,
)

T = 1_700_000_000_000_000_000
HEAD = "1cbfb415c398b37056030c6037b91744f7a33b90"


class GovernancePolicyTests(unittest.TestCase):
    def test_deterministic_policy_id(self) -> None:
        env = build_environment_promotion_policy()
        cw = build_change_window_policy()
        p1 = build_default_release_governance_policy(
            environment_promotion_policy_ref=env.environment_promotion_policy_id,
            change_window_policy_ref=cw.change_window_policy_id,
        )
        p2 = build_default_release_governance_policy(
            environment_promotion_policy_ref=env.environment_promotion_policy_id,
            change_window_policy_ref=cw.change_window_policy_id,
        )
        self.assertEqual(p1.release_governance_policy_id, p2.release_governance_policy_id)
        self.assertTrue(p1.release_governance_policy_id.startswith("RELGOV-"))

    def test_required_build_evidence_covers_25_to_34(self) -> None:
        env = build_environment_promotion_policy()
        cw = build_change_window_policy()
        policy = build_default_release_governance_policy(
            environment_promotion_policy_ref=env.environment_promotion_policy_id,
            change_window_policy_ref=cw.change_window_policy_id,
        )
        for i in range(25, 35):
            self.assertIn(f"BUILD{i}", policy.required_build_evidence)

    def test_forbidden_autonomy_expansions(self) -> None:
        env = build_environment_promotion_policy()
        cw = build_change_window_policy()
        policy = build_default_release_governance_policy(
            environment_promotion_policy_ref=env.environment_promotion_policy_id,
            change_window_policy_ref=cw.change_window_policy_id,
        )
        self.assertIn("autonomous_live_trading", policy.forbidden_authority_expansions)
        self.assertIn("remove_session_authorization", policy.forbidden_authority_expansions)


class EvidenceBundleTests(unittest.TestCase):
    def test_deterministic_bundle_id(self) -> None:
        hashes = {"bundle_content": "abc123"}
        b1 = build_release_evidence_bundle(
            release_manifest_ref="REL-test",
            release_source_sha=HEAD,
            artifact_hashes=hashes,
            assembled_at_ns=T,
        )
        b2 = build_release_evidence_bundle(
            release_manifest_ref="REL-test",
            release_source_sha=HEAD,
            artifact_hashes=hashes,
            assembled_at_ns=T + 1,
        )
        self.assertEqual(b1.release_evidence_bundle_id, b2.release_evidence_bundle_id)
        self.assertTrue(b1.release_evidence_bundle_id.startswith("RELEV-"))

    def test_missing_evidence_detected_in_eligibility(self) -> None:
        (
            _release,
            gov,
            evidence,
            candidate,
            _elig,
            _spec,
            _report,
            _approval,
            _env,
            _cw,
        ) = assemble_release_candidate_fixture(allow_dirty=True)
        bad_evidence = build_release_evidence_bundle(
            release_manifest_ref="REL-wrong",
            release_source_sha=HEAD,
            artifact_hashes=candidate.artifact_hashes,
            assembled_at_ns=T,
        )
        result = assess_release_eligibility(
            policy=gov,
            candidate=candidate,
            evidence_bundle=bad_evidence,
            source_clean=True,
        )
        self.assertEqual(result.disposition, EligibilityDisposition.INELIGIBLE.value)
        self.assertTrue(any("MANIFEST" in r for r in result.blocking_reasons))

    def test_lineage_compatibility(self) -> None:
        ok, violations = verify_evidence_lineage(
            {"BUILD34": "ref"},
            release_source_sha=HEAD,
        )
        self.assertTrue(ok, violations)

    def test_incompatible_lineage_fails(self) -> None:
        ok, violations = verify_evidence_lineage(
            {"BUILD34": "ref"},
            release_source_sha="0000000000000000000000000000000000000000",
        )
        self.assertFalse(ok)
        self.assertTrue(len(violations) > 0)


class EligibilityTests(unittest.TestCase):
    def test_eligible_with_limitations(self) -> None:
        (
            _release,
            _gov,
            _evidence,
            _candidate,
            eligibility,
            _spec,
            _report,
            _approval,
            _env,
            _cw,
        ) = assemble_release_candidate_fixture(allow_dirty=True)
        self.assertEqual(eligibility.disposition, EligibilityDisposition.ELIGIBLE.value)
        self.assertEqual(eligibility.blocking_reasons, ())

    def test_dirty_source_ineligible(self) -> None:
        (
            release,
            gov,
            evidence,
            candidate,
            _elig,
            _spec,
            _report,
            _approval,
            _env,
            _cw,
        ) = assemble_release_candidate_fixture(allow_dirty=True)
        result = assess_release_eligibility(
            policy=gov,
            candidate=candidate,
            evidence_bundle=evidence,
            source_clean=False,
        )
        self.assertEqual(result.disposition, EligibilityDisposition.INELIGIBLE.value)
        self.assertIn("DIRTY_SOURCE", result.blocking_reasons)


class ApprovalTests(unittest.TestCase):
    def test_approval_from_eligible_candidate(self) -> None:
        (
            _release,
            _gov,
            _evidence,
            candidate,
            eligibility,
            _spec,
            _report,
            approval,
            _env,
            _cw,
        ) = assemble_release_candidate_fixture(allow_dirty=True)
        self.assertEqual(approval.approval_status, ReleaseApprovalStatus.APPROVED_SUPERVISED_OPERATION.value)
        self.assertIn("SUPERVISED_PILOT", approval.approved_environment_scope)

    def test_approval_does_not_authorize_live_session(self) -> None:
        self.assertFalse(approval_authorizes_live_session())

    def test_approval_does_not_confirm_order(self) -> None:
        self.assertFalse(approval_confirms_order())

    def test_release_approval_creates_no_live_authority(self) -> None:
        self.assertFalse(release_approval_creates_live_authority())

    def test_revocation(self) -> None:
        (
            _release,
            _gov,
            _evidence,
            candidate,
            eligibility,
            _spec,
            _report,
            approval,
            _env,
            _cw,
        ) = assemble_release_candidate_fixture(allow_dirty=True)
        revoked = revoke_release_approval(
            approval,
            reason="critical defect",
            revocation_time_ns=T + 1,
        )
        self.assertEqual(revoked.approval_status, ReleaseApprovalStatus.REVOKED.value)


class EnvironmentPromotionTests(unittest.TestCase):
    def test_valid_promotion_edge(self) -> None:
        policy = build_environment_promotion_policy()
        result, violations = validate_promotion_edge(
            policy=policy,
            from_environment="TEST",
            to_environment="QUALIFICATION",
            source_artifact_hash="hash-a",
            target_artifact_hash="hash-a",
            evidence_refs=("release_integrity", "dependency_lock", "targeted_tests"),
        )
        self.assertEqual(result, "PROMOTED")
        self.assertEqual(violations, [])

    def test_skipped_stage_blocked(self) -> None:
        policy = build_environment_promotion_policy()
        result, violations = validate_promotion_edge(
            policy=policy,
            from_environment="TEST",
            to_environment="SUPERVISED_LIVE",
            source_artifact_hash="hash-a",
            target_artifact_hash="hash-a",
            evidence_refs=(),
        )
        self.assertEqual(result, "BLOCKED")
        self.assertTrue(any("skipped" in v for v in violations))

    def test_artifact_mismatch_blocked(self) -> None:
        policy = build_environment_promotion_policy()
        result, _ = validate_promotion_edge(
            policy=policy,
            from_environment="TEST",
            to_environment="QUALIFICATION",
            source_artifact_hash="hash-a",
            target_artifact_hash="hash-b",
            evidence_refs=("release_integrity",),
        )
        self.assertEqual(result, "BLOCKED")

    def test_revoked_release_blocked(self) -> None:
        policy = build_environment_promotion_policy()
        result, violations = validate_promotion_edge(
            policy=policy,
            from_environment="SUPERVISED_PILOT",
            to_environment="SUPERVISED_LIVE",
            source_artifact_hash="hash-a",
            target_artifact_hash="hash-a",
            evidence_refs=("BUILD33_pilot_evidence", "BUILD34_deployment_evidence", "BUILD35_release_approval"),
            release_approval_status=ReleaseApprovalStatus.REVOKED.value,
        )
        self.assertEqual(result, "BLOCKED")


class ChangeWindowTests(unittest.TestCase):
    def test_inside_window_allowed(self) -> None:
        policy = build_change_window_policy()
        result, violations = evaluate_change_window(
            policy=policy,
            environment_kind="TEST",
            inside_window=True,
            active_ambiguous_orders=False,
            reconciled=True,
            backup_verified=True,
        )
        self.assertEqual(result, "ALLOWED")
        self.assertEqual(violations, [])

    def test_outside_window_blocked(self) -> None:
        policy = build_change_window_policy()
        result, _ = evaluate_change_window(
            policy=policy,
            environment_kind="SUPERVISED_LIVE",
            inside_window=False,
            active_ambiguous_orders=False,
            reconciled=True,
            backup_verified=True,
        )
        self.assertEqual(result, "BLOCKED")

    def test_active_order_blocks(self) -> None:
        policy = build_change_window_policy()
        result, violations = evaluate_change_window(
            policy=policy,
            environment_kind="SUPERVISED_LIVE",
            inside_window=True,
            active_ambiguous_orders=True,
            reconciled=True,
            backup_verified=True,
        )
        self.assertEqual(result, "BLOCKED")
        self.assertTrue(any("order" in v for v in violations))

    def test_unreconciled_blocked(self) -> None:
        policy = build_change_window_policy()
        result, _ = evaluate_change_window(
            policy=policy,
            environment_kind="SUPERVISED_LIVE",
            inside_window=True,
            active_ambiguous_orders=False,
            reconciled=False,
            backup_verified=True,
        )
        self.assertEqual(result, "BLOCKED")

    def test_emergency_allowed(self) -> None:
        policy = build_change_window_policy()
        result, _ = evaluate_change_window(
            policy=policy,
            environment_kind="SUPERVISED_LIVE",
            inside_window=False,
            active_ambiguous_orders=True,
            reconciled=False,
            backup_verified=False,
            emergency=True,
        )
        self.assertEqual(result, "EMERGENCY_ALLOWED")


class ChangeImpactTests(unittest.TestCase):
    def test_docs_only_minimal_requalification(self) -> None:
        cls = classify_changed_path("docs/engineering/README.md")
        self.assertEqual(cls, ChangeClass.DOCS_ONLY.value)
        self.assertEqual(required_requalification_for_change(cls), ())

    def test_temporal_logic_substantial_requalification(self) -> None:
        cls = classify_changed_path("src/market_platform_foundation/intelligence/temporal/guard.py")
        self.assertEqual(cls, ChangeClass.TEMPORAL_INTEGRITY.value)
        reqs = required_requalification_for_change(cls)
        self.assertIn("BUILD26", reqs)
        self.assertIn("BUILD25", reqs)

    def test_broker_adapter_invalidates_live(self) -> None:
        cls = classify_changed_path("src/market_platform_foundation/intelligence/broker/adapter.py")
        reqs = required_requalification_for_change(cls)
        self.assertIn("BUILD28", reqs)

    def test_risk_invalidates_execution(self) -> None:
        cls = classify_changed_path("src/market_platform_foundation/intelligence/risk/engine.py")
        reqs = required_requalification_for_change(cls)
        self.assertIn("BUILD27", reqs)

    def test_change_impact_policy_deterministic(self) -> None:
        p1 = build_change_impact_policy()
        p2 = build_change_impact_policy()
        self.assertEqual(p1.change_impact_policy_id, p2.change_impact_policy_id)


class RegistryTests(unittest.TestCase):
    def test_append_only_history(self) -> None:
        registry = ProductionReleaseRegistry()
        (
            _release,
            _gov,
            _evidence,
            candidate,
            _elig,
            _spec,
            _report,
            approval,
            _env,
            _cw,
        ) = assemble_release_candidate_fixture(allow_dirty=True)
        registry.register_candidate(candidate)
        registry.register_approval(approval, event_time_ns=T)
        self.assertEqual(registry.event_count(), 2)

    def test_current_approved_derived(self) -> None:
        registry = ProductionReleaseRegistry()
        (
            _release,
            _gov,
            _evidence,
            candidate,
            _elig,
            _spec,
            _report,
            approval,
            _env,
            _cw,
        ) = assemble_release_candidate_fixture(allow_dirty=True)
        registry.register_candidate(candidate)
        registry.register_approval(approval, event_time_ns=T)
        current = registry.current_approved_release()
        self.assertIsNotNone(current)
        assert current is not None
        self.assertEqual(current.release_approval_id, approval.release_approval_id)

    def test_revoked_not_current(self) -> None:
        registry = ProductionReleaseRegistry()
        (
            _release,
            _gov,
            _evidence,
            candidate,
            _elig,
            _spec,
            _report,
            approval,
            _env,
            _cw,
        ) = assemble_release_candidate_fixture(allow_dirty=True)
        registry.register_candidate(candidate)
        registry.register_approval(approval, event_time_ns=T)
        revoked = revoke_release_approval(approval, reason="defect", revocation_time_ns=T + 1)
        registry.register_revocation(revoked, event_time_ns=T + 1, reason="defect")
        self.assertIsNone(registry.current_approved_release())


class AcceptanceMatrixTests(unittest.TestCase):
    def test_spec_covers_all_domains(self) -> None:
        spec = build_full_system_acceptance_spec(source_sha=HEAD)
        self.assertGreaterEqual(len(spec.required_domains), 29)
        self.assertEqual(spec.required_build_range, (1, 35))

    def test_acceptance_report_generated(self) -> None:
        (
            _release,
            _gov,
            evidence,
            candidate,
            _elig,
            spec,
            report,
            _approval,
            _env,
            _cw,
        ) = assemble_release_candidate_fixture(allow_dirty=True)
        self.assertTrue(report.full_system_acceptance_report_id.startswith("FSAREP-"))
        self.assertEqual(len(report.domain_results), len(spec.required_domains))

    def test_false_global_green_blocked(self) -> None:
        results = tuple(
            DomainAcceptanceResultV1(
                domain=f"domain_{i}",
                evidence_refs=(),
                blocking=False,
                result=RequirementResult.PASS.value,
                limitations=(),
            )
            for i in range(99)
        ) + (
            DomainAcceptanceResultV1(
                domain="Temporal integrity",
                evidence_refs=(),
                blocking=True,
                result=RequirementResult.FAIL.value,
                limitations=("temporal leak",),
            ),
        )
        self.assertTrue(false_global_green_blocked(results))

    def test_nonblocking_limitation_allows_acceptance_with_limitations(self) -> None:
        (
            _release,
            _gov,
            _evidence,
            _candidate,
            _elig,
            _spec,
            report,
            _approval,
            _env,
            _cw,
        ) = assemble_release_candidate_fixture(allow_dirty=True)
        self.assertIn(
            report.final_disposition,
            (
                FullSystemAcceptanceDisposition.FULL_SYSTEM_ACCEPTED_WITH_LIMITATIONS.value,
                FullSystemAcceptanceDisposition.FULL_SYSTEM_ACCEPTED_FOR_SUPERVISED_OPERATION.value,
            ),
        )


class AuthorityMapTests(unittest.TestCase):
    def test_no_duplicate_authorities(self) -> None:
        duplicates = find_duplicate_authorities()
        self.assertEqual(duplicates, [])

    def test_authority_map_complete(self) -> None:
        auth_map = build_canonical_authority_map()
        decisions = {e.decision_artifact for e in auth_map.entries}
        self.assertIn("Forecast", decisions)
        self.assertIn("Release governance", decisions)
        self.assertIn("Live session authorization", decisions)

    def test_forbidden_paths_documented(self) -> None:
        auth_map = build_canonical_authority_map()
        self.assertTrue(len(auth_map.forbidden_paths) >= 5)


class DirectPathAuditTests(unittest.TestCase):
    def test_no_forecast_to_broker(self) -> None:
        findings = audit_direct_forecast_to_broker()
        self.assertEqual(findings, [])

    def test_no_llm_to_broker(self) -> None:
        findings = audit_direct_llm_to_broker()
        self.assertEqual(findings, [])

    def test_no_deployment_to_live_authorization(self) -> None:
        findings = audit_deployment_to_live_authorization()
        self.assertEqual(findings, [])

    def test_no_release_approval_to_order_confirmation(self) -> None:
        findings = audit_release_approval_to_order_confirmation()
        self.assertEqual(findings, [])


class RollbackExerciseTests(unittest.TestCase):
    def test_all_rollback_exercises_pass(self) -> None:
        results = run_rollback_exercises()
        self.assertEqual(len(results), 6)
        for r in results:
            self.assertEqual(r.result, "PASS", f"{r.exercise_id}: {r.scenario}")


class RevocationExerciseTests(unittest.TestCase):
    def test_revocation_exercise_passes(self) -> None:
        result = run_revocation_exercise()
        self.assertEqual(result.result, "PASS")
        self.assertTrue(result.deployment_blocked)
        self.assertTrue(result.historical_evidence_preserved)


class LifecycleFixtureTests(unittest.TestCase):
    def test_full_lifecycle_passes(self) -> None:
        result = run_full_lifecycle_fixture()
        self.assertEqual(result.result, "PASS")
        self.assertTrue(result.authority_checks_passed)

    def test_change_window_deployment_fixture(self) -> None:
        self.assertEqual(run_change_window_deployment_fixture(), "PASS")


class NoAutonomyTests(unittest.TestCase):
    def test_no_live_authorization_creation(self) -> None:
        self.assertFalse(release_approval_creates_live_authority())
        self.assertFalse(approval_authorizes_live_session())

    def test_no_adaptation_calls(self) -> None:
        with mock.patch(
            "market_platform_foundation.intelligence.training.factory.TrainingFactory.generate_candidates"
        ) as train:
            assemble_release_candidate_fixture(allow_dirty=True)
            train.assert_not_called()


class KnownLimitationsTests(unittest.TestCase):
    def test_limitations_catalog_not_empty(self) -> None:
        self.assertGreater(len(BUILD35_KNOWN_LIMITATIONS), 5)

    def test_human_confirmation_mandatory(self) -> None:
        self.assertTrue(
            any("human" in lim.lower() and "confirmation" in lim.lower() for lim in BUILD35_KNOWN_LIMITATIONS)
        )


if __name__ == "__main__":
    unittest.main()
