"""Operational acceptance drills for IMP-OF-01 Tasks 9-16."""

from __future__ import annotations

import unittest

from market_platform_foundation.of01.backup import BackupService, BackupState
from market_platform_foundation.of01.health import HealthService, RuntimeMode
from market_platform_foundation.of01.integrity import IntegrityChecker, IntegrityMode
from market_platform_foundation.of01.operations import CAPABILITY_IDS
from market_platform_foundation.of01.restore import RestoreService
from tests.of01.support import DisposableAuthority
from tests.of01.test_readers_stream import _register_run_envelope


class TestAcceptanceDrills(unittest.TestCase):
    def test_end_to_end_operational_surface(self) -> None:
        auth = DisposableAuthority()
        try:
            writer = auth.open_writer()
            envelope = _register_run_envelope(auth.authority_id)
            receipt = writer.submit(envelope)
            writer.close()

            health = HealthService(auth.store, cas=auth.cas)
            status = health.startup_checks(db_path=auth.db_path, cas_root=auth.cas_root)
            self.assertTrue(status.liveness)
            self.assertIn(status.mode, {RuntimeMode.READY, RuntimeMode.DEGRADED})

            checker = IntegrityChecker(auth.store, cas=auth.cas)
            report = checker.check(IntegrityMode.QUICK)
            self.assertFalse(report.has_fatal)

            backup_root = auth.root / "backups"
            backup = BackupService(
                auth.store,
                cas=auth.cas,
                db_path=auth.db_path,
                destination_root=backup_root,
            ).create_backup()
            verified = BackupService(
                auth.store,
                cas=auth.cas,
                db_path=auth.db_path,
                destination_root=backup_root,
            ).verify_backup(backup)
            self.assertEqual(verified.state, BackupState.VERIFIED)

            restore = RestoreService(expected_authority_id=auth.authority_id)
            candidate = restore.load_candidate(backup_root / backup.backup_id)
            validation = restore.validate(candidate)
            self.assertTrue(validation.integrity_ok)

            self.assertIn("OF01.OP.STATUS", CAPABILITY_IDS)
            self.assertGreaterEqual(receipt.commit_sequence, 1)
        finally:
            auth.close()


if __name__ == "__main__":
    unittest.main()
