"""Core quality and capability assessment engine (BUILD 04)."""

from __future__ import annotations

from typing import Any

from ..contracts.common import QualityState
from ..contracts.event import EventV1
from ..temporal.models import TemporalIntegrityReport
from ..temporal.policy import DEFAULT_TEMPORAL_POLICY, TemporalIntegrityPolicy
from ..temporal.validation import inspect_event_temporal_integrity
from .conflicts import detect_provider_conflicts
from .errors import raise_if_fail_closed
from .models import (
    AvailabilityState,
    CapabilityAssessment,
    CapabilityDimensions,
    CapabilityRequirement,
    CompletenessState,
    ConflictState,
    ConnectionState,
    DecisionAction,
    FindingSeverity,
    FreshnessState,
    IntelligenceCapability,
    ProviderCapabilityObservation,
    ProviderHealthSnapshot,
    QualityAssessment,
    QualityDecision,
    QualityFinding,
    QualityFindingCode,
    RequirementSet,
    SupportState,
    UnavailabilityReason,
    ValidityState,
    capability_for_event_type,
)
from .policy import DEFAULT_QUALITY_POLICY, QualityPolicy
from .summary import quality_state_for_action, quality_summary_from_assessment
from .temporal_integration import findings_from_temporal_report, is_future_information
from .validators import (
    assess_borrow_freshness,
    assess_short_interest_freshness,
    validate_event_structure,
)


def _dedupe_findings(findings: list[QualityFinding]) -> tuple[QualityFinding, ...]:
    seen: set[tuple[Any, ...]] = set()
    ordered: list[QualityFinding] = []
    for finding in sorted(findings, key=lambda row: row.sort_key()):
        key = (
            finding.code,
            finding.severity.value,
            finding.provider_id,
            finding.capability.value if finding.capability else None,
            finding.instrument_id,
            finding.event_id,
            finding.message,
        )
        if key in seen:
            continue
        seen.add(key)
        ordered.append(finding)
    return tuple(ordered)


def _quality_rank(state: QualityState) -> int:
    return {
        QualityState.GOOD: 4,
        QualityState.DEGRADED: 3,
        QualityState.UNKNOWN: 2,
        QualityState.INVALID: 1,
    }[state]


def _meets_minimum(actual: QualityState, minimum: QualityState, *, allow_degraded: bool) -> bool:
    if actual == QualityState.INVALID:
        return False
    if actual == QualityState.UNKNOWN:
        return False
    if minimum == QualityState.GOOD:
        return actual == QualityState.GOOD or (allow_degraded and actual == QualityState.DEGRADED)
    if minimum == QualityState.DEGRADED:
        return actual in {QualityState.GOOD, QualityState.DEGRADED}
    return True


def findings_from_provider_health(
    snapshot: ProviderHealthSnapshot,
) -> tuple[QualityFinding, ...]:
    findings: list[QualityFinding] = []
    if snapshot.connection == ConnectionState.DISCONNECTED:
        findings.append(
            QualityFinding(
                code=QualityFindingCode.PROVIDER_DISCONNECTED.value,
                severity=FindingSeverity.ERROR,
                message=f"Provider {snapshot.provider_id} disconnected at {snapshot.as_of_time_ns}ns",
                provider_id=snapshot.provider_id,
                observed_at_ns=snapshot.as_of_time_ns,
            )
        )
    for observation in snapshot.observations:
        if observation.support == SupportState.UNSUPPORTED:
            findings.append(
                QualityFinding(
                    code=QualityFindingCode.CAPABILITY_UNAVAILABLE.value,
                    severity=FindingSeverity.ERROR,
                    message=f"{observation.capability.value} unsupported for {snapshot.provider_id}",
                    provider_id=snapshot.provider_id,
                    capability=observation.capability,
                    instrument_id=observation.instrument_id,
                    observed_at_ns=snapshot.as_of_time_ns,
                    evidence={"reason": UnavailabilityReason.UNSUPPORTED.value},
                )
            )
        elif observation.entitled is False:
            findings.append(
                QualityFinding(
                    code=QualityFindingCode.NOT_ENTITLED.value,
                    severity=FindingSeverity.ERROR,
                    message=f"{observation.capability.value} not entitled for {snapshot.provider_id}",
                    provider_id=snapshot.provider_id,
                    capability=observation.capability,
                    instrument_id=observation.instrument_id,
                    observed_at_ns=snapshot.as_of_time_ns,
                    evidence={"reason": UnavailabilityReason.NOT_ENTITLED.value},
                )
            )
        elif observation.subscribed is False:
            findings.append(
                QualityFinding(
                    code=QualityFindingCode.NOT_SUBSCRIBED.value,
                    severity=FindingSeverity.WARNING,
                    message=f"{observation.capability.value} not subscribed for {snapshot.provider_id}",
                    provider_id=snapshot.provider_id,
                    capability=observation.capability,
                    instrument_id=observation.instrument_id,
                    observed_at_ns=snapshot.as_of_time_ns,
                    evidence={"reason": UnavailabilityReason.NOT_SUBSCRIBED.value},
                )
            )
        elif observation.availability == AvailabilityState.UNAVAILABLE:
            reason = UnavailabilityReason.DISCONNECTED.value
            if snapshot.connection == ConnectionState.DISCONNECTED:
                code = QualityFindingCode.PROVIDER_DISCONNECTED.value
            else:
                code = QualityFindingCode.CAPABILITY_UNAVAILABLE.value
            findings.append(
                QualityFinding(
                    code=code,
                    severity=FindingSeverity.ERROR,
                    message=f"{observation.capability.value} unavailable for {snapshot.provider_id}",
                    provider_id=snapshot.provider_id,
                    capability=observation.capability,
                    instrument_id=observation.instrument_id,
                    observed_at_ns=snapshot.as_of_time_ns,
                    evidence={"reason": reason},
                )
            )
    return _dedupe_findings(findings)


