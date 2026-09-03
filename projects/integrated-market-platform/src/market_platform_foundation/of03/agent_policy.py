"""Agent policy is descriptive. It never authorizes execution."""

from __future__ import annotations

from .contracts import CapabilityDefinition
from .enums import AgentUseDecision, AutomationPolicy, EffectClass, HumanApprovalPolicy
from .errors import OF03Error, OF03ErrorCode


def authorize_execution_from_registry(capability: CapabilityDefinition) -> None:
    raise OF03Error(
        OF03ErrorCode.REGISTRY_DOES_NOT_GRANT_AUTHORITY,
        "a registry entry cannot grant or satisfy required authority",
        {
            "capability_id": capability.capability_id,
            "required_authority_refs": list(capability.required_authority_refs),
        },
    )


def describe_automation_policy(capability: CapabilityDefinition) -> str:
    return capability.automation_policy.value


def evaluate_agent_use(capability: CapabilityDefinition, *, intent: str) -> AgentUseDecision:
    if intent == "INSPECT":
        return AgentUseDecision.DESCRIBE_ONLY
    if intent != "EXECUTE":
        raise OF03Error(OF03ErrorCode.INVALID_COMMAND, "unknown agent intent", {"intent": intent})
    if capability.automation_policy is AutomationPolicy.AGENT_PROHIBITED:
        return AgentUseDecision.DENIED_AGENT_PROHIBITED
    if capability.human_approval_policy is HumanApprovalPolicy.REQUIRED:
        return AgentUseDecision.DENIED_HUMAN_APPROVAL_REQUIRED
    if capability.effect_class in {EffectClass.DESTRUCTIVE_MAINTENANCE, EffectClass.AUTHORITATIVE_MUTATION, EffectClass.EXTERNAL_SIDE_EFFECT}:
        return AgentUseDecision.DENIED_DESTRUCTIVE
    if capability.automation_policy is AutomationPolicy.AUTOMATION_ALLOWED_WITH_GUARD:
        return AgentUseDecision.GUARDED_METADATA_ONLY
    return AgentUseDecision.DENIED_REGISTRY_DOES_NOT_AUTHORIZE
