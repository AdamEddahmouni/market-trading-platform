"""Append-only enrichment request outbox with durable delivery scheduling."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from market_platform_foundation.canonical import canonical_bytes, sha256_bytes

from ...clock import monotonic_wall_ns
from .contracts import EnrichmentRequestV1, enrichment_request_v1_from_dict, enrichment_request_v1_to_dict
from .delivery import (
    DEFAULT_RETRY_POLICY,
    IN_FLIGHT_DELIVERY_STATES,
    TERMINAL_DELIVERY_STATES,
    EnrichmentDeliveryState,
    EnrichmentRetryPolicy,
    compute_next_retry_at_ns,
)


class EnrichmentOutboxPutResult(StrEnum):
    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"


@dataclass(slots=True)
class EnrichmentOutboxDeliveryView:
    request: EnrichmentRequestV1
    delivery_state: EnrichmentDeliveryState
    created_at_ns: int
    retry_count: int
    next_retry_at_ns: int
    claim_owner: str | None = None
    claim_lease_until_ns: int | None = None
    last_error: str | None = None


@runtime_checkable
class EnrichmentOutbox(Protocol):
    def append(self, request: EnrichmentRequestV1) -> EnrichmentOutboxPutResult: ...

    def get(self, request_id: str) -> EnrichmentRequestV1 | None: ...

    def get_delivery(self, request_id: str) -> EnrichmentOutboxDeliveryView | None: ...

    def list_for_opportunity(self, opportunity_id: str) -> tuple[EnrichmentRequestV1, ...]: ...

    def list_pending(self) -> tuple[EnrichmentRequestV1, ...]: ...

    def mark_dispatched(self, request_id: str, *, at_ns: int | None = None) -> None: ...

    def mark_acknowledged(self, request_id: str, *, at_ns: int | None = None) -> None: ...

    def sweep_expired(self, now_ns: int) -> int: ...

    def release_expired_claims(self, now_ns: int) -> int: ...

    def claim_next(
        self,
        worker_id: str,
        *,
        now_ns: int,
        lease_duration_ns: int,
    ) -> EnrichmentRequestV1 | None: ...

    def record_dispatch_failure(
        self,
        request_id: str,
        error: str,
        *,
        now_ns: int,
        policy: EnrichmentRetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> None: ...


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


@dataclass(slots=True)
class _InMemoryDeliveryRow:
    document: dict
    delivery_state: EnrichmentDeliveryState
    created_at_ns: int
    retry_count: int
    next_retry_at_ns: int
    claim_owner: str | None = None
    claim_lease_until_ns: int | None = None
    last_error: str | None = None


class InMemoryEnrichmentOutbox:
    """Thread-safe outbox with idempotent request_id and delivery lifecycle."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._rows: dict[str, _InMemoryDeliveryRow] = {}

    def append(self, request: EnrichmentRequestV1) -> EnrichmentOutboxPutResult:
        document = enrichment_request_v1_to_dict(request)
        created_at_ns = monotonic_wall_ns()
        with self._lock:
            existing = self._rows.get(request.request_id)
            if existing is not None:
                prior = enrichment_request_v1_from_dict(existing.document)
                if enrichment_request_v1_to_dict(prior) == document:
                    return EnrichmentOutboxPutResult.ALREADY_PRESENT
                raise ValueError("ENRICHMENT_REQUEST_IMMUTABLE_CONFLICT")
            self._rows[request.request_id] = _InMemoryDeliveryRow(
                document=document,
                delivery_state=EnrichmentDeliveryState.PENDING,
                created_at_ns=created_at_ns,
                retry_count=0,
                next_retry_at_ns=request.detected_at_ns,
            )
            return EnrichmentOutboxPutResult.INSERTED

    def get(self, request_id: str) -> EnrichmentRequestV1 | None:
        with self._lock:
            row = self._rows.get(str(request_id))
        if row is None:
            return None
        return enrichment_request_v1_from_dict(row.document)

    def get_delivery(self, request_id: str) -> EnrichmentOutboxDeliveryView | None:
        with self._lock:
            row = self._rows.get(str(request_id))
        if row is None:
            return None
        return _delivery_view(row)

    def list_for_opportunity(self, opportunity_id: str) -> tuple[EnrichmentRequestV1, ...]:
        with self._lock:
            rows = list(self._rows.values())
        matches = [
            enrichment_request_v1_from_dict(row.document)
            for row in rows
            if str(row.document.get("opportunity_id")) == str(opportunity_id)
            and row.delivery_state not in TERMINAL_DELIVERY_STATES
        ]
        return tuple(sorted(matches, key=lambda row: (row.detected_at_ns, row.request_id)))

    def list_pending(self) -> tuple[EnrichmentRequestV1, ...]:
        with self._lock:
            rows = list(self._rows.values())
        matches = [
            enrichment_request_v1_from_dict(row.document)
            for row in rows
            if row.delivery_state in IN_FLIGHT_DELIVERY_STATES
        ]
        return tuple(sorted(matches, key=lambda row: (row.detected_at_ns, row.request_id)))

    def mark_dispatched(self, request_id: str, *, at_ns: int | None = None) -> None:
        with self._lock:
            row = self._require_row(request_id)
            row.delivery_state = EnrichmentDeliveryState.DISPATCHED
            row.claim_owner = None
            row.claim_lease_until_ns = None
            row.last_error = None

    def mark_acknowledged(self, request_id: str, *, at_ns: int | None = None) -> None:
        with self._lock:
            row = self._require_row(request_id)
            row.delivery_state = EnrichmentDeliveryState.ACKNOWLEDGED
            row.claim_owner = None
            row.claim_lease_until_ns = None

    def sweep_expired(self, now_ns: int) -> int:
        updated = 0
        with self._lock:
            for row in self._rows.values():
                if row.delivery_state in TERMINAL_DELIVERY_STATES:
                    continue
                hard_expiry_ns = int(row.document.get("hard_expiry_ns") or 0)
                if hard_expiry_ns and now_ns >= hard_expiry_ns:
                    row.delivery_state = EnrichmentDeliveryState.EXPIRED
                    row.claim_owner = None
                    row.claim_lease_until_ns = None
                    updated += 1
        return updated

    def release_expired_claims(self, now_ns: int) -> int:
        released = 0
        with self._lock:
            for row in self._rows.values():
                if row.delivery_state != EnrichmentDeliveryState.CLAIMED:
                    continue
                lease_until = row.claim_lease_until_ns
                if lease_until is not None and now_ns >= lease_until:
                    row.delivery_state = EnrichmentDeliveryState.PENDING
                    row.claim_owner = None
                    row.claim_lease_until_ns = None
                    released += 1
        return released

    def claim_next(
        self,
        worker_id: str,
        *,
        now_ns: int,
        lease_duration_ns: int,
    ) -> EnrichmentRequestV1 | None:
        with self._lock:
            candidates = [
                row
                for row in self._rows.values()
                if row.delivery_state == EnrichmentDeliveryState.PENDING
                and row.next_retry_at_ns <= now_ns
            ]
            candidates.sort(key=lambda row: (row.next_retry_at_ns, row.document.get("request_id")))
            for row in candidates:
                hard_expiry_ns = int(row.document.get("hard_expiry_ns") or 0)
                if hard_expiry_ns and now_ns >= hard_expiry_ns:
                    row.delivery_state = EnrichmentDeliveryState.EXPIRED
                    continue
                row.delivery_state = EnrichmentDeliveryState.CLAIMED
                row.claim_owner = worker_id
                row.claim_lease_until_ns = now_ns + lease_duration_ns
                return enrichment_request_v1_from_dict(row.document)
        return None

    def record_dispatch_failure(
        self,
        request_id: str,
        error: str,
        *,
        now_ns: int,
        policy: EnrichmentRetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> None:
        with self._lock:
            row = self._require_row(request_id)
            row.retry_count += 1
            row.last_error = error[:2000]
            row.claim_owner = None
            row.claim_lease_until_ns = None
            if row.retry_count >= policy.max_attempts:
                row.delivery_state = EnrichmentDeliveryState.DEAD_LETTER
                return
            row.delivery_state = EnrichmentDeliveryState.PENDING
            row.next_retry_at_ns = compute_next_retry_at_ns(
                retry_count=row.retry_count,
                now_ns=now_ns,
                policy=policy,
            )

    def _require_row(self, request_id: str) -> _InMemoryDeliveryRow:
        row = self._rows.get(str(request_id))
        if row is None:
            raise ValueError("ENRICHMENT_REQUEST_NOT_FOUND")
        return row


def _delivery_view(row: _InMemoryDeliveryRow) -> EnrichmentOutboxDeliveryView:
    return EnrichmentOutboxDeliveryView(
        request=enrichment_request_v1_from_dict(row.document),
        delivery_state=row.delivery_state,
        created_at_ns=row.created_at_ns,
        retry_count=row.retry_count,
        next_retry_at_ns=row.next_retry_at_ns,
        claim_owner=row.claim_owner,
        claim_lease_until_ns=row.claim_lease_until_ns,
        last_error=row.last_error,
    )


__all__ = [
    "EnrichmentOutbox",
    "EnrichmentOutboxDeliveryView",
    "EnrichmentOutboxPutResult",
    "InMemoryEnrichmentOutbox",
    "derive_enrichment_request_id",
]
