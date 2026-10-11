"""Actual Finviz health authority metadata must pass the fail-closed response audit."""
from __future__ import annotations
import http.client
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from market_platform_foundation.finviz.authority import authority_matrix_payload
from market_platform_foundation.finviz.credential_manager import FinvizCredentialManager
from market_platform_foundation.finviz.request_manager import FinvizRequestManager
from market_platform_foundation.platform.security.leak_audit import SecretLeakError, assert_no_secrets_in_payload
from market_platform_foundation.ui_api.server import UiApiHandler

class FinvizHealthAuthorityAuditTests(unittest.TestCase):
    def test_real_health_endpoint_keeps_authority_matrix_without_provider_requests(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            "IMP_FINVIZ_SECRET_DIR": directory, "FINVIZ_API_KEY": "synthetic-health-test-token",
            "IMP_FINVIZ_LIVE": "0",
        }):
            credential = FinvizCredentialManager()
            credential.load()
            with patch("market_platform_foundation.finviz.request_manager.get_finviz_credential_manager", return_value=credential):
                manager = FinvizRequestManager()
            with patch("market_platform_foundation.ui_api.discovery_projections.get_finviz_request_manager", return_value=manager), \
                    patch("market_platform_foundation.ui_api.discovery_projections.get_finviz_credential_manager", return_value=credential), \
                    patch.object(manager, "_raw_get", side_effect=AssertionError("health must not request provider data")), \
                    patch.object(UiApiHandler, "_authorize_request", return_value=True):
                server = ThreadingHTTPServer(("127.0.0.1", 0), UiApiHandler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
                    connection.request("GET", "/provider/finviz/health")
                    response = connection.getresponse()
                    payload = json.loads(response.read())
                    connection.close()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(payload["authority"], authority_matrix_payload())
                    self.assertEqual(payload["requests"], 0)
                    self.assertEqual(payload["auth_recoveries"], 0)
                    self.assertNotIn("synthetic-health-test-token", json.dumps(payload))
                finally:
                    server.shutdown(); server.server_close(); thread.join(timeout=5)

    def test_public_authority_matrix_passes_as_real_health_payload(self):
        assert_no_secrets_in_payload({"authority": authority_matrix_payload()})

    def test_generic_authority_label_stays_blocked(self):
        with self.assertRaises(SecretLeakError):
            assert_no_secrets_in_payload({"authority": "FINVIZ_ELITE"})

    def test_secret_under_public_matrix_path_stays_blocked(self):
        with self.assertRaises(SecretLeakError):
            assert_no_secrets_in_payload({"authority": {"matrix": {"broad_screening": {"authority": "credential-value-123"}}}})

    def test_unknown_authority_enum_stays_blocked(self):
        with self.assertRaises(SecretLeakError):
            assert_no_secrets_in_payload({"authority": {"matrix": {"broad_screening": {"authority": "NEW_UNKNOWN_AUTHORITY"}}}})

    def test_lookalike_outer_scope_stays_blocked(self):
        with self.assertRaises(SecretLeakError):
            assert_no_secrets_in_payload({"other": {"authority": authority_matrix_payload()}})

    def test_wrong_documented_assignment_stays_blocked(self):
        with self.assertRaises(SecretLeakError):
            assert_no_secrets_in_payload({"authority": {"matrix": {"broad_screening": {"authority": "MOOMOO"}}}})

    def test_unknown_field_with_public_enum_stays_blocked(self):
        with self.assertRaises(SecretLeakError):
            assert_no_secrets_in_payload({"authority": {"matrix": {"unknown_field": {"authority": "FINVIZ_ELITE"}}}})

    def test_numeric_authority_stays_blocked(self):
        with self.assertRaises(SecretLeakError):
            assert_no_secrets_in_payload({"authority": {"matrix": {"broad_screening": {"authority": 123}}}})

if __name__ == "__main__":
    unittest.main()
