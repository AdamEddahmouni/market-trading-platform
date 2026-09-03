from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


def _sha256(path: Path, chunk_size: int) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_inventory(database_path: Path, *, chunk_size: int = 8_388_608) -> dict[str, object]:
    database_path = database_path.resolve(strict=True)
    before = database_path.stat()
    uri = f"file:{database_path.as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        names = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        tables = {
            name: int(connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0])
            for name in names
        }
        quick_check = str(connection.execute("PRAGMA quick_check").fetchone()[0])
        price_bounds = (
            connection.execute(
                "SELECT MIN(date), MAX(date), COUNT(DISTINCT ticker_id) FROM daily_prices"
            ).fetchone()
            if "daily_prices" in names
            else (None, None, 0)
        )
    finally:
        connection.close()
    digest = _sha256(database_path, chunk_size)
    after = database_path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError("RAW_DATABASE_CHANGED_DURING_INVENTORY")
    return {
        "database_path": str(database_path),
        "size_bytes": before.st_size,
        "modified_time_ns": before.st_mtime_ns,
        "sha256": digest,
        "quick_check": quick_check,
        "tables": tables,
        "daily_prices": {
            "minimum_date": price_bounds[0],
            "maximum_date": price_bounds[1],
            "instrument_count": int(price_bounds[2]),
        },
    }


def write_inventory(database_path: Path, output_path: Path) -> dict[str, object]:
    result = build_inventory(database_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    write_inventory(args.database, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
