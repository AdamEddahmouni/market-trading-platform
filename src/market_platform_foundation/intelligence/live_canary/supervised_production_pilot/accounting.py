"""Cumulative pilot accounting — caps never reset (BUILD 33)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .types import LiveSupervisedPilotPolicyV1


@dataclass
class PilotAccounting:
    sessions_completed: int = 0
    orders_submitted: int = 0
    fills_received: int = 0
    submitted_notional_minor: int = 0
    filled_notional_minor: int = 0
    max_concurrent_exposure_minor: int = 0
    fees_minor: int = 0
    realized_pnl_minor: int = 0
    incidents: int = 0
    _counters_frozen: bool = False

    def record_session(self) -> None:
        self._assert_mutable()
        self.sessions_completed += 1

    def record_order(self, *, notional_minor: int) -> None:
        self._assert_mutable()
        self.orders_submitted += 1
        self.submitted_notional_minor += notional_minor

    def record_fill(self, *, notional_minor: int, fees_minor: int = 0) -> None:
        self._assert_mutable()
        self.fills_received += 1
        self.filled_notional_minor += notional_minor
        self.fees_minor += fees_minor

    def update_exposure(self, exposure_minor: int) -> None:
        self._assert_mutable()
        self.max_concurrent_exposure_minor = max(
            self.max_concurrent_exposure_minor, exposure_minor
        )

    def record_incident(self) -> None:
        self._assert_mutable()
        self.incidents += 1

    def freeze_counters(self) -> None:
        self._counters_frozen = True

    def _assert_mutable(self) -> None:
        if self._counters_frozen:
            raise RuntimeError("PILOT_COUNTERS_FROZEN")

    def pilot_cap_exceeded(self, policy: LiveSupervisedPilotPolicyV1) -> tuple[bool, str | None]:
        if self.sessions_completed >= policy.max_pilot_sessions:
            return True, "PILOT_SESSION_LIMIT"
        if self.orders_submitted >= policy.max_pilot_orders:
            return True, "PILOT_ORDER_LIMIT"
        if self.fills_received >= policy.max_pilot_fills:
            return True, "PILOT_FILL_LIMIT"
        if self.submitted_notional_minor >= policy.max_pilot_total_notional_minor:
            return True, "PILOT_NOTIONAL_LIMIT"
        if self.max_concurrent_exposure_minor >= policy.max_pilot_live_exposure_minor:
            return True, "PILOT_EXPOSURE_LIMIT"
        return False, None

    def order_notional_allowed(
        self,
        policy: LiveSupervisedPilotPolicyV1,
        *,
        order_notional_minor: int,
    ) -> tuple[bool, str | None]:
        exceeded, reason = self.pilot_cap_exceeded(policy)
        if exceeded:
            return False, reason
        if order_notional_minor > policy.max_pilot_single_order_notional_minor:
            return False, "PILOT_SINGLE_ORDER_NOTIONAL_LIMIT"
        if self.submitted_notional_minor + order_notional_minor > policy.max_pilot_total_notional_minor:
            return False, "PILOT_CUMULATIVE_NOTIONAL_LIMIT"
        return True, None
