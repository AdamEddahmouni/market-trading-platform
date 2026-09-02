from __future__ import annotations

import unittest

from market_platform_foundation.of01.errors import OF01Error
from market_platform_foundation.of01.health import HealthService, RuntimeMode
from market_platform_foundation.of01.maintenance import MaintenancePurpose, MaintenanceService
from tests.of01.support import DisposableAuthority
from tests.of01.test_readers_stream import _register_run_envelope


class TestRuntimeLifecycle(unittest.TestCase):
    def test_startup_reaches_ready(self) -> None:
        auth = DisposableAuthority()
        try:
            writer = auth.open_writer()
            writer.submit(_register_run_envelope(auth.authority_id))
            writer.close()
            health = HealthService(auth.store, cas=auth.cas)
            status = health.startup_checks(db_path=auth.db_path, cas_root=auth.cas_root)
            self.assertTrue(status.liveness)
            self.assertIn(status.mode, {RuntimeMode.READY, RuntimeMode.DEGRADED})
        finally:
            auth.close()

    def test_shutdown_records_stopped(self) -> None:
        auth = DisposableAuthority()
        try:
            health = HealthService(auth.store)
            status = health.shutdown()
            self.assertEqual(status.mode, RuntimeMode.STOPPED)
        finally:
            auth.close()


class TestMaintenance(unittest.TestCase):
    def test_enter_and_exit_maintenance(self) -> None:
        auth = DisposableAuthority()
        try:
            service = MaintenanceService(auth.store)
            enter = service.enter(
                purpose=MaintenancePurpose.BACKUP,
                authorization_ref="auth-ref-1",
                owner_ref="operator",
                expected_revision=0,
            )
            self.assertIsNotNone(enter.lease)
            assert enter.lease is not None
            exit_result = service.exit(
                lease_id=enter.lease.lease_id,
                expected_revision=enter.runtime_revision,
            )
            self.assertEqual(exit_result.mode.value, "READY")
        finally:
            auth.close()

    def test_revision_mismatch_rejected(self) -> None:
        auth = DisposableAuthority()
        try:
            service = MaintenanceService(auth.store)
            with self.assertRaises(OF01Error):
                service.enter(
                    purpose=MaintenancePurpose.GENERAL,
                    authorization_ref="auth-ref-1",
                    owner_ref="operator",
                    expected_revision=99,
                )
        finally:
            auth.close()


if __name__ == "__main__":
    unittest.main()