def _dimensions_from_findings(
    findings: tuple[QualityFinding, ...],
    *,
    temporally_legal: bool | None,
    support: SupportState = SupportState.SUPPORTED,
    availability: AvailabilityState = AvailabilityState.AVAILABLE,
    unavailability_reason: UnavailabilityReason | None = None,
) -> CapabilityDimensions:
    validity = ValidityState.VALID
    freshness = FreshnessState.FRESH
    completeness = CompletenessState.COMPLETE
    conflict = ConflictState.NONE
    for finding in findings:
        if finding.code in {
            QualityFindingCode.CROSSED_BOOK.value,
            QualityFindingCode.INVALID_QUOTE.value,
            QualityFindingCode.FUTURE_INFORMATION.value,
        }:
            validity = ValidityState.INVALID
        if finding.code in {
            QualityFindingCode.BORROW_STALE.value,
            QualityFindingCode.SHORT_INTEREST_STALE.value,
            QualityFindingCode.STALE_INFORMATION.value,
        }:
            freshness = FreshnessState.STALE
        if finding.code == QualityFindingCode.PARTIAL_DATA.value:
            completeness = CompletenessState.PARTIAL
        if finding.code == QualityFindingCode.PROVIDER_CONFLICT.value:
            conflict = ConflictState.CONFLICTED
    if temporally_legal is False:
        validity = ValidityState.INVALID
    return CapabilityDimensions(
        support=support,
        availability=availability,
        freshness=freshness,
        completeness=completeness,
        validity=validity,
        conflict=conflict,
        temporally_legal=temporally_legal,
        unavailability_reason=unavailability_reason,
    )


def _quality_state_from_dimensions(dimensions: CapabilityDimensions) -> QualityState:
    if dimensions.validity == ValidityState.INVALID:
        return QualityState.INVALID
    if dimensions.temporally_legal is False:
        return QualityState.INVALID
    if dimensions.availability == AvailabilityState.UNAVAILABLE:
        return QualityState.INVALID
    if dimensions.support == SupportState.UNSUPPORTED:
        return QualityState.INVALID
    if dimensions.support == SupportState.UNKNOWN or dimensions.availability == AvailabilityState.UNKNOWN:
        return QualityState.UNKNOWN
    if (
        dimensions.freshness == FreshnessState.STALE
        or dimensions.completeness == CompletenessState.PARTIAL
        or dimensions.conflict == ConflictState.CONFLICTED
        or dimensions.availability == AvailabilityState.DEGRADED
    ):
        return QualityState.DEGRADED
    if dimensions.validity == ValidityState.UNKNOWN:
        return QualityState.UNKNOWN
    return QualityState.GOOD


