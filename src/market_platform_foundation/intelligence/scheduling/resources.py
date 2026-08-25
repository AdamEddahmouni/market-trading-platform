"""Injected resource state for BUILD 10 admission."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .profiles import ResourceClass


@dataclass(frozen=True, slots=True)
class ResourceSnapshot:
    """Logical scheduling resource state — not hardware allocation."""

    captured_at_ns: int
    cpu_slots_total: int
    cpu_slots_available: int
    gpu_slots_total: int
    gpu_slots_available: int
    vram_bytes_total: int
    vram_bytes_available: int
    current_residency_key: str | None = None
    current_adapter_key: str | None = None
    active_job_count: int = 0
    supported_resource_classes: frozenset[ResourceClass] = frozenset({ResourceClass.CPU, ResourceClass.GPU})

    def __post_init__(self) -> None:
        if self.captured_at_ns < 0:
            raise ValueError("RESOURCE_CAPTURED_AT_INVALID")
        for field_name in (
            "cpu_slots_total",
            "cpu_slots_available",
            "gpu_slots_total",
            "gpu_slots_available",
            "vram_bytes_total",
            "vram_bytes_available",
            "active_job_count",
        ):
            value = getattr(self, field_name)
            if value < 0:
                raise ValueError(f"RESOURCE_{field_name.upper()}_INVALID")
        if self.cpu_slots_available > self.cpu_slots_total:
            raise ValueError("RESOURCE_CPU_AVAILABLE_EXCEEDS_TOTAL")
        if self.gpu_slots_available > self.gpu_slots_total:
            raise ValueError("RESOURCE_GPU_AVAILABLE_EXCEEDS_TOTAL")
        if self.vram_bytes_available > self.vram_bytes_total:
            raise ValueError("RESOURCE_VRAM_AVAILABLE_EXCEEDS_TOTAL")


@runtime_checkable
class ResourceProvider(Protocol):
    """Boundary for injecting current resource snapshots."""

    def snapshot(self, *, now_ns: int) -> ResourceSnapshot: ...


class StaticResourceProvider:
    """Fixed resource snapshot for deterministic tests."""

    def __init__(self, snapshot: ResourceSnapshot) -> None:
        self._snapshot = snapshot

    def snapshot(self, *, now_ns: int) -> ResourceSnapshot:
        _ = now_ns
        return self._snapshot


class ConfiguredResourceProvider:
    """Callable-backed provider for replay timelines."""

    def __init__(self, resolver: object) -> None:
        self._resolver = resolver

    def snapshot(self, *, now_ns: int) -> ResourceSnapshot:
        return self._resolver(now_ns)  # type: ignore[no-any-return]


def default_resource_snapshot(*, now_ns: int) -> ResourceSnapshot:
    """Generous synthetic cloud-safe defaults — no physical GPU required."""
    return ResourceSnapshot(
        captured_at_ns=now_ns,
        cpu_slots_total=8,
        cpu_slots_available=8,
        gpu_slots_total=1,
        gpu_slots_available=1,
        vram_bytes_total=16 * 1024**3,
        vram_bytes_available=16 * 1024**3,
    )


__all__ = [
    "ConfiguredResourceProvider",
    "ResourceProvider",
    "ResourceSnapshot",
    "StaticResourceProvider",
    "default_resource_snapshot",
]
