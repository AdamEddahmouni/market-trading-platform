"""The market stream store: raw Moomoo/Kraken receipts in their own SQLite file beside the state store.

The stream rows were about 8.4 of the state store's 10 GB (2026-10-27) and nothing reads them at run time, yet every
whole-store integrity scan read them too, and the store grew 2.2 GB a trading day. They now live in
``imp-market-stream.sqlite3`` next to ``imp-state.sqlite3``, with compressed payloads (local_state/payload_codec.py):

* The file holds the four ``market_stream_*`` tables of schema v13 unchanged, ``payload_dictionaries`` and
  ``stream_store_meta``. It is created only by ``create_stream_store`` (the one-time split, tools/platform/
  split_stream_store.py, or a test); an open never creates it, so a missing file fails closed.
* ``auto_vacuum=INCREMENTAL`` is set before the first table, so a later retention policy can return space to the disk
  without rewriting the file.
* Until the split has run, ``stream_data_path`` is the state store itself and everything behaves as before. The state
  store keeps its (then empty) stream tables, so older code still opens it and a code rollback needs no data restore.
* The writer's owner lock stays beside the state store (``imp-state.sqlite3.market-writer.lock``).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ..local_state.connection import LocalStateConnection
from ..local_state.payload_codec import TABLE_DDL as DICTIONARY_DDL
from ..local_state.schema import MARKET_STREAM_V13

STREAM_STORE_NAME = 'imp-market-stream.sqlite3'
STREAM_STORE_VERSION = 1
META_DDL = 'CREATE TABLE stream_store_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)'
# Checked on every open that trusts a receipt; the records table is covered by the per-boot full scan.
CRITICAL_TABLES = ('stream_store_meta', 'payload_dictionaries', 'market_stream_runs', 'market_stream_checkpoints')
STREAM_TABLES = ('market_stream_records', 'market_stream_checkpoints', 'market_stream_runs', 'market_stream_gaps')


def stream_store_path(state_path: Path) -> Path:
    """Where the stream store of this state store lives (it may not exist yet)."""
    return Path(state_path).parent / STREAM_STORE_NAME


def stream_data_path(state_path: Path) -> Path:
    """The file that holds the stream tables: the stream store once split, else the state store."""
    split = stream_store_path(state_path)
    return split if split.is_file() else Path(state_path)


def _file_bytes(path: Path) -> int:
    wal = Path(str(path) + '-wal')
    return path.stat().st_size + (wal.stat().st_size if wal.exists() else 0)


def footprint_bytes(state_path: Path) -> int:
    """State store plus stream store, each with its WAL: what the owner-approved storage ceiling bounds."""
    state_path = Path(state_path)
    total = _file_bytes(state_path)
    split = stream_store_path(state_path)
    if split.is_file():
        total += _file_bytes(split)
    return total


def create_stream_store(path: Path) -> None:
    """A new, empty stream store. Refuses to touch an existing file."""
    path = Path(path)
    if path.exists():
        raise FileExistsError('MARKET_STREAM_STORE_EXISTS')
    db = sqlite3.connect(str(path), isolation_level=None)
    try:
        db.execute('PRAGMA auto_vacuum=INCREMENTAL')  # only takes effect before the first table
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('BEGIN IMMEDIATE')
        for statement in (*MARKET_STREAM_V13, DICTIONARY_DDL, META_DDL):
            db.execute(statement)
        db.execute('INSERT INTO stream_store_meta VALUES (?,?)', ('version', str(STREAM_STORE_VERSION)))
        db.execute('COMMIT')
    except BaseException:
        db.close()
        path.unlink(missing_ok=True)
        raise
    db.close()


def open_stream_store(path: Path, *, verify: bool | None = None) -> LocalStateConnection:
    """An existing stream store, integrity-checked like the state store (one full scan per boot, recorded in its own
    receipt) but never migrated into a state store."""
    connection = LocalStateConnection(Path(path), require_existing=True, verify=verify, migrate=False,
                                      critical_tables=CRITICAL_TABLES)
    try:
        row = connection.execute("SELECT value FROM stream_store_meta WHERE key='version'").fetchone()
        if row is None or int(row[0]) != STREAM_STORE_VERSION:
            raise ValueError('MARKET_STREAM_STORE_VERSION_UNKNOWN')
    except sqlite3.DatabaseError as exc:
        connection.close()
        raise ValueError('MARKET_STREAM_STORE_INVALID') from exc
    except Exception:
        connection.close()
        raise
    return connection
