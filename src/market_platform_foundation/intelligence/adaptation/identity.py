"""Deterministic adaptation identities (BUILD 24)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..contracts.common import ContractReference
from ..governance.identity import monitoring_window_identity_payload
from ..promotion.identity import champion_scope_identity_payload
from .types import (
    AdaptationAssessmentV1,
    AdaptationPolicyV1,
    AdaptationCampaignV1,
    AdaptationEventV1,
    ResearchTriggerV1,
)


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_prefix(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest}"


def _sorted_ref_ids(refs: tuple[ContractReference, ...]) -> list[str]:
    return sorted(f"{ref.kind}:{ref.id}" for ref in refs)


def adaptation_policy_identity_payload(policy: AdaptationPolicyV1) -> dict[str, Any]:
    return {
        "champion_scope": champion_scope_identity_payload(policy.champion_scope),
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
    }


def derive_adaptation_policy_id(policy: AdaptationPolicyV1) -> str:
    return _sha256_prefix("ADAPTPOL", adaptation_policy_identity_payload(policy))


def derive_dedup_key(
    *,
    champion_scope: dict[str, Any],
    evidence_class: str,
    primary_drift_type: str | None,
    champion_assignment_ref: str | None,
    runtime_activation_ref: str | None,
) -> str:
    payload = {
        "champion_scope": champion_scope,
        "evidence_class": evidence_class,
        "primary_drift_type": primary_drift_type or "",
        "champion_assignment_ref": champion_assignment_ref or "",
        "runtime_activation_ref": runtime_activation_ref or "",
    }
    return _sha256_prefix("ADAPDEDUP", payload)


def derive_adaptation_assessment_id(
    *,
    policy_id: str,
    champion_scope: dict[str, Any],
    evidence_ref_ids: tuple[str, ...],
    window_payload: dict[str, Any],
    dedup_key: str,
    open_research_key: str | None,
    consumed_trigger_ids: tuple[str, ...],
) -> str:
    payload = {
        "policy_id": policy_id,
        "champion_scope": champion_scope,
        "evidence_ref_ids": list(evidence_ref_ids),
        "window": window_payload,
        "dedup_key": dedup_key,
        "open_research_key": open_research_key or "",
        "consumed_trigger_ids": list(consumed_trigger_ids),
    }
    return _sha256_prefix("ADAPT", payload)


def derive_research_trigger_id(
    *,
    policy_id: str,
    champion_scope: dict[str, Any],
    window_payload: dict[str, Any],
    evidence_ref_ids: tuple[str, ...],
    dedup_key: str,
) -> str:
    payload = {
        "policy_id": policy_id,
        "champion_scope": champion_scope,
        "window": window_payload,
        "evidence_ref_ids": list(evidence_ref_ids),
        "dedup_key": dedup_key,
    }
    return _sha256_prefix("RTRIG", payload)


def derive_adaptation_campaign_id(
    *,
    research_trigger_id: str,
    downstream_refs: dict[str, str | None],
) -> str:
    payload = {"research_trigger_id": research_trigger_id, **downstream_refs}
    return _sha256_prefix("ADAPCMP", payload)


def derive_adaptation_event_id(
    *,
    event_type: str,
    champion_scope: dict[str, Any],
    effective_at_ns: int,
    source_key: str,
) -> str:
    payload = {
        "event_type": event_type,
        "champion_scope": champion_scope,
        "effective_at_ns": effective_at_ns,
        "source_key": source_key,
    }
    return _sha256_prefix("ADAPEVT", payload)


def assessment_identity_inputs(assessment: AdaptationAssessmentV1) -> dict[str, Any]:
    return {
        "policy_id": assessment.policy_ref,
        "champion_scope": champion_scope_identity_payload(assessment.champion_scope),
        "evidence_ref_ids": _sorted_ref_ids(assessment.evidence_refs),
        "window": monitoring_window_identity_payload(assessment.evidence_window),
        "dedup_key": assessment.dedup_key or "",
    }


def trigger_identity_inputs(trigger: ResearchTriggerV1) -> dict[str, Any]:
    return {
        "policy_id": trigger.adaptation_policy_ref,
        "champion_scope": champion_scope_identity_payload(trigger.champion_scope),
        "window": monitoring_window_identity_payload(trigger.evidence_window),
        "evidence_ref_ids": _sorted_ref_ids(trigger.source_evidence_refs),
        "dedup_key": trigger.dedup_key,
    }


__all__ = [
    "derive_adaptation_assessment_id",
    "derive_adaptation_campaign_id",
    "derive_adaptation_event_id",
    "derive_adaptation_policy_id",
    "derive_dedup_key",
    "derive_research_trigger_id",
]
