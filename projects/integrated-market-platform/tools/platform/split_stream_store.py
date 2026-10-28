"""One-time split of the market stream tables out of the state store, compressing payloads on the way.

  split_stream_store.py plan --state <imp-state.sqlite3>
  split_stream_store.py run  --state <imp-state.sqlite3> --backup-dir <dir> --evidence <file.json>

``plan`` only reads. ``run`` needs every IMP process stopped (keeper, collector, platform) and, unless
``--any-time``, the night window 20:00-03:45 New York time. It never uses another drive than the store's own unless
``--backup-dir`` says so. Steps, each fail-closed:

1. The state store has a fresh ``ok`` integrity receipt, no open market-writer run and no writer owner lock.
2. WAL checkpoint, then a byte copy of the state store into ``--backup-dir`` with SHA-256 of source and copy. This
   copy is the rollback for everything below.
3. A new stream store (market_data/stream_store.py) is built as ``imp-market-stream.partial.sqlite3``: checkpoints,
   runs and gaps copied verbatim; records copied in rowid order with their rowids and every column unchanged except
   the payload, which is the codec's encoding (local_state/payload_codec.py: verified per value, or kept plain). A
   scope's first rows stay plain until it has ``SAMPLE_ROWS`` samples for its dictionary.
4. Verification: the destination is read back in rowid order, every payload decoded, and a SHA-256 over all columns
   of all rows (decoded) must equal the one taken from the source; per-scope counts, the three small tables and
   ``PRAGMA integrity_check`` must match too. Only then is the file renamed to ``imp-market-stream.sqlite3``.
5. The state store's four stream tables are emptied (they stay, so its schema and older code are unchanged) and the
   file is compacted in place with ``VACUUM`` (same file identity, temp store in memory, never on C:).
6. Full integrity checks of both files write both receipts. Evidence goes to ``--evidence``.

``--in-memory`` (2026-10-27): on the D: hard drive the stream rows of a store grown over two weeks are scattered
through the file, and reading them in rowid order was seek-bound (~300 then under 100 rows/s, 4+ h for 3.3M rows).
With it, the state store is first read once, in page order, into a private in-memory database (SQLite's backup
API); steps 3-4 read from that copy, step 5 empties and VACUUMs the copy and writes it back into the same file with
the backup API (same file identity, WAL kept), after checking nothing changed the file since it was read. It needs
free RAM of about 1.4x the store. ``--reuse-backup`` takes a backup copy made by an earlier attempt instead of a new
one, provided the state store has not been written since that copy was started.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
for _entry in (ROOT / "src", ROOT):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))

from market_platform_foundation.local_state import integrity_receipt as receipts  # noqa: E402
from market_platform_foundation.local_state.payload_codec import (SAMPLE_ROWS, PayloadCodec,  # noqa: E402
                                                                  stream_scope)
from market_platform_foundation.market_data.persistence import _source, owner_lock_held  # noqa: E402
from market_platform_foundation.market_data.stream_store import (STREAM_STORE_NAME, create_stream_store,  # noqa: E402
                                                                 stream_store_path)

PARTIAL_NAME = "imp-market-stream.partial.sqlite3"
BATCH_ROWS = 10_000
SMALL_TABLES = ("market_stream_checkpoints", "market_stream_runs", "market_stream_gaps")
RECORD_COLUMNS = ("record_id", "provider", "symbol", "capability", "event_ns", "provider_ns", "received_ns",
                  "normalized_ns", "persisted_ns", "source_identity", "payload_json")
WINDOW_START_HOUR, WINDOW_END = 20, (3, 45)
LABEL = "split_stream_store"
MEMORY_URI = "file:imp-split-state-copy?mode=memory&cache=shared"
MEMORY_HEADROOM = 1.4  # free RAM needed per byte of store: pages plus SQLite's per-page overhead and the VACUUM
LOAD_STEP_PAGES = 65_536
BUILD_CACHE_KIB = 2_000_000  # page cache of the new stream store while it is built (~2 GB)


class SplitError(RuntimeError):
    pass


def _ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=30)


def _new_york_now() -> datetime.datetime:
    from zoneinfo import ZoneInfo

    return datetime.datetime.now(ZoneInfo("America/New_York"))


def in_night_window(now: datetime.datetime | None = None) -> bool:
    now = now or _new_york_now()
    return now.hour >= WINDOW_START_HOUR or (now.hour, now.minute) < WINDOW_END


def _file_bytes(path: Path) -> int:
    wal = Path(str(path) + "-wal")
    return (path.stat().st_size if path.exists() else 0) + (wal.stat().st_size if wal.exists() else 0)


def _identity(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_dev, stat.st_ino


def _row_digest(digest: Any, values: tuple) -> None:
    digest.update(json.dumps(values, separators=(",", ":"), default=str).encode("utf-8"))
    digest.update(b"\n")


def _table_digest(db: sqlite3.Connection, table: str, schema: str = "main") -> tuple[int, str]:
    digest, count = hashlib.sha256(), 0
    for row in db.execute(f'SELECT * FROM {schema}."{table}" ORDER BY rowid'):
        _row_digest(digest, tuple(row))
        count += 1
    return count, digest.hexdigest()


def plan(state: Path) -> dict[str, Any]:
    stream = stream_store_path(state)
    out: dict[str, Any] = {"state": str(state), "stream": str(stream), "stream_exists": stream.exists(),
                           "partial_exists": (state.parent / PARTIAL_NAME).exists(),
                           "state_bytes": _file_bytes(state), "free_bytes": shutil.disk_usage(state.parent).free,
                           "receipt_problem": receipts.receipt_problem(state),
                           "writer_owner_lock_held": owner_lock_held(state),
                           "in_night_window": in_night_window()}
    with closing(_ro(state)) as db:
        out["records_max_rowid"] = db.execute("SELECT max(rowid) FROM market_stream_records").fetchone()[0]
        out["open_runs"] = db.execute("SELECT COUNT(*) FROM market_stream_runs WHERE closed_ns IS NULL "
                                      "AND lease_until_ns>?", (time.time_ns(),)).fetchone()[0]
        out["streams"] = [row[0] for row in db.execute("SELECT stream_id FROM market_stream_checkpoints")]
    return out


def _preconditions(state: Path, *, any_time: bool) -> None:
    if not state.is_file():
        raise SplitError("STATE_STORE_MISSING")
    if stream_store_path(state).exists():
        raise SplitError("STREAM_STORE_ALREADY_EXISTS")
    if (state.parent / PARTIAL_NAME).exists():
        raise SplitError("PARTIAL_STREAM_STORE_EXISTS_INSPECT_AND_REMOVE")
    if not any_time and not in_night_window():
        raise SplitError("OUTSIDE_NIGHT_WINDOW")
    problem = receipts.receipt_problem(state)
    if problem is not None:
        raise SplitError(f"STATE_RECEIPT_NOT_FRESH:{problem}")
    if owner_lock_held(state):
        raise SplitError("MARKET_WRITER_RUNNING")
    with closing(_ro(state)) as db:
        if db.execute("SELECT COUNT(*) FROM market_stream_runs WHERE closed_ns IS NULL AND lease_until_ns>?",
                      (time.time_ns(),)).fetchone()[0]:
            raise SplitError("MARKET_WRITER_LEASE_ACTIVE")


def _exclusive_checkpoint(state: Path) -> None:
    """Fold the WAL into the file and prove no other connection is writing (BEGIN EXCLUSIVE)."""
    db = sqlite3.connect(str(state), timeout=5, isolation_level=None)
    try:
        db.execute("PRAGMA busy_timeout=5000")
        busy, _, _ = db.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        if busy:
            raise SplitError("STATE_STORE_IN_USE_CHECKPOINT_BUSY")
        db.execute("BEGIN EXCLUSIVE")
        db.execute("ROLLBACK")
    except sqlite3.OperationalError as exc:
        raise SplitError(f"STATE_STORE_IN_USE:{exc}") from exc
    finally:
        db.close()


def _copy_with_hash(source: Path, dest: Path) -> dict[str, Any]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise SplitError("BACKUP_ALREADY_EXISTS")
    digest, size = hashlib.sha256(), 0
    with open(source, "rb") as src, open(dest, "xb") as out:
        while chunk := src.read(8 * 1024 * 1024):
            digest.update(chunk)
            out.write(chunk)
            size += len(chunk)
        out.flush()
        os.fsync(out.fileno())
    check = hashlib.sha256()
    with open(dest, "rb") as copied:
        while chunk := copied.read(8 * 1024 * 1024):
            check.update(chunk)
    if check.hexdigest() != digest.hexdigest() or dest.stat().st_size != size:
        raise SplitError("BACKUP_COPY_MISMATCH")
    return {"path": str(dest), "bytes": size, "sha256": digest.hexdigest()}


def _reuse_backup(state: Path, backup: Path, sha256: str | None) -> dict[str, Any]:
    """An earlier attempt's backup stands for this run only if the state store was not written after it began."""
    if not backup.is_file():
        raise SplitError("REUSED_BACKUP_MISSING")
    source, copy = state.stat(), backup.stat()
    if copy.st_size != source.st_size:
        raise SplitError("REUSED_BACKUP_SIZE_MISMATCH")
    if source.st_mtime > copy.st_ctime:  # st_ctime is the creation time on Windows
        raise SplitError("STATE_STORE_WRITTEN_AFTER_BACKUP")
    if _file_bytes(state) != source.st_size:
        raise SplitError("STATE_STORE_WAL_NOT_EMPTY")
    return {"path": str(backup), "bytes": copy.st_size, "sha256": sha256, "reused": True,
            "state_mtime": source.st_mtime, "backup_created": copy.st_ctime}


