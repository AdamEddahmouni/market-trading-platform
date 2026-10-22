"""OCT1-09 Paper experiment records and equity snapshots on the local-state DB.

The creation record is immutable; only status and the close facts advance.
Equity snapshots are append-only. Persist-off keeps the same contract in
process memory (INTENTIONAL_EPHEMERAL).
"""
from __future__ import annotations

import json
import threading
from typing import Any

from .paths import persistence_enabled
from .startup import open_local_state

MAX_PAGE = 100


def _encode(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class PaperExperimentRepository:
    def __init__(self, connection=None) -> None:
        self.connection = connection
        self.lock = threading.RLock()
        self._experiments: dict[str, dict[str, Any]] = {}
        self._snapshots: list[dict[str, Any]] = []
        if connection is not None:
            with connection.transaction():
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS paper_experiments ("
                    "experiment_id TEXT PRIMARY KEY, created_at INTEGER NOT NULL, status TEXT NOT NULL, "
                    "ended_at INTEGER, payload TEXT NOT NULL, closing TEXT)"
                )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS paper_equity_snapshots ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, experiment_id TEXT NOT NULL, "
                    "state_hash TEXT NOT NULL, captured_at INTEGER NOT NULL, payload TEXT NOT NULL)"
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS paper_equity_snapshot_history "
                    "ON paper_equity_snapshots(experiment_id, id)"
                )

    @property
    def durability(self) -> str:
        return "SQLITE_LOCAL_STATE" if self.connection else "INTENTIONAL_EPHEMERAL"

    def _write(self, operation):
        with self.lock:
            if self.connection and not self.connection.in_transaction:
                with self.connection.transaction():
                    return operation()
            return operation()

    @staticmethod
    def _row(payload: str, status: str, ended_at: int | None, closing: str | None) -> dict[str, Any]:
        record = json.loads(payload)
        record["status"] = status
        record["ended_at_ns"] = ended_at
        record["closing"] = json.loads(closing) if closing else None
        return record

    def create(self, record: dict[str, Any], *, status: str) -> None:
        experiment_id = str(record["experiment_id"])

        def write() -> None:
            if self.get(experiment_id) is not None:
                raise ValueError("IMMUTABLE_EXPERIMENT_COLLISION")
            if self.connection:
                self.connection.execute(
                    "INSERT INTO paper_experiments(experiment_id, created_at, status, ended_at, payload, closing) "
                    "VALUES (?, ?, ?, NULL, ?, NULL)",
                    (experiment_id, int(record["created_at_ns"]), status, _encode(record)),
                )
            else:
                self._experiments[experiment_id] = {
                    "closing": None,
                    "created_at": int(record["created_at_ns"]),
                    "ended_at": None,
                    "payload": _encode(record),
                    "status": status,
                }

        self._write(write)

    def get(self, experiment_id: str) -> dict[str, Any] | None:
        with self.lock:
            if self.connection:
                row = self.connection.execute(
                    "SELECT payload, status, ended_at, closing FROM paper_experiments WHERE experiment_id=?",
                    (experiment_id,),
                ).fetchone()
                return self._row(row[0], row[1], row[2], row[3]) if row else None
            row = self._experiments.get(experiment_id)
            return self._row(row["payload"], row["status"], row["ended_at"], row["closing"]) if row else None

    def list(self, *, limit: int = 25, status: str | None = None) -> list[dict[str, Any]]:
        limit = min(max(int(limit), 1), MAX_PAGE)
        with self.lock:
            if self.connection:
                if status:
                    rows = self.connection.execute(
                        "SELECT payload, status, ended_at, closing FROM paper_experiments "
                        "WHERE status=? ORDER BY created_at DESC LIMIT ?",
                        (status, limit),
                    ).fetchall()
                else:
                    rows = self.connection.execute(
                        "SELECT payload, status, ended_at, closing FROM paper_experiments "
                        "ORDER BY created_at DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
                return [self._row(r[0], r[1], r[2], r[3]) for r in rows]
            rows = sorted(self._experiments.values(), key=lambda r: r["created_at"], reverse=True)
            if status:
                rows = [r for r in rows if r["status"] == status]
            return [self._row(r["payload"], r["status"], r["ended_at"], r["closing"]) for r in rows[:limit]]

    def count(self) -> int:
        with self.lock:
            if self.connection:
                return int(self.connection.execute("SELECT COUNT(*) FROM paper_experiments").fetchone()[0])
            return len(self._experiments)

    def close(self, experiment_id: str, *, ended_at_ns: int, closing: dict[str, Any], status: str) -> None:
        def write() -> None:
            current = self.get(experiment_id)
            if current is None:
                raise ValueError("EXPERIMENT_NOT_FOUND")
            if current["status"] == status:
                raise ValueError("EXPERIMENT_ALREADY_CLOSED")
            if self.connection:
                self.connection.execute(
                    "UPDATE paper_experiments SET status=?, ended_at=?, closing=? WHERE experiment_id=?",
                    (status, int(ended_at_ns), _encode(closing), experiment_id),
                )
            else:
                row = self._experiments[experiment_id]
                row.update({"closing": _encode(closing), "ended_at": int(ended_at_ns), "status": status})

        self._write(write)

    def latest_snapshot(self, experiment_id: str) -> dict[str, Any] | None:
        rows = self.snapshots(experiment_id, limit=1)
        return rows[0] if rows else None

    def append_snapshot(self, experiment_id: str, *, state_hash: str, captured_at_ns: int, payload: dict[str, Any]) -> bool:
        """Append one snapshot unless it repeats the latest recorded state."""

        def write() -> bool:
            latest = self.latest_snapshot(experiment_id)
            if latest is not None and latest["state_hash"] == state_hash:
                return False
            body = {**payload, "captured_at_ns": int(captured_at_ns), "state_hash": state_hash}
            if self.connection:
                self.connection.execute(
                    "INSERT INTO paper_equity_snapshots(experiment_id, state_hash, captured_at, payload) "
                    "VALUES (?, ?, ?, ?)",
                    (experiment_id, state_hash, int(captured_at_ns), _encode(body)),
                )
            else:
                self._snapshots.append(
                    {"experiment_id": experiment_id, "id": len(self._snapshots) + 1, "payload": _encode(body)}
                )
            return True

        return bool(self._write(write))

    def snapshots(self, experiment_id: str, *, limit: int = 50, before: int | None = None) -> list[dict[str, Any]]:
        """Newest-first page; ``before`` is the snapshot id cursor."""
        limit = min(max(int(limit), 1), MAX_PAGE)
        with self.lock:
            if self.connection:
                if before is None:
                    rows = self.connection.execute(
                        "SELECT id, payload FROM paper_equity_snapshots WHERE experiment_id=? "
                        "ORDER BY id DESC LIMIT ?",
                        (experiment_id, limit),
                    ).fetchall()
                else:
                    rows = self.connection.execute(
                        "SELECT id, payload FROM paper_equity_snapshots WHERE experiment_id=? AND id<? "
                        "ORDER BY id DESC LIMIT ?",
                        (experiment_id, int(before), limit),
                    ).fetchall()
                return [{**json.loads(r[1]), "snapshot_id": int(r[0])} for r in rows]
            rows = [r for r in self._snapshots if r["experiment_id"] == experiment_id]
            if before is not None:
                rows = [r for r in rows if r["id"] < int(before)]
            rows = sorted(rows, key=lambda r: r["id"], reverse=True)[:limit]
            return [{**json.loads(r["payload"]), "snapshot_id": int(r["id"])} for r in rows]

    def snapshot_count(self, experiment_id: str) -> int:
        with self.lock:
            if self.connection:
                return int(
                    self.connection.execute(
                        "SELECT COUNT(*) FROM paper_equity_snapshots WHERE experiment_id=?", (experiment_id,)
                    ).fetchone()[0]
                )
            return sum(1 for r in self._snapshots if r["experiment_id"] == experiment_id)


_REPOSITORY: PaperExperimentRepository | None = None
_CONNECTION: Any = None


def paper_experiment_repository() -> PaperExperimentRepository:
    global _REPOSITORY, _CONNECTION
    local = open_local_state() if persistence_enabled() else None
    connection = local.connection if local else None
    # Holding the connection itself (not its id) so a reopened database is never mistaken for the old one.
    if _REPOSITORY is None or connection is not _CONNECTION:
        _REPOSITORY = PaperExperimentRepository(connection)
        _CONNECTION = connection
    return _REPOSITORY


def reset_paper_experiment_repository_for_tests() -> None:
    global _REPOSITORY, _CONNECTION
    _REPOSITORY = None
    _CONNECTION = None
