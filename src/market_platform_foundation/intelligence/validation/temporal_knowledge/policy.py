"""Temporal knowledge policy and profiles (BUILD 19)."""

from __future__ import annotations

from ..types import (
    KnowledgeCutoffState,
    KnowledgeProfileV1,
    NetworkPolicy,
    TemporalKnowledgePolicyV1,
    ToolPolicyClass,
)

DEFAULT_TEMPORAL_KNOWLEDGE_POLICY = TemporalKnowledgePolicyV1(
    policy_id="tkp-default-v1",
    schema_version="1",
    network_policy=NetworkPolicy.DENIED,
    require_declared_model_cutoff=True,
    reject_prompt_only_time_travel=True,
    allow_synthetic_test_teachers=True,
)


def statistical_candidate_profile(component_id: str) -> KnowledgeProfileV1:
    return KnowledgeProfileV1(
        component_id=component_id,
        component_kind="STATISTICAL_MODEL",
        is_llm=False,
        knowledge_cutoff_state=KnowledgeCutoffState.NOT_APPLICABLE,
        network_policy=NetworkPolicy.DENIED,
    )


def llm_profile(
    *,
    component_id: str,
    knowledge_cutoff_state: KnowledgeCutoffState,
    model_knowledge_cutoff_ns: int | None = None,
    finetune_cutoff_ns: int | None = None,
    tool_policy_classes: tuple[ToolPolicyClass, ...] = (),
    teacher_id: str | None = None,
    teacher_knowledge_cutoff_ns: int | None = None,
    teacher_knowledge_cutoff_state: KnowledgeCutoffState | None = None,
    lineage: dict | None = None,
) -> KnowledgeProfileV1:
    return KnowledgeProfileV1(
        component_id=component_id,
        component_kind="LLM",
        is_llm=True,
        knowledge_cutoff_state=knowledge_cutoff_state,
        model_knowledge_cutoff_ns=model_knowledge_cutoff_ns,
        finetune_cutoff_ns=finetune_cutoff_ns,
        teacher_id=teacher_id,
        teacher_knowledge_cutoff_ns=teacher_knowledge_cutoff_ns,
        teacher_knowledge_cutoff_state=teacher_knowledge_cutoff_state,
        tool_policy_classes=tool_policy_classes,
        network_policy=NetworkPolicy.DENIED,
        lineage=lineage or {},
    )


__all__ = [
    "DEFAULT_TEMPORAL_KNOWLEDGE_POLICY",
    "llm_profile",
    "statistical_candidate_profile",
]
