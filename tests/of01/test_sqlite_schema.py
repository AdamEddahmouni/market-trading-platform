from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.of01.migrations import apply_migrations, bootstrap_authority_metadata
from market_platform_foundation.of01.sqlite_schema import (
    ALL_TABLES,
    AUTHORITATIVE_TABLES,
    CREATE_INDEX_STATEMENTS,
    MIGRATION_V1_STATEMENTS,
    SCHEMA_VERSION,
    append_only_trigger_sql,
)


class TestSQLiteSchema(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "authority.sqlite3"
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute("PRAGMA foreign_keys=ON")

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def test_migration_creates_all_tables(self) -> None:
        apply_migrations(self.conn)
        tables = {
            row[0]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        }
        for table in ALL_TABLES:
            self.assertIn(table, tables)

    def test_tables_are_strict(self) -> None:
        apply_migrations(self.conn)
        for table in ALL_TABLES:
            row = self.conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertIn("STRICT", str(row[0]))

    def test_append_only_triggers_exist(self) -> None:
        apply_migrations(self.conn)
        for table in AUTHORITATIVE_TABLES:
            for suffix in ("append_only_update", "append_only_delete"):
                name = f"trg_{table}_{suffix}"
                row = self.conn.execute(
                    "SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",
                    (name,),
                ).fetchone()
                self.assertIsNotNone(row, name)

    def test_append_only_triggers_block_mutation(self) -> None:
        apply_migrations(self.conn)
        bootstrap_authority_metadata(
            self.conn,
            ledger_authority_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            created_at_ns=1,
        )
        self.conn.execute("COMMIT")
        with self.assertRaises((sqlite3.OperationalError, sqlite3.IntegrityError)):
            self.conn.execute(
                "UPDATE ledger_metadata SET created_at_ns = 2 WHERE singleton = 1"
            )
        with self.assertRaises((sqlite3.OperationalError, sqlite3.IntegrityError)):
            self.conn.execute("DELETE FROM ledger_metadata WHERE singleton = 1")

    def test_indexes_created(self) -> None:
        apply_migrations(self.conn)
        index_names = {
            row[0]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
        }
        for statement in CREATE_INDEX_STATEMENTS:
            name = statement.split("INDEX ")[1].split(" ON")[0]
            self.assertIn(name, index_names)

    def test_trigger_sql_matches_spec(self) -> None:
        update_sql, delete_sql = append_only_trigger_sql("runs")
        self.assertIn("trg_runs_append_only_update", update_sql)
        self.assertIn("OF01_APPEND_ONLY_UPDATE_PROHIBITED", update_sql)
        self.assertIn("trg_runs_append_only_delete", delete_sql)
        self.assertIn("OF01_APPEND_ONLY_DELETE_PROHIBITED", delete_sql)

    def test_schema_version_constant(self) -> None:
        self.assertEqual(SCHEMA_VERSION, 1)
        self.assertGreater(len(MIGRATION_V1_STATEMENTS), 20)


if __name__ == "__main__":
    unittest.main()