def assess_event_quality(
    event: EventV1,
    *,
    decision_time_ns: int,
    temporal_report: TemporalIntegrityReport | None = None,
    temporal_policy: TemporalIntegrityPolicy | None = None,
    quality_policy: QualityPolicy | None = None,
    max_age_ns: int | None = None,
) -> tuple[QualityFinding, ...]:
    """Assess a single normalized event without mutating inputs."""
    active_quality = quality_policy or DEFAULT_QUALITY_POLICY
    report = temporal_report or inspect_event_temporal_integrity(
        event,
        decision_time_ns=decision_time_ns,
        policy=temporal_policy or DEFAULT_TEMPORAL_POLICY,
    )
    findings: list[QualityFinding] = list(findings_from_temporal_report(event, report))
    findings.extend(validate_event_structure(event))

    effective_max_age = max_age_ns
    capability = capability_for_event_type(event.event_type)
    if effective_max_age is None and capability is not None:
        effective_max_age = active_quality.max_age_for_capability(capability)
    if effective_max_age is not None:
        stale = assess_borrow_freshness(event, decision_time_ns=decision_time_ns, max_age_ns=effective_max_age)
        if stale is not None:
            findings.append(stale)
        stale_si = assess_short_interest_freshness(
            event, decision_time_ns=decision_time_ns, max_age_ns=effective_max_age
        )
        if stale_si is not None:
            findings.append(stale_si)

    for flag in event.quality.flags:
        if flag and flag not in {finding.code for finding in findings}:
            findings.append(
                QualityFinding(
                    code=str(flag),
                    severity=FindingSeverity.WARNING,
                    message=f"Normalized event carries quality flag {flag}",
                    provider_id=event.source.provider_id,
                    capability=capability,
                    instrument_id=event.instrument_id,
                    observed_at_ns=event.available_time_ns,
                    event_id=event.event_id,
                )
            )
    return _dedupe_findings(findings)


def _build_capability_assessments(
    events: list[EventV1],
    event_findings: dict[str, tuple[QualityFinding, ...]],
    temporal_reports: dict[str, TemporalIntegrityReport],
    provider_health: tuple[ProviderHealthSnapshot, ...],
    conflict_findings: tuple[QualityFinding, ...],
) -> tuple[CapabilityAssessment, ...]:
    assessments: dict[tuple[str, str, str | None], CapabilityAssessment] = {}

    for snapshot in provider_health:
        for observation in snapshot.observations:
            key = (snapshot.provider_id, observation.capability.value, observation.instrument_id)
            health_findings = tuple(
                finding
                for finding in findings_from_provider_health(snapshot)
                if finding.capability in (None, observation.capability)
            )
            support = observation.support
            availability = observation.availability
            reason = None
            if support == SupportState.UNSUPPORTED:
                reason = UnavailabilityReason.UNSUPPORTED
            elif observation.entitled is False:
                reason = UnavailabilityReason.NOT_ENTITLED
            elif observation.subscribed is False:
                reason = UnavailabilityReason.NOT_SUBSCRIBED
            elif snapshot.connection == ConnectionState.DISCONNECTED:
                reason = UnavailabilityReason.DISCONNECTED
                availability = AvailabilityState.UNAVAILABLE
            dimensions = _dimensions_from_findings(
                health_findings,
                temporally_legal=None,
                support=support,
                availability=availability,
                unavailability_reason=reason,
            )
            assessments[key] = CapabilityAssessment(
                provider_id=snapshot.provider_id,
                capability=observation.capability,
                instrument_id=observation.instrument_id,
                dimensions=dimensions,
                quality_state=_quality_state_from_dimensions(dimensions),
                findings=health_findings,
            )

    for event in events:
        capability = capability_for_event_type(event.event_type)
        if capability is None:
            continue
        provider_id = event.source.provider_id
        key = (provider_id, capability.value, event.instrument_id)
        report = temporal_reports.get(event.event_id)
        temporally_legal = None if report is None else report.eligible
        scoped_conflicts = tuple(
            finding
            for finding in conflict_findings
            if finding.capability == capability
            and (finding.instrument_id is None or finding.instrument_id == event.instrument_id)
            and finding.evidence.get("event_ids")
            and event.event_id in finding.evidence.get("event_ids", [])
        )
        findings = event_findings.get(event.event_id, ()) + scoped_conflicts
        dimensions = _dimensions_from_findings(findings, temporally_legal=temporally_legal)
        quality_state = _quality_state_from_dimensions(dimensions)
        prior = assessments.get(key)
        if prior is None:
            assessments[key] = CapabilityAssessment(
                provider_id=provider_id,
                capability=capability,
                instrument_id=event.instrument_id,
                dimensions=dimensions,
                quality_state=quality_state,
                findings=findings,
                event_ids=(event.event_id,),
            )
            continue
        merged_findings = _dedupe_findings(list(prior.findings) + list(findings))
        merged_dims = _dimensions_from_findings(
            merged_findings,
            temporally_legal=(
                prior.dimensions.temporally_legal
                if prior.dimensions.temporally_legal is False
                else temporally_legal
            ),
            support=prior.dimensions.support,
            availability=prior.dimensions.availability,
            unavailability_reason=prior.dimensions.unavailability_reason,
        )
        merged_state = _quality_state_from_dimensions(merged_dims)
        if _quality_rank(merged_state) > _quality_rank(prior.quality_state):
            final_state = prior.quality_state
        else:
            final_state = merged_state
        assessments[key] = CapabilityAssessment(
            provider_id=provider_id,
            capability=capability,
            instrument_id=event.instrument_id,
            dimensions=merged_dims,
            quality_state=final_state,
            findings=merged_findings,
            event_ids=prior.event_ids + (event.event_id,),
        )

    return tuple(sorted(assessments.values(), key=lambda row: (row.provider_id, row.capability.value, row.instrument_id or "")))


