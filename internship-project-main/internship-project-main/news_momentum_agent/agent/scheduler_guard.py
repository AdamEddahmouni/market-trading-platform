"""Prevent one hung HTTP call from freezing the entire agent scheduler.

Pipeline role
-------------
The main loop uses ``schedule`` on a single thread. A socket stuck in SSL_read
(no effective timeout) would block every subsequent job. These helpers:
  - run each job on a worker pool (schedule thread returns immediately),
  - skip overlapping runs of the same job,
  - enforce a hard wall-clock timeout (release lock so the job can retry),
  - expose ``health_age_seconds`` for the main-loop watchdog.

State file: ``state/health.json`` (updated by the main loop, read for staleness).

``install_socket_default_timeout`` is a global safety net for libraries that omit
per-request timeouts (e.g. some yfinance paths).

Merge notes: fully reusable infrastructure for any long-running scheduled agent.
"""

from __future__ import annotations

import socket
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HEALTH_PATH = PROJECT_ROOT / "state" / "health.json"

_JOB_LOCKS: Dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()
# Persistent pool so timed-out workers are not joined (which would re-block).
_EXECUTOR = ThreadPoolExecutor(max_workers=6, thread_name_prefix="sched_job")


def install_socket_default_timeout(seconds: float = 30.0) -> None:
    """Global safety net for libraries that omit per-request timeouts (e.g. some yfinance paths)."""
    try:
        socket.setdefaulttimeout(float(seconds))
        print(f"[scheduler_guard] socket.setdefaulttimeout({seconds})")
    except Exception as error:
        print(f"[scheduler_guard] could not set socket default timeout: {error}")


def _lock_for(name: str) -> threading.Lock:
    with _LOCKS_GUARD:
        lock = _JOB_LOCKS.get(name)
        if lock is None:
            lock = threading.Lock()
            _JOB_LOCKS[name] = lock
        return lock


def wrap_scheduled_job(
    fn: Callable[..., Any],
    *,
    name: str,
    timeout_sec: float,
) -> Callable[..., Any]:
    """
    Wrap a schedule job so it cannot block the scheduler forever.

    The schedule thread submits work and returns immediately. Overlapping
    invocations of the same job are skipped. On timeout the lock is released
    so a later cycle can retry (the abandoned worker may still be running).
    """

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        lock = _lock_for(name)
        if not lock.acquire(blocking=False):
            print(f"[main] skip overlapping job={name} (previous still running)")
            return None

        started = datetime.now(timezone.utc)
        released = threading.Event()

        def release_once() -> None:
            if released.is_set():
                return
            released.set()
            try:
                lock.release()
            except RuntimeError:
                pass

        def run() -> None:
            try:
                fn(*args, **kwargs)
            except Exception as error:
                print(f"[main] JOB ERROR name={name}: {error}")
            finally:
                release_once()

        fut = _EXECUTOR.submit(run)

        def watch_timeout() -> None:
            try:
                fut.result(timeout=float(timeout_sec))
            except FuturesTimeout:
                elapsed = (datetime.now(timezone.utc) - started).total_seconds()
                print(
                    f"[main] JOB TIMEOUT name={name} after {elapsed:.0f}s "
                    f"(limit={timeout_sec:.0f}s) — abandoning worker, continuing scheduler"
                )
                release_once()
            except Exception:
                # Error already logged in run(); lock released there.
                pass

        threading.Thread(
            target=watch_timeout, name=f"timeout-{name}", daemon=True
        ).start()
        return None

    wrapper.__name__ = getattr(fn, "__name__", name)
    wrapper.__wrapped__ = fn  # type: ignore[attr-defined]
    return wrapper


def run_with_timeout(
    fn: Callable[..., Any],
    *args: Any,
    name: str,
    timeout_sec: float,
    **kwargs: Any,
) -> Any:
    """
    Blocking helper for one-shot startup work (schedule thread not involved).

    Returns the function result, or None on timeout/error.
    """
    started = datetime.now(timezone.utc)
    fut = _EXECUTOR.submit(fn, *args, **kwargs)
    try:
        return fut.result(timeout=float(timeout_sec))
    except FuturesTimeout:
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        print(
            f"[main] JOB TIMEOUT name={name} after {elapsed:.0f}s "
            f"(limit={timeout_sec:.0f}s) — abandoning worker, continuing scheduler"
        )
        return None
    except Exception as error:
        print(f"[main] JOB ERROR name={name}: {error}")
        return None


def health_age_seconds(path: Path = HEALTH_PATH) -> Optional[float]:
    """Seconds since state/health.json updated_at, or None if unreadable."""
    try:
        import json

        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        stamp = str(data.get("updated_at") or "")
        if not stamp:
            return None
        ts = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).total_seconds()
    except Exception:
        return None
