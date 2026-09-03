"""Supported bar book state for BAR_OHLCV_1M events."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SUPPORTED_EVENT_TYPE = "BAR_OHLCV_1M"


@dataclass
class BarBookState:
    bars_by_instrument: dict[str, dict[str, Any]] = field(default_factory=dict)
    applied_event_ids: list[str] = field(default_factory=list)
    rejected_upgrades: list[dict[str, str]] = field(default_factory=list)

    def apply_event(self, event: dict[str, Any]) -> tuple[str, list[str]]:
        event_type = str(event.get("event_type", ""))
        if event_type != SUPPORTED_EVENT_TYPE:
            self.rejected_upgrades.append(
                {
                    "event_type": event_type,
                    "normalized_event_id": str(event.get("normalized_event_id", "")),
                    "reason_code": "BAR_BOOK_UNSUPPORTED_EVENT_TYPE",
                }
            )
            return "REJECTED", ["BAR_BOOK_UNSUPPORTED_EVENT_TYPE"]
        instrument_id = str(event.get("instrument_id", ""))
        if not instrument_id:
            return "REJECTED", ["BAR_BOOK_MISSING_INSTRUMENT"]
        self.bars_by_instrument[instrument_id] = {
            "available_time": int(event["available_time"]),
            "bar_payload": dict(event.get("bar_payload", {})),
            "event_time": int(event["event_time"]),
            "normalized_event_id": str(event["normalized_event_id"]),
        }
        self.applied_event_ids.append(str(event["normalized_event_id"]))
        return "APPLIED", []

    def snapshot(self) -> dict[str, object]:
        return {
            "applied_event_count": len(self.applied_event_ids),
            "bars_by_instrument": {
                key: self.bars_by_instrument[key] for key in sorted(self.bars_by_instrument)
            },
            "rejected_upgrade_count": len(self.rejected_upgrades),
        }
