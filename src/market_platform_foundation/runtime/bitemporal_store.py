"""In-memory append-only bitemporal reference store (Platform P0)."""

from __future__ import annotations

from typing import Any

from ..contracts.reference import ReferenceKind, ReferenceRecord

OPEN_END = "9999-12-31T23:59:59.999999999Z"


class BitemporalAppendError(ValueError):
    """Raised when a reference append would overwrite or overlap an existing version."""


def record_is_visible(
    record: ReferenceRecord | None,
    market_time: str,
    knowledge_time: str,
) -> bool:
    if record is None:
        return False
    return _interval_contains(record.valid_from, record.valid_to, market_time) and _interval_contains(
        record.known_from,
        record.known_to,
        knowledge_time,
    )


def _interval_contains(start: str, end: str, instant: str) -> bool:
    if not start or not instant:
        return False
    if instant < start:
        return False
    if not end:
        return True
    return instant < end


def _intervals_overlap(a_from: str, a_to: str, b_from: str, b_to: str) -> bool:
    a_end = a_to or OPEN_END
    b_end = b_to or OPEN_END
    return a_from < b_end and b_from < a_end


def load_reference_records(rows: list[dict[str, Any]]) -> list[ReferenceRecord]:
    records: list[ReferenceRecord] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        payload = row.get("payload")
        records.append(
            ReferenceRecord(
                kind=ReferenceKind(str(row["kind"])),
                entity_key=str(row["entity_key"]).upper(),
                record_id=str(row["record_id"]),
                record_version=int(row["record_version"]),
                valid_from=str(row.get("valid_from", "")),
                valid_to=str(row.get("valid_to", "")),
                known_from=str(row.get("known_from", "")),
                known_to=str(row.get("known_to", "")),
                payload=dict(payload) if isinstance(payload, dict) else {},
            )
        )
    return records


class BitemporalReferenceStore:
    """Append-only in-memory store. Corrections are new versions, never overwrites."""

    def __init__(self) -> None:
        self._records: list[ReferenceRecord] = []

    def append(self, record: ReferenceRecord) -> None:
        if not record.valid_from or not record.known_from:
            raise BitemporalAppendError("valid_from and known_from are required")
        entity_key = record.entity_key.upper()
        normalized = ReferenceRecord(
            kind=record.kind,
            entity_key=entity_key,
            record_id=record.record_id,
            record_version=record.record_version,
            valid_from=record.valid_from,
            valid_to=record.valid_to,
            known_from=record.known_from,
            known_to=record.known_to,
            payload=dict(record.payload),
            quality_flags=record.quality_flags,
        )
        for existing in self._records:
            if existing.kind != normalized.kind or existing.entity_key != entity_key:
                continue
            if _intervals_overlap(
                existing.valid_from,
                existing.valid_to,
                normalized.valid_from,
                normalized.valid_to,
            ) and _intervals_overlap(
                existing.known_from,
                existing.known_to,
                normalized.known_from,
                normalized.known_to,
            ):
                raise BitemporalAppendError(
                    f"overlapping bitemporal interval for {normalized.kind}:{entity_key}"
                )
        self._records.append(normalized)

    def as_of(
        self,
        kind: ReferenceKind,
        entity_key: str,
        market_time: str,
        knowledge_time: str,
    ) -> ReferenceRecord | None:
        visible = [
            record
            for record in self._records
            if record.kind == kind
            and record.entity_key == entity_key.upper()
            and record_is_visible(record, market_time, knowledge_time)
        ]
        if not visible:
            return None
        return max(visible, key=lambda row: row.record_version)

    def versions(self, kind: ReferenceKind, entity_key: str) -> tuple[ReferenceRecord, ...]:
        key = entity_key.upper()
        return tuple(
            record
            for record in self._records
            if record.kind == kind and record.entity_key == key
        )


__all__ = [
    "BitemporalAppendError",
    "BitemporalReferenceStore",
    "load_reference_records",
    "record_is_visible",
]
