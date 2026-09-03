from __future__ import annotations

import time
import unittest

from market_platform_foundation.of01.authorization import AuthorizationGrant, FakeAuthorizationVerifier
from market_platform_foundation.of01.errors import OF01Error
from market_platform_foundation.of01.operations import CAPABILITY_IDS, OperationsService
from tests.of01.support import DisposableAuthority


class TestAuthorization(unittest.TestCase):
    def test_fake_verifier_accepts_matching_grant(self) -> None:
        now = time.time_ns()
        grant = AuthorizationGrant(
            issuer_identity="test-issuer",
            reference="ref-1",
            capability_id="OF01.OP.BACKUP_CREATE",
            ledger_authority_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            input_hash="ABC",
            initiator_ref="operator",
            allowed_role="maintenance_operator",
            not_before_ns=now - 1,
            expires_at_ns=now + 1_000_000_000,
            revoked=False,
            revocation_version=1,
        )
        verifier = FakeAuthorizationVerifier({"ref-1": grant})
        result = verifier.verify(
            "ref-1",
            capability_id="OF01.OP.BACKUP_CREATE",
            ledger_authority_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            input_hash="ABC",
            initiator_ref="operator",
            observed_at_ns=now,
        )
        self.assertEqual(result.reference, "ref-1")

    def test_expired_grant_rejected(self) -> None:
        now = time.time_ns()
        grant = AuthorizationGrant(
            issuer_identity="test-issuer",
            reference="ref-2",
            capability_id="OF01.OP.BACKUP_CREATE",
            ledger_authority_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            input_hash="ABC",
            initiator_ref="operator",
            allowed_role="maintenance_operator",
            not_before_ns=now - 10,
            expires_at_ns=now - 1,
            revoked=False,
            revocation_version=1,
        )
        verifier = FakeAuthorizationVerifier({"ref-2": grant})
        with self.assertRaises(OF01Error):
            verifier.verify(
                "ref-2",
                capability_id="OF01.OP.BACKUP_CREATE",
                ledger_authority_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                input_hash="ABC",
                initiator_ref="operator",
                observed_at_ns=now,
            )


class TestOperations(unittest.TestCase):
    def test_capability_inventory_complete(self) -> None:
        expected = {
            "OF01.OP.STATUS",
            "OF01.OP.LEDGER_METADATA",
            "OF01.OP.COMMAND_RESOLVE",
            "OF01.OP.SHUTDOWN",
            "OF01.OP.INTEGRITY_QUICK",
        }
        self.assertTrue(expected.issubset(CAPABILITY_IDS))

    def test_status_operation(self) -> None:
        auth = DisposableAuthority()
        try:
            service = OperationsService(store=auth.store)
            result = service.execute("OF01.OP.STATUS")
            self.assertEqual(result.capability_id, "OF01.OP.STATUS")
            self.assertIn("status", result.verification)
        finally:
            auth.close()


if __name__ == "__main__":
    unittest.main()