def _free_memory_bytes() -> int | None:
    if os.name != "nt":
        return None
    import ctypes

    class _Status(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in ("total_phys", "avail_phys", "total_page", "avail_page",
                                                     "total_virtual", "avail_virtual", "avail_extended")]

    status = _Status()
    status.dwLength = ctypes.sizeof(_Status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return int(status.avail_phys)


def load_into_memory(state: Path, *, log=print) -> tuple[sqlite3.Connection, dict[str, Any]]:
    """One page-order read of the state store into a private in-memory copy (kept open by the returned connection)."""
    size, stat = state.stat().st_size, state.stat()
    free = _free_memory_bytes()
    if free is not None and free < size * MEMORY_HEADROOM:
        raise SplitError(f"NOT_ENOUGH_FREE_MEMORY:{free}<{int(size * MEMORY_HEADROOM)}")
    memory = sqlite3.connect(MEMORY_URI, uri=True, isolation_level=None)
    started = time.monotonic()
    try:
        def progress(status: int, remaining: int, total: int) -> None:
            done = total - remaining
            if done and done % (LOAD_STEP_PAGES * 8) == 0:
                log(json.dumps({"event": "LOAD_PROGRESS", "pages": done, "of": total,
                                "elapsed_seconds": round(time.monotonic() - started, 1)}), flush=True)

        with closing(_ro(state)) as source:
            source.backup(memory, pages=LOAD_STEP_PAGES, progress=progress)
        pages = memory.execute("PRAGMA page_count").fetchone()[0]
        page_size = memory.execute("PRAGMA page_size").fetchone()[0]
    except BaseException:
        memory.close()
        raise
    if pages * page_size != size:
        memory.close()
        raise SplitError(f"MEMORY_COPY_SIZE_MISMATCH:{pages * page_size}!={size}")
    return memory, {"bytes": size, "pages": pages, "free_memory_before": free, "mtime": stat.st_mtime,
                    "load_seconds": round(time.monotonic() - started, 1)}


def _table_counts(db: sqlite3.Connection, *, skip: tuple[str, ...] = ()) -> dict[str, int]:
    names = [row[0] for row in db.execute("SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE "
                                          "'sqlite_%' ORDER BY name")]
    return {name: db.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] for name in names if name not in skip}