def inspect_quality(
    *,
    events: list[EventV1] | tuple[EventV1, ...] = (),
    decision_time_ns: int,
    requirements: RequirementSet | None = None,
    provider_health: tuple[ProviderHealthSnapshot, ...] = (),
    temporal_reports: dict[str, TemporalIntegrityReport] | None = None,
    temporal_policy: TemporalIntegrityPolicy | None = None,
    policy: QualityPolicy | None = None,
) -> QualityAssessment:
    """Non-throwing audit API returning all relevant findings and assessments."""
    active_policy = policy or DEFAULT_QUALITY_POLICY
    event_list = list(events)
    reports = dict(temporal_reports or {})
    event_findings: dict[str, tuple[QualityFinding, ...]] = {}
    all_findings: list[QualityFinding] = []

    for event in event_list:
        report = reports.get(event.event_id)
        if report is None:
            report = inspect_event_temporal_integrity(
                event,
                decision_time_ns=decision_time_ns,
                policy=temporal_policy or DEFAULT_TEMPORAL_POLICY,
            )
            reports[event.event_id] = report
        req_max_age = None
        capability = capability_for_event_type(event.event_type)
        if requirements and capability is not None:
            for requirement in requirements.requirements:
                if requirement.capability == capability and requirement.max_age_ns is not None:
                    req_max_age = requirement.max_age_ns
                    break
        findings = assess_event_quality(
            event,
            decision_time_ns=decision_time_ns,
            temporal_report=report,
            temporal_policy=temporal_policy,
            quality_policy=active_policy,
            max_age_ns=req_max_age,
        )
        event_findings[event.event_id] = findings
        all_findings.extend(findings)

    for snapshot in provider_health:
        all_findings.extend(findings_from_provider_health(snapshot))
        all_findings.extend(snapshot.findings)

    conflict_findings = detect_provider_conflicts(event_list, policy=active_policy)
    all_findings.extend(conflict_findings)

    capability_assessments = _build_capability_assessments(
        event_list,
        event_findings,
        reports,
        provider_health,
        conflict_findings,
    )

    return QualityAssessment(
        decision_time_ns=decision_time_ns,
        findings=_dedupe_findings(all_findings),
        capability_assessments=capability_assessments,
        provider_health=provider_health,
        policy_id=active_policy.policy_id,
        policy_version=active_policy.policy_version,
    )


def _best_assessment_for_requirement(
    requirement: CapabilityRequirement,
    assessments: tuple[CapabilityAssessment, ...],
) -> CapabilityAssessment | None:
    candidates = [
        row
        for row in assessments
        if row.capability == requirement.capability
        and (
            not requirement.acceptable_providers
            or row.provider_id in requirement.acceptable_providers
        )
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda row: (_quality_rank(row.quality_state), row.provider_id))


def _action_for_requirement(
    requirement: CapabilityRequirement,
    assessment: CapabilityAssessment | None,
    policy: QualityPolicy,
    *,
    has_conflict: bool,
) -> DecisionAction:
    if assessment is None:
        if requirement.required:
            return requirement.failure_action
        return policy.optional_unavailable_action

    if assessment.dimensions.temporally_legal is False:
        return policy.future_information_action
    if assessment.quality_state == QualityState.UNKNOWN:
        return policy.unknown_mandatory_action if requirement.required else policy.unknown_optional_action
    if assessment.quality_state == QualityState.INVALID:
        return requirement.failure_action if requirement.required else policy.optional_unavailable_action
    if has_conflict and policy.require_provider_agreement:
        return policy.provider_conflict_action
    if not _meets_minimum(
        assessment.quality_state,
        requirement.minimum_quality_state,
        allow_degraded=requirement.allow_degraded,
    ):
        return requirement.failure_action if requirement.required else policy.optional_unavailable_action
    if assessment.quality_state == QualityState.DEGRADED:
        return DecisionAction.DEGRADE if requirement.required else policy.optional_unavailable_action
    if has_conflict:
        return policy.provider_conflict_action
    return DecisionAction.USE


