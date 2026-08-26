"""Opportunity engine errors (BUILD 21)."""

from __future__ import annotations

from typing import Any


class OpportunityError(Exception):
    """Deterministic opportunity assessment failure."""

    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = details or {}
        super().__init__(code)


__all__ = ["OpportunityError"]
