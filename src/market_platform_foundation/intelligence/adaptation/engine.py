"""Controlled adaptation engine (BUILD 24)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION, ContractReference
from ..governance.identity import monitoring_window_identity_payload
from ..governance.types import DriftAssessmentV1, DriftSeverity, MonitoringWindowV1
from ..promotion.identity import champion_scope_identity_payload
from ..promotion.types import ChampionScopeV1
from .evidence import (
    NormalizedEvidence,
    max_severity,
    normalize_drift_assessment,
    normalize_execution_health,
    normalize_fail_safe_decision,
    normalize_governance_alert,
    normalize_intelligence_health,
    normalize_provider_health,
    normalize_rollback_decision,
    primary_drift_type,
    severity_rank,
)
from .identity import (
    derive_adaptation_assessment_id,
    derive_dedup_key,
    derive_research_trigger_id,
)
from .types import (
    AdaptationAction,
    AdaptationAssessmentResult,
    AdaptationAssessmentV1,
    AdaptationEvidenceClass,
    AdaptationEvidenceType,
    AdaptationPolicyV1,
    AdaptationReasonCode,
    ResearchPriority,
    ResearchTriggerV1,
)


@dataclass(frozen=True, slots=True)
class AdaptationContext:
    """Caller-supplied state for dedup, cooldown, and open-research suppression."""

    reference_time_ns: int
    batch_window: MonitoringWindowV1
    existing_triggers: tuple[ResearchTriggerV1, ...] = ()
    consumed_evidence_ref_ids: frozenset[str] = frozenset()
    open_research_dedup_keys: frozenset[str] = frozenset()
    runtime_disabled: bool = False
    champion_assignment_ref: str | None = None
    runtime_activation_ref: str | None = None
    prior_evidence_in_batch: tuple[NormalizedEvidence, ...] = ()


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    drift_assessments: tuple[DriftAssessmentV1, ...] = ()
    governance_alerts: tuple = ()
    fail_safe_decisions: tuple = ()
    rollback_decisions: tuple = ()
    provider_health_snapshots: tuple = ()
    intelligence_health_snapshots: tuple = ()
    execution_health_snapshots: tuple = ()


def _issue_group_key(item: NormalizedEvidence) -> tuple[str, ...]:
    primary = primary_drift_type(item.drift_types)
    return (
        item.evidence_type.value,
        item.evidence_class.value,
        primary.value if primary is not None else "",
        item.suggested_research_class.value,
    )


def _merge_window(items: tuple[NormalizedEvidence, ...]) -> MonitoringWindowV1:
    start = min(item.window.start_ns for item in items)
    end = max(item.window.end_ns for item in items)
    scope = items[0].champion_scope
    return MonitoringWindowV1(
        start_ns=start,
        end_ns=end,
        evaluation_as_of_ns=end,
        scope=scope,
        mode=items[0].window.mode,
        scenario_id=items[0].window.scenario_id,
    )


def _observation_summary(items: tuple[NormalizedEvidence, ...]) -> str:
    primary = primary_drift_type(items[0].drift_types)
    drift_label = primary.value if primary is not None else items[0].evidence_type.value
    return (
        f"Persistent {drift_label.lower().replace('_', ' ')} observed across "
        f"{len({item.window_key for item in items})} monitoring window(s)."
    )


def _priority_for(
    *,
    severity: DriftSeverity,
    recurrence_count: int,
    evidence_class: AdaptationEvidenceClass,
    evidence_type: AdaptationEvidenceType,
) -> ResearchPriority:
    if evidence_type == AdaptationEvidenceType.ROLLBACK_DECISION:
        return ResearchPriority.CRITICAL
    if evidence_class == AdaptationEvidenceClass.STRUCTURAL_INTEGRITY_EVIDENCE:
        return ResearchPriority.HIGH if severity != DriftSeverity.CRITICAL else ResearchPriority.CRITICAL
    if severity == DriftSeverity.CRITICAL:
        return ResearchPriority.HIGH
    if recurrence_count >= 3:
        return ResearchPriority.HIGH
    if severity == DriftSeverity.WARNING:
        return ResearchPriority.NORMAL
    return ResearchPriority.LOW


class AdaptationEngine:
    """Qualifies BUILD 23 evidence and issues governed research triggers."""

    def normalize_bundle(
        self,
        bundle: EvidenceBundle,
        *,
        champion_scope: ChampionScopeV1,
    ) -> tuple[NormalizedEvidence, ...]:
        rows: list[NormalizedEvidence] = []
        for assessment in bundle.drift_assessments:
            rows.append(normalize_drift_assessment(assessment, scope=champion_scope))
        for alert in bundle.governance_alerts:
            rows.append(normalize_governance_alert(alert))
        for decision in bundle.fail_safe_decisions:
            rows.append(normalize_fail_safe_decision(decision))
        for decision in bundle.rollback_decisions:
            normalized = normalize_rollback_decision(decision, scope=champion_scope)
            if normalized is not None:
                rows.append(normalized)
        for snapshot in bundle.provider_health_snapshots:
            normalized = normalize_provider_health(snapshot, scope=champion_scope)
            if normalized is not None:
                rows.append(normalized)
        for snapshot in bundle.intelligence_health_snapshots:
            normalized = normalize_intelligence_health(snapshot)
            if normalized is not None:
                rows.append(normalized)
        for snapshot in bundle.execution_health_snapshots:
            normalized = normalize_execution_health(snapshot, scope=champion_scope)
            if normalized is not None:
                rows.append(normalized)
        return tuple(rows)

    def assess(
        self,
        *,
        policy: AdaptationPolicyV1,
        evidence: tuple[NormalizedEvidence, ...],
        context: AdaptationContext,
    ) -> tuple[AdaptationAssessmentResult, ...]:
        if policy.suppress_when_runtime_disabled and context.runtime_disabled:
            return self._suppress_all(
                policy=policy,
                evidence=evidence,
                context=context,
                action=AdaptationAction.IGNORE,
                reason=AdaptationReasonCode.RUNTIME_DISABLED_SUPPRESSED,
            )

        eligible = [
            item
            for item in evidence
            if item.evidence_type in policy.eligible_evidence_types
            and severity_rank(item.severity) >= severity_rank(policy.minimum_severity)
            and (
                not item.drift_types
                or any(drift in policy.eligible_drift_types for drift in item.drift_types)
            )
        ]
        if not eligible:
            return self._suppress_all(
                policy=policy,
                evidence=evidence,
                context=context,
                action=AdaptationAction.IGNORE,
                reason=AdaptationReasonCode.HEALTHY_NO_ACTION,
            )

        grouped: dict[tuple[str, ...], list[NormalizedEvidence]] = {}
        for item in eligible:
            grouped.setdefault(_issue_group_key(item), []).append(item)

        results: list[AdaptationAssessmentResult] = []
        for group_items in grouped.values():
            result = self._assess_group(
                policy=policy,
                items=tuple(group_items),
                context=context,
            )
            if result is not None:
                results.append(result)
        return tuple(results)

    def _assess_group(
        self,
        *,
        policy: AdaptationPolicyV1,
        items: tuple[NormalizedEvidence, ...],
        context: AdaptationContext,
    ) -> AdaptationAssessmentResult | None:
        scope = items[0].champion_scope
        scope_payload = champion_scope_identity_payload(scope)
        evidence_refs = tuple(
            sorted(
                (item.evidence_ref for item in items),
                key=lambda ref: (ref.kind, ref.id),
            )
        )
        evidence_ref_ids = tuple(ref.id for ref in evidence_refs)
        distinct_windows = {item.window_key for item in items}
        recurrence_count = len(distinct_windows)
        sample_count = sum(item.sample_count for item in items)
        severity = max_severity(*(item.severity for item in items))
        evidence_class = items[0].evidence_class
        primary = primary_drift_type(items[0].drift_types)
        dedup_key = derive_dedup_key(
            champion_scope=scope_payload,
            evidence_class=evidence_class.value,
            primary_drift_type=primary.value if primary is not None else None,
            champion_assignment_ref=context.champion_assignment_ref,
            runtime_activation_ref=context.runtime_activation_ref,
        )
        window = _merge_window(items)
        window_payload = monitoring_window_identity_payload(window)

        if policy.suppress_when_same_evidence_consumed:
            if all(ref.id in context.consumed_evidence_ref_ids for ref in evidence_refs):
                return self._build_assessment(
                    policy=policy,
                    scope=scope,
                    evidence_refs=evidence_refs,
                    window=window,
                    evidence_class=evidence_class,
                    severity=severity,
                    sample_count=sample_count,
                    recurrence_count=recurrence_count,
                    distinct_window_count=len(distinct_windows),
                    action=AdaptationAction.SUPPRESS_DUPLICATE,
                    reason_codes=(AdaptationReasonCode.EXACT_DUPLICATE_SUPPRESSED,),
                    dedup_key=dedup_key,
                    context=context,
                )

        if policy.suppress_when_existing_open_research and dedup_key in context.open_research_dedup_keys:
            return self._build_assessment(
                policy=policy,
                scope=scope,
                evidence_refs=evidence_refs,
                window=window,
                evidence_class=evidence_class,
                severity=severity,
                sample_count=sample_count,
                recurrence_count=recurrence_count,
                distinct_window_count=len(distinct_windows),
                action=AdaptationAction.SUPPRESS_EXISTING_RESEARCH,
                reason_codes=(
                    AdaptationReasonCode.OPEN_RESEARCH_EXISTS,
                    AdaptationReasonCode.SEMANTIC_DUPLICATE_SUPPRESSED,
                ),
                dedup_key=dedup_key,
                open_research_state="OPEN",
                context=context,
            )

        cooldown_active, cooldown_bypass = self._cooldown_state(
            policy=policy,
            dedup_key=dedup_key,
            context=context,
            severity=severity,
            evidence_class=evidence_class,
        )
        if cooldown_active and not cooldown_bypass:
            return self._build_assessment(
                policy=policy,
                scope=scope,
                evidence_refs=evidence_refs,
                window=window,
                evidence_class=evidence_class,
                severity=severity,
                sample_count=sample_count,
                recurrence_count=recurrence_count,
                distinct_window_count=len(distinct_windows),
                action=AdaptationAction.SUPPRESS_COOLDOWN,
                reason_codes=(AdaptationReasonCode.COOLDOWN_ACTIVE,),
                dedup_key=dedup_key,
                cooldown_state="ACTIVE",
                context=context,
            )

        qualifies = False
        reason_codes: list[AdaptationReasonCode] = []
        if evidence_class == AdaptationEvidenceClass.STRUCTURAL_INTEGRITY_EVIDENCE:
            qualifies = True
            reason_codes.append(AdaptationReasonCode.STRUCTURAL_INTEGRITY_TRIGGER)
            if items[0].evidence_type == AdaptationEvidenceType.ROLLBACK_DECISION:
                reason_codes.append(AdaptationReasonCode.ROLLBACK_EVIDENCE)
        else:
            if sample_count < policy.minimum_sample:
                return self._build_assessment(
                    policy=policy,
                    scope=scope,
                    evidence_refs=evidence_refs,
                    window=window,
                    evidence_class=evidence_class,
                    severity=severity,
                    sample_count=sample_count,
                    recurrence_count=recurrence_count,
                    distinct_window_count=len(distinct_windows),
                    action=AdaptationAction.ACCUMULATE,
                    reason_codes=(AdaptationReasonCode.INSUFFICIENT_SAMPLE,),
                    dedup_key=dedup_key,
                    context=context,
                )
            if recurrence_count < policy.minimum_recurrence_count:
                return self._build_assessment(
                    policy=policy,
                    scope=scope,
                    evidence_refs=evidence_refs,
                    window=window,
                    evidence_class=evidence_class,
                    severity=severity,
                    sample_count=sample_count,
                    recurrence_count=recurrence_count,
                    distinct_window_count=len(distinct_windows),
                    action=AdaptationAction.ACCUMULATE,
                    reason_codes=(AdaptationReasonCode.INSUFFICIENT_RECURRENCE,),
                    dedup_key=dedup_key,
                    context=context,
                )
            if len(distinct_windows) < policy.minimum_distinct_windows:
                return self._build_assessment(
                    policy=policy,
                    scope=scope,
                    evidence_refs=evidence_refs,
                    window=window,
                    evidence_class=evidence_class,
                    severity=severity,
                    sample_count=sample_count,
                    recurrence_count=recurrence_count,
                    distinct_window_count=len(distinct_windows),
                    action=AdaptationAction.ACCUMULATE,
                    reason_codes=(AdaptationReasonCode.INSUFFICIENT_DISTINCT_WINDOWS,),
                    dedup_key=dedup_key,
                    context=context,
                )
            qualifies = True
            reason_codes.append(AdaptationReasonCode.RECURRENCE_THRESHOLD_MET)

        if not qualifies:
            return None

        if cooldown_bypass:
            reason_codes.append(AdaptationReasonCode.COOLDOWN_BYPASS_SEVERITY)

        assessment = self._build_assessment(
            policy=policy,
            scope=scope,
            evidence_refs=evidence_refs,
            window=window,
            evidence_class=evidence_class,
            severity=severity,
            sample_count=sample_count,
            recurrence_count=recurrence_count,
            distinct_window_count=len(distinct_windows),
            action=AdaptationAction.TRIGGER_RESEARCH,
            reason_codes=tuple(reason_codes + [AdaptationReasonCode.RESEARCH_TRIGGER_ISSUED]),
            dedup_key=dedup_key,
            cooldown_state="BYPASSED" if cooldown_bypass else None,
            context=context,
        )
        trigger = self._build_trigger(
            policy=policy,
            assessment=assessment.assessment,
            items=items,
            dedup_key=dedup_key,
            context=context,
        )
        linked = AdaptationAssessmentV1(
            adaptation_assessment_id=assessment.assessment.adaptation_assessment_id,
            schema_version=assessment.assessment.schema_version,
            policy_ref=assessment.assessment.policy_ref,
            champion_scope=assessment.assessment.champion_scope,
            evidence_refs=assessment.assessment.evidence_refs,
            evidence_window=assessment.assessment.evidence_window,
            evidence_class=assessment.assessment.evidence_class,
            severity=assessment.assessment.severity,
            sample_count=assessment.assessment.sample_count,
            recurrence_count=assessment.assessment.recurrence_count,
            distinct_window_count=assessment.assessment.distinct_window_count,
            action=assessment.assessment.action,
            reason_codes=assessment.assessment.reason_codes,
            cooldown_state=assessment.assessment.cooldown_state,
            dedup_state=assessment.assessment.dedup_state,
            open_research_state=assessment.assessment.open_research_state,
            research_trigger_ref=trigger.research_trigger_id,
            dedup_key=assessment.assessment.dedup_key,
            lineage_refs=assessment.assessment.lineage_refs,
            metadata=assessment.assessment.metadata,
        )
        return AdaptationAssessmentResult(assessment=linked, trigger=trigger)

    def _cooldown_state(
        self,
        *,
        policy: AdaptationPolicyV1,
        dedup_key: str,
        context: AdaptationContext,
        severity: DriftSeverity,
        evidence_class: AdaptationEvidenceClass,
    ) -> tuple[bool, bool]:
        if policy.cooldown_ns <= 0:
            return False, False
        last_trigger_time: int | None = None
        for trigger in context.existing_triggers:
            if trigger.dedup_key != dedup_key:
                continue
            trigger_time = trigger.evidence_window.end_ns
            if last_trigger_time is None or trigger_time > last_trigger_time:
                last_trigger_time = trigger_time
        if last_trigger_time is None:
            return False, False
        cooldown_end = last_trigger_time + policy.cooldown_ns
        active = context.reference_time_ns < cooldown_end
        bypass = False
        if active and policy.allow_cooldown_bypass_for_structural:
            if evidence_class == AdaptationEvidenceClass.STRUCTURAL_INTEGRITY_EVIDENCE:
                bypass = True
            elif severity_rank(severity) >= severity_rank(policy.allow_cooldown_bypass_severity):
                bypass = True
        return active, bypass

    def _build_assessment(
        self,
        *,
        policy: AdaptationPolicyV1,
        scope: ChampionScopeV1,
        evidence_refs: tuple[ContractReference, ...],
        window: MonitoringWindowV1,
        evidence_class: AdaptationEvidenceClass,
        severity: DriftSeverity,
        sample_count: int,
        recurrence_count: int,
        distinct_window_count: int,
        action: AdaptationAction,
        reason_codes: tuple[AdaptationReasonCode, ...],
        dedup_key: str,
        context: AdaptationContext,
        cooldown_state: str | None = None,
        open_research_state: str | None = None,
    ) -> AdaptationAssessmentResult:
        scope_payload = champion_scope_identity_payload(scope)
        evidence_ref_ids = tuple(ref.id for ref in evidence_refs)
        assessment_id = derive_adaptation_assessment_id(
            policy_id=policy.adaptation_policy_id,
            champion_scope=scope_payload,
            evidence_ref_ids=evidence_ref_ids,
            window_payload=monitoring_window_identity_payload(window),
            dedup_key=dedup_key,
            open_research_key=open_research_state,
            consumed_trigger_ids=tuple(t.research_trigger_id for t in context.existing_triggers),
        )
        assessment = AdaptationAssessmentV1(
            adaptation_assessment_id=assessment_id,
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            policy_ref=policy.adaptation_policy_id,
            champion_scope=scope,
            evidence_refs=evidence_refs,
            evidence_window=window,
            evidence_class=evidence_class,
            severity=severity,
            sample_count=sample_count,
            recurrence_count=recurrence_count,
            distinct_window_count=distinct_window_count,
            action=action,
            reason_codes=reason_codes,
            cooldown_state=cooldown_state,
            dedup_state=dedup_key,
            open_research_state=open_research_state,
            dedup_key=dedup_key,
        )
        return AdaptationAssessmentResult(assessment=assessment, trigger=None)

    def _build_trigger(
        self,
        *,
        policy: AdaptationPolicyV1,
        assessment: AdaptationAssessmentV1,
        items: tuple[NormalizedEvidence, ...],
        dedup_key: str,
        context: AdaptationContext,
    ) -> ResearchTriggerV1:
        scope_payload = champion_scope_identity_payload(assessment.champion_scope)
        evidence_ref_ids = tuple(ref.id for ref in assessment.evidence_refs)
        window_payload = monitoring_window_identity_payload(assessment.evidence_window)
        trigger_id = derive_research_trigger_id(
            policy_id=policy.adaptation_policy_id,
            champion_scope=scope_payload,
            window_payload=window_payload,
            evidence_ref_ids=evidence_ref_ids,
            dedup_key=dedup_key,
        )
        metric_summary: dict[str, float] = {}
        sample_counts: dict[str, int] = {}
        for item in items:
            metric_summary.update(item.metric_observations)
            for key, value in item.sample_counts.items():
                sample_counts[key] = sample_counts.get(key, 0) + value
        evidence_types = tuple(dict.fromkeys(item.evidence_type for item in items))
        priority = _priority_for(
            severity=assessment.severity,
            recurrence_count=assessment.recurrence_count,
            evidence_class=assessment.evidence_class,
            evidence_type=items[0].evidence_type,
        )
        suggested = items[0].suggested_research_class
        if suggested not in policy.allowed_research_classes:
            suggested = policy.allowed_research_classes[0]
        return ResearchTriggerV1(
            research_trigger_id=trigger_id,
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            champion_scope=assessment.champion_scope,
            evidence_window=assessment.evidence_window,
            adaptation_policy_ref=policy.adaptation_policy_id,
            adaptation_assessment_ref=assessment.adaptation_assessment_id,
            source_evidence_refs=assessment.evidence_refs,
            evidence_types=evidence_types,
            severity=assessment.severity,
            champion_assignment_ref=context.champion_assignment_ref,
            runtime_activation_ref=context.runtime_activation_ref,
            observed_metric_summary=metric_summary,
            sample_counts=sample_counts,
            suggested_research_class=suggested,
            priority=priority,
            dedup_key=dedup_key,
            limitations=(
                "Observation only; no causal explanation asserted.",
                "Does not authorize training, promotion, or runtime change.",
            ),
            observation_summary=_observation_summary(items),
            lineage_refs=assessment.evidence_refs,
        )

    def _suppress_all(
        self,
        *,
        policy: AdaptationPolicyV1,
        evidence: tuple[NormalizedEvidence, ...],
        context: AdaptationContext,
        action: AdaptationAction,
        reason: AdaptationReasonCode,
    ) -> tuple[AdaptationAssessmentResult, ...]:
        if not evidence:
            return ()
        scope = evidence[0].champion_scope
        refs = tuple(sorted((item.evidence_ref for item in evidence), key=lambda ref: (ref.kind, ref.id)))
        window = _merge_window(evidence)
        dedup_key = derive_dedup_key(
            champion_scope=champion_scope_identity_payload(scope),
            evidence_class=AdaptationEvidenceClass.STATISTICAL_EVIDENCE.value,
            primary_drift_type=None,
            champion_assignment_ref=context.champion_assignment_ref,
            runtime_activation_ref=context.runtime_activation_ref,
        )
        return (
            self._build_assessment(
                policy=policy,
                scope=scope,
                evidence_refs=refs,
                window=window,
                evidence_class=evidence[0].evidence_class,
                severity=max_severity(*(item.severity for item in evidence)),
                sample_count=sum(item.sample_count for item in evidence),
                recurrence_count=len({item.window_key for item in evidence}),
                distinct_window_count=len({item.window_key for item in evidence}),
                action=action,
                reason_codes=(reason,),
                dedup_key=dedup_key,
                context=context,
            ),
        )


__all__ = ["AdaptationContext", "AdaptationEngine", "EvidenceBundle"]
