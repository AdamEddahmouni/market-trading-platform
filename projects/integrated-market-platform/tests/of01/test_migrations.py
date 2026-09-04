from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.of01.errors import OF01Error, OF01ErrorCode
from market_platform_foundation.of01.migrations import (
    apply_migrations,
    bootstrap_authority,
    current_database_schema_version,
    open_authority,
)
from market_platform_foundation.of01.sqlite_schema import SCHEMA_VERSION
from market_platform_foundation.of01.sqlite_store import configure_connection


AUTHORITY_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


class TestMigrations(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_fresh_bootstrap(self) -> None:
        db_path = self.root / "fresh.sqlite3"
        conn = bootstrap_authority(db_path, ledger_authority_id=AUTHORITY_ID)
        try:
            self.assertEqual(current_database_schema_version(conn), SCHEMA_VERSION)
            row = conn.execute(
                "SELECT ledger_authority_id FROM ledger_metadata WHERE singleton = 1"
            ).fetchone()
            self.assertEqual(row[0], AUTHORITY_ID)
        finally:
            conn.close()

    def test_idempotent_reopen(self) -> None:
        db_path = self.root / "reopen.sqlite3"
        conn1 = bootstrap_authority(db_path, ledger_authority_id=AUTHORITY_ID)
        conn1.close()
        conn2 = open_authority(db_path, ledger_authority_id=AUTHORITY_ID)
        try:
            self.assertEqual(current_database_schema_version(conn2), SCHEMA_VERSION)
        finally:
            conn2.close()

    def test_authority_mismatch_rejected(self) -> None:
        db_path = self.root / "mismatch.sqlite3"
        conn = bootstrap_authority(db_path, ledger_authority_id=AUTHORITY_ID)
        conn.close()
        with self.assertRaises(OF01Error) as ctx:
            open_authority(
                db_path,
                ledger_authority_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            )
        self.assertEqual(ctx.exception.code, OF01ErrorCode.AUTHORITY_IDENTITY_MISMATCH)

    def test_unknown_newer_schema_rejected(self) -> None:
        db_path = self.root / "newer.sqlite3"
        conn = sqlite3.connect(str(db_path))
        configure_connection(conn)
        conn.execute(
            """
            CREATE TABLE ledger_metadata (
              singleton INTEGER PRIMARY KEY,
              ledger_authority_id TEXT NOT NULL,
              database_schema_version INTEGER NOT NULL
            ) STRICT
            """
        )
        conn.execute(
            "INSERT INTO ledger_metadata VALUES (1, ?, 99)",
            (AUTHORITY_ID,),
        )
        conn.commit()
        with self.assertRaises(OF01Error) as ctx:
            apply_migrations(conn)
        self.assertEqual(ctx.exception.code, OF01ErrorCode.SCHEMA_UNSUPPORTED)
        conn.close()

    def test_interrupted_transaction_rolls_back(self) -> None:
        db_path = self.root / "interrupt.sqlite3"
        conn = sqlite3.connect(str(db_path))
        configure_connection(conn)
        conn.execute("BEGIN IMMEDIATE")
        apply_migrations(conn)
        conn.execute("ROLLBACK")
        self.assertIsNone(current_database_schema_version(conn))
        conn.close()


if __name__ == "__main__":
    unittest.main()
