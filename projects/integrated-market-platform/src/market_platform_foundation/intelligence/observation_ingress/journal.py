"""Bounded in-process ingress dispatch journal for audit and replay."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque

from .types import IngressDispatchReceiptV1


@dataclass
class IngressDispatchJournal:
    max_entries: int = 5_000
    _entries: Deque[IngressDispatchReceiptV1] = field(default_factory=deque, init=False)

    def append(self, receipt: IngressDispatchReceiptV1) -> None:
        if receipt.duplicate:
            return
        if len(self._entries) >= self.max_entries:
            raise ValueError("INGRESS_JOURNAL_BOUND_EXCEEDED")
        self._entries.append(receipt)

    def entries(self) -> tuple[IngressDispatchReceiptV1, ...]:
        return tuple(self._entries)

    def replay_event_ids(self) -> tuple[str, ...]:
        return tuple(row.event_id for row in self._entries)


__all__ = ["IngressDispatchJournal"]
