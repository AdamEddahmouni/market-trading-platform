"""Reference resolution for snapshot temporal audits (BUILD 02)."""

from __future__ import annotations

from typing import Any, Protocol

from ..contracts.common import ContractReference
from ..contracts.event import EventV1
from ..contracts.signal import SignalV1


class TemporalReferenceResolver(Protocol):
    """Resolve upstream records referenced by snapshots without a database."""

    def resolve_event(self, ref: ContractReference) -> EventV1 | None:
        ...

    def resolve_signal(self, ref: ContractReference) -> SignalV1 | None:
        ...


class MappingTemporalResolver:
    """In-memory resolver backed by caller-supplied id maps."""

    def __init__(
        self,
        *,
        events: dict[str, EventV1] | None = None,
        signals: dict[str, SignalV1] | None = None,
    ) -> None:
        self._events = events or {}
        self._signals = signals or {}

    def resolve_event(self, ref: ContractReference) -> EventV1 | None:
        if ref.kind != "event":
            return None
        return self._events.get(ref.id)

    def resolve_signal(self, ref: ContractReference) -> SignalV1 | None:
        if ref.kind != "signal":
            return None
        return self._signals.get(ref.id)


def mapping_resolver(
    *,
    events: dict[str, EventV1] | None = None,
    signals: dict[str, SignalV1] | None = None,
) -> MappingTemporalResolver:
    return MappingTemporalResolver(events=events, signals=signals)


__all__ = [
    "MappingTemporalResolver",
    "TemporalReferenceResolver",
    "mapping_resolver",
]
