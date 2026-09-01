"""Append-only SQLite-backed shadow record store (Platformization P6).

Follows the ``local_state`` durability patterns: WAL journal, busy timeout,
fail-closed integrity verification on open, and minimal idempotent migrations
(``CREATE TABLE IF NOT EXISTS`` only). The store is strictly append-only:
there is no UPDATE or DELETE anywhere in this module, and insert-once
semantics mean a duplicate content-addressed id is a no-op that returns the
existing row — never an overwrite.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterator

from .records import (
    ShadowIntegrityError,
    ShadowOutcomeLabel,
    ShadowPredictionRecord,
    ShadowRunManifest,
    verify_label,
    verify_manifest,
    verify_prediction,
)

SHADOW_STORE_SCHEMA_VERSION = "1"

_CREATE_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS shadow_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS shadow_runs (
        run_id TEXT PRIMARY KEY,
        manifest_json TEXT NOT NULL,
        manifest_hash TEXT NOT NULL,
        created_at_ns INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS shadow_predictions (
        prediction_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        decision_time_ns INTEGER NOT NULL,
        created_at_ns INTEGER NOT NULL,
        record_json TEXT NOT NULL,
        record_hash TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS shadow_labels (
        label_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        prediction_id TEXT NOT NULL,
        label_json TEXT NOT NULL,
        label_hash TEXT NOT NULL,
        UNIQUE(run_id, prediction_id)
    )
    """,
)


class ShadowStoreCorruptError(ValueError):
    """SQLite integrity_check failed; original file is preserved."""


def _row_to_prediction(row: sqlite3.Row) -> ShadowPredictionRecord:
    record = ShadowPredictionRecord(**json.loads(row["record_json"]))
    # Recompute identity from CONTENT, not just the stored column: a tampered
    # row whose embedded hash field was left intact is still detected.
    if row["record_hash"] != record.record_hash:
        raise ShadowIntegrityError("PREDICTION_HASH_MISMATCH")
    verify_prediction(record)
    return record


def _row_to_label(row: sqlite3.Row) -> ShadowOutcomeLabel:
    label = ShadowOutcomeLabel(**json.loads(row["label_json"]))
    if row["label_hash"] != label.label_hash:
        raise ShadowIntegrityError("LABEL_HASH_MISMATCH")
    verify_label(label)
    return label


