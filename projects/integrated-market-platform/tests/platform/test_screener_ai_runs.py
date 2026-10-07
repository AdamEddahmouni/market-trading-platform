"""AI Screener runs: asynchronous start, truthful stage reporting, one run per account, re-attach."""

from __future__ import annotations

import http.client
import json
import sys
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.inference.anthropic_synthesis import BudgetedProvider, DailyBudget  # noqa: E402
from market_platform_foundation.platform.security.leak_audit import assert_no_secrets_in_payload  # noqa: E402
from market_platform_foundation.platform.security.route_policy import policy_for_route  # noqa: E402
from market_platform_foundation.ui_api.screener_ai import MAX_INTAKE, ScreenerAiService  # noqa: E402
from market_platform_foundation.ui_api import screener_ai_runs  # noqa: E402
from market_platform_foundation.ui_api.screener_ai_runs import RUN_SCHEMA, STAGES, AiScreenerRuns  # noqa: E402
from market_platform_foundation.ui_api.server import UiApiHandler  # noqa: E402
from market_platform_foundation.ui_api.store import ReplayStore  # noqa: E402
from tests.platform.test_screener_s18 import NOW, CandidateProvider, News, Reader, row  # noqa: E402
from tests.ui1.test_ui_api import COLLECTION_ROOT  # noqa: E402

SCOPE = {"universe": "US_EQUITIES", "search": "", "sort": "volume", "descending": True, "filters": [], "result_set": "set-1"}


class SlowProvider(CandidateProvider):
    """A controlled engine that holds the model call open until the test releases it."""

    def __init__(self) -> None:
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()

    def infer(self, packet, *, rendered_prompt, config):
        self.entered.set()
        if not self.release.wait(10):
            raise TimeoutError("test never released the controlled engine")
        return super().infer(packet, rendered_prompt=rendered_prompt, config=config)


def settled(runs: AiScreenerRuns, account: str, run_id: str) -> dict:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        run = runs.read(account, run_id)
        if run["state"] != "RUNNING":
            return run
        time.sleep(0.01)
    raise AssertionError("run did not finish")


class AiScreenerRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ticks = [100.0]
        self.reader = Reader([row(f"EQ:{chr(65 + index)}") for index in range(MAX_INTAKE)])

    def runs_for(self, provider) -> AiScreenerRuns:
        service = ScreenerAiService(reader=self.reader, news=News(provider), clock=lambda: NOW)
        return AiScreenerRuns(service, clock=lambda: NOW, monotonic=lambda: self.ticks[0])

    def test_start_returns_at_once_and_reports_the_stage_the_server_is_actually_in(self):
        provider = SlowProvider()
        runs = self.runs_for(provider)

        started = runs.start("PAPER-1", SCOPE)

        self.assertEqual(started["schema_version"], RUN_SCHEMA)
        self.assertEqual(started["state"], "RUNNING")
        self.assertFalse(started["joined"])
        self.assertIsNone(started["result"])
        self.assertEqual(started["stage_order"], list(STAGES))
        self.assertEqual(started["engine"], {"provider_id": "inference.test", "model_id": "candidate-reduction.v1", "runtime": "FIXTURE"})
        self.assertEqual(started["timeout_seconds"], 45)
        self.assertTrue(provider.entered.wait(10))

        self.ticks[0] += 7.0
        during = runs.read("PAPER-1", started["run_id"])
        self.assertEqual(during["state"], "RUNNING")
        self.assertEqual(during["stage"], "MODEL_CALL")
        # No budget wraps this engine, so no reservation is claimed.
        self.assertEqual([item["stage"] for item in during["stages"]], ["SCOPE", "NEWS", "EVIDENCE", "PACKET", "MODEL_CALL"])
        self.assertEqual(during["stages"][-1]["elapsed_ms"], 7000)
        self.assertEqual(during["elapsed_ms"], 7000)
        self.assertEqual(during["intake_count"], MAX_INTAKE)
        self.assertGreater(during["packet_bytes"], 0)
        self.assertIsNone(during["result"])

        provider.release.set()
        done = settled(runs, "PAPER-1", started["run_id"])
        self.assertEqual(done["state"], "COMPLETED")
        self.assertIsNone(done["stage"])
        self.assertEqual([item["stage"] for item in done["stages"]],
                         ["SCOPE", "NEWS", "EVIDENCE", "PACKET", "MODEL_CALL", "VALIDATION", "STORED"])
        self.assertTrue(all(isinstance(item["elapsed_ms"], int) for item in done["stages"]))
        self.assertEqual(done["result"]["schema_version"], "screener-ai-screener/1.0.0")
        self.assertEqual(done["result"]["state"], "CURRENT")
        self.assertEqual(done["summary"]["state"], "CURRENT")
        self.assertEqual(done["summary"]["candidate_run_id"], done["result"]["run_id"])
        self.assertEqual(done["summary"]["selected"], [{"instrument_id": "EQ:A", "rank": 1}])
        self.assertEqual(provider.calls, 1)
        assert_no_secrets_in_payload(done)

    def test_a_budgeted_engine_reports_the_reservation_before_the_model_call(self):
        provider = SlowProvider()
        provider.release.set()
        runs = self.runs_for(BudgetedProvider(provider, DailyBudget(None, clock=lambda: NOW)))

        done = settled(runs, "PAPER-1", runs.start("PAPER-1", SCOPE)["run_id"])

        stages = [item["stage"] for item in done["stages"]]
        self.assertEqual(stages, list(STAGES))
        reserved = next(item for item in done["stages"] if item["stage"] == "BUDGET_RESERVED")
        self.assertGreater(reserved["detail"]["reserved_tokens"], 0)

    def test_a_refused_reservation_never_claims_a_model_call(self):
        provider = CandidateProvider()
        runs = self.runs_for(BudgetedProvider(provider, DailyBudget(None, max_tokens=1, clock=lambda: NOW)))

        done = settled(runs, "PAPER-1", runs.start("PAPER-1", SCOPE)["run_id"])

        self.assertEqual(done["state"], "COMPLETED")
        self.assertEqual(done["summary"]["state"], "UNAVAILABLE")
        self.assertEqual(done["summary"]["reason"], "SYNTHESIS_DAILY_TOKEN_LIMIT")
        self.assertEqual([item["stage"] for item in done["stages"]], ["SCOPE", "NEWS", "EVIDENCE", "PACKET", "STORED"])
        self.assertEqual(provider.calls, 0)

    def test_a_cached_result_skips_the_model_stages(self):
        provider = CandidateProvider()
        runs = self.runs_for(provider)
        first = settled(runs, "PAPER-1", runs.start("PAPER-1", SCOPE)["run_id"])

        again = settled(runs, "PAPER-1", runs.start("PAPER-1", SCOPE)["run_id"])

        self.assertNotEqual(again["run_id"], first["run_id"])
        self.assertEqual(again["summary"]["cache"], "HIT")
        self.assertEqual(again["summary"]["candidate_run_id"], first["summary"]["candidate_run_id"])
        self.assertEqual([item["stage"] for item in again["stages"]], ["SCOPE", "NEWS", "EVIDENCE", "PACKET", "STORED"])
        self.assertEqual(provider.calls, 1)

    def test_a_second_start_joins_the_run_in_progress_for_that_account(self):
        provider = SlowProvider()
        runs = self.runs_for(provider)
        first = runs.start("PAPER-1", SCOPE)
        self.assertTrue(provider.entered.wait(10))

        second = runs.start("PAPER-1", {**SCOPE, "sort": "price"})
        other = runs.start("PAPER-2", SCOPE)

        self.assertEqual(second["run_id"], first["run_id"])
        self.assertTrue(second["joined"])
        self.assertEqual(second["scope"]["sort"], "volume")
        self.assertNotEqual(other["run_id"], first["run_id"])
        provider.release.set()
        settled(runs, "PAPER-1", first["run_id"])
        settled(runs, "PAPER-2", other["run_id"])
        self.assertEqual(provider.calls, 1)

    def test_a_reloaded_page_reattaches_to_the_active_run_then_to_the_latest_result(self):
        provider = SlowProvider()
        runs = self.runs_for(provider)
        self.assertEqual(runs.current("PAPER-1"), {"schema_version": "screener-ai-screener-runs/1.0.0", "active": None, "latest": None})
        started = runs.start("PAPER-1", SCOPE)
        self.assertTrue(provider.entered.wait(10))

        attached = runs.current("PAPER-1")
        self.assertEqual(attached["active"]["run_id"], started["run_id"])
        self.assertEqual(attached["active"]["stage"], "MODEL_CALL")
        self.assertIsNone(runs.current("PAPER-2")["active"])
        self.assertIsNone(runs.read("PAPER-2", started["run_id"]))

        provider.release.set()
        settled(runs, "PAPER-1", started["run_id"])
        after = runs.current("PAPER-1")
        self.assertIsNone(after["active"])
        self.assertEqual(after["latest"]["run_id"], started["run_id"])
        # The polled listing stays small; the full result is read once by run id.
        self.assertIsNone(after["latest"]["result"])
        self.assertEqual(after["latest"]["summary"]["state"], "CURRENT")
        self.assertEqual(runs.read("PAPER-1", started["run_id"])["result"]["state"], "CURRENT")

    def test_typical_latency_is_measured_from_this_engine_and_absent_until_measured(self):
        runs = self.runs_for(CandidateProvider())
        first = runs.start("PAPER-1", SCOPE)
        self.assertIsNone(first["typical_latency_ms"])
        self.assertEqual(first["typical_latency_samples"], 0)
        settled(runs, "PAPER-1", first["run_id"])

        second = runs.start("PAPER-1", SCOPE)

        # One measured call of 1 ms; the cached second run adds no sample.
        self.assertEqual(second["typical_latency_ms"], 1)
        done = settled(runs, "PAPER-1", second["run_id"])
        self.assertEqual(done["typical_latency_samples"], 1)

    def test_an_invalid_scope_fails_before_any_run_exists(self):
        runs = self.runs_for(CandidateProvider())

        with self.assertRaisesRegex(ValueError, "INVALID_AI_SCREENER_SCOPE"):
            runs.start("PAPER-1", {**SCOPE, "search": "x" * 121})

        self.assertIsNone(runs.current("PAPER-1")["latest"])

    def test_a_failure_in_the_worker_is_a_failed_run_with_a_stable_code_only(self):
        runs = self.runs_for(CandidateProvider())
        self.reader.read = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("C:/private/path token=abc"))
        failed = settled(runs, "PAPER-1", runs.start("PAPER-1", SCOPE)["run_id"])
        self.assertEqual(failed["state"], "FAILED")
        self.assertEqual(failed["error"], {"code": "AI_SCREENER_RUN_FAILED", "stage": "SCOPE"})
        self.assertNotIn("private", str(failed))

        self.reader.read = lambda **kwargs: (_ for _ in ()).throw(ValueError("EVIDENCE_PACKET_BOUND_EXCEEDED"))
        bounded = settled(runs, "PAPER-1", runs.start("PAPER-1", SCOPE)["run_id"])
        self.assertEqual(bounded["error"]["code"], "EVIDENCE_PACKET_BOUND_EXCEEDED")
        # A failed run releases the account: the next click starts a new run.
        self.assertIsNone(runs.current("PAPER-1")["active"])

    def test_the_synchronous_service_path_is_unchanged_when_nobody_observes(self):
        provider = CandidateProvider()
        service = ScreenerAiService(reader=self.reader, news=News(provider), clock=lambda: NOW)

        self.assertEqual(service.run(SCOPE)["state"], "CURRENT")

    def test_a_harness_built_result_travels_through_the_real_registry(self):
        from tests.support.controlled_ai_run import start_controlled_run

        stored = {"schema_version": "screener-ai-screener/1.0.0", "run_id": "controlled-1", "state": "CURRENT", "candidates": []}
        with patch.object(screener_ai_runs, "_RUNS", None):
            started = start_controlled_run("PAPER-1", SCOPE, lambda scope: {**stored, "scope": scope})
            done = settled(screener_ai_runs.ai_screener_runs(), "PAPER-1", started["run_id"])

        self.assertEqual((started["state"], done["state"]), ("RUNNING", "COMPLETED"))
        self.assertEqual(done["result"], {**stored, "scope": SCOPE})

    def test_run_reads_are_reads_and_starting_a_run_is_a_write(self):
        self.assertEqual(policy_for_route("GET", "/screener/ai-screener/runs/active").capability, "state.read")
        self.assertEqual(policy_for_route("GET", "/screener/ai-screener/runs/abc").capability, "state.read")
        self.assertEqual(policy_for_route("POST", "/screener/ai-screener").capability, "state.write")


