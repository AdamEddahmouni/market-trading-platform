"""Deterministic fault-injection drills at commit boundaries."""

from __future__ import annotations

import queue
import unittest
from unittest.mock import patch

from market_platform_foundation.of01.errors import OF01Error, OF01ErrorCode
from market_platform_foundation.of01.writer import SQLiteAuthoritativeLedgerWriter, WriterConfig
from tests.of01.support import DisposableAuthority
from tests.of01.test_readers_stream import _register_run_envelope


class TestFaultInjection(unittest.TestCase):
    def test_duplicate_command_id_is_idempotent(self) -> None:
        auth = DisposableAuthority()
        writer = auth.open_writer()
        try:
            envelope = _register_run_envelope(auth.authority_id)
            first = writer.submit(envelope)
            second = writer.submit(envelope)
            self.assertEqual(first.commit_sequence, second.commit_sequence)
            self.assertTrue(second.was_existing)
        finally:
            writer.close()
            auth.close()

    def test_queue_backpressure_surfaces_typed_code(self) -> None:
        auth = DisposableAuthority()
        writer = SQLiteAuthoritativeLedgerWriter(
            auth.store,
            config=WriterConfig(queue_capacity=1),
        )
        try:
            envelope = _register_run_envelope(auth.authority_id)
            with patch.object(writer._queue, "put", side_effect=queue.Full):
                with self.assertRaises(OF01Error) as ctx:
                    writer.submit(envelope)
            self.assertEqual(ctx.exception.code, OF01ErrorCode.ADMISSION_BACKPRESSURE)
        finally:
            writer.close()
            auth.close()


if __name__ == "__main__":
    unittest.main()
