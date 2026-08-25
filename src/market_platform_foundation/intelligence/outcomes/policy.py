"""Versioned outcome settlement policies (BUILD 15)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes

OUTCOME_SETTLEMENT_POLICY_ID_VERSION = "outcome-settlement-policy-sha256-v1"
DIRECTION_TARGET_V1 = "direction_up_down_v1"
P6_COMPAT_TARGET_V1 = "p6_direction_up_down_v1"

_NS = 1_000_000_000


@dataclass(frozen=True, slots=True)
class OutcomeSettlementPolicy:
    """Immutable semantic settlement rules for one target family."""

    policy_version: str
    target_kind: str
    observation_kinds: tuple[str, ...]
    target_window_tolerance_ns: int
    late_arrival_grace_ns: int
    zero_return_exact: bool = True
    require_same_observation_kind: bool = True
    fallback_observation_kinds: tuple[str, ...] = ()
    supported_horizons_ns: tuple[int, ...] | None = None
    policy_id: str = ""

    def __post_init__(self) -> None:
        if not self.policy_version:
            raise ValueError("POLICY_VERSION_REQUIRED")
        if not self.target_kind:
            raise ValueError("TARGET_KIND_REQUIRED")
        if not self.observation_kinds:
            raise ValueError("OBSERVATION_KINDS_REQUIRED")
        if self.target_window_tolerance_ns < 0:
            raise ValueError("TARGET_WINDOW_TOLERANCE_INVALID")
        if self.late_arrival_grace_ns < 0:
            raise ValueError("LATE_ARRIVAL_GRACE_INVALID")
        if not self.policy_id:
            object.__setattr__(self, "policy_id", derive_settlement_policy_identity(self))

    def body(self) -> dict[str, Any]:
        return {
            "identity_version": OUTCOME_SETTLEMENT_POLICY_ID_VERSION,
            "policy_version": self.policy_version,
            "target_kind": self.target_kind,
            "observation_kinds": list(self.observation_kinds),
            "fallback_observation_kinds": list(self.fallback_observation_kinds),
            "target_window_tolerance_ns": self.target_window_tolerance_ns,
            "late_arrival_grace_ns": self.late_arrival_grace_ns,
            "zero_return_exact": self.zero_return_exact,
            "require_same_observation_kind": self.require_same_observation_kind,
            "supported_horizons_ns": list(self.supported_horizons_ns or ()),
        }

    def observation_source_policy(self) -> dict[str, Any]:
        return {
            "primary_kinds": list(self.observation_kinds),
            "fallback_kinds": list(self.fallback_observation_kinds),
            "require_same_kind": self.require_same_observation_kind,
        }

    def supports_horizon(self, horizon_ns: int) -> bool:
        if self.supported_horizons_ns is None:
            return horizon_ns > 0
        return horizon_ns in self.supported_horizons_ns

    def target_window(self, *, target_time_ns: int) -> tuple[int, int]:
        start = target_time_ns
        end = target_time_ns + self.target_window_tolerance_ns
        return start, end

    def availability_cutoff(self, *, target_window_end_ns: int) -> int:
        return target_window_end_ns + self.late_arrival_grace_ns


def derive_settlement_policy_identity(policy: OutcomeSettlementPolicy) -> str:
    payload = policy.body()
    return f"OSPOL-{sha256_bytes(canonical_bytes(payload))}"


DIRECTION_UP_DOWN_5M_POLICY = OutcomeSettlementPolicy(
    policy_version=DIRECTION_TARGET_V1,
    target_kind="direction_up_down",
    observation_kinds=("TRADE",),
    target_window_tolerance_ns=60 * _NS,
    late_arrival_grace_ns=0,
)

P6_DIRECTION_POLICY = OutcomeSettlementPolicy(
    policy_version=P6_COMPAT_TARGET_V1,
    target_kind="direction_up_down",
    observation_kinds=("TRADE", "TICK"),
    target_window_tolerance_ns=300 * _NS,
    late_arrival_grace_ns=0,
    supported_horizons_ns=(1800 * _NS,),
)


def policy_for_forecast(*, target_kind: str, horizon_ns: int) -> OutcomeSettlementPolicy | None:
    if target_kind != "direction_up_down":
        return None
    if horizon_ns == 1800 * _NS:
        return P6_DIRECTION_POLICY
    return DIRECTION_UP_DOWN_5M_POLICY


__all__ = [
    "DIRECTION_TARGET_V1",
    "DIRECTION_UP_DOWN_5M_POLICY",
    "OUTCOME_SETTLEMENT_POLICY_ID_VERSION",
    "P6_COMPAT_TARGET_V1",
    "P6_DIRECTION_POLICY",
    "OutcomeSettlementPolicy",
    "derive_settlement_policy_identity",
    "policy_for_forecast",
]
