"""Kill switch persistence — unknown state defaults to BLOCK (BUILD 30)."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..live_execution_safety.types import KillSwitchState


@dataclass
class KillSwitchStore:
    """Persisted kill-switch state survives restart."""

    global_state: KillSwitchState = KillSwitchState.ACTIVE_BLOCK
    program_state: KillSwitchState = KillSwitchState.ACTIVE_BLOCK
    session_state: KillSwitchState = KillSwitchState.INACTIVE
    global_reason: str = "BUILD28_DEFAULT_BLOCK"
    program_reason: str = "PROGRAM_NOT_ACTIVE"
    session_reason: str = ""

    def any_block_active(self) -> bool:
        return (
            self.global_state == KillSwitchState.ACTIVE_BLOCK
            or self.program_state == KillSwitchState.ACTIVE_BLOCK
            or self.session_state == KillSwitchState.ACTIVE_BLOCK
        )

    def activate_program_block(self, reason: str) -> None:
        self.program_state = KillSwitchState.ACTIVE_BLOCK
        self.program_reason = reason

    def activate_session_block(self, reason: str) -> None:
        self.session_state = KillSwitchState.ACTIVE_BLOCK
        self.session_reason = reason

    def permit_program(self, reason: str) -> None:
        self.program_state = KillSwitchState.INACTIVE
        self.program_reason = reason

    def permit_session(self, reason: str) -> None:
        self.session_state = KillSwitchState.INACTIVE
        self.session_reason = reason

    def block_program(self, reason: str) -> None:
        self.activate_program_block(reason)

    def to_persistence_dict(self) -> dict[str, str]:
        return {
            "global_state": self.global_state.value,
            "program_state": self.program_state.value,
            "session_state": self.session_state.value,
            "global_reason": self.global_reason,
            "program_reason": self.program_reason,
            "session_reason": self.session_reason,
        }

    @classmethod
    def from_persistence_dict(cls, data: dict[str, str] | None) -> KillSwitchStore:
        if data is None:
            return KillSwitchStore()
        try:
            return KillSwitchStore(
                global_state=KillSwitchState(data.get("global_state", "ACTIVE_BLOCK")),
                program_state=KillSwitchState(
                    data.get("program_state", "ACTIVE_BLOCK")
                ),
                session_state=KillSwitchState(
                    data.get("session_state", "INACTIVE")
                ),
                global_reason=data.get("global_reason", "UNKNOWN_DEFAULTS_BLOCK"),
                program_reason=data.get("program_reason", ""),
                session_reason=data.get("session_reason", ""),
            )
        except ValueError:
            return KillSwitchStore()
