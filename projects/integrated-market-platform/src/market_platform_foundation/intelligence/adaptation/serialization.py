"""Adaptation serialization (BUILD 24)."""

from __future__ import annotations

from typing import Any

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION, ContractReference
from ..governance.serialization import monitoring_window_v1_from_dict, monitoring_window_v1_to_dict
from ..governance.types import DriftSeverity, DriftType
from ..promotion.serialization import _scope_from_dict, _scope_to_dict
from .types import (
    AdaptationAction,
    AdaptationAssessmentV1,
    AdaptationCampaignV1,
    AdaptationEventType,
    AdaptationEventV1,
    AdaptationEvidenceClass,
    AdaptationEvidenceType,
    AdaptationPolicyV1,
    AdaptationReasonCode,
    ResearchPriority,
    ResearchTriggerV1,
    SuggestedResearchClass,
)


def _refs_to_dict(refs: tuple[ContractReference, ...]) -> list[dict[str, Any]]:
    return [{"kind": ref.kind, "id": ref.id, "schema_version": ref.schema_version} for ref in refs]


def _refs_from_dict(payload: list[dict[str, Any]] | None) -> tuple[ContractReference, ...]:
    if not payload:
        return ()
    return tuple(
        ContractReference(
            kind=str(row["kind"]),
            id=str(row["id"]),
            schema_version=str(row.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        )
        for row in payload
    )


def adaptation_policy_v1_to_dict(policy: AdaptationPolicyV1) -> dict[str, Any]:
    return {
        "schema_version": policy.schema_version,
        "adaptation_policy_id": policy.adaptation_policy_id,
        "champion_scope": _scope_to_dict(policy.champion_scope),
        "eligible_evidence_types": [t.value for t in policy.eligible_evidence_types],
        "eligible_drift_types": [t.value for t in policy.eligible_drift_types],
        "minimum_severity": policy.minimum_severity.value,
        "minimum_sample": policy.minimum_sample,
        "minimum_recurrence_count": policy.minimum_recurrence_count,
        "minimum_distinct_windows": policy.minimum_distinct_windows,
        "batch_window_ns": policy.batch_window_ns,
        "cooldown_ns": policy.cooldown_ns,
        "deduplication_policy": policy.deduplication_policy,
        "scope_merge_policy": policy.scope_merge_policy,
        "critical_integrity_trigger_policy": policy.critical_integrity_trigger_policy,
        "allowed_research_classes": [c.value for c in policy.allowed_research_classes],
        "priority_policy": policy.priority_policy,
        "suppress_when_runtime_disabled": policy.suppress_when_runtime_disabled,
        "suppress_when_existing_open_research": policy.suppress_when_existing_open_research,
        "suppress_when_same_evidence_consumed": policy.suppress_when_same_evidence_consumed,
        "allow_cooldown_bypass_for_structural": policy.allow_cooldown_bypass_for_structural,
        "allow_cooldown_bypass_severity": policy.allow_cooldown_bypass_severity.value,
        "implementation_version": policy.implementation_version,
        "metadata": dict(policy.metadata),
    }


def adaptation_policy_v1_from_dict(payload: dict[str, Any]) -> AdaptationPolicyV1:
    return AdaptationPolicyV1(
        adaptation_policy_id=str(payload["adaptation_policy_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        champion_scope=_scope_from_dict(payload["champion_scope"]),
        eligible_evidence_types=tuple(
            AdaptationEvidenceType(value) for value in payload.get("eligible_evidence_types", [])
        ),
        eligible_drift_types=tuple(DriftType(value) for value in payload.get("eligible_drift_types", [])),
        minimum_severity=DriftSeverity(payload.get("minimum_severity", DriftSeverity.WARNING.value)),
        minimum_sample=int(payload.get("minimum_sample", 10)),
        minimum_recurrence_count=int(payload.get("minimum_recurrence_count", 2)),
        minimum_distinct_windows=int(payload.get("minimum_distinct_windows", 2)),
        batch_window_ns=int(payload.get("batch_window_ns", 3_600_000_000_000)),
        cooldown_ns=int(payload.get("cooldown_ns", 86_400_000_000_000)),
        deduplication_policy=str(payload.get("deduplication_policy", "SEMANTIC_ISSUE_KEY")),
        scope_merge_policy=str(payload.get("scope_merge_policy", "PRESERVE_DISTINCT_ISSUES")),
        critical_integrity_trigger_policy=str(
            payload.get("critical_integrity_trigger_policy", "IMMEDIATE_ON_STRUCTURAL")
        ),
        allowed_research_classes=tuple(
            SuggestedResearchClass(value) for value in payload.get("allowed_research_classes", [])
        ),
        priority_policy=str(payload.get("priority_policy", "SEVERITY_RECURRENCE_TABLE")),
        suppress_when_runtime_disabled=bool(payload.get("suppress_when_runtime_disabled", True)),
        suppress_when_existing_open_research=bool(payload.get("suppress_when_existing_open_research", True)),
        suppress_when_same_evidence_consumed=bool(payload.get("suppress_when_same_evidence_consumed", True)),
        allow_cooldown_bypass_for_structural=bool(payload.get("allow_cooldown_bypass_for_structural", True)),
        allow_cooldown_bypass_severity=DriftSeverity(
            payload.get("allow_cooldown_bypass_severity", DriftSeverity.CRITICAL.value)
        ),
        implementation_version=str(payload.get("implementation_version", "controlled-adaptation-v1")),
        metadata=dict(payload.get("metadata") or {}),
    )


def adaptation_assessment_v1_to_dict(assessment: AdaptationAssessmentV1) -> dict[str, Any]:
    return {
        "schema_version": assessment.schema_version,
        "adaptation_assessment_id": assessment.adaptation_assessment_id,
        "policy_ref": assessment.policy_ref,
        "champion_scope": _scope_to_dict(assessment.champion_scope),
        "evidence_refs": _refs_to_dict(assessment.evidence_refs),
        "evidence_window": monitoring_window_v1_to_dict(assessment.evidence_window),
        "evidence_class": assessment.evidence_class.value,
        "severity": assessment.severity.value,
        "sample_count": assessment.sample_count,
        "recurrence_count": assessment.recurrence_count,
        "distinct_window_count": assessment.distinct_window_count,
        "action": assessment.action.value,
        "reason_codes": [code.value for code in assessment.reason_codes],
        "cooldown_state": assessment.cooldown_state,
        "dedup_state": assessment.dedup_state,
        "open_research_state": assessment.open_research_state,
        "research_trigger_ref": assessment.research_trigger_ref,
        "dedup_key": assessment.dedup_key,
        "lineage_refs": _refs_to_dict(assessment.lineage_refs),
        "metadata": dict(assessment.metadata),
    }


def adaptation_assessment_v1_from_dict(payload: dict[str, Any]) -> AdaptationAssessmentV1:
    return AdaptationAssessmentV1(
        adaptation_assessment_id=str(payload["adaptation_assessment_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        policy_ref=str(payload["policy_ref"]),
        champion_scope=_scope_from_dict(payload["champion_scope"]),
        evidence_refs=_refs_from_dict(payload.get("evidence_refs")),
        evidence_window=monitoring_window_v1_from_dict(payload["evidence_window"]),
        evidence_class=AdaptationEvidenceClass(payload["evidence_class"]),
        severity=DriftSeverity(payload["severity"]),
        sample_count=int(payload["sample_count"]),
        recurrence_count=int(payload["recurrence_count"]),
        distinct_window_count=int(payload["distinct_window_count"]),
        action=AdaptationAction(payload["action"]),
        reason_codes=tuple(AdaptationReasonCode(value) for value in payload.get("reason_codes", [])),
        cooldown_state=payload.get("cooldown_state"),
        dedup_state=payload.get("dedup_state"),
        open_research_state=payload.get("open_research_state"),
        research_trigger_ref=payload.get("research_trigger_ref"),
        dedup_key=payload.get("dedup_key"),
        lineage_refs=_refs_from_dict(payload.get("lineage_refs")),
        metadata=dict(payload.get("metadata") or {}),
    )


def research_trigger_v1_to_dict(trigger: ResearchTriggerV1) -> dict[str, Any]:
    return {
        "schema_version": trigger.schema_version,
        "research_trigger_id": trigger.research_trigger_id,
        "trigger_id": trigger.research_trigger_id,
        "champion_scope": _scope_to_dict(trigger.champion_scope),
        "evidence_window": monitoring_window_v1_to_dict(trigger.evidence_window),
        "adaptation_policy_ref": trigger.adaptation_policy_ref,
        "adaptation_assessment_ref": trigger.adaptation_assessment_ref,
        "source_evidence_refs": _refs_to_dict(trigger.source_evidence_refs),
        "evidence_types": [value.value for value in trigger.evidence_types],
        "severity": trigger.severity.value,
        "champion_assignment_ref": trigger.champion_assignment_ref,
        "runtime_activation_ref": trigger.runtime_activation_ref,
        "observed_metric_summary": dict(trigger.observed_metric_summary),
        "sample_counts": dict(trigger.sample_counts),
        "suggested_research_class": trigger.suggested_research_class.value,
        "priority": trigger.priority.value,
        "dedup_key": trigger.dedup_key,
        "limitations": list(trigger.limitations),
        "observation_summary": trigger.observation_summary,
        "lineage_refs": _refs_to_dict(trigger.lineage_refs),
        "metadata": dict(trigger.metadata),
    }


def research_trigger_v1_from_dict(payload: dict[str, Any]) -> ResearchTriggerV1:
    trigger_id = payload.get("research_trigger_id") or payload.get("trigger_id")
    return ResearchTriggerV1(
        research_trigger_id=str(trigger_id),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        champion_scope=_scope_from_dict(payload["champion_scope"]),
        evidence_window=monitoring_window_v1_from_dict(payload["evidence_window"]),
        adaptation_policy_ref=str(payload["adaptation_policy_ref"]),
        adaptation_assessment_ref=str(payload["adaptation_assessment_ref"]),
        source_evidence_refs=_refs_from_dict(payload.get("source_evidence_refs")),
        evidence_types=tuple(
            AdaptationEvidenceType(value) for value in payload.get("evidence_types", [])
        ),
        severity=DriftSeverity(payload["severity"]),
        champion_assignment_ref=payload.get("champion_assignment_ref"),
        runtime_activation_ref=payload.get("runtime_activation_ref"),
        observed_metric_summary=dict(payload.get("observed_metric_summary") or {}),
        sample_counts={str(k): int(v) for k, v in (payload.get("sample_counts") or {}).items()},
        suggested_research_class=SuggestedResearchClass(payload["suggested_research_class"]),
        priority=ResearchPriority(payload["priority"]),
        dedup_key=str(payload["dedup_key"]),
        limitations=tuple(payload.get("limitations") or ()),
        observation_summary=str(payload["observation_summary"]),
        lineage_refs=_refs_from_dict(payload.get("lineage_refs")),
        metadata=dict(payload.get("metadata") or {}),
    )


def adaptation_campaign_v1_to_dict(campaign: AdaptationCampaignV1) -> dict[str, Any]:
    return {
        "schema_version": campaign.schema_version,
        "adaptation_campaign_id": campaign.adaptation_campaign_id,
        "research_trigger_id": campaign.research_trigger_id,
        "research_finding_id": campaign.research_finding_id,
        "research_hypothesis_id": campaign.research_hypothesis_id,
        "experiment_id": campaign.experiment_id,
        "candidate_id": campaign.candidate_id,
        "validation_report_id": campaign.validation_report_id,
        "promotion_decision_id": campaign.promotion_decision_id,
        "runtime_activation_id": campaign.runtime_activation_id,
        "lineage_refs": _refs_to_dict(campaign.lineage_refs),
        "metadata": dict(campaign.metadata),
    }


def adaptation_campaign_v1_from_dict(payload: dict[str, Any]) -> AdaptationCampaignV1:
    return AdaptationCampaignV1(
        adaptation_campaign_id=str(payload["adaptation_campaign_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        research_trigger_id=str(payload["research_trigger_id"]),
        research_finding_id=payload.get("research_finding_id"),
        research_hypothesis_id=payload.get("research_hypothesis_id"),
        experiment_id=payload.get("experiment_id"),
        candidate_id=payload.get("candidate_id"),
        validation_report_id=payload.get("validation_report_id"),
        promotion_decision_id=payload.get("promotion_decision_id"),
        runtime_activation_id=payload.get("runtime_activation_id"),
        lineage_refs=_refs_from_dict(payload.get("lineage_refs")),
        metadata=dict(payload.get("metadata") or {}),
    )


def adaptation_event_v1_to_dict(event: AdaptationEventV1) -> dict[str, Any]:
    return {
        "schema_version": event.schema_version,
        "event_id": event.event_id,
        "event_type": event.event_type.value,
        "champion_scope": _scope_to_dict(event.champion_scope),
        "effective_at_ns": event.effective_at_ns,
        "source_refs": _refs_to_dict(event.source_refs),
        "reason_codes": [code.value for code in event.reason_codes],
        "metadata": dict(event.metadata),
    }


def adaptation_event_v1_from_dict(payload: dict[str, Any]) -> AdaptationEventV1:
    return AdaptationEventV1(
        event_id=str(payload["event_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        event_type=AdaptationEventType(payload["event_type"]),
        champion_scope=_scope_from_dict(payload["champion_scope"]),
        effective_at_ns=int(payload["effective_at_ns"]),
        source_refs=_refs_from_dict(payload.get("source_refs")),
        reason_codes=tuple(AdaptationReasonCode(value) for value in payload.get("reason_codes", [])),
        metadata=dict(payload.get("metadata") or {}),
    )


__all__ = [
    "adaptation_assessment_v1_from_dict",
    "adaptation_assessment_v1_to_dict",
    "adaptation_campaign_v1_from_dict",
    "adaptation_campaign_v1_to_dict",
    "adaptation_event_v1_from_dict",
    "adaptation_event_v1_to_dict",
    "adaptation_policy_v1_from_dict",
    "adaptation_policy_v1_to_dict",
    "research_trigger_v1_from_dict",
    "research_trigger_v1_to_dict",
]
