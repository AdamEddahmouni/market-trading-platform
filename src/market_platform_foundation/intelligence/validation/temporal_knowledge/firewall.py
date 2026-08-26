"""Temporal knowledge firewall (BUILD 19)."""

from __future__ import annotations

from ..errors import ValidationError
from ..types import (
    KnowledgeAssessmentStatus,
    KnowledgeCutoffState,
    KnowledgeProfileV1,
    TemporalKnowledgeAssessment,
    TemporalKnowledgePolicyV1,
    ToolPolicyClass,
)
from .policy import DEFAULT_TEMPORAL_KNOWLEDGE_POLICY


def effective_knowledge_cutoff_ns(profile: KnowledgeProfileV1) -> int | None:
    cutoffs: list[int] = []
    if profile.model_knowledge_cutoff_ns is not None:
        cutoffs.append(profile.model_knowledge_cutoff_ns)
    if profile.finetune_cutoff_ns is not None:
        cutoffs.append(profile.finetune_cutoff_ns)
    if profile.teacher_knowledge_cutoff_ns is not None:
        cutoffs.append(profile.teacher_knowledge_cutoff_ns)
    if not cutoffs:
        return None
    return max(cutoffs)


def assess_knowledge_cutoff(
    profile: KnowledgeProfileV1,
    decision_time_ns: int,
    policy: TemporalKnowledgePolicyV1 = DEFAULT_TEMPORAL_KNOWLEDGE_POLICY,
) -> TemporalKnowledgeAssessment:
    if not profile.is_llm:
        return TemporalKnowledgeAssessment(
            assessment_id=f"assess-{profile.component_id}-{decision_time_ns}",
            policy_id=policy.policy_id,
            profile_id=profile.component_id,
            decision_time_ns=decision_time_ns,
            status=KnowledgeAssessmentStatus.NOT_APPLICABLE,
            reasons=("statistical_candidate",),
        )

    if profile.knowledge_cutoff_state == KnowledgeCutoffState.SYNTHETIC_TEST:
        if policy.allow_synthetic_test_teachers:
            return TemporalKnowledgeAssessment(
                assessment_id=f"assess-{profile.component_id}-{decision_time_ns}",
                policy_id=policy.policy_id,
                profile_id=profile.component_id,
                decision_time_ns=decision_time_ns,
                status=KnowledgeAssessmentStatus.NOT_APPLICABLE,
                reasons=("synthetic_test_teacher",),
            )

    if profile.knowledge_cutoff_state in {
        KnowledgeCutoffState.UNKNOWN,
        KnowledgeCutoffState.UNBOUNDED,
    }:
        return TemporalKnowledgeAssessment(
            assessment_id=f"assess-{profile.component_id}-{decision_time_ns}",
            policy_id=policy.policy_id,
            profile_id=profile.component_id,
            decision_time_ns=decision_time_ns,
            status=KnowledgeAssessmentStatus.BLOCKED_UNKNOWN_KNOWLEDGE_CUTOFF,
            reasons=("unknown_or_unbounded_cutoff",),
        )

    cutoff = effective_knowledge_cutoff_ns(profile)
    if cutoff is None:
        return TemporalKnowledgeAssessment(
            assessment_id=f"assess-{profile.component_id}-{decision_time_ns}",
            policy_id=policy.policy_id,
            profile_id=profile.component_id,
            decision_time_ns=decision_time_ns,
            status=KnowledgeAssessmentStatus.BLOCKED_UNKNOWN_KNOWLEDGE_CUTOFF,
            reasons=("missing_cutoff_timestamp",),
        )

    if cutoff > decision_time_ns:
        return TemporalKnowledgeAssessment(
            assessment_id=f"assess-{profile.component_id}-{decision_time_ns}",
            policy_id=policy.policy_id,
            profile_id=profile.component_id,
            decision_time_ns=decision_time_ns,
            status=KnowledgeAssessmentStatus.FAIL_KNOWLEDGE_CUTOFF,
            reasons=(f"cutoff_after_decision:{cutoff}>{decision_time_ns}",),
        )

    return TemporalKnowledgeAssessment(
        assessment_id=f"assess-{profile.component_id}-{decision_time_ns}",
        policy_id=policy.policy_id,
        profile_id=profile.component_id,
        decision_time_ns=decision_time_ns,
        status=KnowledgeAssessmentStatus.PASS,
        reasons=("knowledge_cutoff_before_or_at_decision",),
    )


def assess_retrieval_source(
    *,
    available_time_ns: int,
    decision_time_ns: int,
    profile: KnowledgeProfileV1,
    policy: TemporalKnowledgePolicyV1 = DEFAULT_TEMPORAL_KNOWLEDGE_POLICY,
) -> TemporalKnowledgeAssessment:
    if available_time_ns > decision_time_ns:
        return TemporalKnowledgeAssessment(
            assessment_id=f"retrieval-{profile.component_id}-{decision_time_ns}",
            policy_id=policy.policy_id,
            profile_id=profile.component_id,
            decision_time_ns=decision_time_ns,
            status=KnowledgeAssessmentStatus.FAIL_RETRIEVAL_TIME,
            reasons=(f"future_source:{available_time_ns}>{decision_time_ns}",),
        )
    return TemporalKnowledgeAssessment(
        assessment_id=f"retrieval-{profile.component_id}-{decision_time_ns}",
        policy_id=policy.policy_id,
        profile_id=profile.component_id,
        decision_time_ns=decision_time_ns,
        status=KnowledgeAssessmentStatus.PASS,
        reasons=("pit_retrieval",),
    )


