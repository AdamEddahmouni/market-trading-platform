"""Shared disposable authority fixtures for OF-01 tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

from market_platform_foundation.of01.cas import LocalCAS
from market_platform_foundation.of01.ids import new_uuid
from market_platform_foundation.of01.migrations import open_authority
from market_platform_foundation.of01.sqlite_store import SQLiteAuthorityStore
from market_platform_foundation.of01.writer import SQLiteAuthoritativeLedgerWriter, WriterConfig


class DisposableAuthority:
    def __init__(self) -> None:
        self.authority_id = new_uuid()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.db_path = self.root / "ledger.sqlite3"
        self.cas_root = self.root / "cas"
        self._writer: SQLiteAuthoritativeLedgerWriter | None = None
        self.conn = open_authority(self.db_path, ledger_authority_id=self.authority_id)
        self.store = SQLiteAuthorityStore(self.conn, ledger_authority_id=self.authority_id)
        self.cas = LocalCAS(self.cas_root)

    def open_writer(self, *, acquire_lock: bool = False) -> SQLiteAuthoritativeLedgerWriter:
        if self._writer is not None:
            self._writer.close()
        self._writer = SQLiteAuthoritativeLedgerWriter(
            self.store,
            cas=self.cas,
            config=WriterConfig(),
            process_lock=None,
        )
        return self._writer

    def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            self._writer = None
        if self.conn is not None:
            self.conn.close()
            self.conn = None  # type: ignore[assignment]
        self._tmpdir.cleanup()
