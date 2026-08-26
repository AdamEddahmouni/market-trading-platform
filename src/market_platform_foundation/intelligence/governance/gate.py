"""Runtime governance gate for BUILD 21/22 integration."""

from __future__ import annotations

from .types import FailSafeDecisionKind, RuntimeGovernanceState, RuntimeActivationV1


def resolve_governance_state(
    *,
    activation: RuntimeActivationV1 | None,
    fail_safe_decision,
    latest_champion_assignment_id: str | None = None,
) -> RuntimeGovernanceState:
    if activation is None:
        return RuntimeGovernanceState(
            activation=None,
            fail_safe_decision=fail_safe_decision,
            opportunities_allowed=False,
            paper_execution_allowed=False,
            scope_disabled=True,
            latest_champion_assignment_id=latest_champion_assignment_id,
        )

    decision = fail_safe_decision.decision if fail_safe_decision is not None else FailSafeDecisionKind.ALLOW
    scope_disabled = decision in {
        FailSafeDecisionKind.DISABLE_SCOPE,
        FailSafeDecisionKind.FAIL_CLOSED,
    }
    opportunities_allowed = decision in {
        FailSafeDecisionKind.ALLOW,
        FailSafeDecisionKind.DEGRADE,
    }
    paper_execution_allowed = decision in {
        FailSafeDecisionKind.ALLOW,
        FailSafeDecisionKind.DEGRADE,
        FailSafeDecisionKind.DISABLE_NEW_OPPORTUNITIES,
    }

    active_fallback = (
        latest_champion_assignment_id is not None
        and activation.champion_assignment_id != latest_champion_assignment_id
    )

    return RuntimeGovernanceState(
        activation=activation,
        fail_safe_decision=fail_safe_decision,
        opportunities_allowed=opportunities_allowed and not scope_disabled,
        paper_execution_allowed=paper_execution_allowed and not scope_disabled,
        scope_disabled=scope_disabled,
        active_fallback_divergence=active_fallback,
        latest_champion_assignment_id=latest_champion_assignment_id,
    )


def opportunities_permitted(state: RuntimeGovernanceState | None) -> bool:
    if state is None:
        return True
    return state.opportunities_allowed


def paper_execution_permitted(state: RuntimeGovernanceState | None) -> bool:
    if state is None:
        return True
    return state.paper_execution_allowed
