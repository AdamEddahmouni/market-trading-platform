"""Bounded durable inference reuse. Corruption is a miss, never action authority."""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from ..intelligence.inference.evidence_compaction import semantic_hash

MAX_ENTRIES = 512
MAX_BYTES = 128 * 1024 * 1024
MAX_ENTRY_BYTES = 512000


class InferenceCache:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=10, check_same_thread=False)
        self.lock = threading.RLock()
        with self.connection:
            self.connection.execute("CREATE TABLE IF NOT EXISTS inference_cache "
                                    "(identity TEXT PRIMARY KEY, expires REAL NOT NULL, payload TEXT NOT NULL, checksum TEXT NOT NULL)")

    def close(self):
        with self.lock:
            self.connection.close()

    def get(self, identity: str, now: float):
        try:
            with self.lock:
                row = self.connection.execute("SELECT expires,payload,checksum FROM inference_cache WHERE identity=?",
                                              (identity,)).fetchone()
            if row is None or row[0] <= now:
                return None
            result = json.loads(row[1])
            if not isinstance(result, dict) or semantic_hash(result) != row[2] or result.get("input_hash") != identity:
                return None
            return row[0], result
        except (OSError, ValueError, TypeError, sqlite3.Error):
            return None

    def put(self, identity: str, expiry: float, result: dict, now: float):
        encoded = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        if len(encoded.encode("utf-8")) > MAX_ENTRY_BYTES:
            return
        with self.lock, self.connection:
            self.connection.execute("DELETE FROM inference_cache WHERE expires<=?", (now,))
            self.connection.execute("INSERT OR REPLACE INTO inference_cache VALUES (?,?,?,?)",
                                    (identity, expiry, encoded, semantic_hash(result)))
            # Byte length, rather than unicode character length, bounds retained data.
            while True:
                count, size = self.connection.execute(
                    "SELECT COUNT(*),COALESCE(SUM(LENGTH(CAST(payload AS BLOB))),0) FROM inference_cache").fetchone()
                if count <= MAX_ENTRIES and size <= MAX_BYTES:
                    break
                self.connection.execute("DELETE FROM inference_cache WHERE rowid=(SELECT MIN(rowid) FROM inference_cache)")


_STORES = {}
_LOCK = threading.Lock()


def inference_cache():
    from .external_cache import imp_cache_dir
    from .paths import persistence_enabled
    if not persistence_enabled():
        return None
    try:
        path = imp_cache_dir() / "inference" / "screener-reuse.sqlite"
        with _LOCK:
            if path not in _STORES:
                _STORES[path] = InferenceCache(path)
            return _STORES[path]
    except (OSError, sqlite3.Error):
        return None
