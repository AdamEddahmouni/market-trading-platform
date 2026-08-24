import hashlib
import json
import sqlite3
from pathlib import Path

from src.inventory import build_inventory, write_inventory


def _database(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE tickers(id INTEGER PRIMARY KEY, ticker TEXT UNIQUE);
        CREATE TABLE daily_prices(
            ticker_id INTEGER NOT NULL, date TEXT NOT NULL,
            open REAL NOT NULL, high REAL NOT NULL, low REAL NOT NULL,
            close REAL NOT NULL, volume INTEGER NOT NULL, adj_close REAL
        );
        INSERT INTO tickers VALUES (1, 'TEST');
        INSERT INTO daily_prices VALUES
            (1, '2026-08-21', 10, 12, 9, 11, 1000, 11);
        """
    )
    connection.commit()
    connection.close()


def test_inventory_hashes_and_counts_without_writing_database(tmp_path):
    database = tmp_path / "raw.sqlite3"
    _database(database)
    before = database.read_bytes()
    result = build_inventory(database, chunk_size=7)
    assert result["sha256"] == hashlib.sha256(before).hexdigest()
    assert result["quick_check"] == "ok"
    assert result["tables"]["tickers"] == 1
    assert result["tables"]["daily_prices"] == 1
    assert result["daily_prices"]["minimum_date"] == "2026-08-21"
    assert result["daily_prices"]["maximum_date"] == "2026-08-21"
    assert database.read_bytes() == before


def test_write_inventory_uses_sorted_json(tmp_path):
    database = tmp_path / "raw.sqlite3"
    output = tmp_path / "inventory.json"
    _database(database)
    observed = write_inventory(database, output)
    assert json.loads(output.read_text(encoding="utf-8")) == observed
    assert output.read_text(encoding="utf-8").endswith("\n")
