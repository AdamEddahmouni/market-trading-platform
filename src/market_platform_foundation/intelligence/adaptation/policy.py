"""Adaptation policy construction (BUILD 24)."""

from __future__ import annotations

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from ..governance.types import DriftSeverity, DriftType
from ..promotion.types import ChampionScopeV1
from .identity import derive_adaptation_policy_id
from .types import AdaptationEvidenceType, AdaptationPolicyV1, SuggestedResearchClass


def build_adaptation_policy(
    *,
    champion_scope: ChampionScopeV1,
    eligible_evidence_types: tuple[AdaptationEvidenceType, ...] | None = None,
    eligible_drift_types: tuple[DriftType, ...] | None = None,
    minimum_severity: DriftSeverity = DriftSeverity.WARNING,
    minimum_sample: int = 10,
    minimum_recurrence_count: int = 2,
    minimum_distinct_windows: int = 2,
    batch_window_ns: int = 3_600_000_000_000,
    cooldown_ns: int = 86_400_000_000_000,
    suppress_when_runtime_disabled: bool = True,
    suppress_when_existing_open_research: bool = True,
    suppress_when_same_evidence_consumed: bool = True,
    allow_cooldown_bypass_for_structural: bool = True,
    allow_cooldown_bypass_severity: DriftSeverity = DriftSeverity.CRITICAL,
    allowed_research_classes: tuple[SuggestedResearchClass, ...] | None = None,
) -> AdaptationPolicyV1:
    default_evidence_types = (
        AdaptationEvidenceType.DRIFT_ASSESSMENT,
        AdaptationEvidenceType.GOVERNANCE_ALERT,
        AdaptationEvidenceType.FAIL_SAFE_DECISION,
        AdaptationEvidenceType.ROLLBACK_DECISION,
        AdaptationEvidenceType.PROVIDER_HEALTH,
        AdaptationEvidenceType.INTELLIGENCE_HEALTH,
        AdaptationEvidenceType.EXECUTION_HEALTH,
    )
    body = AdaptationPolicyV1(
        adaptation_policy_id="DERIVE",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        champion_scope=champion_scope,
        eligible_evidence_types=eligible_evidence_types or default_evidence_types,
        eligible_drift_types=eligible_drift_types or tuple(DriftType),
        minimum_severity=minimum_severity,
        minimum_sample=minimum_sample,
        minimum_recurrence_count=minimum_recurrence_count,
        minimum_distinct_windows=minimum_distinct_windows,
        batch_window_ns=batch_window_ns,
        cooldown_ns=cooldown_ns,
        suppress_when_runtime_disabled=suppress_when_runtime_disabled,
        suppress_when_existing_open_research=suppress_when_existing_open_research,
        suppress_when_same_evidence_consumed=suppress_when_same_evidence_consumed,
        allow_cooldown_bypass_for_structural=allow_cooldown_bypass_for_structural,
        allow_cooldown_bypass_severity=allow_cooldown_bypass_severity,
        allowed_research_classes=allowed_research_classes or tuple(SuggestedResearchClass),
    )
    policy_id = derive_adaptation_policy_id(body)
    return AdaptationPolicyV1(
        adaptation_policy_id=policy_id,
        schema_version=body.schema_version,
        champion_scope=body.champion_scope,
        eligible_evidence_types=body.eligible_evidence_types,
        eligible_drift_types=body.eligible_drift_types,
        minimum_severity=body.minimum_severity,
        minimum_sample=body.minimum_sample,
        minimum_recurrence_count=body.minimum_recurrence_count,
        minimum_distinct_windows=body.minimum_distinct_windows,
        batch_window_ns=body.batch_window_ns,
        cooldown_ns=body.cooldown_ns,
        deduplication_policy=body.deduplication_policy,
        scope_merge_policy=body.scope_merge_policy,
        critical_integrity_trigger_policy=body.critical_integrity_trigger_policy,
        allowed_research_classes=body.allowed_research_classes,
        priority_policy=body.priority_policy,
        suppress_when_runtime_disabled=body.suppress_when_runtime_disabled,
        suppress_when_existing_open_research=body.suppress_when_existing_open_research,
        suppress_when_same_evidence_consumed=body.suppress_when_same_evidence_consumed,
        allow_cooldown_bypass_for_structural=body.allow_cooldown_bypass_for_structural,
        allow_cooldown_bypass_severity=body.allow_cooldown_bypass_severity,
        implementation_version=body.implementation_version,
        metadata=body.metadata,
    )


__all__ = ["build_adaptation_policy"]
