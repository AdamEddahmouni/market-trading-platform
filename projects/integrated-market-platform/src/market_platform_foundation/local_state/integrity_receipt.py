"""One whole-store integrity scan per boot, recorded in a receipt, instead of one per open.

A full ``PRAGMA integrity_check`` reads the whole file. For the 9.8 GB store on the D: hard drive that is about
63 s at night and 15-80 min while the collector writes. It ran on every open, so a platform start during market
hours outlasted every readiness limit, the launcher and the keeper gave up and retried, and each retry started
another scan (2026-10-27).

A full check that returns ``ok`` now writes ``<store>.verified.json``. An open trusts that receipt only while
all of these hold, and otherwise runs the full check again:

* the schema is this one and the result is ``ok``;
* the file is the same file (``st_dev``, ``st_ino``) and no smaller than it was;
* the PC has not rebooted since (boot time within ``BOOT_TOLERANCE_SECONDS``);
* the receipt is younger than ``IMP_STATE_VERIFY_MAX_AGE_HOURS`` (default 48, clamped to 1-168).

A process crash or a Windows sign-out cannot corrupt a WAL store; a power cut or an OS crash is a new boot, so
the next open scans the whole file again. An open that trusts a receipt still checks the trading-critical tables
(``CRITICAL_TABLES``) with ``PRAGMA integrity_check(<table>)``; the large collection tables are covered by the
boot scan and the keeper's nightly scan. Any failure invalidates the receipt and fails closed.

One full check runs at a time per store (a thread lock and an OS lock on ``<store>.verify.lock``). While it runs,
``<store>.verify-status.json`` says ``VERIFYING`` with a heartbeat, so the launcher and the keeper wait for a real
check instead of declaring the platform dead.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable

RECEIPT_SCHEMA = "imp-store-verified/1.0.0"
STATUS_SCHEMA = "imp-store-verify-status/1.0.0"
INVALIDATED = "INVALIDATED"
VERIFYING = "VERIFYING"
# The keeper's REBOOT_TOLERANCE_SECONDS: boot time derived from uptime drifts with clock adjustments.
BOOT_TOLERANCE_SECONDS = 120
DEFAULT_MAX_AGE_HOURS = 48
HEARTBEAT_SECONDS = 30
# A status older than this belongs to a process that died mid-check.
STALE_HEARTBEAT_SECONDS = 90
# The longest a launcher or keeper waits for a check that is visibly running.
VERIFY_WAIT_CAP_SECONDS = 3 * 3600
LOCK_POLL_SECONDS = 1.0
# Small tables whose damage would mislead Paper trading; checked on every open that trusts a receipt.
CRITICAL_TABLES = (
    "schema_meta",
    "paper_sessions",
    "paper_events",
    "paper_snapshots",
    "paper_idempotency",
    "paper_experiments",
    "paper_equity_snapshots",
    "paper_performance_records",
    "paper_automation_policies",
    "paper_automation_controllers",
    "paper_automation_intents",
    "paper_automation_events",
)

# The files this module keeps next to the store (never a database): receipt, status, lock.
SIDECAR_SUFFIXES = (".verified.json", ".verify-status.json", ".verify.lock")

_THREAD_LOCKS: dict[str, threading.Lock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


def receipt_path(store: Path) -> Path:
    return store.with_name(store.name + ".verified.json")


def status_path(store: Path) -> Path:
    return store.with_name(store.name + ".verify-status.json")


def lock_path(store: Path) -> Path:
    return store.with_name(store.name + ".verify.lock")


def boot_epoch() -> float | None:
    """When this PC booted, from its uptime (the keeper's own measure)."""
    if os.name == "nt":
        import ctypes

        tick = ctypes.windll.kernel32.GetTickCount64
        tick.restype = ctypes.c_ulonglong
        return time.time() - tick() / 1000.0
    try:
        return time.time() - float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def max_age_seconds() -> float:
    try:
        hours = float(os.environ.get("IMP_STATE_VERIFY_MAX_AGE_HOURS", DEFAULT_MAX_AGE_HOURS))
    except (TypeError, ValueError):
        hours = DEFAULT_MAX_AGE_HOURS
    return min(168.0, max(1.0, hours)) * 3600


def _identity(store: Path) -> dict[str, int]:
    stat = store.stat()
    return {"st_dev": int(stat.st_dev), "st_ino": int(stat.st_ino), "size_bytes": int(stat.st_size)}


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _write_json(path: Path, body: dict[str, Any]) -> None:
    temporary = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        temporary.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_receipt(store: Path) -> dict[str, Any] | None:
    return _read_json(receipt_path(store))


def receipt_problem(store: Path, *, now: float | None = None, boot: float | None = None,
                    receipt: dict[str, Any] | None = None) -> str | None:
    """None when the receipt lets this open skip the full scan; otherwise why it does not."""
    receipt = read_receipt(store) if receipt is None else receipt
    if receipt is None:
        return "NO_RECEIPT"
    if receipt.get("schema") != RECEIPT_SCHEMA:
        return "RECEIPT_SCHEMA_UNKNOWN"
    if receipt.get("result") != "ok":
        return f"RECEIPT_{receipt.get('result') or 'UNREADABLE'}"
    try:
        current = _identity(store)
        recorded = receipt["identity"]
        if (int(recorded["st_dev"]), int(recorded["st_ino"])) != (current["st_dev"], current["st_ino"]):
            return "STORE_REPLACED"
        if current["size_bytes"] < int(recorded["size_bytes"]):
            return "STORE_SHRANK"
        checked_at = float(receipt["checked_at_epoch"])
        receipt_boot = receipt.get("boot_epoch")
    except (OSError, KeyError, TypeError, ValueError):
        return "RECEIPT_UNREADABLE"
    now = time.time() if now is None else now
    boot = boot_epoch() if boot is None else boot
    if boot is None or receipt_boot is None or abs(float(receipt_boot) - boot) > BOOT_TOLERANCE_SECONDS:
        return "REBOOTED_SINCE_CHECK"
    if checked_at > now + BOOT_TOLERANCE_SECONDS:
        return "RECEIPT_FROM_THE_FUTURE"
    if now - checked_at > max_age_seconds():
        return "RECEIPT_EXPIRED"
    return None


def write_receipt(store: Path, *, elapsed_seconds: float, label: str, started_at: float | None = None) -> dict[str, Any]:
    """Record a full check that returned ``ok``. Its identity is taken now, after the check."""
    now = time.time()
    body = {
        "schema": RECEIPT_SCHEMA,
        "result": "ok",
        "store": str(store),
        "identity": _identity(store),
        "boot_epoch": boot_epoch(),
        "checked_at_epoch": now if started_at is None else started_at,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "elapsed_seconds": round(float(elapsed_seconds), 3),
        "sqlite_version": sqlite3.sqlite_version,
        "checker": {"pid": os.getpid(), "label": label},
    }
    _write_json(receipt_path(store), body)
    return body


def invalidate(store: Path, reason: str, *, label: str = "") -> None:
    """The next open runs the full check. Never raises: the caller is already failing closed."""
    try:
        _write_json(receipt_path(store), {
            "schema": RECEIPT_SCHEMA,
            "result": INVALIDATED,
            "reason": str(reason)[:500],
            "store": str(store),
            "invalidated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "checker": {"pid": os.getpid(), "label": label},
        })
    except OSError:
        pass


def full_check(conn: sqlite3.Connection) -> str:
    row = conn.execute("PRAGMA integrity_check").fetchone()
    return str(row[0]) if row is not None else "missing"


def critical_check(conn: sqlite3.Connection, tables: tuple[str, ...] = CRITICAL_TABLES) -> str:
    """``ok`` or the first problem in the schema or the trading-critical tables that exist."""
    present = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_schema WHERE type = 'table'")}
    for table in tables:
        if table not in present:
            continue
        row = conn.execute(f'PRAGMA integrity_check("{table}")').fetchone()
        status = str(row[0]) if row is not None else "missing"
        if status != "ok":
            return f"{table}:{status}"
    return "ok"


def read_status(store: Path) -> dict[str, Any] | None:
    return _read_json(status_path(store))


def verification_in_progress(store: Path, *, now: float | None = None) -> dict[str, Any] | None:
    """The status of a full check that is running now (fresh heartbeat), or None."""
    status = read_status(store)
    if not status or status.get("state") != VERIFYING:
        return None
    try:
        beat = float(status["heartbeat_epoch"])
    except (KeyError, TypeError, ValueError):
        return None
    now = time.time() if now is None else now
    return status if 0 <= now - beat <= STALE_HEARTBEAT_SECONDS or beat > now else None


class VerifyLock:
    """One full check per store at a time: a thread lock for this process and an OS lock for the others."""

    def __init__(self, store: Path) -> None:
        self.store = store
        key = os.path.normcase(str(store.resolve()))
        with _THREAD_LOCKS_GUARD:
            self._thread_lock = _THREAD_LOCKS.setdefault(key, threading.Lock())
        self._handle: Any = None

    def acquire(self, *, blocking: bool = True, timeout: float = VERIFY_WAIT_CAP_SECONDS,
                sleep: Callable[[float], None] = time.sleep) -> bool:
        deadline = time.monotonic() + timeout
        acquired = (self._thread_lock.acquire(timeout=max(0.0, timeout)) if blocking
                    else self._thread_lock.acquire(blocking=False))
        if not acquired:
            return False
        try:
            while True:
                if self._try_os_lock():
                    return True
                if not blocking or time.monotonic() >= deadline:
                    self._thread_lock.release()
                    return False
                sleep(LOCK_POLL_SECONDS)
        except BaseException:
            self._thread_lock.release()
            raise

    def _try_os_lock(self) -> bool:
        path = lock_path(self.store)
        handle = open(path, "a+b")
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self._handle = handle
        return True

    def release(self) -> None:
        if self._handle is not None:
            try:
                if os.name == "nt":
                    import msvcrt

                    self._handle.seek(0)
                    try:
                        msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass
            finally:
                self._handle.close()
                self._handle = None
            self._thread_lock.release()

    def __enter__(self) -> "VerifyLock":
        if not self.acquire():
            raise TimeoutError("STATE_VERIFY_LOCK_TIMEOUT")
        return self

    def __exit__(self, *exc: Any) -> None:
        self.release()


class VerifyHeartbeat:
    """``VERIFYING`` with a heartbeat while a full check runs; the outcome when it ends."""

    def __init__(self, store: Path, *, label: str, interval: float = HEARTBEAT_SECONDS) -> None:
        self.store, self.label, self.interval = store, label, interval
        self.started = time.time()
        self.result: str | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _write(self, state: str, **fields: Any) -> None:
        try:
            _write_json(status_path(self.store), {
                "schema": STATUS_SCHEMA, "state": state, "pid": os.getpid(), "label": self.label,
                "started_epoch": self.started, "heartbeat_epoch": time.time(), **fields,
            })
        except OSError:
            pass  # the status only informs waiters; the check itself must not fail on it

    def _beat(self) -> None:
        while not self._stop.wait(self.interval):
            self._write(VERIFYING)

    def __enter__(self) -> "VerifyHeartbeat":
        self._write(VERIFYING)
        self._thread = threading.Thread(target=self._beat, name="imp-store-verify-heartbeat", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type: Any, exc: BaseException | None, tb: Any) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        result = self.result or (type(exc).__name__ if exc is not None else "unknown")
        self._write("DONE", result=result[:500], elapsed_seconds=round(time.time() - self.started, 3))
