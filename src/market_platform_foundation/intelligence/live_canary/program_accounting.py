"""Cumulative program-level live canary accounting (BUILD 30)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .types import LiveCanaryProgramPolicyV1


@dataclass
class ProgramAccounting:
    """Tracks cumulative exposure across sessions — never resets per session."""

    sessions_completed: int = 0
    sessions_authorized: int = 0
    sessions_executed: int = 0
    sessions_clean: int = 0
    sessions_halted: int = 0
    total_submit_attempts: int = 0
    total_acks: int = 0
    total_fills: int = 0
    gross_submitted_notional_minor: int = 0
    filled_notional_minor: int = 0
    fees_minor: int = 0
    realized_pnl_minor: int = 0
    open_residual_exposure_minor: int = 0
    consecutive_incidents: int = 0
    session_refs: list[str] = field(default_factory=list)
    authorization_refs: list[str] = field(default_factory=list)
    last_session_end_ns: int | None = None

    def record_session_submit(self, notional_minor: int) -> None:
        self.total_submit_attempts += 1
        self.gross_submitted_notional_minor += notional_minor

    def record_ack(self) -> None:
        self.total_acks += 1

    def record_fill(self, *, quantity: int, price_minor: int, fees_minor: int = 0) -> None:
        self.total_fills += 1
        notional = quantity * price_minor
        self.filled_notional_minor += notional
        self.fees_minor += fees_minor

    def record_session_complete(
        self,
        *,
        session_ref: str,
        authorization_ref: str | None,
        clean: bool,
        executed: bool,
        end_ns: int,
    ) -> None:
        self.sessions_completed += 1
        self.session_refs.append(session_ref)
        if authorization_ref:
            self.authorization_refs.append(authorization_ref)
        if clean:
            self.sessions_clean += 1
        if executed:
            self.sessions_executed += 1
        self.last_session_end_ns = end_ns
        self.consecutive_incidents = 0

    def record_session_halted(self, session_ref: str) -> None:
        self.sessions_halted += 1
        self.session_refs.append(session_ref)
        self.consecutive_incidents += 1

    def program_cap_exceeded(self, policy: LiveCanaryProgramPolicyV1) -> tuple[bool, str | None]:
        if self.sessions_completed >= policy.max_sessions:
            return True, "SESSION_LIMIT"
        if self.total_submit_attempts >= policy.max_program_order_count:
            return True, "ORDER_COUNT"
        if self.filled_notional_minor >= policy.max_program_live_notional_minor:
            return True, "NOTIONAL"
        if self.realized_pnl_minor <= -policy.max_program_realized_loss_minor:
            return True, "REALIZED_LOSS"
        return False, None

    def cooldown_satisfied(
        self,
        policy: LiveCanaryProgramPolicyV1,
        decision_time_ns: int,
    ) -> bool:
        if self.last_session_end_ns is None:
            return True
        elapsed = decision_time_ns - self.last_session_end_ns
        return elapsed >= policy.minimum_cooldown_between_sessions_ns
