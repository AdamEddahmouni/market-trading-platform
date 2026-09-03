"""Production release governance and full-system acceptance contracts (BUILD 35).

Release governance binds exact artifacts, evidence bundles, and policy envelopes to
explicit human-governed approval decisions. It does NOT authorize live sessions,
orders, model promotion, or runtime activation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

RELEASE_GOVERNANCE_SCHEMA_VERSION = "1"
RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION = "build35-v1"

BUILD34_HEAD = "1cbfb415c398b37056030c6037b91744f7a33b90"

BUILD35_KNOWN_LIMITATIONS = (
    "single-machine local deployment qualification only",
    "no production cloud infrastructure or external release registry service",
    "release approval is local/single-user fixture qualification",
    "BUILD26 forward qualification disposition INSUFFICIENT_FORWARD_EVIDENCE",
    "BUILD29 canary disposition CANARY_NOT_EXECUTED — fixture qualification only",
    "limited real live canary sample — zero real broker submits in qualification",
    "provider redundancy not exercised against live providers",
    "single-host deployment — no HA or multi-instance",
    "no automatic broker failover by design",
    "no derivatives live certification",
    "human session authorization and per-order confirmation remain mandatory",
    "release approval does not authorize autonomous live trading",
    "some acceptance domains rely on deterministic fixtures rather than real live observations",
    "insufficient long-duration real pilot evidence",
)

FORBIDDEN_AUTONOMY_EXPANSIONS = frozenset(
    {
        "autonomous_live_trading",
        "remove_session_authorization",
        "remove_order_confirmation",
        "remove_manual_incident_resume",
        "raise_live_caps",
        "enable_margin",
        "enable_live_shorts",
        "enable_options",
        "enable_futures",
        "enable_crypto",
        "automatic_broker_failover",
        "deployment_creates_live_authorization",
        "release_approval_creates_live_authorization",
    }
)


class ReleaseCandidateStatus(StrEnum):
    ASSEMBLED = "ASSEMBLED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    SUPERSEDED = "SUPERSEDED"


class EligibilityDisposition(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    INCONCLUSIVE = "INCONCLUSIVE"
    INVALID = "INVALID"


class ReleaseApprovalStatus(StrEnum):
    APPROVED_SUPERVISED_OPERATION = "APPROVED_SUPERVISED_OPERATION"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


class FullSystemAcceptanceDisposition(StrEnum):
    FULL_SYSTEM_ACCEPTED_FOR_SUPERVISED_OPERATION = "FULL_SYSTEM_ACCEPTED_FOR_SUPERVISED_OPERATION"
    FULL_SYSTEM_ACCEPTED_WITH_LIMITATIONS = "FULL_SYSTEM_ACCEPTED_WITH_LIMITATIONS"
    REQUIRES_REQUALIFICATION = "REQUIRES_REQUALIFICATION"
    NOT_OPERATIONALLY_ACCEPTABLE = "NOT_OPERATIONALLY_ACCEPTABLE"
    INVALID_EVIDENCE = "INVALID_EVIDENCE"


class RequirementCriticality(StrEnum):
    BLOCKING = "BLOCKING"
    REQUIRED = "REQUIRED"
    NONBLOCKING_LIMITATION = "NONBLOCKING_LIMITATION"
    INFORMATIONAL = "INFORMATIONAL"


class RequirementResult(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    NOT_EVALUATED = "NOT_EVALUATED"


class ChangeClass(StrEnum):
    DOCS_ONLY = "DOCS_ONLY"
    NON_RUNTIME_TOOLING = "NON_RUNTIME_TOOLING"
    UI_READ_ONLY = "UI_READ_ONLY"
    OPERATOR_MUTATION = "OPERATOR_MUTATION"
    OBSERVABILITY = "OBSERVABILITY"
    DEPLOYMENT_CONFIG = "DEPLOYMENT_CONFIG"
    PROVIDER_ADAPTER = "PROVIDER_ADAPTER"
    BROKER_ADAPTER = "BROKER_ADAPTER"
    INTELLIGENCE = "INTELLIGENCE"
    TEMPORAL_INTEGRITY = "TEMPORAL_INTEGRITY"
    PERSISTENCE_SCHEMA = "PERSISTENCE_SCHEMA"
    RISK_EXECUTION = "RISK_EXECUTION"
    GOVERNANCE = "GOVERNANCE"
    SECURITY_CRITICAL = "SECURITY_CRITICAL"


class ReleaseHistoryEventType(StrEnum):
    CANDIDATE_ASSEMBLED = "CANDIDATE_ASSEMBLED"
    ELIGIBILITY_EVALUATED = "ELIGIBILITY_EVALUATED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PROMOTED = "PROMOTED"
    DEPLOYED = "DEPLOYED"
    ROLLED_BACK = "ROLLED_BACK"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class PromotionEdgeResult(StrEnum):
    PROMOTED = "PROMOTED"
    BLOCKED = "BLOCKED"
    INVALID = "INVALID"


class ChangeWindowResult(StrEnum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"
    EMERGENCY_ALLOWED = "EMERGENCY_ALLOWED"


@dataclass(frozen=True)
class ProductionReleaseGovernancePolicyV1:
    release_governance_policy_id: str
    schema_version: str
    eligible_source_branches: tuple[str, ...]
    required_build_evidence: tuple[str, ...]
    required_test_suites: tuple[str, ...]
    required_qualification_dispositions: dict[str, tuple[str, ...]]
    required_source_cleanliness: bool
    required_release_manifest: bool
    required_deployment_qualification_report: bool
    required_operational_pilot_evidence: bool
    minimum_provider_qualification_states: tuple[str, ...]
    required_unresolved_limitation_classifications: tuple[str, ...]
    environment_promotion_policy_ref: str
    change_window_policy_ref: str
    rollback_policy_ref: str
    approval_requirements: tuple[str, ...]
    release_expiry_policy_ref: str
    revocation_conditions: tuple[str, ...]
    forbidden_authority_expansions: tuple[str, ...]
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReleaseEvidenceBundleV1:
    release_evidence_bundle_id: str
    schema_version: str
    release_manifest_ref: str
    build25_acceptance_ref: str
    build26_forward_qualification_ref: str
    build27_execution_qualification_ref: str
    build28_live_safety_qualification_ref: str
    build29_canary_evidence_ref: str
    build30_supervised_operations_ref: str
    build31_operator_qualification_ref: str
    build32_reliability_qualification_ref: str
    build33_production_pilot_ref: str
    build34_deployment_qualification_ref: str
    test_run_refs: tuple[str, ...]
    security_scan_refs: tuple[str, ...]
    known_limitation_refs: tuple[str, ...]
    rollback_evidence_refs: tuple[str, ...]
    backup_restore_evidence_refs: tuple[str, ...]
    source_hashes: dict[str, str]
    artifact_hashes: dict[str, str]
    environment_compatibility_refs: tuple[str, ...]
    assembled_at_ns: int
    lineage: dict[str, str]
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProductionReleaseCandidateV1:
    production_release_candidate_id: str
    schema_version: str
    release_manifest_ref: str
    release_evidence_bundle_ref: str
    release_governance_policy_ref: str
    exact_source_sha: str
    artifact_hashes: dict[str, str]
    configuration_schema_version: str
    allowed_environment_kinds: tuple[str, ...]
    allowed_immutable_policy_refs: tuple[str, ...]
    current_champion_refs: tuple[str, ...]
    known_limitations: tuple[str, ...]
    candidate_status: str
    implementation_version: str
    lineage: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EligibilityReasonV1:
    reason_code: str
    description: str
    blocking: bool


@dataclass(frozen=True)
class ProductionReleaseEligibilityAssessmentV1:
    eligibility_assessment_id: str
    schema_version: str
    candidate_ref: str
    governance_policy_ref: str
    evidence_bundle_ref: str
    disposition: str
    reasons: tuple[EligibilityReasonV1, ...]
    blocking_reasons: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    incompatible_evidence: tuple[str, ...]
    limitations: tuple[str, ...]
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProductionReleaseApprovalV1:
    release_approval_id: str
    schema_version: str
    candidate_ref: str
    eligibility_assessment_ref: str
    approved_environment_scope: tuple[str, ...]
    approval_time_ns: int
    approval_status: str
    limitations_accepted: tuple[str, ...]
    blocking_limitations_rejected: tuple[str, ...]
    release_expiry_ns: int | None
    governance_reason: str
    implementation_version: str
    lineage: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChangeImpactPolicyV1:
    change_impact_policy_id: str
    schema_version: str
    path_surface_classifications: dict[str, str]
    impact_domains: dict[str, tuple[str, ...]]
    required_build_requalification: dict[str, tuple[str, ...]]
    required_tests: dict[str, tuple[str, ...]]
    requires_full_system_acceptance: dict[str, bool]
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChangeWindowPolicyV1:
    change_window_policy_id: str
    schema_version: str
    environment_scope: tuple[str, ...]
    allowed_windows: tuple[dict[str, Any], ...]
    market_session_restrictions: tuple[str, ...]
    emergency_change_rules: tuple[str, ...]
    required_pre_change_reconciliation: bool
    required_pre_change_backup: bool
    required_operator_state: tuple[str, ...]
    required_post_change_observation_duration_ns: int
    required_rollback_availability: bool
    active_order_behavior: str
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EnvironmentPromotionPolicyV1:
    environment_promotion_policy_id: str
    schema_version: str
    environment_graph: tuple[tuple[str, str], ...]
    required_evidence_per_edge: dict[str, tuple[str, ...]]
    artifact_identity_requirement: str
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReleaseHistoryEventV1:
    event_id: str
    schema_version: str
    event_type: str
    event_time_ns: int
    release_candidate_ref: str | None
    release_approval_ref: str | None
    environment_kind: str | None
    details: dict[str, Any]
    implementation_version: str


@dataclass(frozen=True)
class AcceptanceRequirementV1:
    requirement_id: str
    domain: str
    description: str
    criticality: str
    evidence_refs: tuple[str, ...]
    validation_method: str
    result: str
    limitations: tuple[str, ...]
    blocking_behavior: str


@dataclass(frozen=True)
class FullSystemOperationalAcceptanceSpecV1:
    acceptance_spec_id: str
    schema_version: str
    required_build_range: tuple[int, int]
    required_domains: tuple[str, ...]
    blocking_requirement_ids: tuple[str, ...]
    required_evidence_refs: tuple[str, ...]
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DomainAcceptanceResultV1:
    domain: str
    evidence_refs: tuple[str, ...]
    blocking: bool
    result: str
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class FullSystemOperationalAcceptanceReportV1:
    full_system_acceptance_report_id: str
    schema_version: str
    acceptance_spec_ref: str
    release_candidate_ref: str
    release_evidence_bundle_ref: str
    accepted_source_sha: str
    release_artifact_hashes: dict[str, str]
    domain_results: tuple[DomainAcceptanceResultV1, ...]
    blocking_requirements: tuple[AcceptanceRequirementV1, ...]
    nonblocking_limitations: tuple[str, ...]
    unresolved_risks: tuple[str, ...]
    deployment_readiness: str
    supervised_operation_readiness: str
    final_disposition: str
    implementation_version: str
    lineage: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CanonicalAuthorityEntryV1:
    decision_artifact: str
    canonical_authority: str
    authority_module: str
    authority_build: int


@dataclass(frozen=True)
class CanonicalAuthorityMapV1:
    authority_map_id: str
    schema_version: str
    entries: tuple[CanonicalAuthorityEntryV1, ...]
    forbidden_paths: tuple[tuple[str, str], ...]
    implementation_version: str
