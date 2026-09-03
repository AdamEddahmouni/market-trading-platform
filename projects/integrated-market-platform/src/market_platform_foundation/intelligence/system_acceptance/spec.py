"""System acceptance spec builder (BUILD 25)."""

from __future__ import annotations

from .identity import derive_acceptance_spec_id
from .invariants import REQUIRED_INVARIANT_IDS
from .scenarios import REQUIRED_SCENARIOS
from .types import FailureClass, SYSTEM_ACCEPTANCE_IMPLEMENTATION_VERSION, SYSTEM_ACCEPTANCE_SCHEMA_VERSION, SystemAcceptanceSpecV1

KNOWN_LIMITATION_IDS: tuple[str, ...] = (
    "KL-001",
    "KL-002",
    "KL-003",
    "KL-004",
    "KL-005",
    "KL-006",
    "KL-007",
    "KL-008",
    "KL-009",
    "KL-010",
)

REQUIRED_SUITES: tuple[str, ...] = (
    "tests/intelligence",
    "tests/platform/test_shadow_p6",
    "tests/intelligence/test_persistence_conformance",
    "tests/intelligence/test_replay_integration",
    "tests/intelligence/test_build01_24_lifecycle",
    "tests/intelligence/test_system_acceptance",
)


def build_acceptance_spec(*, source_build_head: str) -> SystemAcceptanceSpecV1:
    spec = SystemAcceptanceSpecV1(
        acceptance_spec_id="pending",
        schema_version=SYSTEM_ACCEPTANCE_SCHEMA_VERSION,
        source_build_head=source_build_head,
        required_build_range=(1, 24),
        required_suites=REQUIRED_SUITES,
        required_lifecycle_scenarios=("A01", "A02", "A25"),
        required_adversarial_scenarios=REQUIRED_SCENARIOS,
        required_invariants=REQUIRED_INVARIANT_IDS,
        required_persistence_checks=("immutable_insert", "same_id_conflict", "idempotent_retry"),
        required_replay_checks=("observed_replay_determinism", "fault_containment"),
        required_determinism_checks=("golden_lifecycle_twice", "input_order_shuffle"),
        required_security_checks=("no_live_execution", "no_secrets_in_fixtures", "artifact_integrity"),
        allowed_known_limitations=KNOWN_LIMITATION_IDS,
        blocking_failure_classes=(
            FailureClass.TEMPORAL_LEAKAGE,
            FailureClass.NON_DETERMINISTIC_IDENTITY,
            FailureClass.SILENT_PERSISTENCE_OVERWRITE,
            FailureClass.HOLDOUT_BYPASS,
            FailureClass.CONTAMINATED_PROMOTION,
            FailureClass.NON_CHAMPION_OPPORTUNITY,
            FailureClass.RISK_BYPASS,
            FailureClass.LIVE_EXECUTION_REACHABLE,
            FailureClass.MONITORING_TRAINS,
            FailureClass.ADAPTATION_PROMOTES,
            FailureClass.UNPROMOTED_ACTIVATION,
            FailureClass.ARTIFACT_HASH_MISMATCH_IGNORED,
            FailureClass.AUTHORITY_BYPASS,
        ),
        implementation_version=SYSTEM_ACCEPTANCE_IMPLEMENTATION_VERSION,
        metadata={"build": "BUILD_25_SYSTEM_ACCEPTANCE"},
    )
    spec_id = derive_acceptance_spec_id(spec)
    return SystemAcceptanceSpecV1(
        acceptance_spec_id=spec_id,
        schema_version=spec.schema_version,
        source_build_head=spec.source_build_head,
        required_build_range=spec.required_build_range,
        required_suites=spec.required_suites,
        required_lifecycle_scenarios=spec.required_lifecycle_scenarios,
        required_adversarial_scenarios=spec.required_adversarial_scenarios,
        required_invariants=spec.required_invariants,
        required_persistence_checks=spec.required_persistence_checks,
        required_replay_checks=spec.required_replay_checks,
        required_determinism_checks=spec.required_determinism_checks,
        required_security_checks=spec.required_security_checks,
        allowed_known_limitations=spec.allowed_known_limitations,
        blocking_failure_classes=spec.blocking_failure_classes,
        implementation_version=spec.implementation_version,
        metadata=spec.metadata,
    )