def shrink_in_memory(memory: sqlite3.Connection, state: Path, loaded: dict[str, Any]) -> dict[str, Any]:
    """Step 5 on the in-memory copy, then written back into the same file (same identity, WAL kept)."""
    stream_tables = ("market_stream_records", *SMALL_TABLES)
    counts_before = _table_counts(memory, skip=stream_tables)
    memory.execute("BEGIN IMMEDIATE")
    for table in stream_tables:
        memory.execute(f"DELETE FROM {table}")
    memory.execute("COMMIT")
    started = time.monotonic()
    memory.execute("PRAGMA temp_store=MEMORY")
    memory.execute("VACUUM")
    vacuum_seconds = round(time.monotonic() - started, 1)
    status = receipts.full_check(memory)
    if status != "ok":
        raise SplitError(f"MEMORY_COPY_INTEGRITY:{status}")
    if _table_counts(memory, skip=stream_tables) != counts_before:
        raise SplitError("MEMORY_COPY_COUNTS_CHANGED")
    result = write_back(memory, state, loaded, skip=stream_tables)
    if result["table_counts"] != counts_before or result["skipped_rows"]:
        raise SplitError("STATE_STORE_COUNTS_AFTER_WRITE_BACK")
    return {**result, "vacuum_seconds": vacuum_seconds}


