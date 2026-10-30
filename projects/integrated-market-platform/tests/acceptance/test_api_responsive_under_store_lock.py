"""AUD-044 end to end: the API keeps answering while a write waits on another process's lock on its store.

The real UiApiHandler serves an isolated temporary state store on an ephemeral loopback port. A second
connection (the collector's stand-in) holds the store's write lock while an API-side write waits for it. GET
/context and GET /operator/state, which read SQLite through the shared connection, must still answer quickly.
The legacy switch (IMP_STATE_LEGACY_SHARED_LOCK=1) reproduces the 2026-10-29 stall over HTTP.
"""
from __future__ import annotations

import http.client
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.local_state import startup  # noqa: E402
from market_platform_foundation.local_state.paths import database_path  # noqa: E402
from market_platform_foundation.ui_api.server import UiApiHandler  # noqa: E402
from market_platform_foundation.ui_api.store import ReplayStore  # noqa: E402


class ApiResponsiveUnderStoreLockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        saved = {key: os.environ.get(key) for key in ("IMP_STATE_DIR", "IMP_STATE_BUSY_TIMEOUT_MS",
                                                      "IMP_STATE_LEGACY_SHARED_LOCK")}

        def restore() -> None:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        self.addCleanup(restore)
        os.environ["IMP_STATE_DIR"] = str(Path(self.temp.name) / "state")
        os.environ["IMP_STATE_BUSY_TIMEOUT_MS"] = "4000"
        os.environ.pop("IMP_STATE_LEGACY_SHARED_LOCK", None)
        startup.reset_local_state_for_tests()
        self.addCleanup(startup.reset_local_state_for_tests)
        store = ReplayStore(collection_root=ROOT.parent)
        store.load()
        UiApiHandler.store = store
        for patcher in (patch("market_platform_foundation.market_data.live_runtime.get_live_runtime", return_value=None),
                        patch.object(UiApiHandler, "_authorize_request", return_value=True),
                        patch("market_platform_foundation.ui_api.server.assert_no_secrets_in_payload", lambda _p: None)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), UiApiHandler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def open_store(self):
        startup.reset_local_state_for_tests()
        repo = startup.open_local_state()
        repo.connection.execute("CREATE TABLE IF NOT EXISTS aud044_probe(x INTEGER)")
        return repo

    def get(self, path: str) -> tuple[int, float]:
        conn = http.client.HTTPConnection("127.0.0.1", self.httpd.server_address[1], timeout=30)
        started = time.monotonic()
        try:
            conn.request("GET", path)
            response = conn.getresponse()
            response.read()
            return response.status, time.monotonic() - started
        finally:
            conn.close()

    def stall(self, repo) -> tuple[sqlite3.Connection, threading.Thread, list]:
        blocker = sqlite3.connect(database_path(), check_same_thread=False, isolation_level=None)
        blocker.execute("BEGIN IMMEDIATE")  # another process holds the store's write lock
        outcome: list = []

        def write() -> None:
            try:
                with repo.connection.transaction():
                    repo.connection.execute("INSERT INTO aud044_probe VALUES (1)")
                outcome.append("COMMITTED")
            except sqlite3.OperationalError as exc:
                outcome.append(str(exc))
        writer = threading.Thread(target=write, daemon=True)
        writer.start()
        time.sleep(0.3)  # the API-side write is now waiting on the foreign lock
        return blocker, writer, outcome

    def test_reads_over_http_answer_while_a_write_waits_on_a_foreign_lock(self):
        repo = self.open_store()
        self.assertEqual(self.get("/operator/state")[0], 200)  # warm
        blocker, writer, outcome = self.stall(repo)
        try:
            for path in ("/context", "/operator/state", "/context"):
                status, elapsed = self.get(path)
                self.assertEqual(status, 200, path)
                self.assertLess(elapsed, 2.0, path)
        finally:
            blocker.execute("ROLLBACK")
            blocker.close()
        writer.join(10)
        self.assertEqual(outcome, ["COMMITTED"])  # the waiting write still lands once the lock is released

    def test_the_legacy_switch_reproduces_the_http_stall(self):
        os.environ["IMP_STATE_LEGACY_SHARED_LOCK"] = "1"
        repo = self.open_store()
        self.assertEqual(self.get("/operator/state")[0], 200)
        blocker, writer, outcome = self.stall(repo)
        try:
            status, elapsed = self.get("/operator/state")
        finally:
            writer.join(10)
            blocker.execute("ROLLBACK")
            blocker.close()
        self.assertEqual(status, 200)
        self.assertGreater(elapsed, 2.0)  # queued behind the waiting write for most of its 4 s busy timeout
        self.assertIn("locked", outcome[0])


if __name__ == "__main__":
    unittest.main()
