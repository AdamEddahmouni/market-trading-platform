"""Dependence grouping for BUILD 14 fusion."""

from __future__ import annotations

from dataclasses import dataclass

from .identity import derive_dependence_group_id
from .manifest import ForecastFusionManifest
from .provenance import ForecastProvenanceResolver
from .types import DependenceState, ForecastDependenceGroup, FusionContributorRef


@dataclass(frozen=True, slots=True)
class DependenceGroupingResult:
    groups: tuple[ForecastDependenceGroup, ...]
    dependence_state: DependenceState
    forecast_to_group: dict[str, str]


class DependenceGrouper:
    def __init__(self, resolver: ForecastProvenanceResolver) -> None:
        self._resolver = resolver

    def group(self, manifest: ForecastFusionManifest, eligible: tuple[FusionContributorRef, ...]) -> DependenceGroupingResult:
        if not eligible:
            return DependenceGroupingResult(groups=(), dependence_state=DependenceState.RESOLVED, forecast_to_group={})

        forecast_ids = [ref.forecast.forecast_id for ref in eligible]
        family_by_id = {ref.forecast.forecast_id: ref.forecast_family_key for ref in eligible}
        lineage_by_id = {
            ref.forecast.forecast_id: self._resolver.resolve_terminal_source_ids(ref.forecast)
            for ref in eligible
        }

        parent: dict[str, str] = {forecast_id: forecast_id for forecast_id in forecast_ids}

        def find(node: str) -> str:
            while parent[node] != node:
                parent[node] = parent[parent[node]]
                node = parent[node]
            return node

        def union(left: str, right: str) -> None:
            root_left = find(left)
            root_right = find(right)
            if root_left != root_right:
                parent[root_right] = root_left

        for index, left_id in enumerate(forecast_ids):
            left_family = family_by_id[left_id]
            left_lineage = lineage_by_id[left_id]
            for right_id in forecast_ids[index + 1 :]:
                right_family = family_by_id[right_id]
                right_lineage = lineage_by_id[right_id]
                if left_family is not None and left_family == right_family:
                    union(left_id, right_id)
                    continue
                if left_lineage and right_lineage and left_lineage & right_lineage:
                    union(left_id, right_id)

        components: dict[str, list[str]] = {}
        for forecast_id in forecast_ids:
            root = find(forecast_id)
            components.setdefault(root, []).append(forecast_id)

        groups: list[ForecastDependenceGroup] = []
        forecast_to_group: dict[str, str] = {}
        for member_ids in components.values():
            sorted_ids = tuple(sorted(member_ids))
            group_id = derive_dependence_group_id(
                forecast_ids=sorted_ids,
                fusion_policy_identity=manifest.fusion_policy.policy_identity,
            )
            groups.append(ForecastDependenceGroup(group_id=group_id, forecast_ids=sorted_ids))
            for forecast_id in sorted_ids:
                forecast_to_group[forecast_id] = group_id

        groups.sort(key=lambda group: group.group_id)
        return DependenceGroupingResult(
            groups=tuple(groups),
            dependence_state=DependenceState.RESOLVED,
            forecast_to_group=forecast_to_group,
        )


__all__ = ["DependenceGrouper", "DependenceGroupingResult"]