def write_back(memory: sqlite3.Connection, state: Path, loaded: dict[str, Any], *,
               skip: tuple[str, ...] = ()) -> dict[str, Any]:
    """Write the in-memory copy back into the same file (backup API: same identity, WAL kept), after checking that
    nothing wrote the file since it was read. Returns the file's table counts (``skip`` tables summed apart)."""
    before, identity = _file_bytes(state), _identity(state)
    stat = state.stat()
    if stat.st_size != loaded["bytes"] or stat.st_mtime != loaded["mtime"] or before != loaded["bytes"]:
        raise SplitError("STATE_STORE_CHANGED_SINCE_LOAD")
    started = time.monotonic()
    target = sqlite3.connect(str(state), timeout=30, isolation_level=None)
    try:
        target.execute("PRAGMA busy_timeout=30000")
        memory.backup(target)
        busy, _, _ = target.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        mode = target.execute("PRAGMA journal_mode").fetchone()[0]
        if str(mode).lower() != "wal":
            mode = target.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        counts_after = _table_counts(target, skip=skip)
        skipped_rows = sum(target.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in skip)
    finally:
        target.close()
    if _identity(state) != identity:
        raise SplitError("STATE_STORE_IDENTITY_CHANGED")
    return {"bytes_before": before, "bytes_after": _file_bytes(state), "identity": list(identity),
            "write_back_seconds": round(time.monotonic() - started, 1), "checkpoint_busy": bool(busy),
            "journal_mode": mode, "table_counts": counts_after, "skipped_rows": skipped_rows}


def _scope(provider: str, capability: str) -> str:
    return stream_scope(_source(provider), capability)


