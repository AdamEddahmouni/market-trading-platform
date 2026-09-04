from __future__ import annotations

import unittest
from dataclasses import dataclass, field

from market_platform_foundation.of01.memory import InMemoryLedger
from market_platform_foundation.of01.projections import ProjectionCursorStore, ProjectionReplayer
from market_platform_foundation.of01.protocols import CommitBundle
from tests.of01.support import DisposableAuthority


@dataclass
class FakeProjection:
    applied: list[CommitBundle] = field(default_factory=list)

    def apply(self, bundle: CommitBundle) -> None:
        self.applied.append(bundle)

    def reset(self) -> None:
        self.applied.clear()


class TestProjectionReplay(unittest.TestCase):
    def test_sqlite_cursor_advances(self) -> None:
        auth = DisposableAuthority()
        try:
            from tests.of01.test_readers_stream import _register_run_envelope

            writer = auth.open_writer()
            writer.submit(_register_run_envelope(auth.authority_id))
            writer.close()
            reader = auth.store
            from market_platform_foundation.of01.readers import SQLiteLedgerReader

            ledger_reader = SQLiteLedgerReader(auth.store)
            cursor = ProjectionCursorStore(auth.store)
            consumer = FakeProjection()
            replayer = ProjectionReplayer(
                stream=ledger_reader.stream_commits,
                cursor_store=cursor,
                projection_name="test",
                projection_version="v1",
            )
            applied = replayer.replay(consumer)
            self.assertEqual(applied, 1)
            status = cursor.get_status(projection_name="test", projection_version="v1")
            self.assertEqual(status.last_applied_commit_sequence, 1)
            self.assertEqual(len(consumer.applied), 1)
        finally:
            auth.close()

    def test_rebuild_replays_from_zero(self) -> None:
        ledger = InMemoryLedger(__import__("market_platform_foundation.of01.ids", fromlist=["new_uuid"]).new_uuid())
        from tests.of01.test_readers_stream import _register_run_envelope

        ledger.submit(_register_run_envelope(ledger.ledger_authority_id))
        consumer = FakeProjection()
        applied = 0
        for bundle in ledger.stream_commits(0):
            consumer.apply(bundle)
            applied += 1
        self.assertEqual(applied, 1)


if __name__ == "__main__":
    unittest.main()
