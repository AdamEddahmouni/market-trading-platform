"""Agent operating policy negative tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.of01.authorization import AuthorizationGrant, FakeAuthorizationVerifier
from market_platform_foundation.of01.errors import OF01Error, OF01ErrorCode
from market_platform_foundation.of01.operations import OperationsService
from tests.of01.support import DisposableAuthority


class TestAgentPolicy(unittest.TestCase):
    def test_arbitrary_sql_not_exposed_by_operations(self) -> None:
        auth = DisposableAuthority()
        try:
            service = OperationsService(store=auth.store)
            with self.assertRaises(OF01Error):
                service.execute("OF01.OP.ARBITRARY_SQL")
        finally:
            auth.close()

    def test_caller_supplied_grant_claims_rejected(self) -> None:
        now = __import__("time").time_ns()
        grant = AuthorizationGrant(
            issuer_identity="test",
            reference="ref-x",
            capability_id="OF01.OP.BACKUP_CREATE",
            ledger_authority_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            input_hash="ABC",
            initiator_ref="agent",
            allowed_role="maintenance_operator",
            not_before_ns=now - 1,
            expires_at_ns=now + 1_000_000,
            revoked=False,
            revocation_version=1,
        )
        verifier = FakeAuthorizationVerifier({"ref-x": grant})
        with self.assertRaises(OF01Error) as ctx:
            verifier.verify(
                "ref-x",
                capability_id="OF01.OP.BACKUP_CREATE",
                ledger_authority_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                input_hash="ABC",
                initiator_ref="agent",
                observed_at_ns=now,
            )
        self.assertEqual(ctx.exception.code, OF01ErrorCode.AUTHORIZATION_REQUIRED)

    def test_agent_rules_forbid_projection_as_authority(self) -> None:
        rules = (DisposableAuthority.__module__)  # placeholder import path
        del rules
        text = (
            __import__("pathlib").Path(__file__).resolve().parents[2]
            / "docs"
            / "operations"
            / "of-01"
            / "AGENT_OPERATING_RULES.md"
        ).read_text(encoding="utf-8")
        self.assertIn("projection", text.lower())
        self.assertIn("MUST NOT", text)


if __name__ == "__main__":
    unittest.main()
