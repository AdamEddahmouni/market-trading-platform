"""Observation ingress router errors (fail-closed)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class IngressDispatchError(Exception):
    """Required consumer failure or policy violation during dispatch."""

    code: str
    message: str
    event_id: str | None = None
    partial_outcomes: tuple[dict[str, Any], ...] = ()

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


__all__ = ["IngressDispatchError"]
