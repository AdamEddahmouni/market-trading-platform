"""Execution profiles and domain mapping for BUILD 10 scheduling."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping

from ...canonical import canonical_bytes, sha256_bytes
from ..contracts import ExpertDomain

ONE_SECOND_NS = 1_000_000_000


class ResourceClass(StrEnum):
    CPU = "CPU"
    GPU = "GPU"


@dataclass(frozen=True, slots=True)
class InferenceExecutionProfile:
    """Scheduler-facing specialist runtime requirements — not a governed model registry."""

    profile_id: str
    expert_domain: ExpertDomain
    resource_class: ResourceClass
    min_vram_bytes: int
    cpu_slots: int
    max_concurrency: int
    batch_key: str
    max_batch_size: int
    residency_key: str
    adapter_key: str | None
    estimated_duration_ns: int
    version: str = "1"

    def __post_init__(self) -> None:
        if not self.profile_id:
            raise ValueError("EXECUTION_PROFILE_ID_REQUIRED")
        if not isinstance(self.expert_domain, ExpertDomain):
            object.__setattr__(self, "expert_domain", ExpertDomain(str(self.expert_domain)))
        if not isinstance(self.resource_class, ResourceClass):
            object.__setattr__(self, "resource_class", ResourceClass(str(self.resource_class)))
        if self.min_vram_bytes < 0:
            raise ValueError("EXECUTION_PROFILE_VRAM_INVALID")
        if self.cpu_slots < 0:
            raise ValueError("EXECUTION_PROFILE_CPU_SLOTS_INVALID")
        if self.max_concurrency < 1:
            raise ValueError("EXECUTION_PROFILE_CONCURRENCY_INVALID")
        if self.max_batch_size < 1:
            raise ValueError("EXECUTION_PROFILE_BATCH_SIZE_INVALID")
        if not self.batch_key or not self.residency_key:
            raise ValueError("EXECUTION_PROFILE_KEYS_REQUIRED")
        if self.estimated_duration_ns <= 0:
            raise ValueError("EXECUTION_PROFILE_DURATION_INVALID")

    @property
    def identity(self) -> str:
        payload = {
            "profile_id": self.profile_id,
            "version": self.version,
            "expert_domain": self.expert_domain.value,
            "resource_class": self.resource_class.value,
            "min_vram_bytes": self.min_vram_bytes,
            "cpu_slots": self.cpu_slots,
            "max_concurrency": self.max_concurrency,
            "batch_key": self.batch_key,
            "max_batch_size": self.max_batch_size,
            "residency_key": self.residency_key,
            "adapter_key": self.adapter_key,
            "estimated_duration_ns": self.estimated_duration_ns,
        }
        return f"EXPROF-{sha256_bytes(canonical_bytes(payload))}"


_DEFAULT_PROFILES: dict[ExpertDomain, InferenceExecutionProfile] = {
    ExpertDomain.MICROSTRUCTURE: InferenceExecutionProfile(
        profile_id="microstructure-gpu-v1",
        expert_domain=ExpertDomain.MICROSTRUCTURE,
        resource_class=ResourceClass.GPU,
        min_vram_bytes=8 * 1024**3,
        cpu_slots=1,
        max_concurrency=1,
        batch_key="microstructure-batch",
        max_batch_size=2,
        residency_key="base-llm-micro",
        adapter_key="microstructure-adapter",
        estimated_duration_ns=2 * ONE_SECOND_NS,
    ),
    ExpertDomain.DERIVATIVES: InferenceExecutionProfile(
        profile_id="derivatives-gpu-v1",
        expert_domain=ExpertDomain.DERIVATIVES,
        resource_class=ResourceClass.GPU,
        min_vram_bytes=8 * 1024**3,
        cpu_slots=1,
        max_concurrency=1,
        batch_key="derivatives-batch",
        max_batch_size=2,
        residency_key="base-llm-deriv",
        adapter_key="derivatives-adapter",
        estimated_duration_ns=3 * ONE_SECOND_NS,
    ),
    ExpertDomain.POSITIONING_BORROW: InferenceExecutionProfile(
        profile_id="positioning-cpu-v1",
        expert_domain=ExpertDomain.POSITIONING_BORROW,
        resource_class=ResourceClass.CPU,
        min_vram_bytes=0,
        cpu_slots=1,
        max_concurrency=2,
        batch_key="positioning-batch",
        max_batch_size=4,
        residency_key="positioning-cpu",
        adapter_key=None,
        estimated_duration_ns=5 * ONE_SECOND_NS,
    ),
    ExpertDomain.NARRATIVE_SENTIMENT: InferenceExecutionProfile(
        profile_id="narrative-gpu-v1",
        expert_domain=ExpertDomain.NARRATIVE_SENTIMENT,
        resource_class=ResourceClass.GPU,
        min_vram_bytes=6 * 1024**3,
        cpu_slots=1,
        max_concurrency=1,
        batch_key="narrative-batch",
        max_batch_size=2,
        residency_key="base-llm-narrative",
        adapter_key="narrative-adapter",
        estimated_duration_ns=4 * ONE_SECOND_NS,
    ),
    ExpertDomain.REGIME_CROSS_ASSET: InferenceExecutionProfile(
        profile_id="regime-cpu-v1",
        expert_domain=ExpertDomain.REGIME_CROSS_ASSET,
        resource_class=ResourceClass.CPU,
        min_vram_bytes=0,
        cpu_slots=1,
        max_concurrency=2,
        batch_key="regime-batch",
        max_batch_size=4,
        residency_key="regime-cpu",
        adapter_key=None,
        estimated_duration_ns=3 * ONE_SECOND_NS,
    ),
}


@dataclass(frozen=True, slots=True)
class ExecutionProfileRegistry:
    """Deterministic expert-domain to execution-profile mapping."""

    profiles: Mapping[ExpertDomain, InferenceExecutionProfile] = MappingProxyType(_DEFAULT_PROFILES)

    def __post_init__(self) -> None:
        object.__setattr__(self, "profiles", MappingProxyType(dict(self.profiles)))

    def profile_for(self, expert_domain: ExpertDomain) -> InferenceExecutionProfile | None:
        return self.profiles.get(expert_domain)

    def supported_resource_classes(self) -> frozenset[ResourceClass]:
        return frozenset({profile.resource_class for profile in self.profiles.values()})


DEFAULT_EXECUTION_PROFILE_REGISTRY = ExecutionProfileRegistry()


__all__ = [
    "DEFAULT_EXECUTION_PROFILE_REGISTRY",
    "ExecutionProfileRegistry",
    "InferenceExecutionProfile",
    "ResourceClass",
]
