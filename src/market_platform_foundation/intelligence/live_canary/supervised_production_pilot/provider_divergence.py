"""Provider divergence assessment (BUILD 33)."""

from __future__ import annotations

from .identity import derive_provider_divergence_id
from .types import (
    ProviderDivergenceAssessmentV1,
    ProviderDivergenceStatus,
    ProviderRedundancyPolicyV1,
    SUPERVISED_PILOT_SCHEMA_VERSION,
)


def assess_provider_divergence(
    *,
    policy: ProviderRedundancyPolicyV1,
    as_of_ns: int,
    instrument: str,
    provider_a: str,
    provider_b: str,
    provider_a_value: float | None,
    provider_b_value: float | None,
    provider_a_event_time_ns: int | None = None,
    provider_b_event_time_ns: int | None = None,
    provider_a_freshness_ns: int | None = None,
    provider_b_freshness_ns: int | None = None,
) -> ProviderDivergenceAssessmentV1:
    reason_codes: list[str] = []
    status = ProviderDivergenceStatus.UNKNOWN
    absolute_diff: float | None = None
    relative_bps: float | None = None
    freshness_diff: int | None = None

    if provider_a_value is None or provider_b_value is None:
        reason_codes.append("MISSING_VALUE")
    else:
        absolute_diff = abs(provider_a_value - provider_b_value)
        if provider_a_value != 0:
            relative_bps = (absolute_diff / abs(provider_a_value)) * 10_000
        elif provider_b_value != 0:
            relative_bps = (absolute_diff / abs(provider_b_value)) * 10_000
        else:
            relative_bps = 0.0

        if relative_bps is not None:
            if relative_bps >= policy.divergence_critical_bps:
                status = ProviderDivergenceStatus.CRITICAL
                reason_codes.append("DIVERGENCE_CRITICAL")
            elif relative_bps >= policy.divergence_warning_bps:
                status = ProviderDivergenceStatus.WARNING
                reason_codes.append("DIVERGENCE_WARNING")
            else:
                status = ProviderDivergenceStatus.NORMAL

    if provider_a_event_time_ns is not None and provider_b_event_time_ns is not None:
        if provider_a_event_time_ns != provider_b_event_time_ns:
            reason_codes.append("CLOCK_MISMATCH")
            if status == ProviderDivergenceStatus.NORMAL:
                status = ProviderDivergenceStatus.WARNING

    if provider_a_freshness_ns is not None and provider_b_freshness_ns is not None:
        freshness_diff = abs(provider_a_freshness_ns - provider_b_freshness_ns)
        if freshness_diff > policy.maximum_freshness_ns:
            reason_codes.append("FRESHNESS_MISMATCH")
            if status == ProviderDivergenceStatus.NORMAL:
                status = ProviderDivergenceStatus.WARNING

    assessment = ProviderDivergenceAssessmentV1(
        assessment_id="",
        schema_version=SUPERVISED_PILOT_SCHEMA_VERSION,
        as_of_ns=as_of_ns,
        instrument=instrument,
        capability=policy.capability,
        provider_a=provider_a,
        provider_b=provider_b,
        provider_a_value=provider_a_value,
        provider_b_value=provider_b_value,
        provider_a_event_time_ns=provider_a_event_time_ns,
        provider_b_event_time_ns=provider_b_event_time_ns,
        absolute_difference=absolute_diff,
        relative_difference_bps=relative_bps,
        freshness_difference_ns=freshness_diff,
        status=status.value,
        reason_codes=tuple(reason_codes),
        policy_ref=policy.provider_redundancy_policy_id,
    )
    object.__setattr__(assessment, "assessment_id", derive_provider_divergence_id(assessment))
    return assessment


def critical_divergence_blocks_opportunity(assessment: ProviderDivergenceAssessmentV1) -> bool:
    return assessment.status == ProviderDivergenceStatus.CRITICAL.value