def build(state: Path, partial: Path, *, log=print, source_uri: str | None = None) -> dict[str, Any]:
    """Steps 3 and 4: the verified partial stream store. Returns the copy and verification evidence.

    ``source_uri`` reads the rows from another copy of the state store (the in-memory one) instead of the file."""
    create_stream_store(partial)
    # uri=True lets the ATTACH below open the state store read-only (or the shared in-memory copy).
    db = sqlite3.connect(partial.resolve().as_uri(), uri=True, isolation_level=None)
    try:
        # Unsynced while it is built: until it is verified and renamed the file is disposable, and on the HDD each
        # checkpoint's flush stalled the copy. The final checkpoint below runs with FULL, which makes it durable.
        db.execute("PRAGMA synchronous=OFF")
        # record_id (the primary key) is a hash, so every insert lands on a random page of its index; with the default
        # 2 MB cache each one was a disk seek on the HDD (~300 rows/s). The whole new file fits in this cache.
        db.execute(f"PRAGMA main.cache_size=-{BUILD_CACHE_KIB}")
        db.execute("ATTACH DATABASE ? AS src", (source_uri or state.resolve().as_uri() + "?mode=ro",))
        small = {}
        db.execute("BEGIN IMMEDIATE")
        for table in SMALL_TABLES:
            db.execute(f"INSERT INTO main.{table} SELECT * FROM src.{table}")
        db.execute("COMMIT")
        for table in SMALL_TABLES:
            small[table] = {"source": _table_digest(db, table, "src"), "copy": _table_digest(db, table, "main")}
            if small[table]["source"] != small[table]["copy"]:
                raise SplitError(f"SMALL_TABLE_MISMATCH:{table}")

        codec = PayloadCodec(db)
        samples: dict[str, list[str]] = {}
        counts: dict[str, int] = {}
        digest = hashlib.sha256()
        rows = encoded = plain_bytes = stored_bytes = 0
        last, started = 0, time.monotonic()
        columns = ",".join(RECORD_COLUMNS)
        insert = f"INSERT INTO main.market_stream_records(rowid,{columns}) VALUES ({','.join('?' * 12)})"
        while True:
            batch = db.execute(f"SELECT rowid,{columns} FROM src.market_stream_records WHERE rowid>? "
                               "ORDER BY rowid LIMIT ?", (last, BATCH_ROWS)).fetchall()
            if not batch:
                break
            out = []
            db.execute("BEGIN IMMEDIATE")
            for row in batch:
                payload = row[11]
                if not isinstance(payload, str):
                    raise SplitError(f"SOURCE_PAYLOAD_NOT_TEXT:rowid={row[0]}")
                scope = _scope(row[2], row[4])
                if codec.for_scope(scope) is None:
                    pool = samples.setdefault(scope, [])
                    pool.append(payload)
                    if len(pool) >= SAMPLE_ROWS:
                        codec.create(scope, pool)  # inside this batch's transaction, before any row uses it
                        samples.pop(scope)
                value = codec.encode(scope, payload)
                encoded += not isinstance(value, str)
                plain_bytes += len(payload.encode("utf-8"))
                stored_bytes += len(value) if isinstance(value, bytes) else len(value.encode("utf-8"))
                out.append((*row[:11], value))
                _row_digest(digest, tuple(row))
                counts[scope] = counts.get(scope, 0) + 1
            db.executemany(insert, out)
            db.execute("COMMIT")
            rows += len(batch)
            last = batch[-1][0]
            if rows % (BATCH_ROWS * 20) == 0:
                log(json.dumps({"event": "COPY_PROGRESS", "rows": rows, "last_rowid": last,
                                "elapsed_seconds": round(time.monotonic() - started, 1)}), flush=True)
        copy_seconds = round(time.monotonic() - started, 1)

        # Step 4: read back, decode, compare. A fresh codec reads the dictionaries from the file, not the cache.
        check, verify_counts, verify_rows = hashlib.sha256(), {}, 0
        reader = PayloadCodec(db)
        verify_started, last = time.monotonic(), 0
        while True:
            batch = db.execute(f"SELECT rowid,{columns} FROM main.market_stream_records WHERE rowid>? "
                               "ORDER BY rowid LIMIT ?", (last, BATCH_ROWS)).fetchall()
            if not batch:
                break
            for row in batch:
                decoded = reader.decode(row[11])
                _row_digest(check, (*row[:11], decoded))
                scope = _scope(row[2], row[4])
                verify_counts[scope] = verify_counts.get(scope, 0) + 1
            verify_rows += len(batch)
            last = batch[-1][0]
        if verify_rows != rows or verify_counts != counts or check.hexdigest() != digest.hexdigest():
            raise SplitError("RECORDS_VERIFY_MISMATCH")
        source_max = db.execute("SELECT max(rowid) FROM src.market_stream_records").fetchone()[0]
        copy_max = db.execute("SELECT max(rowid) FROM main.market_stream_records").fetchone()[0]
        if source_max != copy_max:
            raise SplitError("RECORDS_MAX_ROWID_MISMATCH")
        db.execute("DETACH DATABASE src")
        status = receipts.full_check(db)
        if status != "ok":
            raise SplitError(f"STREAM_STORE_INTEGRITY:{status}")
        db.execute("INSERT INTO stream_store_meta VALUES ('split_from', ?), ('split_rows', ?), ('split_sha256', ?)",
                   (str(state), str(rows), digest.hexdigest()))
        db.execute("PRAGMA synchronous=FULL")
        busy, _, _ = db.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        if busy:
            raise SplitError("STREAM_STORE_CHECKPOINT_BUSY")
        dictionaries = [dict(zip(("dictionary_id", "scope", "bytes"), row)) for row in
                        db.execute("SELECT dictionary_id, scope, length(dictionary) FROM payload_dictionaries")]
    finally:
        db.close()
    return {"rows": rows, "encoded_rows": encoded, "plain_payload_bytes": plain_bytes,
            "stored_payload_bytes": stored_bytes, "records_sha256": digest.hexdigest(), "per_scope": counts,
            "small_tables": small, "dictionaries": dictionaries, "copy_seconds": copy_seconds,
            "verify_seconds": round(time.monotonic() - verify_started, 1), "max_rowid": copy_max}


def shrink_state(state: Path) -> dict[str, Any]:
    """Step 5: empty the stream tables of the state store and compact it in place (same file identity)."""
    before, identity = _file_bytes(state), _identity(state)
    db = sqlite3.connect(str(state), timeout=30, isolation_level=None)
    try:
        db.execute("PRAGMA busy_timeout=30000")
        db.execute("BEGIN IMMEDIATE")
        for table in ("market_stream_records", *SMALL_TABLES):
            db.execute(f"DELETE FROM {table}")
        db.execute("COMMIT")
        started = time.monotonic()
        db.execute("PRAGMA temp_store=MEMORY")  # VACUUM's temp copy otherwise goes to TEMP on C:
        db.execute("VACUUM")
        vacuum_seconds = round(time.monotonic() - started, 1)
        busy, _, _ = db.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    finally:
        db.close()
    if _identity(state) != identity:
        raise SplitError("STATE_STORE_IDENTITY_CHANGED")
    return {"bytes_before": before, "bytes_after": _file_bytes(state), "vacuum_seconds": vacuum_seconds,
            "checkpoint_busy": bool(busy), "identity": list(identity)}


