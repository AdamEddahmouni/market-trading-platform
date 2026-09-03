"""Promotion governance errors (BUILD 20)."""

from __future__ import annotations

from typing import Any


class PromotionError(Exception):
    """Raised when promotion governance preconditions fail."""

    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = details or {}
        super().__init__(code)


__all__ = ["PromotionError"]