def decide_quality(
    assessment: QualityAssessment,
    requirements: RequirementSet,
    *,
    policy: QualityPolicy | None = None,
) -> QualityDecision:
    """Map assessment plus caller requirements to a use decision."""
    active_policy = policy or DEFAULT_QUALITY_POLICY
    conflict_caps = {
        finding.capability
        for finding in assessment.findings
        if finding.code == QualityFindingCode.PROVIDER_CONFLICT.value and finding.capability is not None
    }

    actions: list[DecisionAction] = []
    reasons: list[str] = []
    missing: list[IntelligenceCapability] = []
    degraded: list[IntelligenceCapability] = []
    satisfied: list[IntelligenceCapability] = []

    for requirement in requirements.requirements:
        best = _best_assessment_for_requirement(requirement, assessment.capability_assessments)
        action = _action_for_requirement(
            requirement,
            best,
            active_policy,
            has_conflict=requirement.capability in conflict_caps,
        )
        actions.append(action)
        if action == DecisionAction.USE:
            satisfied.append(requirement.capability)
        elif action == DecisionAction.DEGRADE:
            degraded.append(requirement.capability)
            reasons.append(f"{requirement.capability.value}: degraded")
        elif action == DecisionAction.ABSTAIN:
            if requirement.required:
                missing.append(requirement.capability)
            else:
                degraded.append(requirement.capability)
            reasons.append(f"{requirement.capability.value}: abstain")
        elif action == DecisionAction.FAIL_CLOSED:
            missing.append(requirement.capability)
            reasons.append(f"{requirement.capability.value}: fail_closed")

    if not requirements.requirements:
        final_action = DecisionAction.USE
    elif DecisionAction.FAIL_CLOSED in actions:
        final_action = DecisionAction.FAIL_CLOSED
    elif all(action == DecisionAction.USE for action in actions):
        final_action = DecisionAction.USE
    elif any(action == DecisionAction.ABSTAIN for action in actions) and DecisionAction.FAIL_CLOSED not in actions:
        if any(
            requirement.required and action == DecisionAction.ABSTAIN
            for requirement, action in zip(requirements.requirements, actions, strict=True)
        ):
            final_action = DecisionAction.ABSTAIN
        else:
            final_action = DecisionAction.DEGRADE
    elif DecisionAction.DEGRADE in actions:
        final_action = DecisionAction.DEGRADE
    else:
        final_action = DecisionAction.ABSTAIN

    quality_state = quality_state_for_action(final_action, assessment)
    return QualityDecision(
        action=final_action,
        quality_state=quality_state,
        assessment=assessment,
        reasons=tuple(reasons),
        missing_requirements=tuple(missing),
        degraded_requirements=tuple(degraded),
        satisfied_requirements=tuple(satisfied),
    )


def assess_capabilities(
    *,
    events: list[EventV1] | tuple[EventV1, ...] = (),
    decision_time_ns: int,
    requirements: RequirementSet,
    provider_health: tuple[ProviderHealthSnapshot, ...] = (),
    temporal_reports: dict[str, TemporalIntegrityReport] | None = None,
    temporal_policy: TemporalIntegrityPolicy | None = None,
    policy: QualityPolicy | None = None,
) -> QualityDecision:
    """Assess quality and produce a caller-facing decision."""
    assessment = inspect_quality(
        events=events,
        decision_time_ns=decision_time_ns,
        requirements=requirements,
        provider_health=provider_health,
        temporal_reports=temporal_reports,
        temporal_policy=temporal_policy,
        policy=policy,
    )
    return decide_quality(assessment, requirements, policy=policy)


def require_quality_decision(
    *,
    events: list[EventV1] | tuple[EventV1, ...] = (),
    decision_time_ns: int,
    requirements: RequirementSet,
    provider_health: tuple[ProviderHealthSnapshot, ...] = (),
    temporal_reports: dict[str, TemporalIntegrityReport] | None = None,
    temporal_policy: TemporalIntegrityPolicy | None = None,
    policy: QualityPolicy | None = None,
) -> QualityDecision:
    """Strict API — raises QualityCapabilityError on FAIL_CLOSED."""
    decision = assess_capabilities(
        events=events,
        decision_time_ns=decision_time_ns,
        requirements=requirements,
        provider_health=provider_health,
        temporal_reports=temporal_reports,
        temporal_policy=temporal_policy,
        policy=policy,
    )
    raise_if_fail_closed(decision)
    return decision


__all__ = [
    "assess_capabilities",
    "assess_event_quality",
    "decide_quality",
    "findings_from_provider_health",
    "inspect_quality",
    "require_quality_decision",
]
