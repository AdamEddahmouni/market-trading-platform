"""Append-only experiment ledger for prospective shadow runs (P6 Run 1).

Nothing here UPDATEs or DELETEs: the run contract is immutable, lifecycle
and decision facts are insert-only, and run state is derived from events
(spec sections 8-9). Nothing can rewrite what was claimed at decision time.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterator

SCHEMA_VERSION = "platform/shadow/experiment/1"

LIFECYCLE_EVENTS = ("CREATED", "OPEN", "CLOSED", "LABELING", "FULLY_LABELED", "REPORTED")


class ShadowExperimentStore:
    """Append-only ledger composing the governed ShadowStore predictions."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._path, timeout=30.0, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=30000")
        self._apply_schema()

    def _apply_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS experiment_meta (
                key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS run_contract (
                run_id TEXT PRIMARY KEY,
                manifest_json TEXT NOT NULL,
                manifest_hash TEXT NOT NULL,
                created_at_ns INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS run_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                occurred_at_ns INTEGER NOT NULL,
                detail_json TEXT NOT NULL,
                UNIQUE(run_id, event_type, occurred_at_ns));
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                instrument_id TEXT NOT NULL,
                decision_bucket INTEGER NOT NULL,
                outcome TEXT NOT NULL,
                prediction_id TEXT,
                detail_json TEXT NOT NULL,
                created_at_ns INTEGER NOT NULL,
                UNIQUE(run_id, instrument_id, decision_bucket));
            CREATE TABLE IF NOT EXISTS decision_annotations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_id INTEGER NOT NULL REFERENCES decisions(id),
                kind TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at_ns INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS recorder_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                occurred_at_ns INTEGER NOT NULL,
                error_code TEXT NOT NULL,
                detail_json TEXT NOT NULL);
            """
        )
        row = self._conn.execute(
            "SELECT value FROM experiment_meta WHERE key='schema_version'"
        ).fetchone()
        if row is None:
            self._conn.execute(
                "INSERT INTO experiment_meta(key, value) VALUES ('schema_version', ?)",
                (SCHEMA_VERSION,),
            )
        elif row[0] != SCHEMA_VERSION:
            raise ValueError("EXPERIMENT_STORE_SCHEMA_MISMATCH")
        self._conn.commit()

    # -- runs ---------------------------------------------------------------

    def ensure_run(self, run_id: str, manifest_json: str, manifest_hash: str, created_at_ns: int) -> bool:
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT INTO run_contract(run_id, manifest_json, manifest_hash, created_at_ns)"
                    " VALUES (?, ?, ?, ?)",
                    (run_id, manifest_json, manifest_hash, int(created_at_ns)),
                )
                self._conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def manifest(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT run_id, manifest_json, manifest_hash, created_at_ns"
                " FROM run_contract WHERE run_id=?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "run_id": row[0],
            "manifest": json.loads(row[1]),
            "manifest_hash": row[2],
            "created_at_ns": row[3],
        }

    def manifest_hash(self, run_id: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT manifest_hash FROM run_contract WHERE run_id=?",
                (run_id,),
            ).fetchone()
        return None if row is None else str(row[0])

    # -- lifecycle -------------------------------------------------------------

    def append_event(self, run_id: str, event_type: str, occurred_at_ns: int, detail: dict[str, Any] | None = None) -> None:
        if event_type not in LIFECYCLE_EVENTS:
            raise ValueError(f"LIFECYCLE_EVENT_UNKNOWN:{event_type}")
        with self._lock:
            self._conn.execute(
                "INSERT INTO run_events(run_id, event_type, occurred_at_ns, detail_json)"
                " VALUES (?, ?, ?, ?)",
                (run_id, event_type, int(occurred_at_ns), json.dumps(dict(detail or {}), sort_keys=True)),
            )
            self._conn.commit()

    def events(self, run_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT event_type, occurred_at_ns, detail_json FROM run_events"
                " WHERE run_id=? ORDER BY id",
                (run_id,),
            ).fetchall()
        return [
            {"event_type": r[0], "occurred_at_ns": r[1], "detail": json.loads(r[2])}
            for r in rows
        ]

    def run_state(self, run_id: str) -> str | None:
        if self.manifest(run_id) is None:
            return None
        found = self.events(run_id)
        return found[-1]["event_type"] if found else "CREATED"

    # -- decisions ----------------------------------------------------------------

    def record_decision(
        self,
        run_id: str,
        instrument_id: str,
        decision_bucket: int,
        outcome: str,
        *,
        prediction_id: str | None = None,
        detail: dict[str, Any] | None = None,
        created_at_ns: int,
    ) -> tuple[int, bool]:
        with self._lock:
            try:
                cursor = self._conn.execute(
                    "INSERT INTO decisions(run_id, instrument_id, decision_bucket, outcome,"
                    " prediction_id, detail_json, created_at_ns) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        run_id,
                        instrument_id,
                        int(decision_bucket),
                        outcome,
                        prediction_id,
                        json.dumps(dict(detail or {}), sort_keys=True),
                        int(created_at_ns),
                    ),
                )
                self._conn.commit()
                return int(cursor.lastrowid), True
            except sqlite3.IntegrityError:
                self._conn.rollback()
                row = self._conn.execute(
                    "SELECT id FROM decisions WHERE run_id=? AND instrument_id=? AND decision_bucket=?",
                    (run_id, instrument_id, int(decision_bucket)),
                ).fetchone()
                return (int(row[0]) if row is not None else -1), False

    def record_decision_once(self, *args: Any, **kwargs: Any) -> tuple[int | None, bool]:
        """Insert-once variant: returns (None, False) when the bucket is taken."""
        decision_id, inserted = self.record_decision(*args, **kwargs)
        return (decision_id if inserted else None), inserted

    def has_decision(self, run_id: str, instrument_id: str, decision_bucket: int) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM decisions WHERE run_id=? AND instrument_id=? AND decision_bucket=?",
                (run_id, instrument_id, int(decision_bucket)),
            ).fetchone()
        return row is not None

    def _decision_row(self, row: tuple) -> dict[str, Any]:
        return {
            "id": row[0],
            "run_id": row[1],
            "instrument_id": row[2],
            "decision_bucket": row[3],
            "outcome": row[4],
            "prediction_id": row[5],
            "detail": json.loads(row[6]),
            "created_at_ns": row[7],
        }

    _DECISION_SELECT = (
        "SELECT id, run_id, instrument_id, decision_bucket, outcome, prediction_id,"
        " detail_json, created_at_ns FROM decisions"
    )

    def decision(self, decision_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                self._DECISION_SELECT + " WHERE id=?", (int(decision_id),)
            ).fetchone()
        return None if row is None else self._decision_row(row)

    def iter_decisions(self, run_id: str, outcome: str | None = None) -> Iterator[dict[str, Any]]:
        sql = self._DECISION_SELECT + " WHERE run_id=?"
        params: list[Any] = [run_id]
        if outcome is not None:
            sql += " AND outcome=?"
            params.append(outcome)
        with self._lock:
            rows = list(self._conn.execute(sql + " ORDER BY decision_bucket", params))
        for row in rows:
            yield self._decision_row(row)

    def count_outcomes(self, run_id: str) -> dict[str, int]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT outcome, COUNT(*) FROM decisions WHERE run_id=? GROUP BY outcome",
                (run_id,),
            ).fetchall()
        return {r[0]: r[1] for r in rows}

    # -- annotations ---------------------------------------------------------

    def add_annotation(self, decision_id: int, kind: str, payload: dict[str, Any], created_at_ns: int) -> bool:
        if self.decision(decision_id) is None:
            return False
        with self._lock:
            self._conn.execute(
                "INSERT INTO decision_annotations(decision_id, kind, payload_json, created_at_ns)"
                " VALUES (?, ?, ?, ?)",
                (int(decision_id), kind, json.dumps(dict(payload), sort_keys=True), int(created_at_ns)),
            )
            self._conn.commit()
        return True

    def annotations(self, decision_id: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT kind, payload_json, created_at_ns FROM decision_annotations"
                " WHERE decision_id=? ORDER BY id",
                (int(decision_id),),
            ).fetchall()
        return [
            {"kind": r[0], "payload": json.loads(r[1]), "created_at_ns": r[2]}
            for r in rows
        ]

    # -- operational failures ----------------------------------------------------

    def log_error(self, run_id: str, occurred_at_ns: int, error_code: str, detail: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO recorder_errors(run_id, occurred_at_ns, error_code, detail_json)"
                " VALUES (?, ?, ?, ?)",
                (run_id, int(occurred_at_ns), error_code, json.dumps(dict(detail), sort_keys=True)),
            )
            self._conn.commit()

    def recorder_errors(self, run_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT occurred_at_ns, error_code, detail_json FROM recorder_errors"
                " WHERE run_id=? ORDER BY id",
                (run_id,),
            ).fetchall()
        return [
            {"occurred_at_ns": r[0], "error_code": r[1], "detail": json.loads(r[2])}
            for r in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "ShadowExperimentStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