class ShadowStore:
    """Durable append-only store for shadow runs, predictions, and labels."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._configure()
        self._verify_or_raise()
        self._apply_schema()

    def _configure(self) -> None:
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.execute("PRAGMA busy_timeout=5000")

    def _verify_or_raise(self) -> None:
        row = self._conn.execute("PRAGMA integrity_check").fetchone()
        status = str(row[0]) if row else ""
        if status != "ok":
            self._conn.close()
            raise ShadowStoreCorruptError(f"SQLITE_INTEGRITY_FAILED:{status}")

    def _apply_schema(self) -> None:
        with self._conn:
            for statement in _CREATE_STATEMENTS:
                self._conn.execute(statement)
            self._conn.execute(
                "INSERT OR IGNORE INTO shadow_meta(key, value) VALUES (?, ?)",
                ("schema_version", SHADOW_STORE_SCHEMA_VERSION),
            )

    # -- append-only writers -------------------------------------------------

    def append_manifest(
        self, manifest: ShadowRunManifest
    ) -> tuple[ShadowRunManifest, bool]:
        """Insert-once: duplicate run_id returns the stored manifest."""
        verify_manifest(manifest)
        with self._lock:
            existing = self._conn.execute(
                "SELECT * FROM shadow_runs WHERE run_id = ?", (manifest.run_id,)
            ).fetchone()
            if existing is not None:
                stored = ShadowRunManifest(**json.loads(existing["manifest_json"]))
                verify_manifest(stored)
                if existing["manifest_hash"] != stored.manifest_hash:
                    raise ShadowIntegrityError("MANIFEST_HASH_MISMATCH")
                return stored, False
            with self._conn:
                self._conn.execute(
                    "INSERT INTO shadow_runs"
                    "(run_id, manifest_json, manifest_hash, created_at_ns)"
                    " VALUES (?, ?, ?, ?)",
                    (
                        manifest.run_id,
                        json.dumps(manifest.__dict__, sort_keys=True),
                        manifest.manifest_hash,
                        manifest.created_at_ns,
                    ),
                )
        return manifest, True

    def append_prediction(
        self, record: ShadowPredictionRecord
    ) -> tuple[ShadowPredictionRecord, bool]:
        """Insert-once: duplicate prediction_id returns the stored record."""
        verify_prediction(record)
        with self._lock:
            existing = self._conn.execute(
                "SELECT * FROM shadow_predictions WHERE prediction_id = ?",
                (record.prediction_id,),
            ).fetchone()
            if existing is not None:
                return _row_to_prediction(existing), False
            with self._conn:
                self._conn.execute(
                    "INSERT INTO shadow_predictions"
                    "(prediction_id, run_id, decision_time_ns, created_at_ns,"
                    " record_json, record_hash) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        record.prediction_id,
                        record.run_id,
                        record.decision_time_ns,
                        record.created_at_ns,
                        json.dumps(record.__dict__, sort_keys=True),
                        record.record_hash,
                    ),
                )
        return record, True

    def append_label(self, label: ShadowOutcomeLabel) -> tuple[ShadowOutcomeLabel, bool]:
        """Insert-once per (run_id, prediction_id): never overwrite a label."""
        verify_label(label)
        with self._lock:
            existing = self._conn.execute(
                "SELECT * FROM shadow_labels WHERE run_id = ? AND prediction_id = ?",
                (label.run_id, label.prediction_id),
            ).fetchone()
            if existing is not None:
                return _row_to_label(existing), False
            with self._conn:
                self._conn.execute(
                    "INSERT INTO shadow_labels"
                    "(label_id, run_id, prediction_id, label_json, label_hash)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (
                        label.label_id,
                        label.run_id,
                        label.prediction_id,
                        json.dumps(label.__dict__, sort_keys=True),
                        label.label_hash,
                    ),
                )
        return label, True

    # -- readers -------------------------------------------------------------

    def get_prediction(self, prediction_id: str) -> ShadowPredictionRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM shadow_predictions WHERE prediction_id = ?",
                (prediction_id,),
            ).fetchone()
        return None if row is None else _row_to_prediction(row)

    def iter_predictions(self, run_id: str) -> Iterator[ShadowPredictionRecord]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM shadow_predictions WHERE run_id = ?"
                " ORDER BY decision_time_ns ASC, prediction_id ASC",
                (run_id,),
            ).fetchall()
        for row in rows:
            yield _row_to_prediction(row)

    def get_label_for_run_prediction(
        self, run_id: str, prediction_id: str
    ) -> ShadowOutcomeLabel | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM shadow_labels WHERE run_id = ? AND prediction_id = ?",
                (run_id, prediction_id),
            ).fetchone()
        return None if row is None else _row_to_label(row)

    def iter_labels(self, run_id: str) -> Iterator[ShadowOutcomeLabel]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM shadow_labels WHERE run_id = ? ORDER BY label_id ASC",
                (run_id,),
            ).fetchall()
        for row in rows:
            yield _row_to_label(row)

    def get_manifest(self, run_id: str) -> ShadowRunManifest | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM shadow_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        if row is None:
            return None
        stored = ShadowRunManifest(**json.loads(row["manifest_json"]))
        verify_manifest(stored)
        return stored

    def counts(self) -> dict[str, int]:
        with self._lock:
            def _count(table: str) -> int:
                row = self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                return int(row[0])

            return {
                "runs": _count("shadow_runs"),
                "predictions": _count("shadow_predictions"),
                "labels": _count("shadow_labels"),
            }

    # -- lifecycle -----------------------------------------------------------

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "ShadowStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


__all__ = [
    "SHADOW_STORE_SCHEMA_VERSION",
    "ShadowStore",
    "ShadowStoreCorruptError",
]
