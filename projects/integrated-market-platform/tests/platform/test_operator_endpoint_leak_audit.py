"""Regression: operator readiness/config/diagnostics must not trip UI secret-leak audit."""

from __future__ import annotations

import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from market_platform_foundation.ui_api.server import UiApiHandler
from market_platform_foundation.ui_api.store import ReplayStore

from tests.ui1.test_ui_api import COLLECTION_ROOT


class OperatorEndpointLeakAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ReplayStore(collection_root=COLLECTION_ROOT)
        self.store.load()
        UiApiHandler.store = self.store
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), UiApiHandler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self._runtime_patch = patch(
            "market_platform_foundation.market_data.live_runtime.get_live_runtime",
            return_value=None,
        )
        self._runtime_patch.start()
        self._auth_patch = patch.object(UiApiHandler, "_authorize_request", return_value=True)
        self._auth_patch.start()

    def tearDown(self) -> None:
        self._auth_patch.stop()
        self._runtime_patch.stop()
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

    def test_operator_readiness_returns_200_not_leak_blocked(self) -> None:
        status, payload = self._get_json("/operator/readiness")
        self.assertEqual(status, 200)
        self.assertEqual(payload.get("schema_version"), "operator-readiness/1.0")
        self.assertNotEqual(payload.get("code"), "UI_SECRET_LEAK_BLOCKED")

    def test_operator_config_returns_200_not_leak_blocked(self) -> None:
        status, payload = self._get_json("/operator/config")
        self.assertEqual(status, 200)
        self.assertEqual(payload.get("schema_version"), "operator-config/1.0")
        self.assertNotEqual(payload.get("code"), "UI_SECRET_LEAK_BLOCKED")
        providers = payload.get("providers")
        self.assertIsInstance(providers, list)
        self.assertTrue(providers)

    def test_operator_diagnostics_returns_200_not_leak_blocked(self) -> None:
        status, payload = self._get_json("/operator/diagnostics")
        self.assertEqual(status, 200)
        self.assertEqual(payload.get("schema_version"), "operator-diagnostics/1.1.0")
        self.assertNotEqual(payload.get("code"), "UI_SECRET_LEAK_BLOCKED")
        self.assertNotEqual(payload.get("reason_code"), "UI_SECRET_LEAK_BLOCKED")
        sections = payload.get("sections")
        self.assertIsInstance(sections, dict)
        runtime = sections.get("runtime") if isinstance(sections, dict) else None
        self.assertIsInstance(runtime, dict)
        resilience = runtime.get("runtime_resilience") if isinstance(runtime, dict) else None
        self.assertIsInstance(resilience, dict)
        connectivity = (
            resilience.get("provider_connectivity") if isinstance(resilience, dict) else None
        )
        self.assertIsInstance(connectivity, dict)
        self.assertIn("status_token", connectivity)
        fallback = connectivity.get("fallback") if isinstance(connectivity, dict) else None
        self.assertIsInstance(fallback, dict)
        self.assertIn("boundary_token", fallback)

    def test_provider_health_returns_200_not_leak_blocked(self) -> None:
        status, payload = self._get_json("/provider/health")
        self.assertEqual(status, 200)
        self.assertNotEqual(payload.get("code"), "UI_SECRET_LEAK_BLOCKED")
        self.assertNotEqual(payload.get("reason_code"), "UI_SECRET_LEAK_BLOCKED")


if __name__ == "__main__":
    unittest.main()
