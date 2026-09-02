"""OF-01 projection cursor and consumer contracts."""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from .errors import OF01Error, OF01ErrorCode
from .protocols import CommitBundle
from .sqlite_store import SQLiteAuthorityStore


class ProjectionState(StrEnum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    DEGRADED = "DEGRADED"
    REBUILD_REQUIRED = "REBUILD_REQUIRED"


@dataclass(frozen=True, slots=True)
class ProjectionStatus:
    projection_name: str
    projection_version: str
    source_ledger_authority_id: str
    last_applied_commit_sequence: int
    last_applied_commit_id: str | None
    source_high_water: int
    lag_commits: int
    last_success_at_ns: int | None
    last_error_code: str | None
    state: ProjectionState


class ProjectionConsumer(Protocol):
    def apply(self, bundle: CommitBundle) -> None: ...

    def reset(self) -> None: ...


class ProjectionCursorStore:
    def __init__(self, store: SQLiteAuthorityStore) -> None:
        self._store = store

    def get_status(
        self,
        *,
        projection_name: str,
        projection_version: str,
    ) -> ProjectionStatus:
        conn = self._store.connection
        row = conn.execute(
            """
            SELECT last_applied_commit_sequence, last_applied_commit_id,
                   last_success_at_ns, last_error_code
            FROM projection_cursors
            WHERE projection_name = ? AND projection_version = ?
              AND ledger_authority_id = ?
            """,
            (projection_name, projection_version, self._store.ledger_authority_id),
        ).fetchone()
        high_row = conn.execute("SELECT MAX(commit_sequence) FROM ledger_commits").fetchone()
        high_water = int(high_row[0]) if high_row and high_row[0] is not None else 0
        if row is None:
            return ProjectionStatus(
                projection_name=projection_name,
                projection_version=projection_version,
                source_ledger_authority_id=self._store.ledger_authority_id,
                last_applied_commit_sequence=0,
                last_applied_commit_id=None,
                source_high_water=high_water,
                lag_commits=high_water,
                last_success_at_ns=None,
                last_error_code=None,
                state=ProjectionState.STOPPED,
            )
        last_seq = int(row["last_applied_commit_sequence"])
        return ProjectionStatus(
            projection_name=projection_name,
            projection_version=projection_version,
            source_ledger_authority_id=self._store.ledger_authority_id,
            last_applied_commit_sequence=last_seq,
            last_applied_commit_id=row["last_applied_commit_id"],
            source_high_water=high_water,
            lag_commits=max(0, high_water - last_seq),
            last_success_at_ns=row["last_success_at_ns"],
            last_error_code=row["last_error_code"],
            state=ProjectionState.RUNNING if row["last_error_code"] is None else ProjectionState.DEGRADED,
        )

    def advance(
        self,
        *,
        projection_name: str,
        projection_version: str,
        commit_sequence: int,
        commit_id: str,
    ) -> None:
        now = time.time_ns()
        conn = self._store.connection
        conn.execute("BEGIN IMMEDIATE")
        try:
            existing = conn.execute(
                """
                SELECT last_applied_commit_sequence
                FROM projection_cursors
                WHERE projection_name = ? AND projection_version = ?
                  AND ledger_authority_id = ?
                """,
                (projection_name, projection_version, self._store.ledger_authority_id),
            ).fetchone()
            if existing is not None and int(existing[0]) >= commit_sequence:
                conn.execute("ROLLBACK")
                return
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO projection_cursors (
                      projection_name, projection_version, ledger_authority_id,
                      last_applied_commit_sequence, last_applied_commit_id,
                      last_success_at_ns, last_error_code
                    ) VALUES (?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        projection_name,
                        projection_version,
                        self._store.ledger_authority_id,
                        commit_sequence,
                        commit_id,
                        now,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE projection_cursors
                    SET last_applied_commit_sequence = ?,
                        last_applied_commit_id = ?,
                        last_success_at_ns = ?,
                        last_error_code = NULL
                    WHERE projection_name = ? AND projection_version = ?
                      AND ledger_authority_id = ?
                    """,
                    (
                        commit_sequence,
                        commit_id,
                        now,
                        projection_name,
                        projection_version,
                        self._store.ledger_authority_id,
                    ),
                )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def reset_cursor(
        self,
        *,
        projection_name: str,
        projection_version: str,
    ) -> None:
        conn = self._store.connection
        conn.execute(
            """
            DELETE FROM projection_cursors
            WHERE projection_name = ? AND projection_version = ?
              AND ledger_authority_id = ?
            """,
            (projection_name, projection_version, self._store.ledger_authority_id),
        )


class ProjectionReplayer:
    def __init__(
        self,
        *,
        stream: Callable[[int, int | None], Iterator[CommitBundle]],
        cursor_store: ProjectionCursorStore,
        projection_name: str,
        projection_version: str,
    ) -> None:
        self._stream = stream
        self._cursor_store = cursor_store
        self._projection_name = projection_name
        self._projection_version = projection_version

    def replay(
        self,
        consumer: ProjectionConsumer,
        *,
        from_sequence: int = 0,
        through_sequence: int | None = None,
    ) -> int:
        bundles = list(self._stream(from_sequence, through_sequence))
        applied = 0
        for bundle in bundles:
            consumer.apply(bundle)
            self._cursor_store.advance(
                projection_name=self._projection_name,
                projection_version=self._projection_version,
                commit_sequence=bundle.commit_sequence,
                commit_id=bundle.commit_id,
            )
            applied += 1
        return applied

    def rebuild(self, consumer: ProjectionConsumer) -> int:
        consumer.reset()
        self._cursor_store.reset_cursor(
            projection_name=self._projection_name,
            projection_version=self._projection_version,
        )
        return self.replay(consumer, from_sequence=0)
