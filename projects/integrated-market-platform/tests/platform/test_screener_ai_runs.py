"""AI Screener runs: asynchronous start, truthful stage and count reporting, one run per account, re-attach,
Stop, and recovery of a run a restart killed. The run is the full-universe method."""

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
from market_platform_foundation.local_state.action_decisions import action_repository  # noqa: E402
from market_platform_foundation.local_state.ai_screener_coverage import coverage_ledger  # noqa: E402
from market_platform_foundation.platform.security.leak_audit import assert_no_secrets_in_payload  # noqa: E402
from market_platform_foundation.platform.security.route_policy import policy_for_route  # noqa: E402
from market_platform_foundation.ui_api.screener_ai import ScreenerAiService  # noqa: E402
from market_platform_foundation.ui_api import screener_ai_runs  # noqa: E402
from market_platform_foundation.ui_api.screener_ai_runs import RUN_SCHEMA, STAGES, AiScreenerRuns  # noqa: E402
from market_platform_foundation.ui_api.server import UiApiHandler  # noqa: E402
from market_platform_foundation.ui_api.store import ReplayStore  # noqa: E402
from tests.support.coverage_universe import (  # noqa: E402
    NOW, SCOPE, GatedProvider, News, PagingReader, RankingProvider, instrument_id, universe,
)
from tests.ui1.test_ui_api import COLLECTION_ROOT  # noqa: E402


def settled(runs: AiScreenerRuns, account: str, run_id: str) -> dict:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        run = runs.read(account, run_id)
        if run["state"] != "RUNNING":
            return run
        time.sleep(0.01)
    raise AssertionError("run did not finish")


def release_all(provider: GatedProvider, count: int = 50) -> None:
    for _ in range(count):
        provider.release.release()


class AiScreenerRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ticks = [100.0]
        # 120 rows: three batches and one global comparison. The controlled-strong row is the last one.
        self.reader = PagingReader(universe(120, strong={119: 90.0}))

    def runs_for(self, provider) -> AiScreenerRuns:
        service = ScreenerAiService(reader=self.reader, news=News(provider), clock=lambda: NOW)
        return AiScreenerRuns(service, clock=lambda: NOW, monotonic=lambda: self.ticks[0])

    def test_start_returns_at_once_and_reports_the_stage_and_counts_the_server_actually_has(self):
        provider = GatedProvider()
        self.addCleanup(release_all, provider)
        runs = self.runs_for(provider)

        started = runs.start("PAPER-1", SCOPE)

        self.assertEqual(started["schema_version"], RUN_SCHEMA)
        self.assertEqual(started["state"], "RUNNING")
        self.assertFalse(started["joined"])
        self.assertIsNone(started["result"])
        self.assertEqual(started["stage_order"], list(STAGES))
        self.assertEqual(started["engine"], {"provider_id": "inference.test", "model_id": "candidate-reduction.controlled", "runtime": "FIXTURE"})
        self.assertEqual(started["timeout_seconds"], 45)
        self.assertTrue(provider.entered.acquire(timeout=10))

        self.ticks[0] += 7.0
        during = runs.read("PAPER-1", started["run_id"])
        self.assertEqual(during["state"], "RUNNING")
        self.assertEqual(during["stage"], "BATCH_INFERENCE")
        # No budget wraps this engine, so no hold is claimed.
        self.assertEqual([item["stage"] for item in during["stages"]], ["ENUMERATION", "ELIGIBILITY", "PLANNING", "BATCH_INFERENCE"])
        self.assertEqual(during["stages"][-1]["detail"]["step"], "MODEL_CALL")
        self.assertEqual((during["stages"][-1]["detail"]["batch"], during["stages"][-1]["detail"]["batches_planned"]), (1, 3))
        self.assertEqual(during["stages"][-1]["elapsed_ms"], 7000)
        self.assertEqual(during["elapsed_ms"], 7000)
        # Counts are what the run has produced, not a projection: nothing is evaluated until a batch answers.
        self.assertEqual(during["progress"], {"universe_count": 120, "assessed_count": 120, "eligible_count": 120, "batches_planned": 3})
        self.assertIsNone(during["result"])

        provider.release.release()
        self.assertTrue(provider.entered.acquire(timeout=10))
        after_one = runs.read("PAPER-1", started["run_id"])
        self.assertEqual((after_one["progress"]["batches_completed"], after_one["progress"]["rows_evaluated"]), (1, 50))

        release_all(provider)
        done = settled(runs, "PAPER-1", started["run_id"])
        self.assertEqual(done["state"], "COMPLETED")
        self.assertIsNone(done["stage"])
        self.assertEqual([item["stage"] for item in done["stages"]],
                         ["ENUMERATION", "ELIGIBILITY", "PLANNING", "BATCH_INFERENCE", "GLOBAL_REDUCTION", "STORED"])
        self.assertTrue(all(isinstance(item["elapsed_ms"], int) for item in done["stages"]))
        self.assertEqual(done["result"]["schema_version"], "screener-ai-screener/1.0.0")
        self.assertEqual(done["result"]["state"], "CURRENT")
        self.assertEqual(done["summary"]["state"], "CURRENT")
        self.assertEqual(done["summary"]["candidate_run_id"], "CU-" + started["run_id"])
        self.assertEqual(done["summary"]["selected"], [{"instrument_id": instrument_id(119), "rank": 1}])
        coverage = done["summary"]["coverage"]
        self.assertEqual((coverage["status"], coverage["universe_count"], coverage["ai_evaluated_count"]), ("GLOBAL_SELECTION_COMPLETE", 120, 120))
        self.assertTrue(coverage["coverage_complete"] and coverage["selection_complete"] and coverage["reconciled"])
        self.assertEqual(done["progress"]["batches_completed"], 3)
        self.assertEqual(provider.calls, 4)
        assert_no_secrets_in_payload(done)

    def test_a_budgeted_engine_reports_the_whole_plans_hold_before_the_first_call(self):
        runs = self.runs_for(BudgetedProvider(RankingProvider(), DailyBudget(None, max_requests=100, max_tokens=10 ** 9, clock=lambda: NOW)))

        done = settled(runs, "PAPER-1", runs.start("PAPER-1", SCOPE)["run_id"])

        self.assertEqual([item["stage"] for item in done["stages"]], list(STAGES))
        held = next(item for item in done["stages"] if item["stage"] == "BUDGET_HELD")["detail"]
        self.assertGreater(held["held_tokens"], 0)
        self.assertEqual(held["held_requests"], 4)
        self.assertEqual(done["progress"]["required_tokens"], held["held_tokens"])

    def test_a_plan_the_budget_cannot_pay_for_never_claims_a_model_call(self):
        provider = RankingProvider()
        runs = self.runs_for(BudgetedProvider(provider, DailyBudget(None, max_tokens=1, clock=lambda: NOW)))

        done = settled(runs, "PAPER-1", runs.start("PAPER-1", SCOPE)["run_id"])

        self.assertEqual(done["state"], "COMPLETED")
        self.assertEqual(done["summary"]["state"], "INCOMPLETE")
        self.assertEqual(done["summary"]["reason"], "AI_COVERAGE_BUDGET_INSUFFICIENT")
        self.assertEqual([item["stage"] for item in done["stages"]], ["ENUMERATION", "ELIGIBILITY", "PLANNING"])
        coverage = done["summary"]["coverage"]
        self.assertEqual((coverage["eligible_count"], coverage["batches_planned"], coverage["batches_completed"]), (120, 3, 0))
        self.assertEqual(coverage["counts"]["unprocessed"], 120)
        self.assertGreater(coverage["budget"]["required_tokens"], coverage["budget"]["available_tokens"])
        self.assertFalse(coverage["coverage_complete"])
        self.assertEqual(provider.calls, 0)

    def test_repeating_an_identical_run_does_not_buy_the_same_answers_again(self):
        provider = RankingProvider()
        runs = self.runs_for(provider)
        first = settled(runs, "PAPER-1", runs.start("PAPER-1", SCOPE)["run_id"])

        again = settled(runs, "PAPER-1", runs.start("PAPER-1", SCOPE)["run_id"])

        self.assertNotEqual(again["run_id"], first["run_id"])
        self.assertEqual(provider.calls, 4)
        self.assertEqual(again["summary"]["selected"], first["summary"]["selected"])
        # Each run keeps its own immutable record; the second never overwrites the first.
        self.assertNotEqual(again["summary"]["candidate_run_id"], first["summary"]["candidate_run_id"])
        self.assertIsNotNone(action_repository().get("candidate_run", first["summary"]["candidate_run_id"]))

    def test_a_second_start_joins_the_run_in_progress_for_that_account(self):
        provider = GatedProvider()
        self.addCleanup(release_all, provider)
        runs = self.runs_for(provider)
        first = runs.start("PAPER-1", SCOPE)
        self.assertTrue(provider.entered.acquire(timeout=10))

        second = runs.start("PAPER-1", {**SCOPE, "sort": "price"})

        self.assertEqual(second["run_id"], first["run_id"])
        self.assertTrue(second["joined"])
        self.assertEqual(second["scope"]["sort"], "volume")
        release_all(provider)
        settled(runs, "PAPER-1", first["run_id"])
        # One run, one set of requests: the duplicate click started nothing and spent nothing.
        self.assertEqual(provider.calls, 4)
        self.assertEqual(len(coverage_ledger().records(first["run_id"], "run")), 1)

    def test_a_reloaded_page_reattaches_to_the_active_run_then_to_the_latest_result(self):
        provider = GatedProvider()
        self.addCleanup(release_all, provider)
        runs = self.runs_for(provider)
        empty = runs.current("PAPER-1")
        self.assertEqual((empty["active"], empty["latest"]), (None, None))
        started = runs.start("PAPER-1", SCOPE)
        self.assertTrue(provider.entered.acquire(timeout=10))

        attached = runs.current("PAPER-1")
        self.assertEqual(attached["active"]["run_id"], started["run_id"])
        self.assertEqual(attached["active"]["stage"], "BATCH_INFERENCE")
        self.assertIsNone(runs.current("PAPER-2")["active"])
        self.assertIsNone(runs.read("PAPER-2", started["run_id"]))

        release_all(provider)
        settled(runs, "PAPER-1", started["run_id"])
        after = runs.current("PAPER-1")
        self.assertIsNone(after["active"])
        self.assertEqual(after["latest"]["run_id"], started["run_id"])
        # The polled listing stays small; the full result is read once by run id.
        self.assertIsNone(after["latest"]["result"])
        self.assertEqual(after["latest"]["summary"]["state"], "CURRENT")
        self.assertEqual(runs.read("PAPER-1", started["run_id"])["result"]["state"], "CURRENT")

    def test_typical_latency_is_measured_from_this_engine_and_absent_until_measured(self):
        runs = self.runs_for(RankingProvider())
        first = runs.start("PAPER-1", SCOPE)
        self.assertIsNone(first["typical_latency_ms"])
        self.assertEqual(first["typical_latency_samples"], 0)
        settled(runs, "PAPER-1", first["run_id"])

        second = runs.start("PAPER-1", SCOPE)

        self.assertEqual(second["typical_latency_ms"], 1)
        done = settled(runs, "PAPER-1", second["run_id"])
        # The repeated run was answered from cache and adds no sample.
        self.assertEqual(done["typical_latency_samples"], 1)

    def status_runs(self, provider) -> AiScreenerRuns:
        return self.runs_for(provider)

    def test_status_states_the_budget_and_the_size_of_the_last_run_once_one_has_been_held(self):
        runs = self.status_runs(BudgetedProvider(RankingProvider(), DailyBudget(None, max_requests=30, max_tokens=10 ** 9, clock=lambda: NOW)))

        before = runs.current("PAPER-1")
        self.assertEqual(before["schema_version"], "screener-ai-screener-runs/2.0.0")
        self.assertEqual(before["state"], "IDLE")
        self.assertEqual(before["ai"], {"state": "AVAILABLE", "reason": None, "provider_id": "inference.test",
                                        "model_id": "candidate-reduction.controlled", "runtime": "PAID_API"})
        # No run has held anything yet, so the size of a run is not known and no count is invented.
        self.assertEqual(before["budget"], {"day": "2026-10-02", "tokens": 0, "max_tokens": 10 ** 9, "requests": 0, "max_requests": 30,
                                            "headroom": 10 ** 9, "requests_left": 30, "held_tokens": 0, "held_requests": 0,
                                            "run_size": None, "run_size_basis": None, "runs_left": None,
                                            "resets_at": "2026-10-03T00:00:00Z"})
        self.assertEqual(before["interrupted"], [])

        done = settled(runs, "PAPER-1", runs.start("PAPER-1", SCOPE)["run_id"])
        held = next(item for item in done["stages"] if item["stage"] == "BUDGET_HELD")["detail"]["held_tokens"]
        after = runs.current("PAPER-1")["budget"]

        self.assertEqual((after["tokens"], after["requests"]), (4 * 1100, 4))
        self.assertEqual((after["held_tokens"], after["held_requests"]), (0, 0))
        self.assertEqual((after["run_size"], after["run_size_basis"]), (held, "LAST_RUN_HOLD"))
        self.assertEqual(after["runs_left"], min(26, (10 ** 9 - 4400) // held))
        # The whole status, budget included, is a response: it must pass the response guard as it is.
        assert_no_secrets_in_payload(runs.current("PAPER-1"))

    def test_status_does_not_block_a_smaller_query_because_the_last_one_was_large(self):
        budget = DailyBudget(None, max_requests=30, max_tokens=10 ** 9, clock=lambda: NOW)
        runs = self.status_runs(BudgetedProvider(RankingProvider(), budget))
        settled(runs, "PAPER-1", runs.start("PAPER-1", SCOPE)["run_id"])
        budget.max_tokens = budget.status()["tokens"] + 500       # less than the last run held, more than nothing

        current = runs.current("PAPER-1")

        self.assertEqual(current["budget"]["runs_left"], 0)
        # What the next run needs depends on its query; its own plan refuses it, with numbers, if it cannot be paid for.
        self.assertEqual(current["state"], "IDLE")

    def test_status_names_an_exhausted_budget_an_unconfigured_engine_and_any_other_block(self):
        spent = self.status_runs(BudgetedProvider(RankingProvider(), DailyBudget(None, max_requests=0, clock=lambda: NOW)))
        self.assertEqual(spent.current("PAPER-1")["state"], "WAITING_FOR_BUDGET")

        missing = self.status_runs(None).current("PAPER-1")
        self.assertEqual((missing["state"], missing["ai"]["reason"], missing["budget"]), ("NOT_CONFIGURED", "ANTHROPIC_API_KEY_NOT_SET", None))

        blocked = self.status_runs(RankingProvider())
        blocked._fixed_service._news.ai_status = lambda: {"state": "UNAVAILABLE", "reason": "LOCAL_MODEL_UNREACHABLE", "provider_id": "local",
                                                         "model_id": "small", "runtime": "LOCAL_MODEL", "budget": None}
        self.assertEqual((blocked.current("PAPER-1")["state"], blocked.current("PAPER-1")["ai"]["reason"]), ("BLOCKED", "LOCAL_MODEL_UNREACHABLE"))

    def test_status_is_running_while_a_run_is_active_and_a_local_engine_has_no_budget(self):
        provider = GatedProvider()
        self.addCleanup(release_all, provider)
        runs = self.status_runs(provider)
        started = runs.start("PAPER-1", SCOPE)
        self.assertTrue(provider.entered.acquire(timeout=10))

        current = runs.current("PAPER-1")

        self.assertEqual((current["state"], current["budget"], current["ai"]["runtime"]), ("RUNNING", None, "LOCAL_MODEL"))
        release_all(provider)
        done = settled(runs, "PAPER-1", started["run_id"])
        self.assertEqual(runs.current("PAPER-1")["state"], "IDLE")
        self.assertEqual(done["summary"]["coverage"]["budget"]["capped"], False)

    def test_an_invalid_scope_fails_before_any_run_exists(self):
        runs = self.runs_for(RankingProvider())

        with self.assertRaisesRegex(ValueError, "INVALID_AI_SCREENER_SCOPE"):
            runs.start("PAPER-1", {**SCOPE, "search": "x" * 121})

        self.assertIsNone(runs.current("PAPER-1")["latest"])

    def test_a_failure_in_the_worker_is_a_failed_run_with_a_stable_code_only(self):
        runs = self.runs_for(RankingProvider())
        self.reader.read = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("C:/private/path token=abc"))
        failed = settled(runs, "PAPER-1", runs.start("PAPER-1", SCOPE)["run_id"])
        self.assertEqual(failed["state"], "FAILED")
        self.assertEqual(failed["error"], {"code": "AI_SCREENER_RUN_FAILED", "stage": "ENUMERATION"})
        self.assertNotIn("private", str(failed))
        terminal = coverage_ledger().terminal(failed["run_id"])
        self.assertEqual((terminal["status"], terminal["reason"]), ("FAILED", "AI_SCREENER_RUN_FAILED"))

        self.reader.read = lambda **kwargs: (_ for _ in ()).throw(ValueError("MARKET_SNAPSHOT_UNAVAILABLE"))
        bounded = settled(runs, "PAPER-1", runs.start("PAPER-1", SCOPE)["run_id"])
        self.assertEqual(bounded["error"]["code"], "MARKET_SNAPSHOT_UNAVAILABLE")
        # A failed run releases the account: the next click starts a new run.
        self.assertIsNone(runs.current("PAPER-1")["active"])

    def test_the_single_request_service_path_is_unchanged_when_nobody_observes(self):
        service = ScreenerAiService(reader=PagingReader(universe(60, strong={0: 90.0})), news=News(RankingProvider()), clock=lambda: NOW)

        self.assertEqual(service.run(SCOPE)["state"], "CURRENT")

    def test_a_harness_built_result_travels_through_the_real_registry(self):
        from tests.support.controlled_ai_run import start_controlled_run

        stored = {"schema_version": "screener-ai-screener/1.0.0", "run_id": "controlled-1", "state": "CURRENT", "candidates": []}
        with patch.object(screener_ai_runs, "_RUNS", None):
            started = start_controlled_run("PAPER-1", SCOPE, lambda scope: {**stored, "scope": scope})
            done = settled(screener_ai_runs.ai_screener_runs(), "PAPER-1", started["run_id"])

        self.assertEqual((started["state"], done["state"]), ("RUNNING", "COMPLETED"))
        self.assertEqual(done["result"], {**stored, "scope": SCOPE})
        self.assertIsNone(done["summary"]["coverage"])

    def test_run_reads_are_reads_and_starting_or_stopping_a_run_is_a_write(self):
        self.assertEqual(policy_for_route("GET", "/screener/ai-screener/runs/active").capability, "state.read")
        self.assertEqual(policy_for_route("GET", "/screener/ai-screener/runs/abc").capability, "state.read")
        self.assertEqual(policy_for_route("GET", "/screener/ai-screener/runs/abc/coverage").capability, "state.read")
        self.assertEqual(policy_for_route("POST", "/screener/ai-screener").capability, "state.write")
        self.assertEqual(policy_for_route("POST", "/screener/ai-screener/runs/abc/stop").capability, "state.write")


class StopAndRecoveryTests(unittest.TestCase):
    def runs_for(self, provider, rows) -> AiScreenerRuns:
        self.service = ScreenerAiService(reader=PagingReader(rows), news=News(provider), clock=lambda: NOW)
        return AiScreenerRuns(self.service, clock=lambda: NOW)

    def test_stop_lets_the_call_in_flight_finish_and_starts_no_other(self):
        provider = GatedProvider()
        self.addCleanup(release_all, provider)
        budget = DailyBudget(None, max_requests=100, max_tokens=10 ** 9, clock=lambda: NOW)
        runs = self.runs_for(BudgetedProvider(provider, budget), universe(300, strong={index: 90.0 for index in range(0, 300, 7)}))
        started = runs.start("PAPER-1", SCOPE)
        self.assertTrue(provider.entered.acquire(timeout=10))

        self.assertIsNone(runs.stop("PAPER-2", started["run_id"]))
        stopping = runs.stop("PAPER-1", started["run_id"])
        self.assertTrue(stopping["stop_requested"])
        self.assertEqual(stopping["state"], "RUNNING")       # the request already sent is not claimed cancelled
        self.assertGreater(budget.status()["held_tokens"], 0)

        provider.release.release()
        done = settled(runs, "PAPER-1", started["run_id"])

        self.assertEqual(done["state"], "COMPLETED")
        coverage = done["summary"]["coverage"]
        self.assertEqual((coverage["status"], coverage["reason"]), ("STOPPED", "STOPPED_BY_OPERATOR"))
        self.assertEqual(provider.calls, 1)
        self.assertEqual(coverage["batches_completed"], 1)
        self.assertEqual(coverage["counts"]["evaluated"], 50)
        self.assertEqual(coverage["counts"]["unprocessed"], 250)
        self.assertFalse(coverage["coverage_complete"])
        self.assertGreater(done["summary"]["provisional_count"], 0)
        self.assertEqual(done["result"]["candidates"], [])
        # Tokens the finished call used stay spent; the rest of the hold went back to the shared budget.
        status = budget.status()
        self.assertEqual((status["tokens"], status["requests"], status["held_tokens"], status["held_requests"]), (1100, 1, 0, 0))
        self.assertIsNone(action_repository().get("candidate_run", "CU-" + started["run_id"]))
        # Stopping a finished run changes nothing.
        self.assertEqual(runs.stop("PAPER-1", started["run_id"])["state"], "COMPLETED")
        self.assertIsNone(runs.stop("PAPER-1", "not-a-run"))

    def test_receipts_and_per_row_accounting_are_readable_for_the_owning_account_only(self):
        rows = universe(130, strong={129: 90.0})
        rows[0]["fields"].pop("price")
        runs = self.runs_for(RankingProvider(), rows)
        done = settled(runs, "PAPER-1", runs.start("PAPER-1", SCOPE)["run_id"])

        self.assertIsNone(runs.coverage("PAPER-2", done["run_id"]))
        self.assertIsNone(runs.coverage("PAPER-1", "not-a-run"))
        receipts = runs.coverage("PAPER-1", done["run_id"], limit=50)
        self.assertEqual(receipts["rows"]["total"], 130)
        self.assertEqual(len(receipts["rows"]["items"]), 50)
        self.assertEqual(receipts["rows"]["phase"], "FINAL")
        self.assertEqual(len(receipts["calls"]), 4)
        self.assertEqual(receipts["terminal"]["status"], "GLOBAL_SELECTION_COMPLETE")
        self.assertEqual(receipts["plan"]["plan"]["batches_planned"], 3)
        blocked = runs.coverage("PAPER-1", done["run_id"], row_class="EVIDENCE_UNAVAILABLE")
        self.assertEqual([item["instrument_id"] for item in blocked["rows"]["items"]], [instrument_id(0)])
        assert_no_secrets_in_payload(receipts)

    def test_a_run_a_restart_killed_is_reported_interrupted_and_its_unused_hold_returns(self):
        budget = DailyBudget(None, max_requests=100, max_tokens=10 ** 9, clock=lambda: NOW)
        provider = BudgetedProvider(RankingProvider(), budget)
        ledger = coverage_ledger()
        ledger.append("killed-by-restart", "run", {"account_id": "PAPER-7", "method_version": "ai-screener-coverage/1.0.0"})
        ledger.append("killed-by-restart", "batch_started", {"call_id": "BATCH_INFERENCE:0:0", "instrument_ids": ["EQ:A"], "planned_tokens": 800})
        self.assertTrue(budget.hold("killed-by-restart", requests=3, tokens=3000)["held"])
        self.assertIsNone(budget.reserve(800, hold="killed-by-restart"))

        runs = self.runs_for(provider, universe(10))
        current = runs.current("PAPER-7")

        self.assertEqual(current["state"], "IDLE")
        self.assertEqual(len(current["interrupted"]), 1)
        found = current["interrupted"][0]
        self.assertEqual((found["run_id"], found["status"], found["unknown_provider_outcomes"]), ("killed-by-restart", "INTERRUPTED", 1))
        self.assertEqual(runs.current("PAPER-1")["interrupted"], [])
        # Nothing is resumed and nothing is refunded for the call whose outcome is unknown.
        status = budget.status()
        self.assertEqual((status["tokens"], status["requests"], status["held_tokens"]), (800, 1, 0))
        self.assertEqual(ledger.terminal("killed-by-restart")["status"], "INTERRUPTED")
        self.assertEqual(runs.coverage("PAPER-7", "killed-by-restart")["unfinished_calls"][0]["call_id"], "BATCH_INFERENCE:0:0")

    def test_recovery_never_closes_a_run_that_is_alive_in_this_process(self):
        provider = GatedProvider()
        self.addCleanup(release_all, provider)
        runs = self.runs_for(provider, universe(120))
        started = runs.start("PAPER-1", SCOPE)
        self.assertTrue(provider.entered.acquire(timeout=10))

        other = AiScreenerRuns(ScreenerAiService(reader=PagingReader(universe(5)), news=News(RankingProvider()), clock=lambda: NOW))
        self.assertEqual(other.current("PAPER-1")["interrupted"], [])
        self.assertIsNone(coverage_ledger().terminal(started["run_id"]))

        release_all(provider)
        done = settled(runs, "PAPER-1", started["run_id"])
        self.assertEqual(done["summary"]["coverage"]["status"], "COMPLETE_NO_SELECTION")


class AiScreenerRunRouteTests(unittest.TestCase):
    """The HTTP contract: POST starts and returns at once; GET reads status and never starts anything."""

    def setUp(self) -> None:
        self.provider = GatedProvider()
        service = ScreenerAiService(reader=PagingReader(universe(120, strong={119: 90.0})), news=News(self.provider), clock=lambda: NOW)
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
        self.addCleanup(release_all, self.provider)

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
        self.assertTrue(self.provider.entered.acquire(timeout=10))

        status, during = self.call("GET", f"/screener/ai-screener/runs/{started['run_id']}")
        self.assertEqual((status, during["stage"]), (200, "BATCH_INFERENCE"))
        status, joined = self.call("POST", "/screener/ai-screener", SCOPE)
        self.assertEqual((status, joined["run_id"], joined["joined"]), (200, started["run_id"], True))
        status, current = self.call("GET", "/screener/ai-screener/runs/active")
        self.assertEqual((status, current["active"]["run_id"]), (200, started["run_id"]))

        release_all(self.provider)
        settled(self.runs, self.account, started["run_id"])
        status, done = self.call("GET", f"/screener/ai-screener/runs/{started['run_id']}")
        self.assertEqual((status, done["state"], done["result"]["state"]), (200, "COMPLETED", "CURRENT"))
        self.assertEqual(done["result"]["universe_coverage"]["status"], "GLOBAL_SELECTION_COMPLETE")
        self.assertEqual(self.provider.calls, 4)
        status, receipts = self.call("GET", f"/screener/ai-screener/runs/{started['run_id']}/coverage?class=AI_EVALUATED&limit=5")
        self.assertEqual((status, receipts["rows"]["total"], len(receipts["rows"]["items"])), (200, 120, 5))
        status, missing = self.call("GET", "/screener/ai-screener/runs/not-a-run/coverage")
        self.assertEqual((status, missing["reason_code"]), (404, "SCREENER_AI_RUN_UNKNOWN"))

    def test_stop_is_an_explicit_post_and_ends_the_run_as_stopped(self):
        status, started = self.call("POST", "/screener/ai-screener", SCOPE)
        self.assertTrue(self.provider.entered.acquire(timeout=10))

        status, stopping = self.call("POST", f"/screener/ai-screener/runs/{started['run_id']}/stop", {})
        self.assertEqual((status, stopping["stop_requested"], stopping["state"]), (200, True, "RUNNING"))
        status, unknown = self.call("POST", "/screener/ai-screener/runs/not-a-run/stop", {})
        self.assertEqual((status, unknown["reason_code"]), (404, "SCREENER_AI_RUN_UNKNOWN"))

        self.provider.release.release()
        done = settled(self.runs, self.account, started["run_id"])
        self.assertEqual(done["summary"]["coverage"]["status"], "STOPPED")
        self.assertEqual(self.provider.calls, 1)

    def test_status_for_a_paid_engine_with_a_budget_passes_the_response_guard(self):
        # Regression: a budget field named like a credential was blocked by the guard, so the strip had no status
        # for exactly the engines that have a budget.
        paid = BudgetedProvider(RankingProvider(), DailyBudget(None, max_requests=30, max_tokens=10 ** 9))
        runs = AiScreenerRuns(ScreenerAiService(reader=PagingReader(universe(120)), news=News(paid), clock=lambda: NOW))
        with patch.object(screener_ai_runs, "_RUNS", runs):
            status, started = self.call("POST", "/screener/ai-screener", SCOPE)
            self.assertEqual(status, 200)
            settled(runs, self.account, started["run_id"])
            status, current = self.call("GET", "/screener/ai-screener/runs/active")
            self.assertEqual(status, 200, current)
            status, done = self.call("GET", f"/screener/ai-screener/runs/{started['run_id']}")
            self.assertEqual(status, 200, done)
            status, receipts = self.call("GET", f"/screener/ai-screener/runs/{started['run_id']}/coverage")
            self.assertEqual(status, 200, receipts)

        self.assertEqual(done["state"], "COMPLETED")
        self.assertEqual(current["state"], "IDLE")
        self.assertGreater(current["budget"]["run_size"], 0)
        self.assertEqual(current["budget"]["headroom"], 10 ** 9 - current["budget"]["tokens"])
        self.assertIsInstance(current["budget"]["runs_left"], int)
        self.assertGreater(done["result"]["universe_coverage"]["budget"]["required_tokens"], 0)

    def test_reading_status_never_starts_a_run(self):
        status, current = self.call("GET", "/screener/ai-screener/runs/active")
        self.assertEqual((status, current["active"], current["latest"]), (200, None, None))
        status, unknown = self.call("GET", "/screener/ai-screener/runs/not-a-run")
        self.assertEqual((status, unknown["reason_code"]), (404, "SCREENER_AI_RUN_UNKNOWN"))
        self.assertEqual(self.provider.calls, 0)

    def test_an_invalid_scope_is_rejected_with_no_run(self):
        status, error = self.call("POST", "/screener/ai-screener", {**SCOPE, "universe": "NOT_A_UNIVERSE"})
        self.assertEqual((status, error["reason_code"]), (400, "SCREENER_AI_INVALID"))
        self.assertIsNone(self.runs.current(self.account)["latest"])


if __name__ == "__main__":
    unittest.main()
