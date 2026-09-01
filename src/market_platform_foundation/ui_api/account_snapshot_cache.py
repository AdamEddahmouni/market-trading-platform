"""Per-account snapshot cache with isolated refresh coalescing."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar

from ..operational_identity import OperationalIdentity

T = TypeVar("T")


@dataclass
class CachedSnapshot(Generic[T]):
    value: T
    identity: OperationalIdentity
    source_time_ns: int | None
    retrieved_at_ns: int
    stale: bool = False
    refresh_failed: bool = False
    refresh_error: str | None = None


@dataclass
class AccountSnapshotCache:
    """Account-scoped snapshot cache — keys never cross operational identities."""

    _entries: dict[str, CachedSnapshot[Any]] = field(default_factory=dict)
    _refresh_locks: dict[str, threading.Lock] = field(default_factory=dict)
    _lock_guard: threading.Lock = field(default_factory=threading.Lock)

    def _entry_key(self, identity: OperationalIdentity, logical_id: str) -> str:
        return identity.cache_key(logical_id)

    def _lock_for(self, entry_key: str) -> threading.Lock:
        with self._lock_guard:
            lock = self._refresh_locks.get(entry_key)
            if lock is None:
                lock = threading.Lock()
                self._refresh_locks[entry_key] = lock
            return lock

    def get(
        self,
        identity: OperationalIdentity,
        logical_id: str,
    ) -> CachedSnapshot[Any] | None:
        return self._entries.get(self._entry_key(identity, logical_id))

    def put(
        self,
        identity: OperationalIdentity,
        logical_id: str,
        value: Any,
        *,
        source_time_ns: int | None,
        retrieved_at_ns: int | None = None,
        stale: bool = False,
        refresh_failed: bool = False,
        refresh_error: str | None = None,
    ) -> CachedSnapshot[Any]:
        retrieved = retrieved_at_ns if retrieved_at_ns is not None else time.time_ns()
        entry = CachedSnapshot(
            value=value,
            identity=identity,
            source_time_ns=source_time_ns,
            retrieved_at_ns=retrieved,
            stale=stale,
            refresh_failed=refresh_failed,
            refresh_error=refresh_error,
        )
        self._entries[self._entry_key(identity, logical_id)] = entry
        return entry

    def invalidate(self, identity: OperationalIdentity, logical_id: str) -> bool:
        return self._entries.pop(self._entry_key(identity, logical_id), None) is not None

    def get_or_refresh(
        self,
        identity: OperationalIdentity,
        logical_id: str,
        loader: Callable[[], tuple[Any, int | None]],
        *,
        serve_stale_on_failure: bool = True,
    ) -> CachedSnapshot[Any]:
        """Refresh one account context; concurrent callers for the same identity coalesce."""
        entry_key = self._entry_key(identity, logical_id)
        lock = self._lock_for(entry_key)
        with lock:
            existing = self._entries.get(entry_key)
            try:
                value, source_time_ns = loader()
                return self.put(
                    identity,
                    logical_id,
                    value,
                    source_time_ns=source_time_ns,
                    stale=False,
                    refresh_failed=False,
                )
            except Exception as exc:
                if existing is not None and serve_stale_on_failure:
                    return self.put(
                        identity,
                        logical_id,
                        existing.value,
                        source_time_ns=existing.source_time_ns,
                        retrieved_at_ns=time.time_ns(),
                        stale=True,
                        refresh_failed=True,
                        refresh_error=str(exc),
                    )
                raise

    def provenance_fields(self, entry: CachedSnapshot[Any]) -> dict[str, Any]:
        return {
            "source_time": entry.source_time_ns,
            "retrieved_at": entry.retrieved_at_ns,
            "stale": entry.stale,
            "refresh_failed": entry.refresh_failed,
            "refresh_error": entry.refresh_error,
        }


# Module-level cache for UI API account-scoped snapshots.
_ACCOUNT_SNAPSHOT_CACHE = AccountSnapshotCache()


def get_account_snapshot_cache() -> AccountSnapshotCache:
    return _ACCOUNT_SNAPSHOT_CACHE


def reset_account_snapshot_cache_for_tests() -> None:
    global _ACCOUNT_SNAPSHOT_CACHE
    _ACCOUNT_SNAPSHOT_CACHE = AccountSnapshotCache()
