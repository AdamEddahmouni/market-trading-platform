"""Clock fields for observational capture (ADR-REF-001 / ADR-PIT-001 aligned)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TimestampSet:
    event_time_ns: int | None
    provider_time_ns: int | None
    available_time_ns: int | None
    received_time_ns: int | None
    ingested_time_ns: int | None

    def to_dict(self) -> dict[str, int | None]:
        return {
            "available_time_ns": self.available_time_ns,
            "event_time_ns": self.event_time_ns,
            "ingested_time_ns": self.ingested_time_ns,
            "provider_time_ns": self.provider_time_ns,
            "received_time_ns": self.received_time_ns,
        }


def clocks_from_capture(payload: dict[str, Any]) -> TimestampSet:
    clocks = payload.get("clocks") if isinstance(payload.get("clocks"), dict) else payload
    return TimestampSet(
        event_time_ns=_optional_int(clocks.get("event_time_ns")),
        provider_time_ns=_optional_int(clocks.get("provider_time_ns")),
        available_time_ns=_optional_int(clocks.get("available_time_ns")),
        received_time_ns=_optional_int(clocks.get("received_time_ns")),
        ingested_time_ns=_optional_int(clocks.get("ingested_time_ns")),
    )


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    return int(value)
