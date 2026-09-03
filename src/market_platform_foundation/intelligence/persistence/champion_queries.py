"""Champion assignment query helpers (BUILD 20)."""

from __future__ import annotations

from ..promotion.types import ChampionAssignmentStatus, ChampionAssignmentV1


def scope_matches(
    assignment: ChampionAssignmentV1,
    *,
    component: str,
    target_kind: str,
    horizon_ns: int,
    mode: str,
    scenario_id: str | None = None,
) -> bool:
    scope = assignment.champion_scope
    if scope.component != component:
        return False
    if scope.target_kind != target_kind:
        return False
    if scope.horizon_ns != horizon_ns:
        return False
    if scope.mode != mode:
        return False
    if scenario_id is not None and scope.scenario_id != scenario_id:
        return False
    return True


def get_current_champion_assignment(
    assignments: tuple[ChampionAssignmentV1, ...],
    *,
    component: str,
    target_kind: str,
    horizon_ns: int,
    mode: str,
    as_of_ns: int,
    scenario_id: str | None = None,
) -> ChampionAssignmentV1 | None:
    candidates = [
        assignment
        for assignment in assignments
        if scope_matches(
            assignment,
            component=component,
            target_kind=target_kind,
            horizon_ns=horizon_ns,
            mode=mode,
            scenario_id=scenario_id,
        )
        and assignment.effective_from_ns <= as_of_ns
        and assignment.status == ChampionAssignmentStatus.ACTIVE
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.effective_from_ns)


__all__ = ["get_current_champion_assignment", "scope_matches"]
