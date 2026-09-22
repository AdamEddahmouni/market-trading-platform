"""Serving OpportunityV1 / EventV1 book on the canonical local_state SQLite.

Same database as operator acks, trade reviews, and execution decision traces.
Mongo remains BUILD 04.5 operational persistence and is not the UI API serving
composition. Persist-off stays process-local ``INTENTIONAL_EPHEMERAL``.
"""

from __future__ import annotations

import json
import threading

from ...clock import monotonic_wall_ns
from ...local_state.connection import LocalStateConnection
from ...local_state.paths import persistence_enabled
from ...local_state.startup import open_local_state
from ..contracts.common import ContractKind
from ..contracts.event import EventV1
from ..contracts.opportunity import OpportunityV1
from .codec import (
    canonical_semantic_equal,
    codec_for_kind,
    decode_document,
    encode_document,
)
from .errors import RepositoryConflictError
from .memory import InMemoryIntelligenceRepository
from .repository import RepositoryPutResult

OPPORTUNITY_BOOK_STORAGE_DURABLE = "DURABLE_SQLITE"
OPPORTUNITY_BOOK_STORAGE_PROCESS_LOCAL = "PROCESS_LOCAL"

_LOCK = threading.Lock()
_SQLITE: "LocalStateIntelligenceRepository | None" = None


def opportunity_book_storage() -> str:
    if persistence_enabled():
        return OPPORTUNITY_BOOK_STORAGE_DURABLE
    return OPPORTUNITY_BOOK_STORAGE_PROCESS_LOCAL


def opportunity_book_health() -> dict[str, object]:
    """Health of the serving opportunity book. Not a Live/runtime liveness probe."""

    storage = opportunity_book_storage()
    if storage != OPPORTUNITY_BOOK_STORAGE_DURABLE:
        return {
            "available": True,
            "backend": "in_memory",
            "database": None,
            "storage": storage,
            "classification": "INTENTIONAL_EPHEMERAL",
        }
    repo = open_local_state_intelligence_repository()
    health = dict(repo.check_health())
    health["storage"] = storage
    return health


class LocalStateIntelligenceRepository(InMemoryIntelligenceRepository):
    """In-memory IntelligenceRepository with SQLite durability for events + opportunities.

    Other record types remain process-local. Immutable conflict semantics match
    ``InMemoryIntelligenceRepository`` / Mongo.
    """

    def __init__(self, connection: LocalStateConnection) -> None:
        super().__init__()
        self._connection = connection
        self._hydrate()

    def check_health(self) -> dict[str, object]:
        with self._lock:
            event_count = len(self._stores["events"])
            opportunity_count = len(self._stores["opportunities"])
        return {
            "available": True,
            "backend": "local_state_sqlite",
            "database": str(self._connection.path),
            "storage": OPPORTUNITY_BOOK_STORAGE_DURABLE,
            "event_count": event_count,
            "opportunity_count": opportunity_count,
        }

    def put_event(self, event: EventV1) -> RepositoryPutResult:
        self._sqlite_put(
            table="intelligence_events",
            id_column="event_id",
            json_column="event_json",
            record_id=event.event_id,
            document=encode_document(event),
            kind="event",
        )
        return super().put_event(event)

    def put_opportunity(self, opportunity: OpportunityV1) -> RepositoryPutResult:
        self._sqlite_put(
            table="intelligence_opportunities",
            id_column="opportunity_id",
            json_column="opportunity_json",
            record_id=opportunity.opportunity_id,
            document=encode_document(opportunity),
            kind="opportunity",
        )
        return super().put_opportunity(opportunity)

    def _run_write(self, callback):
        if self._connection.in_transaction:
            return callback()
        with self._connection.transaction():
            return callback()

    def _sqlite_put(
        self,
        *,
        table: str,
        id_column: str,
        json_column: str,
        record_id: str,
        document: dict,
        kind: str,
    ) -> RepositoryPutResult:
        payload = json.dumps(document, sort_keys=True, separators=(",", ":"))
        persist_time_ns = monotonic_wall_ns()

        def _write() -> RepositoryPutResult:
            row = self._connection.execute(
                f"SELECT {json_column} FROM {table} WHERE {id_column} = ?",
                (record_id,),
            ).fetchone()
            if row is not None:
                prior = json.loads(str(row[json_column]))
                if canonical_semantic_equal(prior, document):
                    return RepositoryPutResult.ALREADY_PRESENT
                raise RepositoryConflictError(
                    f"IMMUTABLE_CONFLICT:{kind}:{record_id}",
                    details={"kind": kind, "id": record_id},
                )
            self._connection.execute(
                f"""
                INSERT INTO {table}({id_column}, {json_column}, persist_time_ns)
                VALUES (?, ?, ?)
                """,
                (record_id, payload, persist_time_ns),
            )
            return RepositoryPutResult.INSERTED

        return self._run_write(_write)

    def _hydrate(self) -> None:
        event_codec = codec_for_kind(ContractKind.EVENT)
        for row in self._connection.execute(
            "SELECT event_id, event_json FROM intelligence_events"
        ).fetchall():
            document = json.loads(str(row["event_json"]))
            super().put_event(decode_document(document, event_codec))
        opportunity_codec = codec_for_kind(ContractKind.OPPORTUNITY)
        for row in self._connection.execute(
            "SELECT opportunity_id, opportunity_json FROM intelligence_opportunities"
        ).fetchall():
            document = json.loads(str(row["opportunity_json"]))
            super().put_opportunity(decode_document(document, opportunity_codec))


def open_local_state_intelligence_repository() -> InMemoryIntelligenceRepository:
    """Serving IntelligenceRepository: SQLite-backed when persist is on."""

    if not persistence_enabled():
        return InMemoryIntelligenceRepository()
    local = open_local_state()
    if local is None:
        return InMemoryIntelligenceRepository()
    global _SQLITE
    with _LOCK:
        if _SQLITE is None or _SQLITE._connection is not local.connection:
            _SQLITE = LocalStateIntelligenceRepository(local.connection)
        return _SQLITE


def reset_local_state_intelligence_repository_for_tests() -> None:
    global _SQLITE
    with _LOCK:
        _SQLITE = None


__all__ = [
    "OPPORTUNITY_BOOK_STORAGE_DURABLE",
    "OPPORTUNITY_BOOK_STORAGE_PROCESS_LOCAL",
    "LocalStateIntelligenceRepository",
    "open_local_state_intelligence_repository",
    "opportunity_book_health",
    "opportunity_book_storage",
    "reset_local_state_intelligence_repository_for_tests",
]
