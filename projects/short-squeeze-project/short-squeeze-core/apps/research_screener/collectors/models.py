from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CollectorRecord:
    """One harvested evidence item for a symbol."""

    symbol: str
    payload: dict[str, Any]
    received_at: str
    source_id: str
    field_hints: dict[str, Any] = field(default_factory=dict)
    dedupe_key: str | None = None


__all__ = ["CollectorRecord"]
