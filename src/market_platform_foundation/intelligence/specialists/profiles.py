"""BUILD 11 microstructure execution profile registration."""

from __future__ import annotations

from ..scheduling.profiles import DEFAULT_EXECUTION_PROFILE_REGISTRY, ExecutionProfileRegistry
from ..scheduling.profiles import InferenceExecutionProfile, ResourceClass
from ..contracts import ExpertDomain

MICROSTRUCTURE_CPU_PROFILE = DEFAULT_EXECUTION_PROFILE_REGISTRY.profile_for(ExpertDomain.MICROSTRUCTURE)
assert MICROSTRUCTURE_CPU_PROFILE is not None
assert MICROSTRUCTURE_CPU_PROFILE.resource_class == ResourceClass.CPU


def build_11_execution_profile_registry() -> ExecutionProfileRegistry:
    return DEFAULT_EXECUTION_PROFILE_REGISTRY


BUILD_11_EXECUTION_PROFILE_REGISTRY = DEFAULT_EXECUTION_PROFILE_REGISTRY


__all__ = [
    "BUILD_11_EXECUTION_PROFILE_REGISTRY",
    "MICROSTRUCTURE_CPU_PROFILE",
    "build_11_execution_profile_registry",
]
