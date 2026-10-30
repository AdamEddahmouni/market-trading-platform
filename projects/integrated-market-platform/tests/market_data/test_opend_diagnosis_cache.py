"""AUD-048 / CA-8: GET /state/startup must not start PowerShell and a Moomoo quote context on every request."""
from __future__ import annotations

import threading
import time
import unittest
from unittest import mock

from market_platform_foundation.local_state import opend


class OpenDDiagnosisCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        opend.reset_opend_diagnosis_cache()
        self.addCleanup(opend.reset_opend_diagnosis_cache)
        self.runs: list[bool] = []

        def run(*, start):
            self.runs.append(start)
            time.sleep(0.05)
            return {"status": "READY", "run": len(self.runs)}
        patcher = mock.patch.object(opend, "_run_check", run)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_repeated_reads_share_one_check_within_the_cache_window(self):
        now = [100.0]
        first = opend.diagnose_opend(clock=lambda: now[0])
        now[0] += 30
        second = opend.diagnose_opend(clock=lambda: now[0])
        self.assertEqual(first, second)
        self.assertEqual(self.runs, [False])
        now[0] += 31  # past the 60 s window
        self.assertEqual(opend.diagnose_opend(clock=lambda: now[0])["run"], 2)

    def test_concurrent_requests_run_one_check(self):
        results: list[dict] = []
        threads = [threading.Thread(target=lambda: results.append(opend.diagnose_opend())) for _ in range(8)]
        [thread.start() for thread in threads]
        [thread.join(5) for thread in threads]
        self.assertEqual(len(results), 8)
        self.assertEqual(self.runs, [False])

    def test_a_start_request_always_runs_a_fresh_check(self):
        opend.diagnose_opend()
        opend.diagnose_opend(start=True)
        self.assertEqual(self.runs, [False, True])

    def test_a_caller_cannot_mutate_the_shared_answer(self):
        opend.diagnose_opend()["status"] = "CHANGED"
        self.assertEqual(opend.diagnose_opend()["status"], "READY")

    def test_the_window_can_be_disabled(self):
        with mock.patch.dict("os.environ", {"IMP_OPEND_DIAGNOSIS_CACHE_SECONDS": "0"}):
            opend.diagnose_opend()
            opend.diagnose_opend()
        self.assertEqual(self.runs, [False, False])


if __name__ == "__main__":
    unittest.main()
