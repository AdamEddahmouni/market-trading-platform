"""Thread-safe SQLite connection with WAL and fail-closed integrity checks."""

from __future__ import annotations

import logging
import os
import re
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import integrity_receipt as receipts
from .migrations import SchemaVersionError, apply_migrations, current_schema_version
from .schema import SCHEMA_VERSION


class CorruptStateError(ValueError):
    """SQLite integrity_check failed; original file is preserved."""


# SQLite primary result codes a bounded retry can outlast: BUSY, LOCKED, IOERR, CANTOPEN, PROTOCOL.
_TRANSIENT_SQLITE_CODES = frozenset({5, 6, 10, 14, 15})
_CONTENTION_SQLITE_CODES = frozenset({5, 6})  # BUSY, LOCKED
_CORRUPTION_SQLITE_CODES = frozenset({11, 26})  # CORRUPT, NOTADB

# A write that meets a busy neighbour waits this long before the connection reports the contention. The
# explicit transaction retry below adds the rest of its window; both are bounded and environment-overridable.
_DEFAULT_BUSY_TIMEOUT_MS = 15000
_DEFAULT_TRANSACTION_WAIT_SECONDS = 5.0
# Critical unattended writes (automation receipts, leases, risk stops) opt into the explicit window.
CRITICAL_WRITE_RETRY_SECONDS = 5.0
# AUD-044 (2026-10-29): a write that met a foreign write lock used to wait out the whole busy timeout while holding
# the shared connection lock, so every API read queued behind it (15.7 s behind one waiting write, 39.3 s behind
# three). Writes now wait in short slices and release the shared lock between them, within the same total budget,
# and plain SELECTs from threads that do not hold the shared lock read through their own query-only connections
# (a WAL reader never waits for a writer). IMP_STATE_LEGACY_SHARED_LOCK=1 restores the previous behaviour.
_SHORT_BUSY_TIMEOUT_MS = 50
_DEFAULT_READ_POOL_SIZE = 4
# A wait for the write lock longer than this is logged with its timestamps (CA-7: lock waits were unmeasurable).
_SLOW_LOCK_WAIT_SECONDS = 1.0
_PRAGMA_BUSY_TIMEOUT = re.compile(r"\s*PRAGMA\s+busy_timeout\s*=\s*(\d+)\s*;?\s*$", re.IGNORECASE)

_log = logging.getLogger(__name__)


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


def corruption_error(exc: BaseException) -> bool:
    """True when SQLite reports a damaged file: the store's receipt no longer stands."""
    if not isinstance(exc, sqlite3.DatabaseError):
        return False
    code = getattr(exc, "sqlite_errorcode", None)
    if code is not None and code != 0:
        return code & 0xFF in _CORRUPTION_SQLITE_CODES
    text = str(exc).lower()
    return "malformed" in text or "not a database" in text


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


def _legacy_shared_lock() -> bool:
    return os.environ.get("IMP_STATE_LEGACY_SHARED_LOCK") == "1"


def _read_pool_size() -> int:
    try:
        return max(0, int(os.environ.get("IMP_STATE_READ_POOL", _DEFAULT_READ_POOL_SIZE)))
    except (TypeError, ValueError):
        return _DEFAULT_READ_POOL_SIZE


def _plain_select(sql: str) -> bool:
    """A single read statement that a query-only connection can answer with the same rows."""
    return sql.lstrip()[:6].upper() == "SELECT"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


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


class _ReadPool:
    """Query-only connections for plain SELECTs, so a read never queues behind a write waiting on SQLite's lock.

    Each statement borrows one idle connection (or opens one, up to ``size``) and materialises its rows before
    returning it. An autocommit SELECT starts its own WAL read snapshot, so it sees every committed write.
    """

    def __init__(self, path: Path, size: int, busy_timeout_ms: int) -> None:
        self._uri = path.resolve().as_uri() + "?mode=rw"
        self._busy_timeout_ms = busy_timeout_ms
        self._idle: list[sqlite3.Connection] = []
        self._guard = threading.Lock()
        self._slots = threading.BoundedSemaphore(size)
        self._closed = False

    def _open(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._uri, uri=True, check_same_thread=False, isolation_level=None)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute(f"PRAGMA busy_timeout={self._busy_timeout_ms}")
            conn.execute("PRAGMA query_only=ON")
        except Exception:
            conn.close()
            raise
        return conn

    def execute(self, sql: str, params: tuple[Any, ...]) -> "_MaterializedCursor":
        with self._slots:
            with self._guard:
                if self._closed:
                    raise sqlite3.ProgrammingError("Cannot operate on a closed database.")
                conn = self._idle.pop() if self._idle else None
            if conn is None:
                conn = self._open()
            reusable = False
            try:
                cursor = _MaterializedCursor(conn.execute(sql, params))
                reusable = True
                return cursor
            finally:
                with self._guard:
                    if reusable and not self._closed:
                        self._idle.append(conn)
                    else:
                        conn.close()

    def close(self) -> None:
        with self._guard:
            self._closed = True
            idle, self._idle = self._idle, []
        for conn in idle:
            conn.close()


