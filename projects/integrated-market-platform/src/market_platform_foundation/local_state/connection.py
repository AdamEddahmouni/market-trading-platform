"""Thread-safe SQLite connection with WAL and fail-closed integrity checks."""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from .migrations import SchemaVersionError, apply_migrations, current_schema_version
from .schema import SCHEMA_VERSION


class CorruptStateError(ValueError):
    """SQLite integrity_check failed; original file is preserved."""


# SQLite primary result codes a bounded retry can outlast: BUSY, LOCKED, IOERR, CANTOPEN, PROTOCOL.
_TRANSIENT_SQLITE_CODES = frozenset({5, 6, 10, 14, 15})
_CONTENTION_SQLITE_CODES = frozenset({5, 6})  # BUSY, LOCKED

# A write that meets a busy neighbour waits this long before the connection reports the contention. The
# explicit transaction retry below adds the rest of its window; both are bounded and environment-overridable.
_DEFAULT_BUSY_TIMEOUT_MS = 15000
_DEFAULT_TRANSACTION_WAIT_SECONDS = 5.0
# Critical unattended writes (automation receipts, leases, risk stops) opt into the explicit window.
CRITICAL_WRITE_RETRY_SECONDS = 5.0


def transient_storage_error(exc: BaseException) -> bool:
    """True for contention or I/O conditions that a bounded retry may outlast.

    Corruption, schema, constraint, identity and disk-full failures are never transient.
    """
    if isinstance(exc, sqlite3.OperationalError):
        code = getattr(exc, "sqlite_errorcode", None)
        if code is not None and code != 0:
            return code & 0xFF in _TRANSIENT_SQLITE_CODES
        # Code 0 (or absent) is not a licence to retry every programming error. SQLite's "not an error"
        # is the lost-code case a busy BEGIN can report; cursor-lifecycle messages are faults, not contention.
        text = str(exc).lower()
        return text == "not an error" or any(
            token in text for token in ("locked", "busy", "disk i/o", "unable to open"))
    return isinstance(exc, OSError)


def lock_contention_error(exc: BaseException) -> bool:
    """True when another connection held the write lock past this connection's busy timeout.

    Contention means a busy neighbour or a slow disk, not a fault in the store (2026-10-21..23 stalls).
    """
    if not isinstance(exc, sqlite3.OperationalError):
        return False
    code = getattr(exc, "sqlite_errorcode", None)
    if code is not None and code != 0:
        return code & 0xFF in _CONTENTION_SQLITE_CODES
    text = str(exc).lower()
    return text == "not an error" or "locked" in text or "busy" in text


def lock_retry_window_seconds(name: str) -> float:
    """How long a worker keeps retrying lock contention before it reports that it gave up."""
    return float(os.environ.get(name, "600"))


def _busy_timeout_ms() -> int:
    try:
        return max(0, int(os.environ.get("IMP_STATE_BUSY_TIMEOUT_MS", _DEFAULT_BUSY_TIMEOUT_MS)))
    except (TypeError, ValueError):
        return _DEFAULT_BUSY_TIMEOUT_MS


def _transaction_wait_seconds(default: float = 0.0) -> float:
    raw = os.environ.get("IMP_STATE_TRANSACTION_LOCK_WAIT_SECONDS")
    if raw is None:
        return default
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return default


def verified_by_supervisor() -> bool:
    """A supervised collection child opens the store its supervisor's own connection verified moments earlier."""
    return bool(os.environ.get("IMP_PF01_SUPERVISOR_OWNER"))


class _MaterializedCursor:
    """The rows of one completed statement, fetched while the shared connection lock was held.

    Python's sqlite3 returns a live cursor that is stepped again on ``fetchone``/``fetchall``. With one
    connection shared by the API, the automation worker and the reevaluation loops, a second thread could
    execute between ``execute`` and that step. SQLite then reports the wrong statement's state or error
    ("another row available", "no more rows available"), and a busy error could be read as a different code.
    Reading the bounded result inside the lock and exposing only its rows removes that cursor lifecycle.
    """

    def __init__(self, cursor: sqlite3.Cursor) -> None:
        self._rows = cursor.fetchall()
        self._index = 0
        self.rowcount = getattr(cursor, "rowcount", -1)
        self.lastrowid = getattr(cursor, "lastrowid", None)
        self.description = getattr(cursor, "description", None)
        self.closed = False

    def fetchone(self) -> Any:
        if self._index >= len(self._rows):
            return None
        row = self._rows[self._index]
        self._index += 1
        return row

    def fetchmany(self, size: int | None = None) -> list[Any]:
        if size is None or size < 0:
            size = len(self._rows) - self._index
        start, end = self._index, min(len(self._rows), self._index + size)
        self._index = end
        return self._rows[start:end]

    def fetchall(self) -> list[Any]:
        rows = self._rows[self._index:]
        self._index = len(self._rows)
        return rows

    def __iter__(self):
        return iter(self._rows[self._index:])

    def __next__(self) -> Any:
        row = self.fetchone()
        if row is None:
            raise StopIteration
        return row

    def close(self) -> None:
        self.closed = True

    def __enter__(self) -> "_MaterializedCursor":
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any) -> None:
        self.close()


