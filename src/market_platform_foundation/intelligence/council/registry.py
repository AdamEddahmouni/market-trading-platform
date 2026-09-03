"""Production specialist registry for BUILD 12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..contracts import ExpertDomain
from ..specialists import MicrostructureSpecialist, Specialist


@runtime_checkable
class DeliberatingSpecialist(Protocol):
    expert_domain: ExpertDomain
    component_id: str
    component_version: str

    def deliberate(self, context) -> object: ...


@dataclass(frozen=True, slots=True)
class SpecialistRegistry:
    specialists: tuple[Specialist, ...]

    def __post_init__(self) -> None:
        seen: set[ExpertDomain] = set()
        for specialist in self.specialists:
            if specialist.expert_domain in seen:
                raise ValueError("SPECIALIST_REGISTRY_DUPLICATE_DOMAIN")
            seen.add(specialist.expert_domain)

    def get(self, domain: ExpertDomain) -> Specialist | None:
        for specialist in self.specialists:
            if specialist.expert_domain == domain:
                return specialist
        return None

    def domains(self) -> tuple[ExpertDomain, ...]:
        return tuple(sorted((specialist.expert_domain for specialist in self.specialists), key=lambda d: d.value))


DEFAULT_SPECIALIST_REGISTRY = SpecialistRegistry(specialists=(MicrostructureSpecialist(),))


__all__ = [
    "DEFAULT_SPECIALIST_REGISTRY",
    "DeliberatingSpecialist",
    "SpecialistRegistry",
]