def _checker_label() -> str:
    return os.environ.get("IMP_STATE_VERIFY_LABEL") or Path(sys.argv[0] if sys.argv and sys.argv[0] else "python").name


class LocalStateConnection:
    """``verify``: None (default) skips the check in a supervised child and otherwise trusts a valid receipt
    (integrity_receipt.py) after a check of the critical tables, running the full check when there is none;
    True always runs the full check; False runs none. ``verification`` records which happened.
    ``migrate=False`` and ``critical_tables`` serve a store that is not the state store (the market stream store,
    market_data/stream_store.py): no state schema is created in it, and its own small tables are the critical ones."""

    def __init__(self, path: Path, *, require_existing: bool = False,
                 expected_identity: tuple[int, int] | None = None, verify: bool | None = None,
                 migrate: bool = True, critical_tables: tuple[str, ...] | None = None) -> None:
        # A full integrity_check reads the whole file: about 63 s at night and 15-80 min during collection for the
        # 9.8 GB store on the D: hard drive (2026-10-27). One full check per boot is recorded in a receipt; a
        # supervised child still skips it, since its supervisor's connection verified the store moments earlier.
        supervised = verify is None and verified_by_supervisor()
        self.path = path
        self.verification: dict[str, Any] = {"mode": "SKIPPED", "reason": None, "elapsed_seconds": 0.0}
        self._lock = threading.RLock()
        # A transaction belongs to one thread. Nested ``with connection.transaction()`` calls on that thread
        # are re-entrant; another thread waits for the outer transaction instead of joining it implicitly.
        self._tx_owner: int | None = None
        self._tx_depth = 0
        self._critical_tables = receipts.CRITICAL_TABLES if critical_tables is None else tuple(critical_tables)
        self._busy_timeout_ms = _busy_timeout_ms()
        self._read_pool: _ReadPool | None = None
        # Telemetry for waits on SQLite's write lock (AUD-044 / CA-7).
        self.lock_waits: dict[str, Any] = {"count": 0, "slow": 0, "max_seconds": 0.0, "last_slow": None}
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
            if supervised:
                self.verification["mode"] = "SUPERVISED"
            elif verify is not False:
                self._verify_store(full=verify is True)
            if migrate:
                apply_migrations(self._conn)
        except Exception:
            self._conn.close()
            raise
        pool_size = _read_pool_size()
        if pool_size and not _legacy_shared_lock() and self.path.is_file():
            self._read_pool = _ReadPool(self.path, pool_size, self._busy_timeout_ms)

    def _configure(self) -> None:
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute(f"PRAGMA busy_timeout={self._busy_timeout_ms}")

    def _verify_or_raise(self) -> None:
        status = receipts.full_check(self._conn)
        if status != "ok":
            raise CorruptStateError(f"SQLITE_INTEGRITY_FAILED:{status}")

    def _verify_store(self, *, full: bool) -> None:
        started = time.monotonic()
        store = self.path.resolve()
        if not store.is_file():  # nothing on disk to hold a receipt for
            self._verify_or_raise()
            self.verification = {"mode": "FULL", "reason": "NOT_A_FILE",
                                 "elapsed_seconds": round(time.monotonic() - started, 3)}
            return
        reason = "FULL_CHECK_REQUESTED" if full else receipts.receipt_problem(store)
        if reason is None:
            self._critical_or_raise(store)
            self.verification = {"mode": "RECEIPT", "reason": None,
                                 "elapsed_seconds": round(time.monotonic() - started, 3)}
            return
        # One full check per store at a time. An opener that waited re-reads the receipt: the check it waited
        # for usually answers its own question.
        with receipts.VerifyLock(store):
            if not full and receipts.receipt_problem(store) is None:
                self._critical_or_raise(store)
                self.verification = {"mode": "RECEIPT", "reason": "VERIFIED_WHILE_WAITING",
                                     "elapsed_seconds": round(time.monotonic() - started, 3)}
                return
            checked_at, check_started = time.time(), time.monotonic()
            with receipts.VerifyHeartbeat(store, label=_checker_label()) as beat:
                try:
                    self._verify_or_raise()
                except Exception as exc:
                    if isinstance(exc, CorruptStateError) or corruption_error(exc):
                        receipts.invalidate(store, str(exc), label=_checker_label())
                    beat.result = str(exc)
                    raise
                beat.result = "ok"
            elapsed = time.monotonic() - check_started
            try:
                receipts.write_receipt(store, elapsed_seconds=elapsed, label=_checker_label(), started_at=checked_at)
            except OSError:
                reason = f"{reason};RECEIPT_NOT_WRITTEN"
        self.verification = {"mode": "FULL", "reason": reason, "elapsed_seconds": round(elapsed, 3)}

    def _critical_or_raise(self, store: Path) -> None:
        try:
            status = receipts.critical_check(self._conn, self._critical_tables)
        except sqlite3.DatabaseError as exc:
            if corruption_error(exc):
                receipts.invalidate(store, f"CRITICAL_CHECK:{exc}", label=_checker_label())
            raise
        if status != "ok":
            receipts.invalidate(store, f"CRITICAL_CHECK:{status}", label=_checker_label())
            raise CorruptStateError(f"SQLITE_INTEGRITY_FAILED:{status}")

    def _note_corruption(self, exc: BaseException) -> None:
        """A damaged page found at run time invalidates the receipt, so the next open scans the whole file."""
        if corruption_error(exc):
            receipts.invalidate(self.path.resolve(), f"RUNTIME:{exc}", label=_checker_label())

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> _MaterializedCursor:
        pool = self._read_pool
        if pool is not None and _plain_select(sql) and not self._lock._is_owned():
            # Not inside this thread's transaction or locked section: read without queueing behind writers.
            try:
                return pool.execute(sql, params)
            except sqlite3.DatabaseError as exc:
                self._note_corruption(exc)
                raise
        configured = _PRAGMA_BUSY_TIMEOUT.match(sql)
        pragma = sql.lstrip()[:6].upper() == "PRAGMA"  # reads or sets a connection setting: never sliced
        if self._lock._is_owned() or _legacy_shared_lock() or pragma:
            with self._lock:
                try:
                    cursor = _MaterializedCursor(self._conn.execute(sql, params))
                except sqlite3.DatabaseError as exc:
                    self._note_corruption(exc)
                    raise
                if configured:
                    self._busy_timeout_ms = int(configured.group(1))
                return cursor
        # One autocommit statement is atomic: a BUSY failure applied nothing, so it is safe to try again.
        return self._contended(lambda: _MaterializedCursor(self._conn.execute(sql, params)),
                               self._busy_timeout_ms / 1000.0, "STATEMENT")

    def _set_busy_timeout(self, milliseconds: int) -> None:
        self._conn.execute(f"PRAGMA busy_timeout={int(milliseconds)}")

    def _record_lock_wait(self, waited: float, started_at: str, what: str) -> None:
        waits = self.lock_waits
        waits["count"] += 1
        waits["max_seconds"] = max(float(waits["max_seconds"]), round(waited, 3))
        if waited >= _SLOW_LOCK_WAIT_SECONDS:
            waits["slow"] += 1
            waits["last_slow"] = {"what": what, "started_at": started_at, "ended_at": _utc_now(),
                                  "seconds": round(waited, 3)}
            _log.warning("SQLITE_WRITE_LOCK_WAIT store=%s what=%s started_at=%s waited_s=%.3f thread=%s",
                         self.path.name, what, started_at, waited, threading.current_thread().name)

    def _contended(self, operation: Any, budget_seconds: float, what: str) -> Any:
        """Run ``operation`` on the shared connection, waiting for SQLite's write lock in short slices.

        The shared lock is held for each attempt only, so other threads' statements interleave while this
        one waits; the total wait stays within ``budget_seconds`` as SQLite's own busy timeout did.
        """
        started, started_at = time.monotonic(), None
        deadline = started + max(0.0, budget_seconds)
        delay = 0.01
        while True:
            with self._lock:
                self._set_busy_timeout(_SHORT_BUSY_TIMEOUT_MS)
                try:
                    result = operation()
                except sqlite3.OperationalError as exc:
                    if not lock_contention_error(exc) or time.monotonic() >= deadline:
                        if started_at is not None:
                            self._record_lock_wait(time.monotonic() - started, started_at, what + ":GAVE_UP")
                        if corruption_error(exc):
                            self._note_corruption(exc)
                        raise
                except sqlite3.DatabaseError as exc:
                    self._note_corruption(exc)
                    raise
                else:
                    if started_at is not None:
                        self._record_lock_wait(time.monotonic() - started, started_at, what)
                    return result
                finally:
                    self._set_busy_timeout(self._busy_timeout_ms)
            started_at = started_at or _utc_now()
            time.sleep(min(delay, max(0.0, deadline - time.monotonic())))
            delay = min(delay * 2, 0.25)

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
            try:
                return _MaterializedCursor(self._conn.executemany(sql, seq))
            except sqlite3.DatabaseError as exc:
                self._note_corruption(exc)
                raise

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
            status = receipts.full_check(self._conn)
        if status != "ok":
            receipts.invalidate(self.path.resolve(), f"INTEGRITY_OK:{status}", label=_checker_label())
        return status == "ok"

    def schema_version(self) -> int:
        with self._lock:
            version = current_schema_version(self._conn)
        if version is None:
            raise SchemaVersionError("SCHEMA_MISSING")
        if version > SCHEMA_VERSION:
            raise SchemaVersionError(f"UNKNOWN_NEWER_SCHEMA:{version}")
        return version

    def close(self) -> None:
        if self._read_pool is not None:
            self._read_pool.close()
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
        # A thread that already holds the shared lock (an outer locked section) cannot release it while it waits.
        held_outside = conn._lock._is_owned()
        conn._lock.acquire()
        try:
            if conn._tx_owner == threading.get_ident():
                conn._tx_depth += 1
                self._nested = True
                return conn
            if held_outside or _legacy_shared_lock():
                self._begin_immediate(conn)
            else:
                self._begin_immediate_sliced(conn)
            conn._tx_owner, conn._tx_depth = threading.get_ident(), 1
            return conn
        except Exception:
            conn._lock.release()
            raise

    def _begin_immediate_sliced(self, conn: LocalStateConnection) -> None:
        """BEGIN IMMEDIATE within SQLite's busy timeout plus ``retry_seconds``, as ``_begin_immediate`` allows,
        but sleeping between short attempts with the shared lock released (AUD-044). Returns holding the lock."""
        started, started_at = time.monotonic(), None
        deadline = started + conn._busy_timeout_ms / 1000.0 + self.retry_seconds
        delay = 0.01
        while True:
            conn._set_busy_timeout(_SHORT_BUSY_TIMEOUT_MS)
            try:
                conn._conn.execute("BEGIN IMMEDIATE")
                begun = conn._conn.in_transaction
            except sqlite3.OperationalError as exc:
                if not lock_contention_error(exc) or time.monotonic() >= deadline:
                    if started_at is not None:
                        conn._record_lock_wait(time.monotonic() - started, started_at, "BEGIN_IMMEDIATE:GAVE_UP")
                    raise
                begun = False
            finally:
                conn._set_busy_timeout(conn._busy_timeout_ms)
            if begun:
                if started_at is not None:
                    conn._record_lock_wait(time.monotonic() - started, started_at, "BEGIN_IMMEDIATE")
                return
            # Also covers a refused BEGIN whose failure was lost: the body must not run in autocommit.
            if time.monotonic() >= deadline:
                raise sqlite3.OperationalError("database is locked: transaction did not start")
            started_at = started_at or _utc_now()
            conn._lock.release()
            try:
                time.sleep(min(delay, max(0.0, deadline - time.monotonic())))
            finally:
                conn._lock.acquire()
            delay = min(delay * 2, 0.25)

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
