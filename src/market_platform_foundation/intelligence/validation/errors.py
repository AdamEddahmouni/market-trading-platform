"""Validation errors (BUILD 19)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ValidationError(Exception):
    code: str
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        if self.details:
            return f"{self.code}: {self.details}"
        return self.code


__all__ = ["ValidationError"]
