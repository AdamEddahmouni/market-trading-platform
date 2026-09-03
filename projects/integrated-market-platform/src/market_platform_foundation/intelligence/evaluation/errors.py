"""Evaluation errors (BUILD 16)."""

from __future__ import annotations

from typing import Any


class EvaluationError(Exception):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


__all__ = ["EvaluationError"]
