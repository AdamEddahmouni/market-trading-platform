"""Regression: /security/readiness must not trip the UI secret-leak audit (IMP-010)."""

from __future__ import annotations

import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from market_platform_foundation.platform.security.leak_audit import scan_snapshot
from market_platform_foundation.ui_api.auth_projections import build_security_readiness_payload
from market_platform_foundation.ui_api.server import UiApiHandler


class SecurityReadinessLeakAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        # The readiness route reads only env gates and auth config, never the store.
        UiApiHandler.store = None  # type: ignore[assignment]
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), UiApiHandler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self._auth_patch = patch.object(UiApiHandler, "_authorize_request", return_value=True)
        self._auth_patch.start()

    def tearDown(self) -> None:
        self._auth_patch.stop()
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    def _get_json(self, path: str) -> tuple[int, dict[str, object]]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        conn.request("GET", path)
        response = conn.getresponse()
        body = response.read().decode("utf-8")
        conn.close()
        return response.status, json.loads(body)

    def test_readiness_payload_has_no_secret_shaped_findings(self) -> None:
        self.assertEqual(scan_snapshot(build_security_readiness_payload()), ())

    def test_security_readiness_returns_200_not_leak_blocked(self) -> None:
        status, payload = self._get_json("/security/readiness")
        self.assertNotEqual(payload.get("reason_code"), "UI_SECRET_LEAK_BLOCKED")
        self.assertEqual(status, 200)
        self.assertEqual(payload.get("schema"), "platform/readiness/auth/1.0.0")
        self.assertIn(payload["checks"].get("enforcement_mode"), {"LOOPBACK_TRUST", "ENFORCED"})


if __name__ == "__main__":
    unittest.main()
