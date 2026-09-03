"""Production release governance and full-system acceptance (BUILD 35)."""

from .acceptance import (
    ACCEPTANCE_DOMAINS,
    build_full_system_acceptance_report,
    build_full_system_acceptance_spec,
    false_global_green_blocked,
)
from .approval import (
    approval_authorizes_live_session,
    approval_confirms_order,
    build_release_approval,
    revoke_release_approval,
)
from .audit import (
    audit_deployment_to_live_authorization,
    audit_direct_forecast_to_broker,
    audit_direct_llm_to_broker,
    audit_direct_research_to_active_model,
    audit_release_approval_to_order_confirmation,
)
from .authority import build_canonical_authority_map, find_duplicate_authorities
from .candidate import build_production_release_candidate
from .change_impact import build_change_impact_policy, classify_changed_path, required_requalification_for_change
from .change_window import build_change_window_policy, evaluate_change_window
from .eligibility import assess_release_eligibility, release_approval_creates_live_authority
from .environment_promotion import build_environment_promotion_policy, validate_promotion_edge
from .evidence import build_release_evidence_bundle, load_build_dispositions_from_artifacts, verify_evidence_lineage
from .policy import build_default_release_governance_policy
from .registry import ProductionReleaseRegistry
from .runner import (
    assemble_release_candidate_fixture,
    run_change_window_deployment_fixture,
    run_full_lifecycle_fixture,
    run_revocation_exercise,
    run_rollback_exercises,
)
from .types import (
    BUILD34_HEAD,
    BUILD35_KNOWN_LIMITATIONS,
    FORBIDDEN_AUTONOMY_EXPANSIONS,
    RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION,
    RELEASE_GOVERNANCE_SCHEMA_VERSION,
    ChangeClass,
    EligibilityDisposition,
    FullSystemAcceptanceDisposition,
    ReleaseApprovalStatus,
    ReleaseCandidateStatus,
)

__all__ = [
    "ACCEPTANCE_DOMAINS",
    "BUILD34_HEAD",
    "BUILD35_KNOWN_LIMITATIONS",
    "ChangeClass",
    "EligibilityDisposition",
    "FORBIDDEN_AUTONOMY_EXPANSIONS",
    "FullSystemAcceptanceDisposition",
    "ProductionReleaseRegistry",
    "RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION",
    "RELEASE_GOVERNANCE_SCHEMA_VERSION",
    "ReleaseApprovalStatus",
    "ReleaseCandidateStatus",
    "approval_authorizes_live_session",
    "approval_confirms_order",
    "assemble_release_candidate_fixture",
    "assess_release_eligibility",
    "audit_deployment_to_live_authorization",
    "audit_direct_forecast_to_broker",
    "audit_direct_llm_to_broker",
    "audit_direct_research_to_active_model",
    "audit_release_approval_to_order_confirmation",
    "build_canonical_authority_map",
    "build_change_impact_policy",
    "build_change_window_policy",
    "build_default_release_governance_policy",
    "build_environment_promotion_policy",
    "build_full_system_acceptance_report",
    "build_full_system_acceptance_spec",
    "build_production_release_candidate",
    "build_release_approval",
    "build_release_evidence_bundle",
    "classify_changed_path",
    "evaluate_change_window",
    "false_global_green_blocked",
    "find_duplicate_authorities",
    "load_build_dispositions_from_artifacts",
    "release_approval_creates_live_authority",
    "required_requalification_for_change",
    "revoke_release_approval",
    "run_change_window_deployment_fixture",
    "run_full_lifecycle_fixture",
    "run_revocation_exercise",
    "run_rollback_exercises",
    "validate_promotion_edge",
    "verify_evidence_lineage",
]
