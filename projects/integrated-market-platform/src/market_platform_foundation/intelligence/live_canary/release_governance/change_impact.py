"""Change impact policy (BUILD 35)."""

from __future__ import annotations

from .identity import derive_change_impact_policy_id
from .types import (
    RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION,
    RELEASE_GOVERNANCE_SCHEMA_VERSION,
    ChangeClass,
    ChangeImpactPolicyV1,
)

# Path/surface classifications mapped to change classes
PATH_CLASSIFICATIONS: dict[str, str] = {
    "docs/": ChangeClass.DOCS_ONLY.value,
    "tools/": ChangeClass.NON_RUNTIME_TOOLING.value,
    "tests/": ChangeClass.NON_RUNTIME_TOOLING.value,
    "ui/src/components/read": ChangeClass.UI_READ_ONLY.value,
    "ui/src/components/operator": ChangeClass.OPERATOR_MUTATION.value,
    "src/market_platform_foundation/intelligence/contracts": ChangeClass.INTELLIGENCE.value,
    "src/market_platform_foundation/intelligence/temporal": ChangeClass.TEMPORAL_INTEGRITY.value,
    "src/market_platform_foundation/intelligence/providers": ChangeClass.PROVIDER_ADAPTER.value,
    "src/market_platform_foundation/intelligence/broker": ChangeClass.BROKER_ADAPTER.value,
    "src/market_platform_foundation/intelligence/risk": ChangeClass.RISK_EXECUTION.value,
    "src/market_platform_foundation/intelligence/execution": ChangeClass.RISK_EXECUTION.value,
    "src/market_platform_foundation/intelligence/persistence": ChangeClass.PERSISTENCE_SCHEMA.value,
    "src/market_platform_foundation/intelligence/live_canary/deployment": ChangeClass.DEPLOYMENT_CONFIG.value,
    "src/market_platform_foundation/intelligence/live_canary/release_governance": ChangeClass.GOVERNANCE.value,
    "src/market_platform_foundation/intelligence/observability": ChangeClass.OBSERVABILITY.value,
    "src/market_platform_foundation/security": ChangeClass.SECURITY_CRITICAL.value,
}

IMPACT_DOMAINS: dict[str, tuple[str, ...]] = {
    ChangeClass.DOCS_ONLY.value: ("documentation",),
    ChangeClass.TEMPORAL_INTEGRITY.value: (
        "temporal_integrity",
        "replay",
        "forward_qualification",
        "scientific_qualification",
    ),
    ChangeClass.PROVIDER_ADAPTER.value: (
        "normalization",
        "quality",
        "forward_qualification",
        "provider_failover",
    ),
    ChangeClass.BROKER_ADAPTER.value: (
        "live_execution_certification",
        "reconciliation",
        "deployment_acceptance",
    ),
    ChangeClass.RISK_EXECUTION.value: (
        "paper_execution",
        "live_safety",
        "supervised_operations",
    ),
    ChangeClass.PERSISTENCE_SCHEMA.value: ("persistence", "migration", "backup_restore"),
    ChangeClass.DEPLOYMENT_CONFIG.value: ("deployment", "environment_promotion"),
    ChangeClass.GOVERNANCE.value: ("release_governance", "full_system_acceptance"),
    ChangeClass.SECURITY_CRITICAL.value: ("security", "live_safety", "release_governance"),
    ChangeClass.OPERATOR_MUTATION.value: ("operator_control_plane", "live_safety"),
}

REQUIRED_REQUALIFICATION: dict[str, tuple[str, ...]] = {
    ChangeClass.DOCS_ONLY.value: (),
    ChangeClass.TEMPORAL_INTEGRITY.value: ("BUILD26", "BUILD25", "BUILD27"),
    ChangeClass.PROVIDER_ADAPTER.value: ("BUILD26", "BUILD33"),
    ChangeClass.BROKER_ADAPTER.value: ("BUILD28", "BUILD29", "BUILD30", "BUILD34"),
    ChangeClass.RISK_EXECUTION.value: ("BUILD22", "BUILD27", "BUILD28", "BUILD29", "BUILD30"),
    ChangeClass.PERSISTENCE_SCHEMA.value: ("BUILD34", "BUILD32"),
    ChangeClass.DEPLOYMENT_CONFIG.value: ("BUILD34", "BUILD35"),
    ChangeClass.GOVERNANCE.value: ("BUILD35",),
    ChangeClass.SECURITY_CRITICAL.value: ("BUILD28", "BUILD35"),
    ChangeClass.OPERATOR_MUTATION.value: ("BUILD31", "BUILD30"),
}

FULL_SYSTEM_ACCEPTANCE_REQUIRED: dict[str, bool] = {
    ChangeClass.DOCS_ONLY.value: False,
    ChangeClass.TEMPORAL_INTEGRITY.value: True,
    ChangeClass.BROKER_ADAPTER.value: True,
    ChangeClass.RISK_EXECUTION.value: True,
    ChangeClass.GOVERNANCE.value: True,
}


def classify_changed_path(path: str) -> str:
    """Classify a changed path to a change class (conservative)."""
    normalized = path.replace("\\", "/")
    for prefix, change_class in sorted(PATH_CLASSIFICATIONS.items(), key=lambda x: -len(x[0])):
        if normalized.startswith(prefix):
            return change_class
    return ChangeClass.INTELLIGENCE.value


def build_change_impact_policy() -> ChangeImpactPolicyV1:
    policy = ChangeImpactPolicyV1(
        change_impact_policy_id="",
        schema_version=RELEASE_GOVERNANCE_SCHEMA_VERSION,
        path_surface_classifications=PATH_CLASSIFICATIONS,
        impact_domains=IMPACT_DOMAINS,
        required_build_requalification=REQUIRED_REQUALIFICATION,
        required_tests={},
        requires_full_system_acceptance=FULL_SYSTEM_ACCEPTANCE_REQUIRED,
        implementation_version=RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION,
    )
    return ChangeImpactPolicyV1(
        change_impact_policy_id=derive_change_impact_policy_id(policy),
        schema_version=policy.schema_version,
        path_surface_classifications=policy.path_surface_classifications,
        impact_domains=policy.impact_domains,
        required_build_requalification=policy.required_build_requalification,
        required_tests=policy.required_tests,
        requires_full_system_acceptance=policy.requires_full_system_acceptance,
        implementation_version=policy.implementation_version,
        metadata=policy.metadata,
    )


def required_requalification_for_change(change_class: str) -> tuple[str, ...]:
    return REQUIRED_REQUALIFICATION.get(change_class, ("BUILD25",))
