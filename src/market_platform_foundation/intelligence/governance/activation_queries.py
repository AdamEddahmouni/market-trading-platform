"""Runtime activation queries (BUILD 23)."""

from __future__ import annotations

from ..promotion.types import ChampionScopeV1
from .types import ActivationStatus, RuntimeActivationV1


def _scope_matches(
    scope: ChampionScopeV1,
    *,
    component: str,
    target_kind: str,
    horizon_ns: int,
    mode: str,
    scenario_id: str | None = None,
) -> bool:
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


def get_current_runtime_activation(
    activations: tuple[RuntimeActivationV1, ...],
    *,
    component: str,
    target_kind: str,
    horizon_ns: int,
    mode: str,
    as_of_ns: int,
    scenario_id: str | None = None,
) -> RuntimeActivationV1 | None:
    eligible = [
        activation
        for activation in activations
        if _scope_matches(
            activation.champion_scope,
            component=component,
            target_kind=target_kind,
            horizon_ns=horizon_ns,
            mode=mode,
            scenario_id=scenario_id,
        )
        and activation.status == ActivationStatus.ACTIVE
        and activation.effective_from_ns <= as_of_ns
        and (activation.effective_until_ns is None or as_of_ns < activation.effective_until_ns)
    ]
    if not eligible:
        return None
    eligible.sort(key=lambda item: (item.effective_from_ns, item.activation_id))
    return eligible[-1]
