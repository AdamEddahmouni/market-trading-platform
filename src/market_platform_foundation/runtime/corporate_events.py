"""Platform P1 corporate event registry (fixture scope) — P0 visibility adapter."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..contracts.reference import ReferenceKind, ReferenceRecord
from ..normalization.equity_bars import iso_to_epoch_ns
from .bitemporal_store import record_is_visible

PRODUCER_VERSION = "platform_corporate_event_registry_v1"


def _epoch_ns_to_iso(ns: int) -> str:
    seconds, nano = divmod(int(ns), 1_000_000_000)
    stamp = datetime.fromtimestamp(seconds, tz=timezone.utc)
    return stamp.strftime("%Y-%m-%dT%H:%M:%S") + f".{nano:09d}Z"


@dataclass(frozen=True, slots=True)
class CorporateEventRecord:
    event_id: str
    instrument_id: str
    canonical_event_type: str
    event_time: str
    available_time: str
    source_document_ids: tuple[str, ...] = ()
    provenance_ref: str = PRODUCER_VERSION

    def as_reference(self) -> ReferenceRecord:
        return ReferenceRecord(
            kind=ReferenceKind.EARNINGS_CALENDAR,
            entity_key=self.instrument_id,
            record_id=self.event_id,
            record_version=1,
            valid_from=self.available_time,
            valid_to="",
            known_from=self.available_time,
            known_to="",
            payload={
                "earnings_event_time": self.event_time,
                "event_type": self.canonical_event_type,
            },
        )


def corporate_event_to_dict(item: CorporateEventRecord) -> dict[str, Any]:
    return {
        "event_id": item.event_id,
        "instrument_id": item.instrument_id,
        "canonical_event_type": item.canonical_event_type,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "source_document_ids": list(item.source_document_ids),
        "provenance_ref": item.provenance_ref,
    }


class CorporateEventRegistry:
    """PIT-aware corporate event registry backed by admitted MC fixtures."""

    def __init__(self, records: tuple[CorporateEventRecord, ...]) -> None:
        self._records = records

    @classmethod
    def from_extraction_summaries(
        cls,
        summaries: list[dict[str, Any]],
        *,
        instrument_id: str,
    ) -> CorporateEventRegistry:
        rows: list[CorporateEventRecord] = []
        for summary in summaries:
            if not isinstance(summary, dict):
                continue
            event_id = str(summary.get("event_id", ""))
            if not event_id:
                continue
            rows.append(
                CorporateEventRecord(
                    event_id=event_id,
                    instrument_id=instrument_id.upper(),
                    canonical_event_type=str(summary.get("canonical_event_type", "unknown")),
                    event_time=str(summary.get("event_time", "")),
                    available_time=str(summary.get("available_time", "")),
                    source_document_ids=tuple(
                        str(value)
                        for value in (summary.get("source_document_ids") or [])
                        if value
                    ),
                )
            )
        return cls(tuple(rows))

    @classmethod
    def from_fixture_file(cls, path: Path, *, instrument_id: str) -> CorporateEventRegistry:
        payload = json.loads(path.read_text(encoding="utf-8"))
        summaries = payload.get("event_extraction_summaries") or payload.get("events") or []
        if not isinstance(summaries, list):
            summaries = []
        return cls.from_extraction_summaries(summaries, instrument_id=instrument_id)

    def query_events(
        self,
        instrument_id: str,
        *,
        prediction_cutoff: int,
    ) -> list[CorporateEventRecord]:
        symbol = instrument_id.upper()
        knowledge_time = _epoch_ns_to_iso(prediction_cutoff)
        eligible: list[CorporateEventRecord] = []
        for record in self._records:
            if record.instrument_id != symbol:
                continue
            if not record.available_time:
                continue
            if record_is_visible(record.as_reference(), knowledge_time, knowledge_time):
                eligible.append(record)
        eligible.sort(key=lambda item: iso_to_epoch_ns(item.available_time))
        return eligible


__all__ = [
    "CorporateEventRecord",
    "CorporateEventRegistry",
    "PRODUCER_VERSION",
    "corporate_event_to_dict",
]
