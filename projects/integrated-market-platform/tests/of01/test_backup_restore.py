from __future__ import annotations

import unittest

from market_platform_foundation.of01.backup import BackupService, BackupState
from market_platform_foundation.of01.restore import RestoreService
from tests.of01.support import DisposableAuthority
from tests.of01.test_readers_stream import _register_run_envelope


class TestBackupRestore(unittest.TestCase):
    def test_create_and_verify_backup(self) -> None:
        auth = DisposableAuthority()
        try:
            writer = auth.open_writer()
            writer.submit(_register_run_envelope(auth.authority_id))
            writer.close()
            backup_root = auth.root / "backups"
            service = BackupService(
                auth.store,
                cas=auth.cas,
                db_path=auth.db_path,
                destination_root=backup_root,
            )
            manifest = service.create_backup()
            self.assertEqual(manifest.source_authority_id, auth.authority_id)
            verified = service.verify_backup(manifest)
            self.assertEqual(verified.state, BackupState.VERIFIED)
            restore = RestoreService(expected_authority_id=auth.authority_id)
            candidate = restore.load_candidate(backup_root / manifest.backup_id)
            result = restore.validate(candidate)
            self.assertEqual(result.authority_id, auth.authority_id)
            self.assertTrue(result.integrity_ok)
        finally:
            auth.close()


if __name__ == "__main__":
    unittest.main()
