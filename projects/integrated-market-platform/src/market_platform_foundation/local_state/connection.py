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


# SQLite primary result codes a bounded retry can outlast: BUSY, LOCKED, IOERR, CANTOPEN, PROTOCOL.
_TRANSIENT_SQLITE_CODES = frozenset({5, 6, 10, 14, 15})


def transient_storage_error(exc: BaseException) -> bool:
    """True for contention or I/O conditions that a bounded retry may outlast.

    Corruption, schema, constraint, identity and disk-full failures are never transient.
    """
    if isinstance(exc, sqlite3.OperationalError):
        code = getattr(exc, "sqlite_errorcode", None)
        if code is not None:
            return code & 0xFF in _TRANSIENT_SQLITE_CODES
        text = str(exc).lower()
        return any(token in text for token in ("locked", "busy", "disk i/o", "unable to open"))
    return isinstance(exc, OSError)


class LocalStateConnection:
    def __init__(self, path: Path, *, require_existing: bool = False,
                 expected_identity: tuple[int, int] | None = None) -> None:
        self.path = path
        self._lock = threading.RLock()
        if require_existing:
            if not self.path.is_file():
                raise FileNotFoundError("STATE_STORAGE_MISSING")
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            self.path.resolve().as_uri() + "?mode=rw" if require_existing else str(self.path),
            uri=require_existing,
            check_same_thread=False,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        try:
            if expected_identity is not None:
                stat = self.path.stat()
                if (stat.st_dev, stat.st_ino) != expected_identity:
                    raise FileNotFoundError('STATE_STORAGE_REPLACED')
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

    @property
    def in_transaction(self) -> bool:
        return bool(self._conn.in_transaction)

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

    def __enter__(self) -> LocalStateConnection:
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any) -> None:
        self.close()


class StateTransaction:
    def __init__(self, connection: LocalStateConnection) -> None:
        self.connection = connection

    def __enter__(self) -> LocalStateConnection:
        self.connection._lock.acquire()
        try:
            self.connection._conn.execute("BEGIN IMMEDIATE")
        except Exception:
            self.connection._lock.release()
            raise
        return self.connection

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any) -> None:
        try:
            if exc_type is None:
                try:
                    self.connection._conn.execute("COMMIT")
                except Exception:
                    if self.connection._conn.in_transaction:
                        self.connection._conn.execute("ROLLBACK")
                    raise
            else:
                self.connection._conn.execute("ROLLBACK")
        finally:
            self.connection._lock.release()
