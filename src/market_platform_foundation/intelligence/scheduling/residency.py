"""Residency and adapter planning for BUILD 10."""

from __future__ import annotations

from .models import AdapterAction, ResidencyAction, ResidencyPlan
from .profiles import InferenceExecutionProfile
from .resources import ResourceSnapshot


def plan_residency(
    profile: InferenceExecutionProfile,
    resources: ResourceSnapshot,
) -> ResidencyPlan:
    current_residency = resources.current_residency_key
    current_adapter = resources.current_adapter_key

    if current_residency == profile.residency_key:
        if profile.adapter_key is None:
            return ResidencyPlan(
                ResidencyAction.KEEP_CURRENT,
                profile.residency_key,
                AdapterAction.NO_SPECIAL_ACTION,
                None,
            )
        if current_adapter == profile.adapter_key:
            return ResidencyPlan(
                ResidencyAction.KEEP_CURRENT,
                profile.residency_key,
                AdapterAction.KEEP_CURRENT,
                profile.adapter_key,
            )
        return ResidencyPlan(
            ResidencyAction.KEEP_CURRENT,
            profile.residency_key,
            AdapterAction.SWITCH_ADAPTER,
            profile.adapter_key,
        )

    return ResidencyPlan(
        ResidencyAction.LOAD_RESIDENCY,
        profile.residency_key,
        AdapterAction.SWITCH_ADAPTER if profile.adapter_key else AdapterAction.NO_SPECIAL_ACTION,
        profile.adapter_key,
    )


def residency_affinity_rank(
    profile: InferenceExecutionProfile,
    resources: ResourceSnapshot,
) -> int:
    """Lower rank means better affinity — used only as tie-breaker."""
    if resources.current_residency_key == profile.residency_key:
        if profile.adapter_key is None or resources.current_adapter_key == profile.adapter_key:
            return 0
        return 1
    return 2


__all__ = ["plan_residency", "residency_affinity_rank"]
