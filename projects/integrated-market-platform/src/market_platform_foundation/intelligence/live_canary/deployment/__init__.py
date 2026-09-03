"""Deployment packaging and change control (BUILD 34)."""

from .canary import build_deployment_canary_spec, run_deployment_canary
from .change_control import (
    build_change_request,
    deployment_requires_approved_change_request,
)
from .configuration import (
    build_deployment_configuration,
    configuration_hash,
    validate_configuration_for_environment,
    validate_configuration_no_policy_override,
)
from .drift import assess_configuration_drift, drift_blocks_live_actions
from .environment import (
    build_environment_manifest,
    unknown_environment_fails_closed,
    validate_environment_manifest,
)
from .identity import derive_release_id, hash_configuration
from .migration import (
    build_migration_plan,
    destructive_migration_without_backup_blocked,
    rollback_compatible,
)
from .packaging import (
    build_release_manifest,
    compare_semantic_identity,
    create_release_bundle,
    scan_bundle_for_secrets,
)
from .plan import (
    build_deployment_plan,
    build_deployment_record,
    deployment_grants_live_authority,
)
from .policy import BUILD33_HEAD, build_default_deployment_policy_refs
from .promotion import floating_latest_prohibited, promote_release, validate_promotion_gates
from .qualification import (
    build_deployment_qualification_report,
    build_deployment_qualification_spec,
)
from .rollback import (
    build_rollback_plan,
    decide_rollback,
    rollback_auto_resumes_live,
)
from .runner import (
    run_failed_deployment_rollback_fixture,
    run_full_successful_deployment_fixture,
    run_migration_fixture,
    run_reproducibility_fixture,
)
from .source_provenance import (
    collect_source_provenance,
    dirty_tree_blocks_release,
    hash_dependency_lock,
    hash_tracked_source_tree,
    is_source_tree_clean,
    verify_dependency_lock_consistent,
)
from .supervision import (
    CRASH_LOOP_THRESHOLD,
    FixtureServiceSupervisor,
    build_default_service_graph,
    validate_startup_order,
)
from .telemetry import build_deployment_snapshot, build_runtime_version_report
from .types import (
    BUILD34_KNOWN_LIMITATIONS,
    DEPLOYMENT_IMPLEMENTATION_VERSION,
    DEPLOYMENT_SCHEMA_VERSION,
    BrokerEnvironment,
    ChangeApprovalState,
    ChangeType,
    DeploymentDisposition,
    EnvironmentKind,
    ExecutionAuthority,
    ExecutionMode,
    PromotionResult,
    RollbackDecision,
)

__all__ = [
    "BUILD33_HEAD",
    "BUILD34_KNOWN_LIMITATIONS",
    "BrokerEnvironment",
    "CRASH_LOOP_THRESHOLD",
    "ChangeApprovalState",
    "ChangeType",
    "DEPLOYMENT_IMPLEMENTATION_VERSION",
    "DEPLOYMENT_SCHEMA_VERSION",
    "DeploymentDisposition",
    "EnvironmentKind",
    "ExecutionAuthority",
    "ExecutionMode",
    "FixtureServiceSupervisor",
    "PromotionResult",
    "RollbackDecision",
    "assess_configuration_drift",
    "build_change_request",
    "build_default_deployment_policy_refs",
    "build_default_service_graph",
    "build_deployment_canary_spec",
    "build_deployment_configuration",
    "build_deployment_plan",
    "build_deployment_qualification_report",
    "build_deployment_qualification_spec",
    "build_deployment_record",
    "build_deployment_snapshot",
    "build_environment_manifest",
    "build_migration_plan",
    "build_release_manifest",
    "build_rollback_plan",
    "build_runtime_version_report",
    "collect_source_provenance",
    "compare_semantic_identity",
    "configuration_hash",
    "create_release_bundle",
    "decide_rollback",
    "deployment_grants_live_authority",
    "deployment_requires_approved_change_request",
    "derive_release_id",
    "destructive_migration_without_backup_blocked",
    "dirty_tree_blocks_release",
    "drift_blocks_live_actions",
    "floating_latest_prohibited",
    "hash_configuration",
    "hash_dependency_lock",
    "hash_tracked_source_tree",
    "is_source_tree_clean",
    "promote_release",
    "rollback_auto_resumes_live",
    "rollback_compatible",
    "run_deployment_canary",
    "run_failed_deployment_rollback_fixture",
    "run_full_successful_deployment_fixture",
    "run_migration_fixture",
    "run_reproducibility_fixture",
    "scan_bundle_for_secrets",
    "unknown_environment_fails_closed",
    "validate_configuration_for_environment",
    "validate_configuration_no_policy_override",
    "validate_environment_manifest",
    "validate_promotion_gates",
    "validate_startup_order",
    "verify_dependency_lock_consistent",
]
