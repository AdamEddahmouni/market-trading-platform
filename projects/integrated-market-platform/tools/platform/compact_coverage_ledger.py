"""One-time compression of the AI coverage ledger's existing records in the state store (2026-10-27).

  compact_coverage_ledger.py plan --state <imp-state.sqlite3>
  compact_coverage_ledger.py run  --state <imp-state.sqlite3> --backup-dir <dir> --evidence <file.json>

New records are compressed as they are written (local_state/ai_screener_coverage.py); this converts the records
written before that, which were 1.61 GB of the 10 GB store. ``run`` needs every IMP process stopped and the night
window (as split_stream_store.py). Steps, each fail-closed:

1. Fresh ``ok`` receipt, no market writer, WAL folded and no other connection (BEGIN EXCLUSIVE).
2. Backup copy with SHA-256 into ``--backup-dir`` (the rollback).
3. The store is read once into RAM (split_stream_store.load_into_memory). For each record kind without a
   dictionary, one is made from that kind's latest plain records (the scope the ledger itself uses), then every
   plain record is replaced by the codec's encoding (verified per value; kept plain if it would not round-trip).
4. A SHA-256 over (run_id, seq, kind, decoded payload) of every record in rowid order must equal the one taken before
   any change; every other table's row count must be unchanged; ``integrity_check`` must be ok.
5. VACUUM in RAM, then written back into the same file (same identity, WAL kept), full check, receipt.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
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
from market_platform_foundation.local_state.payload_codec import SAMPLE_ROWS, PayloadCodec  # noqa: E402
from market_platform_foundation.market_data.persistence import owner_lock_held  # noqa: E402
from tools.platform.split_stream_store import (SplitError, _copy_with_hash, _exclusive_checkpoint,  # noqa: E402
                                               _identity, _ro, _table_counts, in_night_window, load_into_memory,
                                               verify_and_receipt, write_back)

TABLE = "ai_screener_coverage_records"
BATCH_ROWS = 2_000


def _scope(kind: str) -> str:
    return f"ai_screener_coverage:{kind}"


def _digest(db, codec: PayloadCodec) -> tuple[int, str]:
    digest, count = hashlib.sha256(), 0
    for run_id, seq, kind, payload in db.execute(f"SELECT run_id, seq, kind, payload FROM {TABLE} ORDER BY rowid"):
        digest.update(json.dumps([run_id, seq, kind, codec.decode(payload)], separators=(",", ":")).encode("utf-8"))
        digest.update(b"\n")
        count += 1
    return count, digest.hexdigest()


def plan(state: Path) -> dict[str, Any]:
    with closing(_ro(state)) as db:
        kinds = {kind: dict(rows=rows, text_rows=text, text_bytes=size) for kind, rows, text, size in db.execute(
            f"SELECT kind, COUNT(*), SUM(typeof(payload)='text'), SUM(CASE WHEN typeof(payload)='text' "
            f"THEN length(CAST(payload AS BLOB)) ELSE 0 END) FROM {TABLE} GROUP BY kind")}
    return {"state": str(state), "state_bytes": state.stat().st_size, "kinds": kinds,
            "receipt_problem": receipts.receipt_problem(state), "writer_owner_lock_held": owner_lock_held(state),
            "in_night_window": in_night_window()}


def compress_in_memory(memory, *, log=print) -> dict[str, Any]:
    reader = PayloadCodec(memory)
    rows_before, digest_before = _digest(memory, reader)
    counts_before = _table_counts(memory, skip=(TABLE,))
    codec = PayloadCodec(memory)
    kinds = [row[0] for row in memory.execute(f"SELECT DISTINCT kind FROM {TABLE}")]
    memory.execute("BEGIN IMMEDIATE")
    try:
        for kind in kinds:
            if codec.for_scope(_scope(kind)) is None:
                samples = [row[0] for row in memory.execute(
                    f"SELECT payload FROM {TABLE} WHERE kind=? AND typeof(payload)='text' ORDER BY rowid DESC LIMIT ?",
                    (kind, SAMPLE_ROWS))]
                codec.create(_scope(kind), list(reversed(samples)))
        converted = kept_plain = 0
        last, started = 0, time.monotonic()
        while True:
            batch = memory.execute(f"SELECT rowid, kind, payload FROM {TABLE} WHERE rowid>? AND typeof(payload)='text' "
                                   "ORDER BY rowid LIMIT ?", (last, BATCH_ROWS)).fetchall()
            if not batch:
                break
            updates = []
            for rowid, kind, payload in batch:
                value = codec.encode(_scope(kind), payload)
                if isinstance(value, str):
                    kept_plain += 1
                else:
                    updates.append((value, rowid))
            memory.executemany(f"UPDATE {TABLE} SET payload=? WHERE rowid=?", updates)
            converted += len(updates)
            last = batch[-1][0]
        memory.execute("COMMIT")
    except BaseException:
        memory.execute("ROLLBACK")
        raise
    convert_seconds = round(time.monotonic() - started, 1)
    rows_after, digest_after = _digest(memory, PayloadCodec(memory))
    if (rows_after, digest_after) != (rows_before, digest_before):
        raise SplitError("COVERAGE_RECORDS_VERIFY_MISMATCH")
    if _table_counts(memory, skip=(TABLE, "payload_dictionaries")) != {
            k: v for k, v in counts_before.items() if k != "payload_dictionaries"}:
        raise SplitError("OTHER_TABLE_COUNTS_CHANGED")
    started = time.monotonic()
    memory.execute("PRAGMA temp_store=MEMORY")
    memory.execute("VACUUM")
    vacuum_seconds = round(time.monotonic() - started, 1)
    status = receipts.full_check(memory)
    if status != "ok":
        raise SplitError(f"MEMORY_COPY_INTEGRITY:{status}")
    log(json.dumps({"event": "COMPRESSED", "rows": rows_after, "converted": converted, "kept_plain": kept_plain}),
        flush=True)
    return {"rows": rows_after, "converted": converted, "kept_plain": kept_plain, "records_sha256": digest_after,
            "convert_seconds": convert_seconds, "vacuum_seconds": vacuum_seconds,
            "dictionaries": [dict(zip(("dictionary_id", "scope"), row)) for row in memory.execute(
                "SELECT dictionary_id, scope FROM payload_dictionaries WHERE scope LIKE 'ai_screener_coverage:%'")]}


def run(state: Path, *, backup_dir: Path | None, evidence: Path | None, any_time: bool = False,
        log=print) -> dict[str, Any]:
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
        if not any_time and not in_night_window():
            raise SplitError("OUTSIDE_NIGHT_WINDOW")
        problem = receipts.receipt_problem(state)
        if problem is not None:
            raise SplitError(f"STATE_RECEIPT_NOT_FRESH:{problem}")
        if owner_lock_held(state):
            raise SplitError("MARKET_WRITER_RUNNING")
        _exclusive_checkpoint(state)
        save("PRECONDITIONS_OK")
        if backup_dir is not None:
            result["backup"] = _copy_with_hash(state, backup_dir / state.name)
            save("BACKUP_DONE")
        memory, result["load"] = load_into_memory(state, log=log)
        save("LOADED_IN_MEMORY")
        result["compress"] = compress_in_memory(memory, log=log)
        save("COMPRESSED_IN_MEMORY")
        result["write_back"] = write_back(memory, state, result["load"])
        memory.close()
        memory = None
        save("WRITTEN_BACK")
        result["verify"] = verify_and_receipt(state)
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
    args = parser.parse_args(argv)
    if args.mode == "plan":
        print(json.dumps(plan(args.state), indent=2, default=str))
        return 0
    if args.backup_dir is None:
        parser.error("run needs --backup-dir: the backup copy is the rollback")
    try:
        result = run(args.state, backup_dir=args.backup_dir, evidence=args.evidence, any_time=args.any_time)
    except SplitError as exc:
        print(json.dumps({"result": "FAILED", "error": str(exc)}), flush=True)
        return 2
    print(json.dumps({"result": "COMPLETE", "compress": {k: v for k, v in result["compress"].items()
                                                         if k != "dictionaries"},
                      "write_back": {k: v for k, v in result["write_back"].items() if k != "table_counts"}},
                     default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
