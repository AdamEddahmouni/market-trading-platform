"""Adaptation errors (BUILD 24)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AdaptationError(Exception):
    code: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        if self.details:
            return f"{self.code}:{self.details}"
        return self.code


__all__ = ["AdaptationError"]
