"""TD-005 authentication, authorization, and account-access enforcement tests."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from market_platform_foundation.paper.ledger import PaperExecutionLedger
from market_platform_foundation.platform.security.access_control import (
    AuthorizationFailure,
    AuthorizedPrincipal,
    ROLE_ENFORCEMENT_ENFORCED,
    ROLE_ENFORCEMENT_LOOPBACK_TRUST,
    login_principal,
    reset_principal_registry_for_tests,
    role_enforcement_status,
)
from market_platform_foundation.platform.security.auth_config import AuthEnforcementMode, load_auth_config
from market_platform_foundation.platform.security.roles import (
    OperatorRole,
    ROLE_ENFORCEMENT_STATUS,
    role_allows,
)
from market_platform_foundation.ui_api.request_auth import authorize_http_request
from market_platform_foundation.ui_api.store import ReplayStore

PRINCIPALS_FIXTURE = ROOT / "fixtures" / "auth" / "principals.json"
COLLECTION_ROOT = ROOT.parent


def _store_with_paper() -> ReplayStore:
    store = ReplayStore(collection_root=COLLECTION_ROOT)
    ledger = PaperExecutionLedger.open_session(
        replay_session_id=store.session_id,
        instrument_id="AAPL",
        symbol="AAPL",
        execution_mode="INTERNAL_SIMULATION",
        execution_authority="AUTHORIZED",
    )
    store.paper_ledger = ledger
    return store


class AuthConfigIsolationTest(unittest.TestCase):
    def setUp(self) -> None:
        reset_principal_registry_for_tests()
        self._env_backup = dict(os.environ)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env_backup)
        reset_principal_registry_for_tests()

    def test_loopback_trust_default(self) -> None:
        os.environ.pop("IMP_AUTH_ENFORCEMENT_MODE", None)
        os.environ.pop("IMP_AUTH_ENFORCEMENT", None)
        config = load_auth_config()
        self.assertEqual(config.enforcement_mode, AuthEnforcementMode.LOOPBACK_TRUST)
        self.assertEqual(role_enforcement_status(), ROLE_ENFORCEMENT_LOOPBACK_TRUST)
        self.assertEqual(ROLE_ENFORCEMENT_STATUS, ROLE_ENFORCEMENT_LOOPBACK_TRUST)

    def test_enforced_mode_requires_principals_path(self) -> None:
        os.environ["IMP_AUTH_ENFORCEMENT_MODE"] = "ENFORCED"
        os.environ.pop("IMP_AUTH_PRINCIPALS_PATH", None)
        with self.assertRaises(Exception):
            load_auth_config()


class LoopbackTrustAuthorizationTest(unittest.TestCase):
    def setUp(self) -> None:
        reset_principal_registry_for_tests()
        self._env_backup = dict(os.environ)
        os.environ.pop("IMP_AUTH_ENFORCEMENT_MODE", None)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env_backup)
        reset_principal_registry_for_tests()

    def test_unauthenticated_context_read_allowed(self) -> None:
        store = _store_with_paper()
        principal = authorize_http_request(
            store,
            method="GET",
            path="/context",
            headers={},
            query={},
        )
        self.assertIsInstance(principal, AuthorizedPrincipal)
        self.assertTrue(principal.permits_capability("state.read"))

    def test_paper_submit_allowed_without_token(self) -> None:
        store = _store_with_paper()
        principal = authorize_http_request(
            store,
            method="POST",
            path="/paper/orders",
            headers={},
            query={},
            body={"symbol": "AAPL", "side": "BUY", "quantity": 1},
        )
        self.assertIsInstance(principal, AuthorizedPrincipal)


class EnforcedAuthorizationTest(unittest.TestCase):
    def setUp(self) -> None:
        reset_principal_registry_for_tests()
        self._env_backup = dict(os.environ)
        os.environ["IMP_AUTH_ENFORCEMENT_MODE"] = "ENFORCED"
        os.environ["IMP_AUTH_PRINCIPALS_PATH"] = str(PRINCIPALS_FIXTURE)
        os.environ["IMP_AUTH_SESSION_TTL_SECONDS"] = "3600"

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env_backup)
        reset_principal_registry_for_tests()

    def test_enforcement_status_enforced(self) -> None:
        self.assertEqual(role_enforcement_status(), ROLE_ENFORCEMENT_ENFORCED)

    def test_missing_session_denied(self) -> None:
        store = _store_with_paper()
        result = authorize_http_request(
            store,
            method="GET",
            path="/context",
            headers={},
            query={},
        )
        self.assertIsInstance(result, AuthorizationFailure)
        self.assertEqual(result.code.value, "AUTH_REQUIRED")

    def test_viewer_cannot_submit_paper_order(self) -> None:
        store = _store_with_paper()
        login = login_principal(principal_id="canary-viewer", secret="canary-viewer-secret")
        self.assertNotIsInstance(login, AuthorizationFailure)
        session, _ = login
        result = authorize_http_request(
            store,
            method="POST",
            path="/paper/orders",
            headers={"Authorization": f"Bearer {session.token}"},
            query={},
            body={"symbol": "AAPL", "side": "BUY", "quantity": 1},
        )
        self.assertIsInstance(result, AuthorizationFailure)
        self.assertEqual(result.code.value, "CAPABILITY_DENIED")

    def test_viewer_denied_other_canary_account(self) -> None:
        store = _store_with_paper()
        login = login_principal(principal_id="canary-viewer", secret="canary-viewer-secret")
        self.assertNotIsInstance(login, AuthorizationFailure)
        session, _ = login
        result = authorize_http_request(
            store,
            method="GET",
            path="/canary/snapshot",
            headers={"Authorization": f"Bearer {session.token}"},
            query={"account_id": ["fp-canary-alt"]},
        )
        self.assertIsInstance(result, AuthorizationFailure)
        self.assertEqual(result.code.value, "ACCOUNT_ACCESS_DENIED")

    def test_operator_can_submit_paper_order(self) -> None:
        store = _store_with_paper()
        login = login_principal(principal_id="paper-operator", secret="paper-operator-secret")
        self.assertNotIsInstance(login, AuthorizationFailure)
        session, principal = login
        result = authorize_http_request(
            store,
            method="POST",
            path="/paper/orders",
            headers={"Authorization": f"Bearer {session.token}"},
            query={},
            body={"symbol": "AAPL", "side": "BUY", "quantity": 1},
        )
        self.assertIsInstance(result, AuthorizedPrincipal)
        self.assertEqual(result.principal_id, "paper-operator")


class RoleMatrixRegressionTest(unittest.TestCase):
    def test_viewer_operator_admin_monotone(self) -> None:
        self.assertFalse(role_allows(OperatorRole.VIEWER, "paper.order.submit"))
        self.assertTrue(role_allows(OperatorRole.OPERATOR, "paper.order.submit"))


if __name__ == "__main__":
    unittest.main()
