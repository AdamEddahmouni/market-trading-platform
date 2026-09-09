"""Local IBKR subscription pacing / caps (G6).

Exact provider subscription limits depend on account entitlements and
market-data lines (IBKR documents a depth range of 3–60 active requests and a
50 msg/s rate ceiling), so IMP models a *configurable local cap* per
capability and rejects beyond it with an explicit reason. No provider-wide
production pacing guarantee is claimed; pacing-error codes are normalized in
:mod:`.errors` from the documented message-code reference.
"""

from __future__ import annotations

from dataclasses import dataclass

from .constants import IB_DEPTH_SUBSCRIPTION_FLOOR
from .contracts import CapabilityKind, PacingReport


@dataclass(frozen=True, slots=True)
class SubscriptionCapPolicy:
    max_l1: int = 50
    max_l2: int = 20
    max_trades: int = 20
    #: Minimum accepted depth request count (IBKR TWS floors at 3 rows).
    min_depth_levels: int = IB_DEPTH_SUBSCRIPTION_FLOOR
    #: Maximum accepted depth request count (local ceiling, default below the
    #: documented 60-request entitlement-dependent ceiling).
    max_depth_levels: int = 20

    def validate_depth_levels(self, depth_levels: int) -> tuple[bool, str | None]:
        if (
            not isinstance(depth_levels, int)
            or isinstance(depth_levels, bool)
            or depth_levels < self.min_depth_levels
        ):
            return (
                False,
                f"depth_levels must be at least {self.min_depth_levels} (IBKR floor)",
            )
        if depth_levels > self.max_depth_levels:
            return (
                False,
                f"depth_levels exceeds local ceiling {self.max_depth_levels}",
            )
        return True, None


class LocalPacingState:
    """Deterministic, clock-injected local subscription cap state."""

    def __init__(
        self,
        policy: SubscriptionCapPolicy | None = None,
        *,
        monotonic: object = None,
    ) -> None:
        self.policy = policy or SubscriptionCapPolicy()
        self._monotonic = monotonic
        self.rejected_reasons: list[str] = []
        self.cooldown_until_ns: int | None = None

    def _now(self) -> int | None:
        if self._monotonic is None:
            return None
        return int(self._monotonic())

    def can_subscribe(
        self,
        *,
        capability: CapabilityKind,
        active_l1: int,
        active_l2: int,
        active_trades: int = 0,
    ) -> tuple[bool, str | None]:
        if self.cooldown_until_ns is not None:
            now = self._now()
            if now is not None and now < self.cooldown_until_ns:
                return False, "COOLDOWN_ACTIVE"
            self.cooldown_until_ns = None
        if capability is CapabilityKind.L1:
            allowed = active_l1 < self.policy.max_l1
            reason = None if allowed else f"L1_CAP_REACHED ({active_l1}/{self.policy.max_l1})"
        elif capability is CapabilityKind.L2:
            allowed = active_l2 < self.policy.max_l2
            reason = None if allowed else f"L2_CAP_REACHED ({active_l2}/{self.policy.max_l2})"
        else:
            allowed = active_trades < self.policy.max_trades
            reason = (
                None
                if allowed
                else f"TRADES_CAP_REACHED ({active_trades}/{self.policy.max_trades})"
            )
        if reason is not None:
            self.rejected_reasons.append(reason)
        return allowed, reason

    def enter_cooldown(self, *, seconds: float, now_ns: int | None = None) -> None:
        """Enter a bounded cooldown (pacing error path); deterministic tests
        inject ``now_ns`` directly instead of sleeping."""
        if seconds <= 0:
            return
        base = now_ns if now_ns is not None else self._now()
        if base is None:
            return
        self.cooldown_until_ns = base + int(seconds * 1_000_000_000)

    def report(
        self,
        *,
        active_l1: int,
        active_l2: int,
        active_trades: int = 0,
    ) -> PacingReport:
        return PacingReport(
            active_l1=active_l1,
            active_l2=active_l2,
            active_trades=active_trades,
            configured_max_l1=self.policy.max_l1,
            configured_max_l2=self.policy.max_l2,
            configured_max_trades=self.policy.max_trades,
            rejected_reasons=tuple(self.rejected_reasons[-20:]),
            cooldown_until_ns=self.cooldown_until_ns,
        )


__all__ = ["LocalPacingState", "SubscriptionCapPolicy"]