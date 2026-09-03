"""Quota-aware subscription allocation for scarce live observational slots."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True, slots=True)
class SubscriptionRequest:
    instrument_id: str
    capability: str
    priority: int
    lane: str = ""
    thesis_id: str = ""


@dataclass(frozen=True, slots=True)
class AllocationDecision:
    accepted: tuple[str, ...]
    rejected: tuple[str, ...]
    reused: tuple[str, ...]
    released: tuple[str, ...]
    reason_codes: tuple[str, ...]


@dataclass
class SubscriptionAllocator:
    max_slots: int = 100
    cooldown_cycles: int = 1
    held: set[str] = field(default_factory=set)
    cooldown: dict[str, int] = field(default_factory=dict)

    def allocate(self, requests: Iterable[SubscriptionRequest]) -> AllocationDecision:
        ranked = sorted(requests, key=lambda item: (-int(item.priority), item.instrument_id))
        accepted: list[str] = []
        rejected: list[str] = []
        reused: list[str] = []
        reasons: list[str] = []
        wanted = {item.instrument_id.upper() for item in ranked}
        for request in ranked:
            symbol = request.instrument_id.upper()
            if symbol in self.held:
                reused.append(symbol)
                continue
            if self.cooldown.get(symbol, 0) > 0:
                rejected.append(symbol)
                reasons.append("COOLDOWN")
                continue
            if len(self.held) + len(accepted) >= self.max_slots:
                rejected.append(symbol)
                reasons.append("QUOTA_EXHAUSTED")
                continue
            accepted.append(symbol)
        released = sorted(symbol for symbol in self.held if symbol not in wanted)
        for symbol in released:
            self.held.discard(symbol)
            self.cooldown[symbol] = self.cooldown_cycles
        self.held.update(accepted)
        for symbol in list(self.cooldown):
            remaining = self.cooldown[symbol] - 1
            if remaining <= 0:
                del self.cooldown[symbol]
            else:
                self.cooldown[symbol] = remaining
        return AllocationDecision(
            accepted=tuple(accepted),
            rejected=tuple(rejected),
            reused=tuple(reused),
            released=tuple(released),
            reason_codes=tuple(dict.fromkeys(reasons)),
        )
