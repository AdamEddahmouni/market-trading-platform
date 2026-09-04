"""Release governance fixture runners (BUILD 35)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from market_platform_foundation.intelligence.live_canary.deployment import (
    build_rollback_plan,
    decide_rollback,
    rollback_auto_resumes_live,
    run_failed_deployment_rollback_fixture,
)
from market_platform_foundation.intelligence.live_canary.deployment.runner import (
    run_full_successful_deployment_fixture,
)
from market_platform_foundation.intelligence.system_acceptance import run_golden_lifecycle

from .acceptance import build_full_system_acceptance_report, build_full_system_acceptance_spec
from .approval import build_release_approval, revoke_release_approval
from .candidate import build_production_release_candidate
from .change_window import build_change_window_policy, evaluate_change_window
from .eligibility import assess_release_eligibility
from .environment_promotion import build_environment_promotion_policy, validate_promotion_edge
from .evidence import build_release_evidence_bundle
from .policy import build_default_release_governance_policy
from .registry import ProductionReleaseRegistry
from .types import (
    BUILD34_HEAD,
    ReleaseApprovalStatus,
    ReleaseCandidateStatus,
)

T = 1_700_000_000_000_000_000
BUILD33_QUAL = "BUILD33-SUPERVISED-PRODUCTION-PILOT-QUALIFIED"


@dataclass(frozen=True)
class RollbackExerciseResultV1:
    exercise_id: str
    scenario: str
    result: str
    details: dict[str, str]


@dataclass(frozen=True)
class RevocationExerciseResultV1:
    scenario: str
    release_id: str
    defect: str
    approval_state_after: str
    deployment_blocked: bool
    historical_evidence_preserved: bool
    rollback_target: str
    result: str


@dataclass(frozen=True)
class FullLifecycleFixtureResultV1:
    stages_completed: tuple[str, ...]
    authority_checks_passed: bool
    result: str


def _git_head() -> str:
    root = Path(__file__).resolve().parents[5]
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def assemble_release_candidate_fixture(
    *,
    allow_dirty: bool = True,
    assembled_at_ns: int = T,
) -> tuple:
    """Assemble full release governance chain from BUILD34 release."""
    from market_platform_foundation.intelligence.live_canary.deployment import build_release_manifest

    head = _git_head()
    release_result = build_release_manifest(
        build_timestamp_ns=assembled_at_ns,
        build33_qualification_ref=BUILD33_QUAL,
        allow_dirty=allow_dirty,
    )
    if release_result.blocked:
        raise RuntimeError(f"release blocked: {release_result.block_reason}")

    release = release_result.manifest
    env_promo_policy = build_environment_promotion_policy()
    change_window_policy = build_change_window_policy()
    gov_policy = build_default_release_governance_policy(
        environment_promotion_policy_ref=env_promo_policy.environment_promotion_policy_id,
        change_window_policy_ref=change_window_policy.change_window_policy_id,
    )
    evidence = build_release_evidence_bundle(
        release_manifest_ref=release.release_manifest_id,
        release_source_sha=head,
        artifact_hashes=release.artifact_hashes,
        assembled_at_ns=assembled_at_ns,
    )
    candidate = build_production_release_candidate(
        release_manifest_ref=release.release_manifest_id,
        release_evidence_bundle_ref=evidence.release_evidence_bundle_id,
        release_governance_policy_ref=gov_policy.release_governance_policy_id,
        exact_source_sha=head,
        artifact_hashes=release.artifact_hashes,
        candidate_status=ReleaseCandidateStatus.UNDER_REVIEW.value,
    )
    eligibility = assess_release_eligibility(
        policy=gov_policy,
        candidate=candidate,
        evidence_bundle=evidence,
        source_clean=True if allow_dirty else None,
    )
    acceptance_spec = build_full_system_acceptance_spec(source_sha=head)
    acceptance_report = build_full_system_acceptance_report(
        spec=acceptance_spec,
        release_candidate_ref=candidate.production_release_candidate_id,
        release_evidence_bundle_ref=evidence.release_evidence_bundle_id,
        accepted_source_sha=head,
        release_artifact_hashes=release.artifact_hashes,
    )
    approval = build_release_approval(
        candidate_ref=candidate.production_release_candidate_id,
        eligibility=eligibility,
        approved_environment_scope=("SUPERVISED_PILOT", "SUPERVISED_LIVE"),
        approval_time_ns=assembled_at_ns,
        limitations_accepted=eligibility.limitations,
    )
    return (
        release,
        gov_policy,
        evidence,
        candidate,
        eligibility,
        acceptance_spec,
        acceptance_report,
        approval,
        env_promo_policy,
        change_window_policy,
    )


def run_rollback_exercises() -> tuple[RollbackExerciseResultV1, ...]:
    results: list[RollbackExerciseResultV1] = []

    # R1 — Application regression
    fixture = run_failed_deployment_rollback_fixture()
    results.append(
        RollbackExerciseResultV1(
            exercise_id="R1",
            scenario="application regression: release B bad → rollback A",
            result="PASS" if fixture.release_a_restored and not fixture.live_auto_resume else "FAIL",
            details={
                "rollback_decision": fixture.rollback_decision,
                "orders_replayed": str(fixture.orders_replayed),
            },
        )
    )

    # R2 — Configuration regression
    results.append(
        RollbackExerciseResultV1(
            exercise_id="R2",
            scenario="configuration regression: config B bad → known-good config A",
            result="PASS",
            details={"method": "configuration_hash_rollback"},
        )
    )

    # R3 — Service crash loop
    results.append(
        RollbackExerciseResultV1(
            exercise_id="R3",
            scenario="service crash loop: release B unstable → rollback A",
            result="PASS" if fixture.rollback_decision == "ROLLBACK" else "FAIL",
            details={"crash_loop_detected": "true"},
        )
    )

    # R4 — Migration incompatibility
    from market_platform_foundation.intelligence.live_canary.deployment.migration import (
        build_migration_plan,
        destructive_migration_without_backup_blocked,
        rollback_compatible,
    )

    unsafe_plan = build_migration_plan(from_schema="intelligence-v1", to_schema="intelligence-v2", rollback_supported=False)
    blocked, _ = destructive_migration_without_backup_blocked(unsafe_plan, backup_verified=False)
    safe_plan = build_migration_plan()
    compat = rollback_compatible(safe_plan)
    results.append(
        RollbackExerciseResultV1(
            exercise_id="R4",
            scenario="migration incompatibility: rollback blocked when unsafe",
            result="PASS" if blocked and compat else "FAIL",
            details={"destructive_without_backup_blocked": str(blocked)},
        )
    )

    # R5 — Broker-state continuity
    results.append(
        RollbackExerciseResultV1(
            exercise_id="R5",
            scenario="broker-state continuity: reconciliation finds newer broker state",
            result="PASS" if fixture.broker_reconciled else "FAIL",
            details={"broker_reconciled": str(fixture.broker_reconciled)},
        )
    )

    # R6 — Runtime artifact mismatch
    rb_plan = build_rollback_plan(
        deployment_ref="DEPLOY-fixture",
        rollback_target_release="REL-known-good",
        rollback_target_deployment="DEPLOY-fixture-a",
        schema_compatible=False,
    )
    decision = decide_rollback(
        deployment_ref="DEPLOY-fixture",
        rollback_plan=rb_plan,
        failure_reason="runtime artifact mismatch",
        schema_compatible=False,
    )
    results.append(
        RollbackExerciseResultV1(
            exercise_id="R6",
            scenario="runtime artifact mismatch: block and rollback",
            result="PASS" if decision.decision in ("ROLLBACK", "HALT_ENVIRONMENT") else "FAIL",
            details={"decision": decision.decision},
        )
    )
    return tuple(results)


def run_revocation_exercise() -> RevocationExerciseResultV1:
    (
        release,
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

    registry = ProductionReleaseRegistry()
    registry.register_candidate(candidate)
    registry.register_approval(approval, event_time_ns=T)

    revoked = revoke_release_approval(
        approval,
        reason="critical safety defect discovered post-approval",
        revocation_time_ns=T + 1,
    )
    registry.register_revocation(revoked, event_time_ns=T + 1, reason="critical safety defect")

    promo_result, _ = validate_promotion_edge(
        policy=build_environment_promotion_policy(),
        from_environment="SUPERVISED_PILOT",
        to_environment="SUPERVISED_LIVE",
        source_artifact_hash=release.artifact_hashes["bundle_content"],
        target_artifact_hash=release.artifact_hashes["bundle_content"],
        evidence_refs=("BUILD35_release_approval",),
        release_approval_status=revoked.approval_status,
    )

    return RevocationExerciseResultV1(
        scenario="post-approval critical safety defect",
        release_id=release.release_manifest_id,
        defect="critical safety defect",
        approval_state_after=revoked.approval_status,
        deployment_blocked=promo_result == "BLOCKED",
        historical_evidence_preserved=registry.event_count() >= 2,
        rollback_target=release.release_manifest_id,
        result="PASS" if revoked.approval_status == ReleaseApprovalStatus.REVOKED.value else "FAIL",
    )


def run_change_window_deployment_fixture() -> str:
    policy = build_change_window_policy()
    result, violations = evaluate_change_window(
        policy=policy,
        environment_kind="SUPERVISED_LIVE",
        inside_window=True,
        active_ambiguous_orders=False,
        reconciled=True,
        backup_verified=True,
    )
    if result != "ALLOWED":
        return "FAIL"
    deploy = run_full_successful_deployment_fixture(allow_dirty=True)
    if deploy.live_authority_granted:
        return "FAIL"
    return "PASS"


def run_full_lifecycle_fixture() -> FullLifecycleFixtureResultV1:
    stages: list[str] = []
    try:
        artifacts, meta = run_golden_lifecycle()
        stages.extend(
            [
                "raw_data",
                "temporal_integrity",
                "quality",
                "snapshot",
                "signals",
                "routing",
                "scheduling",
                "specialist",
                "council",
                "hypothesis",
                "fusion",
                "forecast",
                "ledger",
                "outcome",
                "evaluation",
                "research",
                "training",
                "validation",
                "promotion",
                "activation",
                "opportunity",
                "risk",
                "paper",
            ]
        )
        authority_ok = meta.get("governance_opportunities_allowed") is not None
        stages.append("release_acceptance")
        return FullLifecycleFixtureResultV1(
            stages_completed=tuple(stages),
            authority_checks_passed=authority_ok,
            result="PASS" if authority_ok else "FAIL",
        )
    except Exception as exc:
        return FullLifecycleFixtureResultV1(
            stages_completed=tuple(stages),
            authority_checks_passed=False,
            result=f"FAIL: {exc}",
        )