def verify_and_receipt(store: Path) -> dict[str, Any]:
    """Step 6: a full check of a file nothing else has open, recorded as its receipt."""
    with receipts.VerifyLock(store):
        started_epoch, started = time.time(), time.monotonic()
        with closing(_ro(store)) as db:
            status = receipts.full_check(db)
        elapsed = round(time.monotonic() - started, 3)
        if status != "ok":
            receipts.invalidate(store, f"FULL_CHECK:{status}", label=LABEL)
            raise SplitError(f"INTEGRITY:{store.name}:{status}")
        receipts.write_receipt(store, elapsed_seconds=elapsed, label=LABEL, started_at=started_epoch)
    return {"store": str(store), "result": "ok", "elapsed_seconds": elapsed, "bytes": _file_bytes(store)}


def run(state: Path, *, backup_dir: Path | None, evidence: Path | None, any_time: bool = False,
        log=print, in_memory: bool = False, reuse_backup: Path | None = None,
        reuse_backup_sha256: str | None = None) -> dict[str, Any]:
    state = state.resolve()
    result: dict[str, Any] = {"started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                              "state": str(state), "identity_before": list(_identity(state))}

    def save(stage: str) -> None:
        result["stage"] = stage
        if evidence is not None:
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
        log(json.dumps({"event": "STAGE", "stage": stage}), flush=True)

    memory = None
    try:
        _preconditions(state, any_time=any_time)
        _exclusive_checkpoint(state)
        save("PRECONDITIONS_OK")
        if reuse_backup is not None:
            result["backup"] = _reuse_backup(state, reuse_backup, reuse_backup_sha256)
            save("BACKUP_DONE")
        elif backup_dir is not None:
            result["backup"] = _copy_with_hash(state, backup_dir / state.name)
            save("BACKUP_DONE")
        if in_memory:
            memory, result["load"] = load_into_memory(state, log=log)
            save("LOADED_IN_MEMORY")
        partial = state.parent / PARTIAL_NAME
        result["copy"] = build(state, partial, log=log, source_uri=MEMORY_URI if in_memory else None)
        save("STREAM_STORE_VERIFIED")
        final = state.parent / STREAM_STORE_NAME
        if final.exists():
            raise SplitError("STREAM_STORE_APPEARED")
        wal = Path(str(partial) + "-wal")
        if wal.exists() and wal.stat().st_size:
            raise SplitError("STREAM_STORE_WAL_NOT_EMPTY")  # its frames would not follow the rename
        for suffix in ("-wal", "-shm"):
            Path(str(partial) + suffix).unlink(missing_ok=True)
        os.replace(partial, final)
        save("STREAM_STORE_IN_PLACE")
        if memory is not None:
            result["shrink"] = shrink_in_memory(memory, state, result["load"])
            memory.close()
            memory = None
        else:
            result["shrink"] = shrink_state(state)
        save("STATE_STORE_COMPACTED")
        result["verify"] = [verify_and_receipt(state), verify_and_receipt(final)]
        result["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save("COMPLETE")
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}:{exc}"
        save("FAILED")
        raise
    finally:
        if memory is not None:
            memory.close()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=("plan", "run"))
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--any-time", action="store_true", help="skip the night-window check (tests only)")
    parser.add_argument("--in-memory", action="store_true", help="read the store once into RAM, work there")
    parser.add_argument("--reuse-backup", type=Path, help="an earlier attempt's backup copy of this same store")
    parser.add_argument("--reuse-backup-sha256", help="that copy's recorded SHA-256 (for the evidence)")
    args = parser.parse_args(argv)
    if args.mode == "plan":
        print(json.dumps(plan(args.state), indent=2, default=str))
        return 0
    if args.backup_dir is None and args.reuse_backup is None:
        parser.error("run needs --backup-dir or --reuse-backup: the backup copy is the rollback")
    try:
        result = run(args.state, backup_dir=args.backup_dir, evidence=args.evidence, any_time=args.any_time,
                     in_memory=args.in_memory, reuse_backup=args.reuse_backup,
                     reuse_backup_sha256=args.reuse_backup_sha256)
    except SplitError as exc:
        print(json.dumps({"result": "FAILED", "error": str(exc)}), flush=True)
        return 2
    print(json.dumps({"result": "COMPLETE", "rows": result["copy"]["rows"], "shrink": result["shrink"],
                      "verify": result["verify"]}, default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
