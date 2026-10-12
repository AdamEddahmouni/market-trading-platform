"""AUTO-01 — the controller's full-universe step against the real run tracker and coverage method.

The production AiScreenerRuns, ScreenerAiService.run_universe and ScreenerAiCoverage run here over the
controlled universe fixture. What is proven: an unattended run is the full-universe method (never the
first-50 intake), an owner spending cap refuses a plan before any hold or model call, and only a
complete selection reaches the reevaluation loop.
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.inference.anthropic_synthesis import BudgetedProvider, DailyBudget  # noqa: E402
from market_platform_foundation.local_state.ai_screener_coverage import CoverageLedger  # noqa: E402
from market_platform_foundation.local_state.paper_automation import PaperAutomationRepository  # noqa: E402
from market_platform_foundation.platform.security.leak_audit import assert_no_secrets_in_payload  # noqa: E402
from market_platform_foundation.ui_api.paper_automation import PaperAutomationService  # noqa: E402
from market_platform_foundation.ui_api.screener_ai import ScreenerAiService  # noqa: E402
from market_platform_foundation.ui_api.screener_ai_coverage import ScreenerAiCoverage  # noqa: E402
from market_platform_foundation.ui_api.screener_ai_runs import AiScreenerRuns  # noqa: E402
from tests.intelligence.test_paper_automation_policy import policy  # noqa: E402
from tests.intelligence.test_reevaluation import SCOPE as LOOP_SCOPE, Harness  # noqa: E402
from tests.support.coverage_universe import (  # noqa: E402
    NOW, SCOPE, GatedProvider, News, PagingReader, RankingProvider, instrument_id, universe,
)

SHA = "0" * 40
_SEQUENCE = [0]


class Base(unittest.TestCase):
    def setUp(self) -> None:
        patcher = patch("market_platform_foundation.local_state.ai_screener_coverage._LEDGER", CoverageLedger())
        patcher.start()
        self.addCleanup(patcher.stop)
        # 120 rows: three batches and one global comparison. The strongest row is the last one, far past the first 50.
        self.reader = PagingReader(universe(120, strong={119: 90.0}))

    def tracker(self, provider) -> AiScreenerRuns:
        self.screener = ScreenerAiService(reader=self.reader, news=News(provider), clock=lambda: NOW)
        return AiScreenerRuns(self.screener, clock=lambda: NOW, monotonic=lambda: 100.0)

    def controller(self, runs: AiScreenerRuns, engine_provider=None):
        self.loop = Harness(provider=engine_provider)
        self.loop.service.attach_driver("PAPER_AUTOMATION", scope=LOOP_SCOPE, requested_cadence_seconds=60)
        service = PaperAutomationService(self.loop.store, repository=PaperAutomationRepository(), reevaluation=self.loop.service,
                                         runs=runs, clock=self.loop.clock)
        self.work = dict(account_id=self.loop.ledger.paper_account_id, universe={})
        return service

    def step(self, service, automation_policy, gate=None) -> dict:
        summary = dict(blockers=[], universe=None)
        now = self.loop.clock()
        # The adaptive scheduler reads the market session as one of its facts, so the same fixed clock decides it.
        service._universe(self.work, automation_policy, summary, now, service.session(now), gate or dict(allowed=True, reason=None))
        return summary

    def settle(self, runs: AiScreenerRuns) -> dict:
        run_id = self.work["universe"]["active_run_id"]
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            run = runs.read(self.work["account_id"], run_id)
            if run["state"] != "RUNNING":
                return run
            time.sleep(0.01)
        raise AssertionError("run did not finish")


class UnattendedUniverseRunTests(Base):
    def test_the_unattended_run_is_the_full_universe_method_and_its_complete_selection_is_adopted(self):
        provider = RankingProvider()
        runs = self.tracker(provider)
        service = self.controller(runs)
        scope = dict(SCOPE)

        started = self.step(service, dict(policy(), scope=scope))
        self.assertEqual(started["universe"]["state"], "STARTED")
        done = self.settle(runs)
        self.assertEqual((done["origin"], done["state"]), ("AUTOMATION", "COMPLETED"))
        finished = self.step(service, dict(policy(), scope=scope))

        result = finished["universe"]["last_result"]
        self.assertEqual((result["status"], result["coverage_complete"], result["selection_complete"], result["adopted"]),
                         ("GLOBAL_SELECTION_COMPLETE", True, True, True))
        # Every one of the 120 rows was accounted for, and the pick is row 119: unreachable from a first-50 intake.
        self.assertEqual((result["universe_count"], result["ai_evaluated_count"], result["ai_coverage_pct"]), (120, 120, 100.0))
        self.assertEqual(result["selected"][0], instrument_id(119))
        self.assertEqual(provider.calls, 4)
        pending = self.loop.service._loop()["pending_selection"]
        self.assertEqual((pending["chosen"][0], pending["run_id"]), (instrument_id(119), result["candidate_run_id"]))
        self.assertEqual(self.loop.ai.reductions, 0)
        event = service.repository.events(self.work["account_id"], kinds=["UNIVERSE_RUN_FINISHED"])[0]
        self.assertEqual((event["tokens_input"], event["model_calls"]), (result["tokens_input"], result["model_calls"]))
        assert_no_secrets_in_payload(event)
        assert_no_secrets_in_payload(finished)

    def test_a_run_is_not_started_again_before_the_owners_interval(self):
        runs = self.tracker(RankingProvider())
        service = self.controller(runs)
        automation_policy = dict(policy(), scope=dict(SCOPE))
        self.step(service, automation_policy)
        first = self.settle(runs)["run_id"]
        self.step(service, automation_policy)
        for _ in range(3):
            self.loop.clock.value += 60
            self.assertEqual(self.step(service, automation_policy)["universe"]["state"], "IDLE")
        self.assertIsNone(self.work["universe"]["active_run_id"])
        self.loop.clock.value += 1800
        self.assertEqual(self.step(service, automation_policy)["universe"]["state"], "STARTED")
        self.assertNotEqual(self.work["universe"]["active_run_id"], first)
        self.settle(runs)

    def test_a_withheld_gate_starts_no_run(self):
        provider = RankingProvider()
        runs = self.tracker(provider)
        service = self.controller(runs)
        summary = self.step(service, dict(policy(), scope=dict(SCOPE)), gate=dict(allowed=False, reason="AUTONOMOUS_SPENDING_NOT_AUTHORIZED"))
        self.assertEqual(summary["universe"]["withheld"]["reason"], "AUTONOMOUS_SPENDING_NOT_AUTHORIZED")
        self.assertEqual((self.work["universe"].get("active_run_id"), provider.calls, runs.current(self.work["account_id"]).get("active")),
                         (None, 0, None))

    def test_a_run_in_progress_is_reported_as_running_and_joined_not_duplicated(self):
        provider = GatedProvider()
        self.addCleanup(lambda: [provider.release.release() for _ in range(50)])
        runs = self.tracker(provider)
        service = self.controller(runs)
        automation_policy = dict(policy(), scope=dict(SCOPE))
        operator = runs.start(self.work["account_id"], dict(SCOPE))  # the operator started one from the Screener first
        summary = self.step(service, automation_policy)
        self.assertEqual(self.work["universe"]["active_run_id"], operator["run_id"])
        self.assertEqual((summary["universe"]["state"], self.work["universe"]["origin"]), ("STARTED", "OPERATOR"))
        self.assertEqual(self.step(service, automation_policy)["universe"]["state"], "RUNNING")
        service._halt = None  # a halt must never stop an operator's run: checked through the origin recorded above
        self.assertFalse(runs.read(self.work["account_id"], operator["run_id"])["stop_requested"])


class OwnerSpendingCapTests(Base):
    def budgeted(self, **limits):
        inner = RankingProvider()
        budget = DailyBudget(None, clock=lambda: NOW, **limits)
        return inner, budget, BudgetedProvider(inner, budget)

    def required(self) -> dict:
        _SEQUENCE[0] += 1
        _, _, provider = self.budgeted(max_requests=1000, max_tokens=10 ** 12)
        service = ScreenerAiService(reader=self.reader, news=News(provider), clock=lambda: NOW)
        block = ScreenerAiCoverage(service, ledger=CoverageLedger(), software_sha=SHA).run(
            dict(SCOPE), run_id=f"need{_SEQUENCE[0]:028d}", account_id="PAPER-1")["universe_coverage"]
        return block["plan"]["required"]

    def coverage(self, spend_limit, **limits):
        inner, budget, provider = self.budgeted(**limits)
        service = ScreenerAiService(reader=self.reader, news=News(provider), clock=lambda: NOW)
        _SEQUENCE[0] += 1  # stored candidate runs are immutable process-wide: every run needs its own identity
        extra = {} if spend_limit is None else {"spend_limit": spend_limit}
        result = ScreenerAiCoverage(service, ledger=CoverageLedger(), software_sha=SHA).run(
            dict(SCOPE), run_id=f"cap{_SEQUENCE[0]:029d}", account_id="PAPER-1", **extra)
        return inner, budget, result["universe_coverage"], result

    def test_a_plan_over_the_owner_cap_is_refused_before_any_hold_or_model_call(self):
        need = self.required()
        for limit in (dict(requests=need["requests"] - 1, tokens=need["tokens"]), dict(requests=need["requests"], tokens=need["tokens"] - 1),
                      dict(requests=0, tokens=0)):
            inner, budget, block, result = self.coverage(limit, max_requests=1000, max_tokens=10 ** 12)
            self.assertEqual((block["status"], block["reason"]), ("AI_COVERAGE_BUDGET_INSUFFICIENT", "AUTONOMOUS_SPENDING_LIMIT"))
            self.assertEqual((inner.calls, result["state"], result["candidates"]), (0, "INCOMPLETE", []))
            self.assertFalse(block["coverage_complete"] or block["selection_complete"])
            self.assertEqual((block["counts"]["unprocessed"], block["batches_completed"]), (120, 0))
            self.assertEqual(block["budget"]["held"], False)
            self.assertEqual((block["budget"]["available_requests"], block["budget"]["required_requests"], block["budget"]["available_basis"]),
                             (limit["requests"], need["requests"], "OWNER_AUTONOMOUS_LIMIT"))
            status = budget.status()
            self.assertEqual((status["requests"], status["tokens"], status["held_requests"], status["held_tokens"]), (0, 0, 0, 0))
            assert_no_secrets_in_payload(block)

    def test_a_plan_inside_the_owner_cap_runs_and_the_shared_budget_still_binds(self):
        need = self.required()
        inner, _, block, _ = self.coverage(dict(requests=need["requests"], tokens=need["tokens"]), max_requests=1000, max_tokens=10 ** 12)
        self.assertEqual((block["status"], inner.calls), ("GLOBAL_SELECTION_COMPLETE", need["requests"]))
        # A generous owner cap never widens the shared daily allowance.
        inner, _, block, _ = self.coverage(dict(requests=10 ** 6, tokens=10 ** 12), max_requests=1000, max_tokens=need["tokens"] - 1)
        self.assertEqual((block["status"], block["reason"], inner.calls), ("AI_COVERAGE_BUDGET_INSUFFICIENT", "SYNTHESIS_DAILY_TOKEN_LIMIT", 0))

    def test_no_cap_argument_leaves_the_operator_method_unchanged(self):
        inner, _, block, _ = self.coverage(None, max_requests=1000, max_tokens=10 ** 12)
        self.assertEqual((block["status"], inner.calls), ("GLOBAL_SELECTION_COMPLETE", 4))
        self.assertNotIn("available_basis", block["budget"])

    def test_the_controller_passes_the_tighter_of_owner_and_shared_remaining_and_blocks_by_budget(self):
        need = self.required()
        inner, budget, provider = self.budgeted(max_requests=30, max_tokens=10 ** 9)
        runs = self.tracker(provider)

        class Engine:  # the loop's selected engine reads the same shared budget
            provider_id, model_id, runtime = "paid", "paid-model", "PAID_API"
            budget_status = staticmethod(budget.status)

        service = self.controller(runs, engine_provider=Engine())
        short = dict(policy(ai=dict(allow_paid_inference=True, max_paid_requests_per_day=need["requests"] - 1, max_paid_tokens_per_day=10 ** 9)),
                     scope=dict(SCOPE))
        self.step(service, short)
        done = self.settle(runs)
        self.assertEqual(done["summary"]["reason"], "AI_COVERAGE_BUDGET_INSUFFICIENT")
        summary = self.step(service, short)
        self.assertIn(dict(category="BUDGET", code="AI_COVERAGE_BUDGET_INSUFFICIENT"), summary["blockers"])
        result = summary["universe"]["last_result"]
        self.assertEqual((result["adopted"], result["reason"], result["selected"], inner.calls), (False, "AUTONOMOUS_SPENDING_LIMIT", [], 0))
        self.assertIsNone(self.loop.service._loop().get("pending_selection"))
        started = service.repository.events(self.work["account_id"], kinds=["UNIVERSE_RUN_STARTED"])[0]
        self.assertEqual(started["spend_limit"], dict(requests=need["requests"] - 1, tokens=10 ** 9))


# An adaptive owner policy: a maximum useful age for the selection, the material-change trigger, and a daily
# workload ceiling. Everything else is the same policy the tests above use.
ADAPTIVE = dict(universe_max_age_seconds=3600, universe_material_change_trigger=True, universe_max_runs_per_day=4)


class AdaptiveSchedulingTests(Base):
    """The controller's adaptive step against the real run tracker: what it decides, refuses and records."""

    def adaptive(self, **schedule) -> dict:
        return dict(policy(schedule=dict(ADAPTIVE, **schedule)), scope=dict(SCOPE))

    def on_one_clock(self, provider):
        """A tracker and controller on the fixture's own clock, so a run's completion and the schedule agree.

        The controlled universe's evidence is anchored to ``NOW``, so the controller's clock starts there too:
        a scheduler whose notion of when a selection completed disagrees with the run tracker's is not testable.
        """
        self.loop = Harness()
        self.loop.clock.value = NOW
        self.loop.service.attach_driver("PAPER_AUTOMATION", scope=LOOP_SCOPE, requested_cadence_seconds=60)
        screener = ScreenerAiService(reader=self.reader, news=News(provider), clock=lambda: NOW)
        runs = AiScreenerRuns(screener, clock=lambda: NOW, monotonic=lambda: 100.0)
        self.work = dict(account_id=self.loop.ledger.paper_account_id, universe={})
        service = PaperAutomationService(self.loop.store, repository=PaperAutomationRepository(), reevaluation=self.loop.service,
                                         runs=runs, clock=self.loop.clock)
        return runs, service

    def run_once(self, service, runs, automation_policy) -> dict:
        self.assertEqual(self.step(service, automation_policy)["universe"]["state"], "STARTED")
        self.settle(runs)
        return self.step(service, automation_policy)

    def test_a_fresh_unchanged_selection_is_skipped_and_only_rerun_once_it_expires(self):
        provider = RankingProvider()
        runs, service = self.on_one_clock(provider)
        automation_policy = self.adaptive()
        adopted = self.run_once(service, runs, automation_policy)
        self.assertTrue(adopted["universe"]["last_result"]["adopted"])
        calls = provider.calls
        # Past the minimum separation, comfortably inside the maximum useful age, nothing has changed.
        self.loop.clock.value += 1800
        summary = self.step(service, automation_policy)
        self.assertEqual((summary["universe"]["state"], summary["universe"]["decision"]["decision"]), ("IDLE", "SKIP"))
        self.assertEqual(provider.calls, calls)
        self.assertIsNone(self.work["universe"].get("active_run_id"))
        for _ in range(3):  # repeated cycles neither re-run nor repeat the receipt
            self.loop.clock.value += 60
            self.step(service, automation_policy)
        skipped = service.repository.events(self.work["account_id"], kinds=["UNIVERSE_RUN_SKIPPED"])
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0]["reason_codes"], ["UNIVERSE_SELECTION_FRESH_AND_UNCHANGED"])
        self.assertEqual(provider.calls, calls)
        self.loop.clock.value += 1800  # now the selection is past its maximum useful age
        self.assertEqual(self.step(service, automation_policy)["universe"]["state"], "STARTED")
        self.settle(runs)

    def test_an_exhausted_allowance_blocks_the_run_and_the_refusal_is_recorded_once(self):
        runs, service = self.on_one_clock(RankingProvider())
        automation_policy = self.adaptive()
        # No ``kind`` is supplied: it is derived from the refusal reason, so a budget refusal is a block.
        gate = dict(allowed=False, reason="AUTONOMOUS_SPENDING_LIMIT_REACHED")
        self.step(service, automation_policy, gate=gate)
        summary = self.step(service, automation_policy, gate=gate)
        self.assertEqual(summary["universe"]["decision"]["decision"], "BLOCK")
        self.assertEqual(summary["universe"]["decision"]["detail"], dict(gate="DAILY_ALLOWANCE"))
        self.assertIn(dict(category="BUDGET", code="AUTONOMOUS_SPENDING_LIMIT_REACHED"), summary["blockers"])
        self.assertEqual(self.work["universe"]["withheld"]["reason"], "AUTONOMOUS_SPENDING_LIMIT_REACHED")
        self.assertIsNone(self.work["universe"].get("active_run_id"))
        self.assertEqual(len(service.repository.events(self.work["account_id"], kinds=["UNIVERSE_RUN_BLOCKED"])), 1)

    def test_an_incomplete_run_backs_off_instead_of_being_relaunched_every_cycle(self):
        inner = RankingProvider()
        provider = BudgetedProvider(inner, DailyBudget(None, max_requests=1, max_tokens=1000, clock=lambda: NOW))
        runs, service = self.on_one_clock(provider)
        automation_policy = self.adaptive()
        self.assertEqual(self.step(service, automation_policy)["universe"]["state"], "STARTED")
        self.settle(runs)
        summary = self.step(service, automation_policy)
        self.assertEqual(summary["universe"]["decision"]["reason_codes"], ["UNIVERSE_RETRY_BACKOFF"])
        self.assertEqual(summary["universe"]["last_result"]["status"], "AI_COVERAGE_BUDGET_INSUFFICIENT")
        failure = self.work["universe"]["failure"]
        self.assertEqual(failure["count"], 1)
        self.assertIsNotNone(failure["code"])
        self.assertIsNone(self.work["universe"].get("active_run_id"))
        self.assertEqual(inner.calls, 0)  # the refused plan was never paid for
        deferred = service.repository.events(self.work["account_id"], kinds=["UNIVERSE_RUN_DEFERRED"])[0]
        self.assertEqual(deferred["reason_codes"], ["UNIVERSE_RETRY_BACKOFF"])

    def test_a_new_trading_session_is_a_material_change_that_starts_a_run(self):
        provider = RankingProvider()
        runs, service = self.on_one_clock(provider)
        automation_policy = self.adaptive(universe_max_age_seconds=86400)
        self.run_once(service, runs, automation_policy)
        self.loop.clock.value += 259200  # Friday's selection, revisited on Monday's session
        summary = self.step(service, automation_policy)
        self.assertEqual(summary["universe"]["state"], "STARTED")
        decision = self.work["universe"]["last_decision"]
        self.assertEqual(decision["reason_codes"], ["UNIVERSE_MATERIAL_CHANGE", "NEW_SESSION"])
        self.assertEqual(decision["detail"]["material_change"], ["NEW_SESSION"])
        # The new run's fingerprint belongs to the session it started in; the completed selection it replaces
        # was made in the previous one.
        self.assertEqual((self.work["universe"]["last_complete_fingerprint"]["session_date"],
                          self.work["universe"]["run_fingerprint"]["session_date"]), ("2026-10-02", "2026-10-05"))
        self.settle(runs)

    def test_the_scheduling_state_is_persisted_so_a_restart_resumes_the_same_schedule(self):
        provider = RankingProvider()
        runs, service = self.on_one_clock(provider)
        automation_policy = self.adaptive()
        self.run_once(service, runs, automation_policy)
        # The controller row is where the scheduler's own state lives between cycles and across a restart.
        service.repository.save_controller(dict(schema_version="paper-automation-controller/1.0.0",
                                                account_id=self.work["account_id"], updated_epoch=self.loop.clock(),
                                                universe=self.work["universe"]))
        persisted = service.repository.get_controller(self.work["account_id"])["universe"]
        self.assertEqual(persisted["last_complete_fingerprint"]["session_date"], "2026-10-02")
        self.assertTrue(persisted["last_complete_fingerprint"]["scope"])
        self.assertEqual(persisted["last_decision"]["decision"], "DEFER")
        # A restarted service reads that state instead of rebuilding a schedule from nothing.
        restarted = PaperAutomationService(self.loop.store, repository=service.repository, reevaluation=self.loop.service,
                                           runs=runs, clock=self.loop.clock)
        summary = dict(blockers=[], universe=None)
        now = self.loop.clock()
        restarted._universe(dict(self.work, universe=persisted), automation_policy, summary, now, restarted.session(now),
                            dict(allowed=True, reason=None))
        self.assertEqual(summary["universe"]["decision"]["reason_codes"], ["UNIVERSE_MIN_SEPARATION"])
        self.assertEqual(provider.calls, 4)  # one complete run, and no duplicate paid work after the restart


if __name__ == "__main__":
    unittest.main()
