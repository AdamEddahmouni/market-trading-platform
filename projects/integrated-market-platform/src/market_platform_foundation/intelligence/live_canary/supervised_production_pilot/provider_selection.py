"""Deterministic provider selection with hysteresis (BUILD 33)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .identity import derive_provider_selection_decision_id
from .types import (
    ProviderCandidateHealthV1,
    ProviderHealthState,
    ProviderRedundancyPolicyV1,
    ProviderSelectionDecisionV1,
    ProviderSelectionReason,
    SUPERVISED_PILOT_IMPLEMENTATION_VERSION,
    SUPERVISED_PILOT_SCHEMA_VERSION,
)

_HEALTH_RANK = {
    ProviderHealthState.HEALTHY.value: 3,
    ProviderHealthState.DEGRADED.value: 2,
    ProviderHealthState.STALE.value: 1,
    ProviderHealthState.UNHEALTHY.value: 0,
    ProviderHealthState.UNKNOWN.value: 0,
}


def _health_satisfies(actual: str, minimum: str) -> bool:
    return _HEALTH_RANK.get(actual, 0) >= _HEALTH_RANK.get(minimum, 0)


def _freshness_ok(freshness_ns: int | None, maximum_freshness_ns: int) -> bool:
    if freshness_ns is None:
        return False
    return freshness_ns <= maximum_freshness_ns


def _candidate_eligible(
    candidate: ProviderCandidateHealthV1,
    *,
    minimum_health: str,
    maximum_freshness_ns: int,
) -> bool:
    return _health_satisfies(candidate.health, minimum_health) and _freshness_ok(
        candidate.freshness_ns, maximum_freshness_ns
    )


def _sort_candidates(candidates: tuple[ProviderCandidateHealthV1, ...]) -> tuple[ProviderCandidateHealthV1, ...]:
    """Deterministic ordering independent of input iteration order."""
    return tuple(sorted(candidates, key=lambda c: (c.provider, c.health)))


@dataclass
class ProviderSelectionTracker:
    """Mutable runtime tracker for hysteresis; decisions are recorded immutably."""

    current_provider: str | None = None
    primary_unhealthy_since_ns: int | None = None
    primary_healthy_since_ns: int | None = None
    last_switch_ns: int | None = None
    decisions: list[ProviderSelectionDecisionV1] = field(default_factory=list)

    def select_provider(
        self,
        *,
        policy: ProviderRedundancyPolicyV1,
        candidates: tuple[ProviderCandidateHealthV1, ...],
        decision_time_ns: int,
        scope: str = "live_intelligence_path",
    ) -> ProviderSelectionDecisionV1:
        sorted_candidates = _sort_candidates(candidates)
        primary = next((c for c in sorted_candidates if c.provider == policy.primary_provider), None)
        fallbacks = tuple(c for c in sorted_candidates if c.provider in policy.fallback_providers)
        previous = self.current_provider
        reason = ProviderSelectionReason.PRIMARY_HEALTHY
        selected: str | None = None
        switch_state = "STABLE"

        primary_eligible = primary is not None and _candidate_eligible(
            primary,
            minimum_health=policy.minimum_primary_health,
            maximum_freshness_ns=policy.maximum_freshness_ns,
        )

        if primary_eligible:
            self.primary_unhealthy_since_ns = None
            if self.primary_healthy_since_ns is None:
                self.primary_healthy_since_ns = decision_time_ns
            if (
                self.current_provider is not None
                and self.current_provider != policy.primary_provider
                and self.primary_healthy_since_ns is not None
                and decision_time_ns - self.primary_healthy_since_ns
                >= policy.minimum_recovery_duration_ns
                and (
                    self.last_switch_ns is None
                    or decision_time_ns - self.last_switch_ns >= policy.switch_cooldown_ns
                )
            ):
                selected = policy.primary_provider
                reason = ProviderSelectionReason.PRIMARY_RECOVERED
                switch_state = "SWITCH_BACK"
                self.last_switch_ns = decision_time_ns
                self.primary_healthy_since_ns = decision_time_ns
            elif self.current_provider == policy.primary_provider or self.current_provider is None:
                selected = policy.primary_provider
                reason = ProviderSelectionReason.PRIMARY_HEALTHY
            else:
                if (
                    self.last_switch_ns is not None
                    and decision_time_ns - self.last_switch_ns < policy.switch_cooldown_ns
                ):
                    selected = self.current_provider
                    reason = ProviderSelectionReason.COOLDOWN_ACTIVE
                else:
                    selected = self.current_provider
        else:
            self.primary_healthy_since_ns = None
            if self.primary_unhealthy_since_ns is None:
                self.primary_unhealthy_since_ns = decision_time_ns

            failure_duration = decision_time_ns - (self.primary_unhealthy_since_ns or decision_time_ns)
            if failure_duration < policy.minimum_failure_duration_ns:
                if self.current_provider == policy.primary_provider:
                    selected = policy.primary_provider
                    reason = ProviderSelectionReason.PRIMARY_HEALTHY
                elif self.current_provider is not None:
                    selected = self.current_provider
                    reason = ProviderSelectionReason.COOLDOWN_ACTIVE
                else:
                    selected = None
                    reason = ProviderSelectionReason.NO_CANDIDATE
            elif (
                self.last_switch_ns is not None
                and decision_time_ns - self.last_switch_ns < policy.switch_cooldown_ns
                and self.current_provider is not None
            ):
                selected = self.current_provider
                reason = ProviderSelectionReason.COOLDOWN_ACTIVE
            else:
                eligible_fallbacks = tuple(
                    c
                    for c in _sort_candidates(fallbacks)
                    if _candidate_eligible(
                        c,
                        minimum_health=policy.minimum_fallback_health,
                        maximum_freshness_ns=policy.maximum_freshness_ns,
                    )
                )
                if eligible_fallbacks:
                    selected = eligible_fallbacks[0].provider
                    reason = (
                        ProviderSelectionReason.PRIMARY_FAILURE_THRESHOLD_MET
                        if self.current_provider == policy.primary_provider
                        else ProviderSelectionReason.FALLBACK_SELECTED
                    )
                    if selected != self.current_provider:
                        switch_state = "FAILOVER"
                        self.last_switch_ns = decision_time_ns
                elif fallbacks and not any(
                    _freshness_ok(c.freshness_ns, policy.maximum_freshness_ns) for c in fallbacks
                ):
                    selected = None
                    reason = ProviderSelectionReason.FALLBACK_STALE
                else:
                    selected = None
                    reason = ProviderSelectionReason.BOTH_UNHEALTHY

        self.current_provider = selected
        decision = ProviderSelectionDecisionV1(
            provider_selection_decision_id="",
            schema_version=SUPERVISED_PILOT_SCHEMA_VERSION,
            decision_time_ns=decision_time_ns,
            scope=scope,
            capability=policy.capability,
            primary_provider=policy.primary_provider,
            available_candidates=sorted_candidates,
            selected_provider=selected,
            decision_reason=reason.value,
            previous_provider=previous,
            switch_state=switch_state,
            policy_ref=policy.provider_redundancy_policy_id,
        )
        object.__setattr__(
            decision,
            "provider_selection_decision_id",
            derive_provider_selection_decision_id(decision),
        )
        self.decisions.append(decision)
        return decision


def pit_safe_candidate(
    candidate: ProviderCandidateHealthV1,
    *,
    decision_time_ns: int,
) -> bool:
    """Verify point-in-time semantics: available_time <= decision_time."""
    if candidate.last_available_time_ns is None:
        return False
    return candidate.last_available_time_ns <= decision_time_ns
