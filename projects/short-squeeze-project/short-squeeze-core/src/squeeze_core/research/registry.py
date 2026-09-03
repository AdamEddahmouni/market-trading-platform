from collections.abc import Sequence

from .models import (
    CandidateCaseRegistry,
    CandidateCaseRegistryEntry,
    OrderingPolicy,
)


class ResearchRegistryError(ValueError):
    def __init__(self, code: str, values: Sequence[str]):
        self.code = code
        self.values = tuple(values)
        super().__init__(code, self.values)


def build_case_registry(
    registry_version: str,
    entries: Sequence[CandidateCaseRegistryEntry],
) -> CandidateCaseRegistry:
    return CandidateCaseRegistry(
        registry_version=registry_version,
        entries=tuple(entries),
    )


def resolve_registry_cases(
    registry: CandidateCaseRegistry,
    case_ids: Sequence[str],
    ordering_policy: OrderingPolicy,
) -> tuple[CandidateCaseRegistryEntry, ...]:
    normalized = tuple(item.strip() for item in case_ids)
    if len(set(normalized)) != len(normalized):
        raise ResearchRegistryError("RESEARCH_CASE_DUPLICATE", normalized)
    by_id = {item.case_id: item for item in registry.entries}
    unknown = tuple(item for item in normalized if item not in by_id)
    if unknown:
        raise ResearchRegistryError("RESEARCH_CASE_UNKNOWN", unknown)
    ordered = normalized
    if ordering_policy is OrderingPolicy.CANONICAL_CASE_ID:
        ordered = tuple(sorted(normalized))
    return tuple(by_id[item] for item in ordered)


__all__ = ["ResearchRegistryError", "build_case_registry", "resolve_registry_cases"]
