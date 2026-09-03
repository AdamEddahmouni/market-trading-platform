"""Thread-safe SQLite connection with WAL and fail-closed integrity checks."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

from .migrations import SchemaVersionError, apply_migrations, current_schema_version
from .schema import SCHEMA_VERSION


class CorruptStateError(ValueError):
    """SQLite integrity_check failed; original file is preserved."""


class LocalStateConnection:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self.path),
            check_same_thread=False,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        try:
            self._configure()
            self._verify_or_raise()
            apply_migrations(self._conn)
        except Exception:
            self._conn.close()
            raise

    def _configure(self) -> None:
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=5000")

    def _verify_or_raise(self) -> None:
        row = self._conn.execute("PRAGMA integrity_check").fetchone()
        status = str(row[0]) if row is not None else "missing"
        if status != "ok":
            raise CorruptStateError(f"SQLITE_INTEGRITY_FAILED:{status}")

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, params)

    def executemany(self, sql: str, seq: list[tuple[Any, ...]]) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.executemany(sql, seq)

    def transaction(self) -> "StateTransaction":
        return StateTransaction(self)

    def backup(self, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            dest_conn = sqlite3.connect(str(dest))
            try:
                self._conn.backup(dest_conn)
            finally:
                dest_conn.close()

    def integrity_ok(self) -> bool:
        with self._lock:
            row = self._conn.execute("PRAGMA integrity_check").fetchone()
            return bool(row) and str(row[0]) == "ok"

    def schema_version(self) -> int:
        with self._lock:
            version = current_schema_version(self._conn)
        if version is None:
            raise SchemaVersionError("SCHEMA_MISSING")
        if version > SCHEMA_VERSION:
            raise SchemaVersionError(f"UNKNOWN_NEWER_SCHEMA:{version}")
        return version

    def close(self) -> None:
        with self._lock:
            self._conn.close()


class StateTransaction:
    def __init__(self, connection: LocalStateConnection) -> None:
        self.connection = connection

    def __enter__(self) -> LocalStateConnection:
        self.connection._lock.acquire()
        self.connection._conn.execute("BEGIN IMMEDIATE")
        return self.connection

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any) -> None:
        try:
            if exc_type is None:
                self.connection._conn.execute("COMMIT")
            else:
                self.connection._conn.execute("ROLLBACK")
        finally:
            self.connection._lock.release()
