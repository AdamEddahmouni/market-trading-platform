from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .models import CollectorRecord


@dataclass
class RateLimitState:
    tokens: float = 0.0
    last_refill: float = field(default_factory=time.time)
    requests_this_minute: int = 0
    minute_window_start: float = field(default_factory=time.time)


class EvidenceCollector(ABC):
    """Background harvester for supplemental evidence."""

    name: str = "BaseCollector"

    @property
    @abstractmethod
    def configured(self) -> bool:
        raise NotImplementedError

    @property
    def capabilities(self) -> list[str]:
        return []

    @property
    def rate_limit_state(self) -> dict[str, Any]:
        return {"configured": self.configured}

    @abstractmethod
    def poll(
        self, symbols: list[str], *, force: bool = False
    ) -> list[CollectorRecord]:
        raise NotImplementedError


__all__ = ["EvidenceCollector", "RateLimitState"]
