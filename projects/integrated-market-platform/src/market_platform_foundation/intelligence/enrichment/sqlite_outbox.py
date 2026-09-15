"""SQLite-backed enrichment outbox (local_state schema v7)."""

from __future__ import annotations

import json
from typing import Any

from ...clock import monotonic_wall_ns
from ...local_state.connection import LocalStateConnection
from .contracts import EnrichmentRequestV1, enrichment_request_v1_from_dict, enrichment_request_v1_to_dict
from .delivery import (
    DEFAULT_RETRY_POLICY,
    IN_FLIGHT_DELIVERY_STATES,
    TERMINAL_DELIVERY_STATES,
    EnrichmentDeliveryState,
    EnrichmentRetryPolicy,
    compute_next_retry_at_ns,
)
from .outbox import EnrichmentOutboxDeliveryView, EnrichmentOutboxPutResult


class SqliteEnrichmentOutbox:
    def __init__(self, connection: LocalStateConnection) -> None:
        self._connection = connection

    def _run_write(self, callback):
        if self._connection.in_transaction:
            return callback()
        with self._connection.transaction():
            return callback()

    def append(self, request: EnrichmentRequestV1) -> EnrichmentOutboxPutResult:
        document = enrichment_request_v1_to_dict(request)
        payload = json.dumps(document, sort_keys=True, separators=(",", ":"))
        created_at_ns = monotonic_wall_ns()

        def _write() -> EnrichmentOutboxPutResult:
            row = self._connection.execute(
                "SELECT request_json FROM enrichment_outbox WHERE request_id = ?",
                (request.request_id,),
            ).fetchone()
            if row is not None:
                prior = json.loads(str(row["request_json"]))
                if prior == json.loads(payload):
                    return EnrichmentOutboxPutResult.ALREADY_PRESENT
                raise ValueError("ENRICHMENT_REQUEST_IMMUTABLE_CONFLICT")
            self._connection.execute(
                """
                INSERT INTO enrichment_outbox(
                    request_id, opportunity_id, hard_expiry_ns, request_json,
                    delivery_state, created_at_ns, retry_count, next_retry_at_ns
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.request_id,
                    request.opportunity_id,
                    request.hard_expiry_ns,
                    payload,
                    EnrichmentDeliveryState.PENDING.value,
                    created_at_ns,
                    0,
                    request.detected_at_ns,
                ),
            )
            return EnrichmentOutboxPutResult.INSERTED

        return self._run_write(_write)

    def get(self, request_id: str) -> EnrichmentRequestV1 | None:
        row = self._connection.execute(
            "SELECT request_json FROM enrichment_outbox WHERE request_id = ?",
            (str(request_id),),
        ).fetchone()
        if row is None:
            return None
        return enrichment_request_v1_from_dict(json.loads(str(row["request_json"])))

    def get_delivery(self, request_id: str) -> EnrichmentOutboxDeliveryView | None:
        row = self._connection.execute(
            """
            SELECT request_json, delivery_state, created_at_ns, retry_count,
                   next_retry_at_ns, claim_owner, claim_lease_until_ns, last_error
            FROM enrichment_outbox WHERE request_id = ?
            """,
            (str(request_id),),
        ).fetchone()
        if row is None:
            return None
        return _row_to_delivery_view(row)

    def list_for_opportunity(self, opportunity_id: str) -> tuple[EnrichmentRequestV1, ...]:
        rows = self._connection.execute(
            """
            SELECT request_json, delivery_state FROM enrichment_outbox
            WHERE opportunity_id = ?
            ORDER BY created_at_ns ASC, request_id ASC
            """,
            (str(opportunity_id),),
        ).fetchall()
        matches: list[EnrichmentRequestV1] = []
        for row in rows:
            state = EnrichmentDeliveryState(str(row["delivery_state"]))
            if state in TERMINAL_DELIVERY_STATES:
                continue
            matches.append(enrichment_request_v1_from_dict(json.loads(str(row["request_json"]))))
        return tuple(matches)

    def list_pending(self) -> tuple[EnrichmentRequestV1, ...]:
        placeholders = ",".join("?" for _ in IN_FLIGHT_DELIVERY_STATES)
        rows = self._connection.execute(
            f"""
            SELECT request_json FROM enrichment_outbox
            WHERE delivery_state IN ({placeholders})
            ORDER BY created_at_ns ASC, request_id ASC
            """,
            tuple(state.value for state in IN_FLIGHT_DELIVERY_STATES),
        ).fetchall()
        return tuple(
            enrichment_request_v1_from_dict(json.loads(str(row["request_json"]))) for row in rows
        )

    def mark_dispatched(self, request_id: str, *, at_ns: int | None = None) -> None:
        def _write() -> None:
            self._connection.execute(
                """
                UPDATE enrichment_outbox
                SET delivery_state = ?, claim_owner = NULL, claim_lease_until_ns = NULL,
                    last_error = NULL, dispatched_at_ns = ?
                WHERE request_id = ?
                """,
                (
                    EnrichmentDeliveryState.DISPATCHED.value,
                    at_ns if at_ns is not None else monotonic_wall_ns(),
                    str(request_id),
                ),
            )

        self._run_write(_write)

    def mark_acknowledged(self, request_id: str, *, at_ns: int | None = None) -> None:
        def _write() -> None:
            self._connection.execute(
                """
                UPDATE enrichment_outbox
                SET delivery_state = ?, claim_owner = NULL, claim_lease_until_ns = NULL,
                    acknowledged_at_ns = ?
                WHERE request_id = ?
                """,
                (
                    EnrichmentDeliveryState.ACKNOWLEDGED.value,
                    at_ns if at_ns is not None else monotonic_wall_ns(),
                    str(request_id),
                ),
            )

        self._run_write(_write)

    def sweep_expired(self, now_ns: int) -> int:
        def _write() -> int:
            cursor = self._connection.execute(
                """
                UPDATE enrichment_outbox
                SET delivery_state = ?, claim_owner = NULL, claim_lease_until_ns = NULL
                WHERE hard_expiry_ns <= ?
                  AND delivery_state NOT IN (?, ?, ?)
                """,
                (
                    EnrichmentDeliveryState.EXPIRED.value,
                    now_ns,
                    EnrichmentDeliveryState.ACKNOWLEDGED.value,
                    EnrichmentDeliveryState.EXPIRED.value,
                    EnrichmentDeliveryState.DEAD_LETTER.value,
                ),
            )
            return int(cursor.rowcount)

        return self._run_write(_write)

    def release_expired_claims(self, now_ns: int) -> int:
        def _write() -> int:
            cursor = self._connection.execute(
                """
                UPDATE enrichment_outbox
                SET delivery_state = ?, claim_owner = NULL, claim_lease_until_ns = NULL
                WHERE delivery_state = ?
                  AND claim_lease_until_ns IS NOT NULL
                  AND claim_lease_until_ns <= ?
                """,
                (
                    EnrichmentDeliveryState.PENDING.value,
                    EnrichmentDeliveryState.CLAIMED.value,
                    now_ns,
                ),
            )
            return int(cursor.rowcount)

        return self._run_write(_write)

    def claim_next(
        self,
        worker_id: str,
        *,
        now_ns: int,
        lease_duration_ns: int,
    ) -> EnrichmentRequestV1 | None:
        def _write() -> EnrichmentRequestV1 | None:
            self._connection.execute(
                """
                UPDATE enrichment_outbox
                SET delivery_state = ?
                WHERE hard_expiry_ns <= ?
                  AND delivery_state NOT IN (?, ?, ?)
                """,
                (
                    EnrichmentDeliveryState.EXPIRED.value,
                    now_ns,
                    EnrichmentDeliveryState.ACKNOWLEDGED.value,
                    EnrichmentDeliveryState.EXPIRED.value,
                    EnrichmentDeliveryState.DEAD_LETTER.value,
                ),
            )
            row = self._connection.execute(
                """
                SELECT request_id FROM enrichment_outbox
                WHERE delivery_state = ?
                  AND next_retry_at_ns <= ?
                  AND hard_expiry_ns > ?
                ORDER BY next_retry_at_ns ASC, request_id ASC
                LIMIT 1
                """,
                (EnrichmentDeliveryState.PENDING.value, now_ns, now_ns),
            ).fetchone()
            if row is None:
                return None
            request_id = str(row["request_id"])
            updated = self._connection.execute(
                """
                UPDATE enrichment_outbox
                SET delivery_state = ?, claim_owner = ?, claim_lease_until_ns = ?
                WHERE request_id = ? AND delivery_state = ?
                """,
                (
                    EnrichmentDeliveryState.CLAIMED.value,
                    worker_id,
                    now_ns + lease_duration_ns,
                    request_id,
                    EnrichmentDeliveryState.PENDING.value,
                ),
            )
            if int(updated.rowcount) != 1:
                return None
            payload = self._connection.execute(
                "SELECT request_json FROM enrichment_outbox WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            assert payload is not None
            return enrichment_request_v1_from_dict(json.loads(str(payload["request_json"])))

        return self._run_write(_write)

    def record_dispatch_failure(
        self,
        request_id: str,
        error: str,
        *,
        now_ns: int,
        policy: EnrichmentRetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> None:
        trimmed = error[:2000]

        def _write() -> None:
            row = self._connection.execute(
                "SELECT retry_count FROM enrichment_outbox WHERE request_id = ?",
                (str(request_id),),
            ).fetchone()
            if row is None:
                raise ValueError("ENRICHMENT_REQUEST_NOT_FOUND")
            retry_count = int(row["retry_count"]) + 1
            if retry_count >= policy.max_attempts:
                self._connection.execute(
                    """
                    UPDATE enrichment_outbox
                    SET delivery_state = ?, retry_count = ?, last_error = ?,
                        claim_owner = NULL, claim_lease_until_ns = NULL
                    WHERE request_id = ?
                    """,
                    (
                        EnrichmentDeliveryState.DEAD_LETTER.value,
                        retry_count,
                        trimmed,
                        str(request_id),
                    ),
                )
                return
            next_retry = compute_next_retry_at_ns(
                retry_count=retry_count,
                now_ns=now_ns,
                policy=policy,
            )
            self._connection.execute(
                """
                UPDATE enrichment_outbox
                SET delivery_state = ?, retry_count = ?, next_retry_at_ns = ?,
                    last_error = ?, claim_owner = NULL, claim_lease_until_ns = NULL
                WHERE request_id = ?
                """,
                (
                    EnrichmentDeliveryState.PENDING.value,
                    retry_count,
                    next_retry,
                    trimmed,
                    str(request_id),
                ),
            )

        self._run_write(_write)


def _row_to_delivery_view(row: Any) -> EnrichmentOutboxDeliveryView:
    return EnrichmentOutboxDeliveryView(
        request=enrichment_request_v1_from_dict(json.loads(str(row["request_json"]))),
        delivery_state=EnrichmentDeliveryState(str(row["delivery_state"])),
        created_at_ns=int(row["created_at_ns"]),
        retry_count=int(row["retry_count"]),
        next_retry_at_ns=int(row["next_retry_at_ns"]),
        claim_owner=row["claim_owner"],
        claim_lease_until_ns=(
            int(row["claim_lease_until_ns"]) if row["claim_lease_until_ns"] is not None else None
        ),
        last_error=row["last_error"],
    )


__all__ = ["SqliteEnrichmentOutbox"]