class AiScreenerRunRouteTests(unittest.TestCase):
    """The HTTP contract: POST starts and returns at once; GET reads status and never starts anything."""

    def setUp(self) -> None:
        self.provider = SlowProvider()
        service = ScreenerAiService(reader=Reader([row("EQ:A")]), news=News(self.provider), clock=lambda: NOW)
        self.runs = AiScreenerRuns(service)
        store = ReplayStore(collection_root=COLLECTION_ROOT)
        store.load()
        self.account = store.paper_ledger.paper_account_id
        for patcher in (patch.object(screener_ai_runs, "_RUNS", self.runs), patch.object(UiApiHandler, "store", store, create=True),
                        patch.object(UiApiHandler, "_authorize_request", return_value=True)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), UiApiHandler)
        thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.addCleanup(self.provider.release.set)

    def call(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        connection = http.client.HTTPConnection("127.0.0.1", self.httpd.server_address[1], timeout=30)
        connection.request(method, path, body=json.dumps(body) if body is not None else None,
                           headers={"Content-Type": "application/json"} if body is not None else {})
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        connection.close()
        return response.status, payload

    def test_post_returns_a_running_run_and_get_follows_it_to_the_result(self):
        status, started = self.call("POST", "/screener/ai-screener", SCOPE)
        self.assertEqual((status, started["schema_version"], started["state"]), (200, RUN_SCHEMA, "RUNNING"))
        self.assertEqual(started["account_id"], self.account)
        self.assertTrue(self.provider.entered.wait(10))

        status, during = self.call("GET", f"/screener/ai-screener/runs/{started['run_id']}")
        self.assertEqual((status, during["stage"]), (200, "MODEL_CALL"))
        status, joined = self.call("POST", "/screener/ai-screener", SCOPE)
        self.assertEqual((status, joined["run_id"], joined["joined"]), (200, started["run_id"], True))
        status, current = self.call("GET", "/screener/ai-screener/runs/active")
        self.assertEqual((status, current["active"]["run_id"]), (200, started["run_id"]))

        self.provider.release.set()
        settled(self.runs, self.account, started["run_id"])
        status, done = self.call("GET", f"/screener/ai-screener/runs/{started['run_id']}")
        self.assertEqual((status, done["state"], done["result"]["state"]), (200, "COMPLETED", "CURRENT"))
        self.assertEqual(self.provider.calls, 1)

    def test_reading_status_never_starts_a_run(self):
        status, current = self.call("GET", "/screener/ai-screener/runs/active")
        self.assertEqual((status, current["active"], current["latest"]), (200, None, None))
        status, unknown = self.call("GET", "/screener/ai-screener/runs/not-a-run")
        self.assertEqual((status, unknown["reason_code"]), (404, "SCREENER_AI_RUN_UNKNOWN"))
        self.assertFalse(self.provider.entered.is_set())

    def test_an_invalid_scope_is_rejected_with_no_run(self):
        status, error = self.call("POST", "/screener/ai-screener", {**SCOPE, "universe": "NOT_A_UNIVERSE"})
        self.assertEqual((status, error["reason_code"]), (400, "SCREENER_AI_INVALID"))
        self.assertIsNone(self.runs.current(self.account)["latest"])


if __name__ == "__main__":
    unittest.main()
