"""Kill-switch state for independent risk halts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KillSwitchState:
    active: bool = False
    reason_code: str | None = None