def assess_tool_policy(
    tool_class: ToolPolicyClass,
    profile: KnowledgeProfileV1,
    decision_time_ns: int,
    policy: TemporalKnowledgePolicyV1 = DEFAULT_TEMPORAL_KNOWLEDGE_POLICY,
) -> TemporalKnowledgeAssessment:
    if tool_class == ToolPolicyClass.PIT_SAFE:
        status = KnowledgeAssessmentStatus.PASS
        reasons = ("pit_safe_tool",)
    elif tool_class in {ToolPolicyClass.CURRENT_ONLY, ToolPolicyClass.UNSAFE_UNBOUNDED}:
        status = KnowledgeAssessmentStatus.FAIL_TOOL_POLICY
        reasons = (f"unsafe_tool:{tool_class.value}",)
    else:
        status = KnowledgeAssessmentStatus.UNKNOWN
        reasons = ("unknown_tool_class",)

    return TemporalKnowledgeAssessment(
        assessment_id=f"tool-{profile.component_id}-{decision_time_ns}",
        policy_id=policy.policy_id,
        profile_id=profile.component_id,
        decision_time_ns=decision_time_ns,
        status=status,
        reasons=reasons,
    )


def assess_prompt_only_time_travel(
    profile: KnowledgeProfileV1,
    decision_time_ns: int,
    *,
    prompt_claims_historical_date: bool,
    policy: TemporalKnowledgePolicyV1 = DEFAULT_TEMPORAL_KNOWLEDGE_POLICY,
) -> TemporalKnowledgeAssessment:
    if not policy.reject_prompt_only_time_travel:
        return TemporalKnowledgeAssessment(
            assessment_id=f"prompt-{profile.component_id}-{decision_time_ns}",
            policy_id=policy.policy_id,
            profile_id=profile.component_id,
            decision_time_ns=decision_time_ns,
            status=KnowledgeAssessmentStatus.PASS,
            reasons=("prompt_check_disabled",),
        )
    if prompt_claims_historical_date and profile.is_llm:
        cutoff = effective_knowledge_cutoff_ns(profile)
        if cutoff is not None and cutoff > decision_time_ns:
            return TemporalKnowledgeAssessment(
                assessment_id=f"prompt-{profile.component_id}-{decision_time_ns}",
                policy_id=policy.policy_id,
                profile_id=profile.component_id,
                decision_time_ns=decision_time_ns,
                status=KnowledgeAssessmentStatus.FAIL_KNOWLEDGE_CUTOFF,
                reasons=("prompt_only_time_travel_insufficient",),
            )
    return TemporalKnowledgeAssessment(
        assessment_id=f"prompt-{profile.component_id}-{decision_time_ns}",
        policy_id=policy.policy_id,
        profile_id=profile.component_id,
        decision_time_ns=decision_time_ns,
        status=KnowledgeAssessmentStatus.PASS,
        reasons=("no_prompt_only_violation",),
    )


def require_historical_inference_allowed(
    profile: KnowledgeProfileV1,
    decision_time_ns: int,
    policy: TemporalKnowledgePolicyV1 = DEFAULT_TEMPORAL_KNOWLEDGE_POLICY,
) -> TemporalKnowledgeAssessment:
    assessment = assess_knowledge_cutoff(profile, decision_time_ns, policy)
    if assessment.status not in {
        KnowledgeAssessmentStatus.PASS,
        KnowledgeAssessmentStatus.NOT_APPLICABLE,
    }:
        raise ValidationError(
            assessment.status.value,
            details={
                "component_id": profile.component_id,
                "decision_time_ns": decision_time_ns,
                "reasons": assessment.reasons,
            },
        )
    return assessment


def aggregate_assessment_status(
    assessments: tuple[TemporalKnowledgeAssessment, ...],
) -> KnowledgeAssessmentStatus:
    if not assessments:
        return KnowledgeAssessmentStatus.UNKNOWN
    priority = [
        KnowledgeAssessmentStatus.FAIL_KNOWLEDGE_CUTOFF,
        KnowledgeAssessmentStatus.BLOCKED_UNKNOWN_KNOWLEDGE_CUTOFF,
        KnowledgeAssessmentStatus.FAIL_TOOL_POLICY,
        KnowledgeAssessmentStatus.FAIL_RETRIEVAL_TIME,
        KnowledgeAssessmentStatus.FAIL_TEACHER_PROVENANCE,
        KnowledgeAssessmentStatus.UNKNOWN,
        KnowledgeAssessmentStatus.NOT_APPLICABLE,
        KnowledgeAssessmentStatus.PASS,
    ]
    statuses = {a.status for a in assessments}
    for status in priority:
        if status in statuses:
            return status
    return KnowledgeAssessmentStatus.UNKNOWN


__all__ = [
    "aggregate_assessment_status",
    "assess_knowledge_cutoff",
    "assess_prompt_only_time_travel",
    "assess_retrieval_source",
    "assess_tool_policy",
    "effective_knowledge_cutoff_ns",
    "require_historical_inference_allowed",
]
