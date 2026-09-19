"""Registered IBP system-under-test profiles (stub baseline vs bounded non-stub)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

IBP_HYPOTHESIS_FACTS_SUT_V1 = "LANE-E-HYP-IBP-FACTS-SUT-V1"

IBP_SYNTHETIC_SUT_PROFILE_ID = "synthetic_intelligence_fixture_v1_baseline_v1"
IBP_SYNTHETIC_SUT_MODEL_ID = "ibp-deterministic-stub-v1"

IBP_FACTS_SUT_NAME = "IMP SmartRouter + Grounded Facts Responder"
IBP_FACTS_SUT_VERSION = "imp.ibp-facts-sut/1.1.0"
IBP_FACTS_SUT_PROFILE_ID = "imp_historical_routing_grounded_facts_v1"
IBP_FACTS_SUT_MODEL_ID = "grounded.evidence:deterministic.v1"

IBP_FACTS_SUT_LIMITATION_CLASS = "BOUNDED_OFFLINE_NO_LLM_GROUNDED_HISTORICAL"
IBP_FACTS_SUT_LIMITATION_SUMMARY = (
    "Uses in-repo SmartRouter (BUILD 09), admitted-evidence grounded fact extraction "
    "(question_class handlers), and legacy GroundedEvidenceInference for non-factual "
    "blind modes; no Anthropic/network LLM and no evaluator gold."
)

IBP_FACTS_MODEL_ROUTING = {
    "primary_inference": "grounded.evidence:deterministic.v1",
    "assistant_env_policy": "IMP_ASSISTANT_STUB unset; IMP_ASSISTANT_PROVIDER=grounded",
    "llm_network": "DISABLED_BY_CONSTRUCTION",
    "router": "market_platform_foundation.intelligence.routing.SmartRouter",
    "router_policy": "RoutingPolicyV1",
}

IBP_FACTS_TOOLS_AVAILABLE = (
    "historical_development_fixture_reader",
    "smart_router_route",
    "grounded_evidence_infer",
    "grounded_fact_extraction_v1",
)

IBP_FACTS_CONTEXT_RULES = (
    "one_fresh_context_per_case_v1",
    "stateless_sut_runner_no_cross_case_memory",
    "evaluator_gold_prefix_blocked:evaluator_only/",
    "scores_after_sut_response_only",
)


@dataclass(frozen=True, slots=True)
class IbpSutProfile:
    profile_id: str
    model_id: str
    name: str
    version: str
    hypothesis_id: str | None
    runner_id: str
    limitation_class: str | None = None
    limitation_summary: str | None = None
    model_routing: dict[str, Any] | None = None
    tools_available: tuple[str, ...] = ()
    context_rules: tuple[str, ...] = ()


def sut_profile_registry() -> dict[str, IbpSutProfile]:
    return {
        IBP_SYNTHETIC_SUT_PROFILE_ID: IbpSutProfile(
            profile_id=IBP_SYNTHETIC_SUT_PROFILE_ID,
            model_id=IBP_SYNTHETIC_SUT_MODEL_ID,
            name="IBP Deterministic Stub Responder",
            version="imp.ibp-synthetic-stub/1.0.0",
            hypothesis_id=None,
            runner_id="synthetic",
        ),
        IBP_FACTS_SUT_PROFILE_ID: IbpSutProfile(
            profile_id=IBP_FACTS_SUT_PROFILE_ID,
            model_id=IBP_FACTS_SUT_MODEL_ID,
            name=IBP_FACTS_SUT_NAME,
            version=IBP_FACTS_SUT_VERSION,
            hypothesis_id=IBP_HYPOTHESIS_FACTS_SUT_V1,
            runner_id="facts",
            limitation_class=IBP_FACTS_SUT_LIMITATION_CLASS,
            limitation_summary=IBP_FACTS_SUT_LIMITATION_SUMMARY,
            model_routing=dict(IBP_FACTS_MODEL_ROUTING),
            tools_available=IBP_FACTS_TOOLS_AVAILABLE,
            context_rules=IBP_FACTS_CONTEXT_RULES,
        ),
    }


def resolve_sut_profile(profile_id: str) -> IbpSutProfile:
    try:
        return sut_profile_registry()[profile_id]
    except KeyError as exc:
        raise ValueError(f"IBP_SUT_PROFILE_UNKNOWN:{profile_id}") from exc


def sut_profile_documentation(profile: IbpSutProfile, *, code_sha: str) -> dict[str, Any]:
    return {
        "SUT_NAME": profile.name,
        "SUT_VERSION": profile.version,
        "CODE_SHA": code_sha,
        "SUT_PROFILE_ID": profile.profile_id,
        "SUT_MODEL_ID": profile.model_id,
        "HYPOTHESIS_ID": profile.hypothesis_id,
        "MODEL_ROUTING": profile.model_routing,
        "TOOLS_AVAILABLE": list(profile.tools_available),
        "CONTEXT_RULES": list(profile.context_rules),
        "LIMITATION_CLASS": profile.limitation_class,
        "LIMITATION_SUMMARY": profile.limitation_summary,
    }


SutRunner = Callable[[dict[str, Any]], dict[str, Any]]


__all__ = [
    "IBP_FACTS_CONTEXT_RULES",
    "IBP_FACTS_MODEL_ROUTING",
    "IBP_FACTS_SUT_LIMITATION_CLASS",
    "IBP_FACTS_SUT_LIMITATION_SUMMARY",
    "IBP_FACTS_SUT_MODEL_ID",
    "IBP_FACTS_SUT_NAME",
    "IBP_FACTS_SUT_PROFILE_ID",
    "IBP_FACTS_SUT_VERSION",
    "IBP_FACTS_TOOLS_AVAILABLE",
    "IBP_HYPOTHESIS_FACTS_SUT_V1",
    "IBP_SYNTHETIC_SUT_MODEL_ID",
    "IBP_SYNTHETIC_SUT_PROFILE_ID",
    "IbpSutProfile",
    "SutRunner",
    "resolve_sut_profile",
    "sut_profile_documentation",
    "sut_profile_registry",
]
