"""Append-only enrichment request outbox (in-process reference backend)."""

from __future__ import annotations

import threading
from enum import StrEnum
from typing import Protocol, runtime_checkable

from market_platform_foundation.canonical import canonical_bytes, sha256_bytes

from .contracts import EnrichmentRequestV1, enrichment_request_v1_from_dict, enrichment_request_v1_to_dict


class EnrichmentOutboxPutResult(StrEnum):
    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"


@runtime_checkable
class EnrichmentOutbox(Protocol):
    def append(self, request: EnrichmentRequestV1) -> EnrichmentOutboxPutResult: ...

    def get(self, request_id: str) -> EnrichmentRequestV1 | None: ...

    def list_for_opportunity(self, opportunity_id: str) -> tuple[EnrichmentRequestV1, ...]: ...

    def list_pending(self) -> tuple[EnrichmentRequestV1, ...]: ...


def derive_enrichment_request_id(
    *,
    opportunity_id: str,
    requested_bot_role: str,
    event_id: str | None = None,
) -> str:
    material = {
        "opportunity_id": opportunity_id,
        "requested_bot_role": requested_bot_role,
        "event_id": event_id,
    }
    digest = sha256_bytes(canonical_bytes(material))
    return f"ENRQ-{digest[:24]}"


class InMemoryEnrichmentOutbox:
    """Thread-safe append-only outbox with idempotent request_id."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._by_id: dict[str, dict] = {}
        self._pending: list[str] = []

    def append(self, request: EnrichmentRequestV1) -> EnrichmentOutboxPutResult:
        document = enrichment_request_v1_to_dict(request)
        with self._lock:
            if request.request_id in self._by_id:
                prior = enrichment_request_v1_from_dict(self._by_id[request.request_id])
                if enrichment_request_v1_to_dict(prior) == document:
                    return EnrichmentOutboxPutResult.ALREADY_PRESENT
                raise ValueError("ENRICHMENT_REQUEST_IMMUTABLE_CONFLICT")
            self._by_id[request.request_id] = document
            self._pending.append(request.request_id)
            return EnrichmentOutboxPutResult.INSERTED

    def get(self, request_id: str) -> EnrichmentRequestV1 | None:
        with self._lock:
            payload = self._by_id.get(str(request_id))
        if payload is None:
            return None
        return enrichment_request_v1_from_dict(payload)

    def list_for_opportunity(self, opportunity_id: str) -> tuple[EnrichmentRequestV1, ...]:
        with self._lock:
            rows = list(self._by_id.values())
        matches = [
            enrichment_request_v1_from_dict(row)
            for row in rows
            if str(row.get("opportunity_id")) == str(opportunity_id)
        ]
        return tuple(sorted(matches, key=lambda row: (row.detected_at_ns, row.request_id)))

    def list_pending(self) -> tuple[EnrichmentRequestV1, ...]:
        with self._lock:
            ids = list(self._pending)
        rows = [self.get(request_id) for request_id in ids]
        return tuple(row for row in rows if row is not None)

    def mark_dispatched(self, request_id: str) -> None:
        with self._lock:
            if request_id in self._pending:
                self._pending.remove(request_id)


__all__ = [
    "EnrichmentOutbox",
    "EnrichmentOutboxPutResult",
    "InMemoryEnrichmentOutbox",
    "derive_enrichment_request_id",
]
