"""Training factory errors (BUILD 18)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class TrainingFactoryError(Exception):
    code: str
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        if self.message:
            return f"{self.code}:{self.message}"
        return self.code


__all__ = ["TrainingFactoryError"]