class LocalStateConnection:
    def __init__(self, path: Path, *, require_existing: bool = False,
                 expected_identity: tuple[int, int] | None = None, verify: bool | None = None) -> None:
        # A full integrity_check reads the whole file: about 75 s per open for the 6.7 GB store on a hard drive,
        # three times per collector child start. The first opener (API, supervisor, unsupervised run) still checks.
        verify = not verified_by_supervisor() if verify is None else verify
        self.path = path
        self._lock = threading.RLock()
        # A transaction belongs to one thread. Nested ``with connection.transaction()`` calls on that thread
        # are re-entrant; another thread waits for the outer transaction instead of joining it implicitly.
        self._tx_owner: int | None = None
        self._tx_depth = 0
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
            if verify:
                self._verify_or_raise()
            apply_migrations(self._conn)
        except Exception:
            self._conn.close()
            raise

    def _configure(self) -> None:
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute(f"PRAGMA busy_timeout={_busy_timeout_ms()}")

    def _verify_or_raise(self) -> None:
        row = self._conn.execute("PRAGMA integrity_check").fetchone()
        status = str(row[0]) if row is not None else "missing"
        if status != "ok":
            raise CorruptStateError(f"SQLITE_INTEGRITY_FAILED:{status}")

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> _MaterializedCursor:
        with self._lock:
            return _MaterializedCursor(self._conn.execute(sql, params))

    def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        """Read one row with the fetch inside the connection lock.

        Fetching from the cursor ``execute`` returned steps the shared connection outside the lock,
        which can replace the result code of another thread's failing statement.
        """
        return self.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[Any]:
        return self.execute(sql, params).fetchall()

    def executemany(self, sql: str, seq: list[tuple[Any, ...]]) -> _MaterializedCursor:
        with self._lock:
            return _MaterializedCursor(self._conn.executemany(sql, seq))

    def transaction(self, *, retry_seconds: float | None = None) -> "StateTransaction":
        """One write transaction. ``retry_seconds`` opts into the explicit contention window.

        The default leaves waiting to SQLite's bounded busy timeout, so callers that run their own
        retry/backoff policy (the news collector, the market writer) keep the timing they own.
        """
        return StateTransaction(self, retry_seconds=retry_seconds)

    @property
    def in_transaction(self) -> bool:
        """True only when the calling thread owns this connection's active transaction."""
        return self._tx_depth > 0 and self._tx_owner == threading.get_ident()

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
            try:
                if self._conn.in_transaction:
                    try:
                        self._conn.execute("ROLLBACK")
                    except sqlite3.OperationalError:
                        pass
            except sqlite3.ProgrammingError:
                pass  # already closed by its repository; closing twice stays harmless
            self._tx_owner, self._tx_depth = None, 0
            try:
                self._conn.close()
            except sqlite3.ProgrammingError:
                pass

    def __enter__(self) -> LocalStateConnection:
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any) -> None:
        self.close()


class StateTransaction:
    """A bounded, re-entrant write transaction.

    ``BEGIN IMMEDIATE`` is retried only for genuine BUSY/LOCKED contention. A syntax, constraint or
    programming error is raised at once. COMMIT is retried in the same bounded window; a transaction that
    cannot commit is rolled back before the error leaves this context.
    """

    def __init__(self, connection: LocalStateConnection, *, retry_seconds: float | None = None) -> None:
        self.connection = connection
        self.retry_seconds = max(0.0, float(
            _transaction_wait_seconds(0.0) if retry_seconds is None else retry_seconds))
        self._nested = False

    def __enter__(self) -> LocalStateConnection:
        conn = self.connection
        conn._lock.acquire()
        try:
            if conn._tx_owner == threading.get_ident():
                conn._tx_depth += 1
                self._nested = True
                return conn
            self._begin_immediate(conn)
            conn._tx_owner, conn._tx_depth = threading.get_ident(), 1
            return conn
        except Exception:
            conn._lock.release()
            raise

    def _begin_immediate(self, conn: LocalStateConnection) -> None:
        deadline = time.monotonic() + self.retry_seconds
        delay = 0.01
        while True:
            try:
                conn._conn.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError as exc:
                if (not self.retry_seconds or not lock_contention_error(exc)
                        or time.monotonic() >= deadline):
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 0.25)
                continue
            if conn._conn.in_transaction:
                return
            # A refused BEGIN whose failure was lost must not let the body run in autocommit.
            if not self.retry_seconds or time.monotonic() >= deadline:
                raise sqlite3.OperationalError("database is locked: transaction did not start")
            time.sleep(delay)
            delay = min(delay * 2, 0.25)

    def _commit(self, conn: LocalStateConnection) -> None:
        deadline = time.monotonic() + self.retry_seconds
        delay = 0.01
        while True:
            try:
                conn._conn.execute("COMMIT")
                return
            except sqlite3.OperationalError as exc:
                if (not self.retry_seconds or not lock_contention_error(exc)
                        or time.monotonic() >= deadline):
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 0.25)

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any) -> None:
        conn = self.connection
        try:
            if self._nested:
                conn._tx_depth -= 1
                return
            try:
                if exc_type is None:
                    try:
                        self._commit(conn)
                    except Exception:
                        if conn._conn.in_transaction:
                            try:
                                conn._conn.execute("ROLLBACK")
                            except sqlite3.OperationalError:
                                pass
                        raise
                elif conn._conn.in_transaction:
                    try:
                        conn._conn.execute("ROLLBACK")
                    except sqlite3.OperationalError:
                        # The body's exception is the one that must reach the caller.
                        pass
            finally:
                conn._tx_owner, conn._tx_depth = None, 0
        finally:
            conn._lock.release()
