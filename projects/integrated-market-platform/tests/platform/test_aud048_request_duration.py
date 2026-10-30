"""AUD-048: request duration telemetry from isolated real HTTP handlers."""
from __future__ import annotations

import json
import os
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

from market_platform_foundation.ui_api import server


class RequestDurationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.events = []
        self.env = mock.patch.dict(os.environ, {"IMP_API_SLOW_REQUEST_SECONDS": "0"})
        self.env.start()
        self.log = mock.patch.object(server, "log_server_event", side_effect=lambda event, **fields:
                                     self.events.append((event, fields)))
        self.log.start()
        self.context = mock.patch.object(server.projections, "build_context_payload", return_value={"ok": True})
        self.context_mock = self.context.start()
        self.old_store = getattr(server.UiApiHandler, "store", None)
        server.UiApiHandler.store = mock.Mock()
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), server.UiApiHandler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.http.server_address[1]}"

    def tearDown(self) -> None:
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=2)
        server.UiApiHandler.store = self.old_store
        self.context.stop()
        self.log.stop()
        self.env.stop()

    def request(self, path="/context", headers=None):
        request = urllib.request.Request(self.base + path, headers=headers or {})
        try:
            response = urllib.request.urlopen(request, timeout=3)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            response.read()
            return response.code

    def completed(self):
        # handle_one_request logs immediately after sending; synchronize with the request thread.
        for _ in range(100):
            matches = [fields for event, fields in self.events if event == "ui_api.request_completed"]
            if matches:
                return matches
            time.sleep(.002)
        return []

    def test_duration_logs_status_and_route_without_query_or_credentials(self):
        self.assertEqual(self.request("/context?api_key=PRIVATE_QUERY", {"Authorization": "Bearer PRIVATE_HEADER"}), 200)
        events = self.completed()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["route"], "/context")
        self.assertEqual(events[0]["status"], 200)
        self.assertEqual(events[0]["method"], "GET")
        self.assertGreaterEqual(events[0]["duration_ms"], 0)
        self.assertNotIn("PRIVATE", json.dumps(events))

    def test_slow_handler_is_measured(self):
        os.environ["IMP_API_SLOW_REQUEST_SECONDS"] = ".01"
        with mock.patch.object(server.projections, "build_context_payload",
                               side_effect=lambda *_a, **_kw: (time.sleep(.025) or {"ok": True})):
            self.assertEqual(self.request(), 200)
        events = self.completed()
        self.assertEqual(len(events), 1)
        self.assertGreaterEqual(events[0]["duration_ms"], 20)

    def test_fast_requests_and_invalid_thresholds_do_not_flood_logs(self):
        for threshold in ("60", "nan", "inf", "bad", "-1"):
            with self.subTest(threshold=threshold):
                os.environ["IMP_API_SLOW_REQUEST_SECONDS"] = threshold
                self.assertEqual(self.request(), 200)
        time.sleep(.02)
        self.assertEqual([e for e, _ in self.events if e == "ui_api.request_completed"], [])

    def test_browser_refusal_is_measured_without_dispatch(self):
        self.assertEqual(self.request(headers={"Origin": "https://foreign.invalid"}), 403)
        events = self.completed()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["status"], 403)
        self.context_mock.assert_not_called()
