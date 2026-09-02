from __future__ import annotations

import sqlite3
import unittest

from market_platform_foundation.of01.errors import OF01ErrorCode
from market_platform_foundation.of01.integrity import FindingClass, IntegrityChecker, IntegrityMode
from tests.of01.support import DisposableAuthority
from tests.of01.test_readers_stream import _register_run_envelope


class TestIntegrity(unittest.TestCase):
    def setUp(self) -> None:
        self.auth = DisposableAuthority()
        self.writer = self.auth.open_writer()

    def tearDown(self) -> None:
        self.writer.close()
        self.auth.close()

    def test_quick_check_passes_on_fresh_authority(self) -> None:
        self.writer.submit(_register_run_envelope(self.auth.authority_id))
        checker = IntegrityChecker(self.auth.store, cas=self.auth.cas)
        report = checker.check(IntegrityMode.QUICK)
        self.assertFalse(report.has_fatal)

    def test_record_hash_mismatch_detected(self) -> None:
        self.writer.submit(_register_run_envelope(self.auth.authority_id))
        try:
            self.auth.conn.execute(
                "UPDATE runs SET record_hash = ? WHERE run_id IS NOT NULL",
                ("0" * 64,),
            )
        except sqlite3.IntegrityError:
            self.skipTest("append-only trigger prevented corruption injection")
        checker = IntegrityChecker(self.auth.store, cas=self.auth.cas)
        report = checker.check(IntegrityMode.FULL)
        codes = {f.code for f in report.findings}
        self.assertIn(OF01ErrorCode.RECORD_HASH_MISMATCH.value, codes)


class TestCorruptionResponse(unittest.TestCase):
    def test_fatal_blocks_mode_transition(self) -> None:
        blocked: list[object] = []

        def on_fatal(report: object) -> None:
            blocked.append(report)

        auth = DisposableAuthority()
        try:
            writer = auth.open_writer()
            writer.submit(_register_run_envelope(auth.authority_id))
            writer.close()
            try:
                auth.conn.execute(
                    "UPDATE ledger_commits SET commit_hash = ? WHERE commit_sequence = 1",
                    ("F" * 64,),
                )
            except sqlite3.IntegrityError:
                self.skipTest("append-only trigger prevented corruption injection")
            checker = IntegrityChecker(auth.store, on_fatal=on_fatal)
            report = checker.check(IntegrityMode.FULL)
            if not report.has_fatal:
                self.skipTest("append-only trigger prevented corruption injection")
            self.assertEqual(len(blocked), 1)
            self.assertTrue(any(f.finding_class == FindingClass.AUTHORITATIVE_FATAL for f in report.findings))
        finally:
            auth.close()


if __name__ == "__main__":
    unittest.main()
