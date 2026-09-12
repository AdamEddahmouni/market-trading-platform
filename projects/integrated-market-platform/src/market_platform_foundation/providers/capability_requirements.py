"""Reusable capability requirement templates and campaign profiles (Wave B)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .capability_contract import CapabilityAccessState, CampaignRole


class RequirementTemplateId(StrEnum):
    """Named templates composed into campaign profiles."""

    FUTURES_MARKET_CONTEXT = "futures_market_context"
    NEWS_CATALYST_CONTEXT = "news_catalyst_context"
    CAPABILITY_CONTRACT_CAMPAIGN_BINDING = "capability_contract_campaign_binding"


@dataclass(frozen=True, slots=True)
class CapabilityRequirement:
    requirement_id: str
    capability_id: str
    provider_id: str | None
    minimum_access_state: CapabilityAccessState
    campaign_role: CampaignRole | None = None
    activation_gate_id: str | None = None
    notes: str = ""


@dataclass(frozen=True, slots=True)
class CampaignRequirementProfile:
    profile_id: str
    campaign_slug: str
    templates: tuple[RequirementTemplateId, ...]
    capability_requirements: tuple[CapabilityRequirement, ...]
    wave_a_gap_ids: tuple[str, ...]
    code_gap_ids: tuple[str, ...]
    activation_gate_ids: tuple[str, ...]


def _futures_market_context_requirements() -> tuple[CapabilityRequirement, ...]:
    return (
        CapabilityRequirement(
            requirement_id="futures.es_quote.moomoo",
            capability_id="US_FUTURES_QUOTE",
            provider_id="MOOMOO",
            minimum_access_state=CapabilityAccessState.SAMPLE_VERIFIED,
            campaign_role=CampaignRole.AUTHORITY,
            activation_gate_id="G-A7",
            notes="ES lane market context; stale Wave A probe showed entitlement unknown.",
        ),
    )


def _news_catalyst_context_requirements() -> tuple[CapabilityRequirement, ...]:
    return (
        CapabilityRequirement(
            requirement_id="news.finviz_export",
            capability_id="NEWS_EXPORT",
            provider_id="FINVIZ_ELITE",
            minimum_access_state=CapabilityAccessState.CATALOGED,
            campaign_role=CampaignRole.CONTEXT_ONLY,
            activation_gate_id="G-A7",
            notes="Equity-scoped headline context; ES linkage is owner policy (WAVE-A-003).",
        ),
    )


def _campaign_binding_requirements() -> tuple[CapabilityRequirement, ...]:
    return (
        CapabilityRequirement(
            requirement_id="binding.authority_campaign_bound",
            capability_id="US_EQUITY_L1",
            provider_id="MOOMOO",
            minimum_access_state=CapabilityAccessState.CAMPAIGN_BOUND,
            campaign_role=CampaignRole.AUTHORITY,
            activation_gate_id="G-A6",
            notes="Market Data Capability Contract campaign binding for authority provider.",
        ),
    )


_TEMPLATE_BUILDERS: dict[RequirementTemplateId, tuple[CapabilityRequirement, ...]] = {
    RequirementTemplateId.FUTURES_MARKET_CONTEXT: _futures_market_context_requirements(),
    RequirementTemplateId.NEWS_CATALYST_CONTEXT: _news_catalyst_context_requirements(),
    RequirementTemplateId.CAPABILITY_CONTRACT_CAMPAIGN_BINDING: _campaign_binding_requirements(),
}


def expand_template_requirements(
    template_ids: tuple[RequirementTemplateId, ...],
) -> tuple[CapabilityRequirement, ...]:
    rows: list[CapabilityRequirement] = []
    seen: set[str] = set()
    for template_id in template_ids:
        for row in _TEMPLATE_BUILDERS[template_id]:
            if row.requirement_id in seen:
                continue
            seen.add(row.requirement_id)
            rows.append(row)
    return tuple(rows)


FTEP_V1_001_ES_NEWS_PROFILE = CampaignRequirementProfile(
    profile_id="FTEP-V1-001",
    campaign_slug="FTEP-V1-001",
    templates=(
        RequirementTemplateId.FUTURES_MARKET_CONTEXT,
        RequirementTemplateId.NEWS_CATALYST_CONTEXT,
        RequirementTemplateId.CAPABILITY_CONTRACT_CAMPAIGN_BINDING,
    ),
    capability_requirements=expand_template_requirements(
        (
            RequirementTemplateId.FUTURES_MARKET_CONTEXT,
            RequirementTemplateId.NEWS_CATALYST_CONTEXT,
            RequirementTemplateId.CAPABILITY_CONTRACT_CAMPAIGN_BINDING,
        )
    ),
    wave_a_gap_ids=(
        "WAVE-A-001",
        "WAVE-A-002",
        "WAVE-A-003",
        "WAVE-A-004",
        "WAVE-A-009",
        "WAVE-A-010",
    ),
    code_gap_ids=("CG-01", "CG-02"),
    activation_gate_ids=("G-A6", "G-A7"),
)

_PROFILES: dict[str, CampaignRequirementProfile] = {
    FTEP_V1_001_ES_NEWS_PROFILE.profile_id: FTEP_V1_001_ES_NEWS_PROFILE,
    FTEP_V1_001_ES_NEWS_PROFILE.campaign_slug: FTEP_V1_001_ES_NEWS_PROFILE,
}


def get_campaign_requirement_profile(profile_or_slug: str) -> CampaignRequirementProfile:
    key = profile_or_slug.strip()
    try:
        return _PROFILES[key]
    except KeyError:
        raise KeyError(f"UNKNOWN_CAMPAIGN_REQUIREMENT_PROFILE:{key}") from None
