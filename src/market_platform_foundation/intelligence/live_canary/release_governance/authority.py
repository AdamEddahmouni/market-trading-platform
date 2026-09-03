"""Canonical authority map (BUILD 35)."""

from __future__ import annotations

from .identity import derive_authority_map_id
from .types import (
    RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION,
    RELEASE_GOVERNANCE_SCHEMA_VERSION,
    CanonicalAuthorityEntryV1,
    CanonicalAuthorityMapV1,
)

AUTHORITY_ENTRIES: tuple[CanonicalAuthorityEntryV1, ...] = (
    CanonicalAuthorityEntryV1("Forecast", "ForecastEngine", "intelligence.forecast", 14),
    CanonicalAuthorityEntryV1("Outcome", "OutcomeSettlement", "intelligence.outcomes", 15),
    CanonicalAuthorityEntryV1("Evaluation", "EvaluationEngine", "intelligence.evaluation", 16),
    CanonicalAuthorityEntryV1("Research hypothesis", "ResearchOrchestrator", "intelligence.research", 17),
    CanonicalAuthorityEntryV1("Training candidate", "TrainingFactory", "intelligence.training", 18),
    CanonicalAuthorityEntryV1("Independent validation", "ValidationEngine", "intelligence.validation", 19),
    CanonicalAuthorityEntryV1("Champion promotion", "PromotionEngine", "intelligence.promotion", 20),
    CanonicalAuthorityEntryV1("Opportunity", "OpportunityEngine", "intelligence.opportunity", 21),
    CanonicalAuthorityEntryV1("RiskDecision", "RiskEngine", "intelligence.risk", 22),
    CanonicalAuthorityEntryV1("PAPER execution", "PaperExecutionEngine", "intelligence.execution.paper", 22),
    CanonicalAuthorityEntryV1("Runtime activation", "RuntimeGovernance", "intelligence.governance", 23),
    CanonicalAuthorityEntryV1("Adaptation", "AdaptationOrchestrator", "intelligence.adaptation", 24),
    CanonicalAuthorityEntryV1("Live execution gate", "LiveExecutionSafetyGate", "live_canary.safety", 28),
    CanonicalAuthorityEntryV1("Live session authorization", "LiveSessionAuthorization", "live_canary.authorization", 29),
    CanonicalAuthorityEntryV1("Order confirmation", "LiveOrderConfirmation", "live_canary.confirmation", 29),
    CanonicalAuthorityEntryV1("Reconciliation", "ReconciliationWorker", "live_canary.reconciliation", 30),
    CanonicalAuthorityEntryV1("Operator control", "OperatorControlPlane", "live_canary.operator", 31),
    CanonicalAuthorityEntryV1("Deployment", "DeploymentRunner", "live_canary.deployment", 34),
    CanonicalAuthorityEntryV1("Release governance", "ReleaseGovernance", "live_canary.release_governance", 35),
)

FORBIDDEN_AUTHORITY_PATHS: tuple[tuple[str, str], ...] = (
    ("Forecast", "broker"),
    ("LLM specialist", "broker"),
    ("Research agent", "active model"),
    ("Operator read model", "broker"),
    ("Deployment service", "LiveExecutionAuthorization"),
    ("Release governor", "LiveExecutionAuthorization"),
    ("Release approval", "order confirmation"),
)

DUPLICATE_AUTHORITY_FORBIDDEN = True


def build_canonical_authority_map() -> CanonicalAuthorityMapV1:
    auth_map = CanonicalAuthorityMapV1(
        authority_map_id="",
        schema_version=RELEASE_GOVERNANCE_SCHEMA_VERSION,
        entries=AUTHORITY_ENTRIES,
        forbidden_paths=FORBIDDEN_AUTHORITY_PATHS,
        implementation_version=RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION,
    )
    return CanonicalAuthorityMapV1(
        authority_map_id=derive_authority_map_id(auth_map),
        schema_version=auth_map.schema_version,
        entries=auth_map.entries,
        forbidden_paths=auth_map.forbidden_paths,
        implementation_version=auth_map.implementation_version,
    )


def find_duplicate_authorities() -> list[str]:
    seen: dict[str, str] = {}
    duplicates: list[str] = []
    for entry in AUTHORITY_ENTRIES:
        if entry.decision_artifact in seen:
            duplicates.append(
                f"{entry.decision_artifact}: {seen[entry.decision_artifact]} and {entry.canonical_authority}"
            )
        seen[entry.decision_artifact] = entry.canonical_authority
    return duplicates
