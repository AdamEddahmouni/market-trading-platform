"""Full-universe AI Screener coverage: every row accounted for, eligible rows reduced in bounded batches,
finalists compared globally, and every incomplete outcome reported as incomplete. Controlled engine, no spend."""

from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.inference.anthropic_synthesis import BudgetedProvider, DailyBudget  # noqa: E402
from market_platform_foundation.intelligence.inference.candidate_reduction import MAX_INTAKE, MAX_SELECTED  # noqa: E402
from market_platform_foundation.intelligence.inference.coverage_plan import METHOD_VERSION  # noqa: E402
from market_platform_foundation.local_state.action_decisions import action_repository  # noqa: E402
from market_platform_foundation.local_state.ai_screener_coverage import CoverageLedger  # noqa: E402
from market_platform_foundation.platform.security.leak_audit import assert_no_secrets_in_payload  # noqa: E402
from market_platform_foundation.ui_api.screener_ai import ScreenerAiService  # noqa: E402
from market_platform_foundation.ui_api.screener_ai_coverage import ScreenerAiCoverage, interrupt_open_runs  # noqa: E402
from tests.support.coverage_universe import (  # noqa: E402
    NOW, SCOPE, FailingProvider, News, PagingReader, RankingProvider, answer, instrument_id, row, universe,
)

SHA = "a" * 40
_SEQUENCE = [0]


def run_id() -> str:
    _SEQUENCE[0] += 1
    return f"cov{_SEQUENCE[0]:029d}"


class Harness:
    def __init__(self, rows, provider=None, *, clock=lambda: NOW, reader=None) -> None:
        self.provider = provider if provider is not None else RankingProvider()
        self.reader = reader or PagingReader(rows)
        self.service = ScreenerAiService(reader=self.reader, news=News(self.provider), clock=clock)
        self.ledger = CoverageLedger()
        self.run_id = run_id()

    def run(self, *, should_stop=lambda: False, scope=SCOPE):
        self.result = ScreenerAiCoverage(self.service, ledger=self.ledger, software_sha=SHA).run(
            scope, run_id=self.run_id, account_id="PAPER-1", should_stop=should_stop)
        self.block = self.result["universe_coverage"]
        return self.result

    def selected(self) -> list[str]:
        return [pick["instrument_id"] for pick in self.result["candidates"]]

    def calls(self) -> list[dict]:
        return self.ledger.records(self.run_id, "batch")


def reconciled(test: unittest.TestCase, block: dict, universe_count: int) -> None:
    counts = block["counts"]
    test.assertTrue(block["reconciled"])
    test.assertEqual(counts["evaluated"] + counts["ineligible"] + counts["evidence_blocked"] + counts["unprocessed"], universe_count)
    test.assertEqual(sum(counts["by_class"].values()), universe_count)
    test.assertEqual(block["universe_count"], universe_count)


class ScaleAndAccountingTests(unittest.TestCase):
    def test_every_size_enumerates_accounts_and_reconciles(self):
        for size in (0, 7, 49, 50, 51, 100, 500, 4600):
            with self.subTest(size=size):
                h = Harness(universe(size))
                h.run()
                reconciled(self, h.block, size)
                self.assertEqual(h.block["assessed_count"], size)
                self.assertEqual(h.block["eligible_count"], size)
                self.assertEqual(h.block["ai_evaluated_count"], size)
                batches = -(-size // MAX_INTAKE)
                self.assertEqual((h.block["batches_planned"], h.block["batches_completed"]), (batches, batches))
                self.assertEqual(sum(len(seen) for seen in h.provider.seen[:batches]), size)
                self.assertTrue(all(len(seen) <= MAX_INTAKE for seen in h.provider.seen))
                self.assertTrue(h.block["coverage_complete"] and h.block["selection_complete"])
                self.assertEqual(h.block["status"], "EMPTY_UNIVERSE" if size == 0 else "COMPLETE_NO_SELECTION")
                # No controlled-strong row exists, so nothing is selected and nothing is invented.
                self.assertEqual(h.result["candidates"], [])
                self.assertEqual(h.result["state"], "NO_GROUNDED_CANDIDATES")

    def test_exactly_one_batch_needs_no_second_request(self):
        h = Harness(universe(50, strong={49: 90.0}))
        h.run()
        self.assertEqual(h.provider.calls, 1)
        self.assertEqual(h.block["plan"]["reduction_rounds_planned"], [])
        self.assertEqual(h.selected(), [instrument_id(49)])
        self.assertEqual(h.block["status"], "GLOBAL_SELECTION_COMPLETE")

    def test_fifty_one_rows_are_two_batches_and_one_global_comparison(self):
        h = Harness(universe(51, strong={50: 90.0}))
        h.run()
        self.assertEqual(h.block["batches_planned"], 2)
        self.assertEqual(h.block["plan"]["reduction_rounds_planned"], [1])
        self.assertEqual(h.provider.calls, 3)
        self.assertEqual(h.selected(), [instrument_id(50)])

    def test_the_run_identity_and_method_are_on_the_result_and_the_ledger(self):
        h = Harness(universe(120, strong={119: 90.0}))
        h.run()
        head = h.ledger.records(h.run_id, "run")[0]
        self.assertEqual(head["method_version"], METHOD_VERSION)
        self.assertEqual(head["software_sha"], SHA)
        self.assertEqual(head["wire_schema_version"], "ai-screener-wire/3.0.0")
        self.assertEqual(head["prompt_id"], "screener.ai_candidate_reduction.v3")
        self.assertEqual(h.block["method_version"], METHOD_VERSION)
        self.assertEqual(h.block["software_sha"], SHA)
        self.assertEqual(h.block["enumeration"]["result_set"], "set-1")
        self.assertEqual(h.result["wire_schema_version"], "ai-screener-wire/3.0.0")
        assert_no_secrets_in_payload(h.result)


class LateUniverseTests(unittest.TestCase):
    def test_a_strong_candidate_at_position_51_is_selected(self):
        h = Harness(universe(200, strong={50: 95.0}))
        h.run()
        self.assertEqual(h.selected(), [instrument_id(50)])
        self.assertTrue(h.block["selection_complete"])

    def test_the_best_controlled_candidate_at_position_4600_is_ranked_first(self):
        h = Harness(universe(4600, strong={4599: 99.0, 10: 85.0, 2000: 91.0}))
        h.run()
        self.assertEqual(h.selected(), [instrument_id(4599), instrument_id(2000), instrument_id(10)])
        self.assertEqual([pick["rank"] for pick in h.result["candidates"]], [1, 2, 3])
        reconciled(self, h.block, 4600)
        self.assertEqual(h.block["plan"]["reduction_rounds_planned"], [10, 1])
        # Three finalists fit one request, so the planned worst case of eleven comparison calls is not spent.
        self.assertEqual(h.block["model_calls"], 93)

    def test_first_fifty_rows_hold_nothing_worthwhile(self):
        h = Harness(universe(300, strong={60: 82.0, 299: 97.0}))
        h.run()
        self.assertEqual(h.selected(), [instrument_id(299), instrument_id(60)])
        self.assertFalse(set(h.selected()) & {instrument_id(index) for index in range(50)})

    def test_later_batches_beat_earlier_finalists_and_only_five_survive(self):
        strong = {5: 81.0, 17: 82.0, 140: 83.0, 260: 84.0, 301: 90.0, 388: 96.0, 450: 97.0, 499: 99.0}
        h = Harness(universe(500, strong=strong))
        h.run()
        expected = [instrument_id(index) for index, _ in sorted(strong.items(), key=lambda item: -item[1])[:MAX_SELECTED]]
        self.assertEqual(h.selected(), expected)
        self.assertEqual(h.block["finalist_count"], len(strong))
        self.assertEqual(h.block["selected_count"], MAX_SELECTED)
        self.assertNotIn(instrument_id(5), h.selected())

    def test_many_finalists_take_more_than_one_comparison_round(self):
        strong = {index: 80.0 + (index % 19) for index in range(0, 4600, 7)}
        h = Harness(universe(4600, strong=strong))
        h.run()
        self.assertGreater(h.block["finalist_count"], MAX_INTAKE)
        self.assertGreaterEqual(h.block["reduction"]["rounds_completed"], 2)
        self.assertEqual(len(h.selected()), MAX_SELECTED)
        self.assertTrue(all(strong[int(value[4:])] == 98.0 for value in h.selected()))
        rounds = h.ledger.records(h.run_id, "round")
        self.assertEqual(rounds[-1]["calls"], 1)
        self.assertTrue(all(later["entrants"] < earlier["entrants"] for earlier, later in zip(rounds, rounds[1:])))

    def test_several_batches_select_nothing_and_that_is_a_completed_result(self):
        h = Harness(universe(260))
        h.run()
        self.assertEqual(h.block["status"], "COMPLETE_NO_SELECTION")
        self.assertEqual(h.result["reason"], "COMPLETE_NO_SELECTION")
        self.assertEqual(h.provider.calls, 6)
        self.assertEqual(h.result["provisional"], [])


class FairnessTests(unittest.TestCase):
    def test_sort_order_and_page_position_change_neither_batches_nor_the_selection(self):
        strong = {3: 88.0, 77: 93.0, 410: 91.0, 911: 86.0}
        rows = universe(1000, strong=strong)
        shuffled = list(rows)
        random.Random(11).shuffle(shuffled)
        first, second, third = Harness(rows), Harness(shuffled), Harness(list(reversed(rows)))
        for h in (first, second, third):
            h.run()
        batches = [[frozenset(call["instrument_ids"]) for call in h.calls() if call["stage"] == "BATCH_INFERENCE"] for h in (first, second, third)]
        self.assertEqual(batches[0], batches[1])
        self.assertEqual(batches[0], batches[2])
        self.assertEqual(first.selected(), second.selected())
        self.assertEqual(first.selected(), third.selected())
        self.assertEqual(first.selected(), [instrument_id(77), instrument_id(410), instrument_id(3), instrument_id(911)])

    def test_batches_are_disjoint_and_each_finalist_enters_the_comparison_once(self):
        h = Harness(universe(150, strong={10: 90.0, 60: 91.0, 110: 92.0}))
        h.run()
        first_pass = [call["instrument_ids"] for call in h.calls() if call["stage"] == "BATCH_INFERENCE"]
        sent = [value for batch in first_pass for value in batch]
        self.assertEqual(len(sent), len(set(sent)))
        self.assertEqual(sorted(sent), sorted(instrument_id(index) for index in range(150)))
        final = h.provider.seen[-1]
        self.assertEqual(len(final), len(set(final)))
        self.assertEqual(sorted(final), sorted(instrument_id(index) for index in (10, 60, 110)))


class EligibilityTests(unittest.TestCase):
    def test_missing_stale_and_future_evidence_is_reported_and_never_sent(self):
        rows = universe(120, strong={119: 90.0})
        rows[0] = row(0, price=None)                                    # no price observation at all
        rows[1] = row(1, as_of="2026-10-02T13:00:00Z")                  # stale
        rows[2] = row(2, as_of="2026-10-02T16:00:00Z")                  # future-dated
        rows[3] = row(3, state="UNAVAILABLE")                           # provider state
        h = Harness(rows)
        h.run()
        reconciled(self, h.block, 120)
        counts = h.block["counts"]
        self.assertEqual(counts["evidence_blocked"], 4)
        self.assertEqual(counts["evaluated"], 116)
        self.assertEqual(counts["ineligible"], 0)
        sent = {value for seen in h.provider.seen for value in seen}
        self.assertFalse(sent & {instrument_id(index) for index in range(4)})
        self.assertTrue(h.block["coverage_complete"])
        self.assertEqual(h.selected(), [instrument_id(119)])
        rows_record = [item for part in h.ledger.records(h.run_id, "rows") if part["phase"] == "FINAL" for item in part["rows"]]
        by_id = {item[0]: item for item in rows_record}
        self.assertEqual(len(rows_record), 120)
        self.assertEqual(by_id[instrument_id(2)][1:], ["EVIDENCE_UNAVAILABLE", ["FUTURE_OBSERVATION_TIME"]])
        self.assertNotEqual(by_id[instrument_id(0)][1], "INELIGIBLE")
        self.assertEqual(by_id[instrument_id(1)][1], "EVIDENCE_STALE")

    def test_a_universe_with_no_eligible_row_calls_no_model(self):
        h = Harness([row(index, price=None) for index in range(70)])
        h.run()
        self.assertEqual(h.provider.calls, 0)
        self.assertEqual(h.block["status"], "NO_ELIGIBLE_ROWS")
        self.assertEqual(h.block["counts"]["evidence_blocked"], 70)
        self.assertTrue(h.block["selection_complete"])
        reconciled(self, h.block, 70)

    def test_an_unconfigured_engine_evaluates_nothing_and_says_so(self):
        h = Harness(universe(60))
        h.service = ScreenerAiService(reader=h.reader, news=News(None), clock=lambda: NOW)
        h.run()
        self.assertEqual(h.block["status"], "FAILED")
        self.assertEqual(h.block["counts"]["unprocessed"], 60)
        self.assertFalse(h.block["coverage_complete"])
        self.assertEqual(h.result["state"], "INCOMPLETE")


class ClockReader(PagingReader):
    """Rows observed at the moment they are read, as a live Screener serves them; ``frozen`` rows keep one clock."""

    def __init__(self, rows, clock, *, frozen=()):
        super().__init__(rows)
        self.clock, self.frozen = clock, {instrument_id(index) for index in frozen}

    def read(self, **kwargs):
        from datetime import UTC, datetime

        now = datetime.fromtimestamp(self.clock(), UTC).isoformat().replace("+00:00", "Z")
        for item in self.rows:
            if item["instrument"]["instrument_id"] not in self.frozen:
                for field in item["fields"].values():
                    field["as_of"] = now
        return super().read(**{**kwargs, "result_set": None})


class Snapshots:
    """The bounded vendor snapshot source: records every acquisition and can be made to fail from a given one."""

    def __init__(self, clock, *, fail_from=None):
        self.clock, self.fail_from, self.sizes = clock, fail_from, []

    def latest(self):
        return None

    def current(self, rows, *, catalog_as_of, force=False):
        from datetime import UTC, datetime
        from types import SimpleNamespace

        self.sizes.append(len(rows))
        if self.fail_from is not None and len(self.sizes) >= self.fail_from:
            return None, "MARKET_SNAPSHOT_UNAVAILABLE"
        now = datetime.fromtimestamp(self.clock(), UTC).isoformat().replace("+00:00", "Z")
        ids = [item["instrument"]["instrument_id"] for item in rows]
        return SimpleNamespace(values={key: {"price": 100.0, "volume": 5000.0, "change_pct": 1.0, "bid": None, "ask": None, "spread_pct": None} for key in ids},
                               row_as_of={key: now for key in ids}, refused=frozenset(), as_of=now, catalog_as_of=catalog_as_of), None


class TemporalTests(unittest.TestCase):
    def test_eligible_rows_that_age_out_before_their_request_are_not_sent_and_the_run_is_not_complete(self):
        ticks = [NOW]
        provider = RankingProvider()
        provider.on_call = lambda call, packet: (ticks.__setitem__(0, NOW + 90), provider.respond(packet))[1]
        h = Harness(universe(100, strong={0: 90.0, 99: 95.0}), provider, clock=lambda: ticks[0])
        h.run()
        # The first request was sent on current evidence; ninety seconds later the second batch's quotes had expired.
        self.assertEqual(provider.calls, 1)
        reconciled(self, h.block, 100)
        counts = h.block["counts"]
        self.assertEqual((counts["evaluated"], counts["unprocessed"], counts["evidence_blocked"]), (50, 50, 0))
        self.assertTrue(all(key.startswith("UNPROCESSED:EVIDENCE_STALE_AT_REQUEST_CUTOFF") or key.startswith("UNPROCESSED:") for key in counts["reasons"]))
        self.assertEqual(counts["reasons"]["UNPROCESSED:EVIDENCE_STALE_AT_REQUEST_CUTOFF"], 50)
        # Half of the eligible rows never reached the model: that is never complete and never 100%.
        self.assertEqual((h.block["status"], h.block["reason"]), ("PROVISIONAL_PARTIAL_COVERAGE", "ELIGIBLE_ROWS_NOT_SUBMITTED"))
        self.assertEqual(h.block["ai_coverage_pct"], 50.0)
        self.assertFalse(h.block["coverage_complete"] or h.block["selection_complete"])
        self.assertEqual((h.result["state"], h.result["candidates"]), ("INCOMPLETE", []))
        self.assertIsNone(action_repository().get("candidate_run", "CU-" + h.run_id))

    def test_rows_are_read_again_for_every_request_so_a_long_run_does_not_age_out_its_own_evidence(self):
        ticks = [NOW]
        provider = RankingProvider()
        provider.on_call = lambda call, packet: (ticks.__setitem__(0, ticks[0] + 50), provider.respond(packet))[1]
        clock = lambda: ticks[0]
        h = Harness([], provider, clock=clock, reader=ClockReader(universe(200, strong={199: 95.0}), clock))
        h.run()
        # Five requests fifty seconds apart, 200 seconds in all against a 60-second quote policy: every request saw
        # rows observed at its own cutoff, where rows kept from enumeration would have expired by the third.
        self.assertEqual(provider.calls, 5)
        self.assertEqual((h.block["status"], h.block["ai_evaluated_count"]), ("GLOBAL_SELECTION_COMPLETE", 200))
        self.assertTrue(h.block["coverage_complete"])
        self.assertEqual(h.selected(), [instrument_id(199)])
        for call in h.calls():
            self.assertEqual(call["dropped"], {})

    def test_a_finalist_stale_at_the_final_comparison_is_excluded_and_the_result_says_so(self):
        ticks = [NOW]
        provider = RankingProvider()
        provider.on_call = lambda call, packet: (ticks.__setitem__(0, ticks[0] + 35), provider.respond(packet))[1]
        clock = lambda: ticks[0]
        # Row 99 is the strongest and keeps its first observation clock; every other row is observed afresh.
        h = Harness([], provider, clock=clock, reader=ClockReader(universe(100, strong={5: 90.0, 99: 95.0}), clock, frozen=(99,)))
        h.run()
        self.assertEqual(provider.calls, 3)
        self.assertEqual((h.block["status"], h.block["reason"]), ("GLOBAL_SELECTION_COMPLETE", "FINALISTS_EXCLUDED_AT_FINAL_CUTOFF"))
        self.assertEqual(h.selected(), [instrument_id(5)])
        excluded = h.block["reduction"]["finalists_excluded"]
        self.assertEqual([(item["instrument_id"], item["class"]) for item in excluded], [(instrument_id(99), "EVIDENCE_STALE")])
        self.assertEqual(h.block["reduction"]["finalists_excluded_count"], 1)
        self.assertTrue(any("1 batch finalist(s) had no admissible" in text for text in h.result["limitations"]))
        stored = action_repository().get("candidate_run", h.result["run_id"])
        self.assertEqual(stored["universe_coverage"]["reduction"]["finalists_excluded_count"], 1)
        self.assertNotIn(instrument_id(99), provider.seen[-1])

    def test_no_finalist_admissible_at_the_final_comparison_is_not_a_completed_selection(self):
        ticks = [NOW]
        provider = RankingProvider()
        provider.on_call = lambda call, packet: (ticks.__setitem__(0, ticks[0] + 35), provider.respond(packet))[1]
        clock = lambda: ticks[0]
        h = Harness([], provider, clock=clock, reader=ClockReader(universe(100, strong={5: 90.0, 99: 95.0}), clock, frozen=(5, 99)))
        h.run()
        self.assertEqual(provider.calls, 2)
        self.assertEqual((h.block["status"], h.block["reason"]), ("PROVISIONAL_PARTIAL_COVERAGE", "NO_FINALIST_ADMISSIBLE_AT_FINAL_CUTOFF"))
        self.assertFalse(h.block["selection_complete"])
        self.assertEqual(len(h.result["provisional"]), 2)

    def test_an_answer_that_arrives_after_its_evidence_expired_is_not_stored_as_a_selection(self):
        ticks = [NOW]
        provider = RankingProvider()
        provider.on_call = lambda call, packet: (ticks.__setitem__(0, ticks[0] + 70), provider.respond(packet))[1]
        h = Harness(universe(40, strong={7: 90.0}), provider, clock=lambda: ticks[0])
        h.run()
        self.assertEqual((h.block["status"], h.block["reason"]), ("PROVISIONAL_PARTIAL_COVERAGE", "FINAL_SELECTION_EXPIRED_DURING_INFERENCE"))
        self.assertEqual((h.result["state"], h.result["candidates"]), ("INCOMPLETE", []))
        self.assertEqual([item["instrument_id"] for item in h.result["provisional"]], [instrument_id(7)])
        self.assertFalse(h.block["selection_complete"])
        self.assertIsNone(action_repository().get("candidate_run", "CU-" + h.run_id))

    def test_a_bounded_vendor_snapshot_is_acquired_once_for_classification_and_once_for_every_request(self):
        rows = [row(index, price=None, rsi=90.0 if index == 119 else 50.0) for index in range(120)]
        h = Harness(rows)
        snapshots = Snapshots(lambda: NOW)
        h.service = ScreenerAiService(reader=h.reader, news=News(h.provider), clock=lambda: NOW, market_snapshots=snapshots)
        h.run()
        # No row carries a price of its own: eligibility and every request's quote come from the snapshot source.
        self.assertEqual(snapshots.sizes, [120, 50, 50, 20, 1])
        self.assertEqual((h.block["status"], h.block["ai_evaluated_count"]), ("GLOBAL_SELECTION_COMPLETE", 120))
        self.assertEqual(h.selected(), [instrument_id(119)])
        quote = next(item for item in h.result["evidence"][0]["current_market_evidence"] if item["capability"] == "QUOTE")
        self.assertEqual((quote["source"], quote["facts"]["price"]), ("MOOMOO_OPEND_SNAPSHOT", 100.0))

    def test_a_snapshot_source_that_fails_mid_run_leaves_those_rows_unprocessed_by_name(self):
        rows = [row(index, price=None) for index in range(120)]
        h = Harness(rows)
        snapshots = Snapshots(lambda: NOW, fail_from=3)
        h.service = ScreenerAiService(reader=h.reader, news=News(h.provider), clock=lambda: NOW, market_snapshots=snapshots)
        h.run()
        reconciled(self, h.block, 120)
        self.assertEqual(h.provider.calls, 1)
        self.assertEqual(h.block["status"], "PROVISIONAL_PARTIAL_COVERAGE")
        self.assertEqual((h.block["counts"]["evaluated"], h.block["counts"]["unprocessed"]), (50, 70))
        self.assertEqual(h.block["counts"]["reasons"]["UNPROCESSED:PROVIDER_UNAVAILABLE_AT_REQUEST_CUTOFF"], 70)
        self.assertFalse(h.block["coverage_complete"])

    def test_a_quote_source_that_returns_nothing_is_reported_as_that_and_not_as_no_eligible_rows(self):
        rows = [row(index, price=None) for index in range(80)]
        h = Harness(rows)
        h.service = ScreenerAiService(reader=h.reader, news=News(h.provider), clock=lambda: NOW, market_snapshots=Snapshots(lambda: NOW, fail_from=1))
        h.run()
        reconciled(self, h.block, 80)
        self.assertEqual((h.block["status"], h.block["reason"]), ("EVIDENCE_PROVIDER_UNAVAILABLE", "MARKET_SNAPSHOT_UNAVAILABLE"))
        self.assertEqual(h.block["counts"]["by_class"], {"PROVIDER_UNAVAILABLE": 80})
        self.assertFalse(h.block["coverage_complete"] or h.block["selection_complete"])
        self.assertEqual((h.result["state"], h.provider.calls), ("INCOMPLETE", 0))

    def test_each_call_records_its_own_cutoff_and_none_precedes_its_evidence(self):
        ticks = [NOW]
        provider = RankingProvider()
        provider.on_call = lambda call, packet: (ticks.__setitem__(0, ticks[0] + 5), provider.respond(packet))[1]
        h = Harness(universe(150, strong={149: 90.0}), provider, clock=lambda: ticks[0])
        h.run()
        cutoffs = [call["evidence_cutoff"] for call in h.calls()]
        self.assertEqual(cutoffs, sorted(cutoffs))
        self.assertEqual(len(set(cutoffs)), len(cutoffs))
        self.assertTrue(all(call["completed_at"] >= call["evidence_cutoff"] for call in h.calls()))
        self.assertEqual(h.block["cutoffs"]["first_batch"], cutoffs[0])
        self.assertEqual(h.block["cutoffs"]["final"], cutoffs[-1])
        # The stored result's evidence was observed no later than the final comparison's own cutoff.
        self.assertEqual(h.result["decision_cutoff"], cutoffs[-1])
        for candidate in h.result["evidence"]:
            for item in (*candidate["current_market_evidence"], *candidate["reference_evidence"]):
                self.assertLessEqual(item["as_of"], h.result["decision_cutoff"])


class FailureTests(unittest.TestCase):
    def partial(self, h: Harness, size: int) -> None:
        reconciled(self, h.block, size)
        self.assertEqual(h.block["status"], "PROVISIONAL_PARTIAL_COVERAGE")
        self.assertFalse(h.block["coverage_complete"])
        self.assertFalse(h.block["selection_complete"])
        self.assertEqual(h.result["state"], "INCOMPLETE")
        self.assertEqual(h.result["candidates"], [])
        self.assertEqual(h.result["evidence"], [])
        self.assertIsNone(action_repository().get("candidate_run", h.result["run_id"]))
        self.assertIsNone(action_repository().get("candidate_run", "CU-" + h.run_id))

    def test_a_provider_failure_mid_scan_stops_the_scan_and_reports_what_was_not_evaluated(self):
        h = Harness(universe(260, strong={index: 90.0 for index in range(0, 260, 9)}), FailingProvider(fail_on=3))
        h.run()
        self.partial(h, 260)
        self.assertEqual(h.provider.calls, 3)
        self.assertEqual(h.block["batches_completed"], 2)
        self.assertEqual(h.block["counts"]["evaluated"], 100)
        self.assertEqual(h.block["counts"]["unprocessed"], 160)
        reasons = h.block["counts"]["reasons"]
        self.assertEqual(reasons["UNPROCESSED:BATCH_FAILED:ANTHROPIC_OVERLOADED_ERROR"], 50)
        self.assertEqual(reasons["UNPROCESSED:NOT_STARTED_AFTER_BATCH_FAILURE"], 110)
        self.assertEqual(h.block["reason"], "BATCH_FAILED:ANTHROPIC_OVERLOADED_ERROR")
        # Finalists from the two finished batches are shown as provisional and are not a selection.
        self.assertTrue(h.result["provisional"])
        self.assertTrue(all(item["batch"] in (1, 2) for item in h.result["provisional"]))

    def test_a_timeout_is_an_unknown_provider_outcome_and_is_not_retried(self):
        h = Harness(universe(150), FailingProvider(fail_on=2, reason="ANTHROPIC_TIMEOUT", timeout=True))
        h.run()
        self.partial(h, 150)
        self.assertEqual(h.provider.calls, 2)
        self.assertEqual(h.calls()[-1]["outcome"], "UNKNOWN_PROVIDER_OUTCOME")

    def test_invalid_model_output_is_rejected_canonically_and_never_becomes_a_finalist(self):
        cases = {
            "MALFORMED_JSON": "{not json",
            "WIRE_REFERENCE_INDEX_INVALID": '{"schema_version":"ai-screener-output/1.0.0","limitations":["x"],"candidates":[{"candidate_key":0,"rank":1,'
                                            '"rationale":"Candidate for review.","supporting_refs":[0,99],"conflicting_refs":[],"uncertainties":[]}]}',
            "WIRE_CANDIDATE_KEY_INVALID": '{"schema_version":"ai-screener-output/1.0.0","limitations":["x"],"candidates":[{"candidate_key":999,"rank":1,'
                                          '"rationale":"Candidate for review.","supporting_refs":[0,1],"conflicting_refs":[],"uncertainties":[]}]}',
        }
        for reason, raw in cases.items():
            with self.subTest(reason=reason):
                h = Harness(universe(120, strong={5: 90.0}), FailingProvider(fail_on=1, raw=raw))
                h.run()
                self.partial(h, 120)
                self.assertEqual(h.block["reason"], "BATCH_FAILED:" + reason)
                self.assertEqual(h.calls()[0]["state"], "INVALID_OUTPUT")
                self.assertEqual(h.result["provisional"], [])

    def test_a_batch_answer_naming_one_symbol_twice_is_rejected(self):
        class Twice(RankingProvider):
            def on_call(self, call, packet):
                first = packet.candidates[0]
                response = self.respond(packet)
                return type(response)(answer(packet.candidates, [first, first]), self.provider_id, self.model_id,
                                      tokens_input=1000, tokens_output=100, latency_ms=1, simulated=True)

        h = Harness(universe(120), Twice())
        h.run()
        self.partial(h, 120)
        self.assertEqual(h.block["reason"], "BATCH_FAILED:UNKNOWN_OR_DUPLICATE_CANDIDATE")

    def test_a_failed_global_comparison_leaves_finalists_provisional(self):
        h = Harness(universe(150, strong={10: 90.0, 60: 91.0, 110: 92.0}), FailingProvider(fail_on=4))
        h.run()
        reconciled(self, h.block, 150)
        self.assertEqual(h.block["status"], "PROVISIONAL_PARTIAL_COVERAGE")
        self.assertEqual(h.block["reason"], "GLOBAL_REDUCTION_INCOMPLETE:ANTHROPIC_OVERLOADED_ERROR")
        self.assertEqual(h.block["counts"]["evaluated"], 150)
        self.assertFalse(h.block["selection_complete"])
        self.assertEqual(len(h.result["provisional"]), 3)
        self.assertEqual(h.result["candidates"], [])
        self.assertIsNone(action_repository().get("candidate_run", "CU-" + h.run_id))

    def test_a_paging_failure_evaluates_nothing(self):
        class Moving(PagingReader):
            def read(self, **kwargs):
                if kwargs["offset"]:
                    raise ValueError("RESULT_SET_CHANGED")
                return super().read(**kwargs)

        h = Harness([], reader=Moving(universe(1200)))
        h.run()
        self.assertEqual(h.block["status"], "UNIVERSE_ENUMERATION_FAILED")
        self.assertEqual(h.block["reason"], "RESULT_SET_CHANGED")
        self.assertFalse(h.block["enumeration"]["complete"])
        self.assertFalse(h.block["reconciled"])
        self.assertEqual(h.provider.calls, 0)
        self.assertEqual(h.result["state"], "INCOMPLETE")

    def test_an_unexpected_error_still_ends_with_a_terminal_record(self):
        class Exploding(RankingProvider):
            def on_call(self, call, packet):
                raise RuntimeError("boom with private detail")

        h = Harness(universe(60), Exploding())
        with self.assertRaises(RuntimeError):
            h.run()
        terminal = h.ledger.terminal(h.run_id)
        self.assertEqual((terminal["status"], terminal["reason"]), ("FAILED", "AI_SCREENER_RUN_FAILED"))
        self.assertEqual(h.ledger.open_runs(), [])
        self.assertNotIn("boom", str(terminal))


class StopTests(unittest.TestCase):
    def test_stop_prevents_the_next_call_and_keeps_completed_receipts(self):
        stop = [False]
        provider = RankingProvider()
        provider.on_call = lambda call, packet: (stop.__setitem__(0, call >= 2), provider.respond(packet))[1]
        h = Harness(universe(300, strong={index: 90.0 for index in range(0, 300, 11)}), provider)
        h.run(should_stop=lambda: stop[0])
        reconciled(self, h.block, 300)
        self.assertEqual(h.block["status"], "STOPPED")
        self.assertEqual(provider.calls, 2)
        self.assertEqual(len(h.calls()), 2)
        self.assertEqual(h.block["counts"]["evaluated"], 100)
        self.assertEqual(h.block["counts"]["reasons"]["UNPROCESSED:STOPPED_BY_OPERATOR"], 200)
        self.assertFalse(h.block["coverage_complete"])
        self.assertIsNone(action_repository().get("candidate_run", "CU-" + h.run_id))

    def test_a_long_stopped_run_with_hundreds_of_finalists_still_writes_one_terminal_and_one_row_account(self):
        stop = [False]
        provider = RankingProvider()
        provider.on_call = lambda call, packet: (stop.__setitem__(0, call >= 50), provider.respond(packet))[1]
        h = Harness(universe(3000, strong={index: 80.0 + index % 17 for index in range(3000)}), provider)
        h.run(should_stop=lambda: stop[0])
        terminal = h.ledger.terminal(h.run_id)
        self.assertEqual(terminal["status"], "STOPPED")
        self.assertEqual(h.ledger.open_runs(), [])
        self.assertEqual(len(h.result["provisional"]), 250)
        self.assertEqual((terminal["provisional_count"], len(terminal["provisional"])), (250, 250))
        self.assertNotIn("rationale", terminal["provisional"][0])
        self.assertNotIn("plan", terminal["universe_coverage"])
        final_rows = [item for part in h.ledger.records(h.run_id, "rows") if part["phase"] == "FINAL" for item in part["rows"]]
        self.assertEqual(len(final_rows), 3000)

    def test_stop_before_the_first_call_spends_nothing(self):
        h = Harness(universe(120))
        h.run(should_stop=lambda: True)
        self.assertEqual(h.provider.calls, 0)
        self.assertEqual(h.block["counts"]["unprocessed"], 120)
        self.assertEqual(h.block["status"], "STOPPED")


class BudgetTests(unittest.TestCase):
    def budgeted(self, rows, *, max_tokens, max_requests=1000, inner=None):
        inner = inner or RankingProvider()
        budget = DailyBudget(None, max_requests=max_requests, max_tokens=max_tokens, clock=lambda: NOW)
        h = Harness(rows, BudgetedProvider(inner, budget))
        h.inner, h.budget = inner, budget
        return h

    def required(self, rows) -> dict:
        probe = self.budgeted(rows, max_tokens=10 ** 12)
        probe.run()
        return probe.block["plan"]["required"]

    def test_a_local_engine_has_no_token_or_request_cap(self):
        h = Harness(universe(4600, strong={4599: 90.0}))
        h.run()
        self.assertEqual(h.block["budget"]["capped"], False)
        self.assertEqual(h.block["plan"]["budget_basis"], "UNCAPPED_ENGINE")
        self.assertEqual(h.block["batches_completed"], 92)
        self.assertTrue(h.block["selection_complete"])

    def test_sufficient_budget_holds_the_whole_plan_then_releases_what_it_did_not_use(self):
        rows = universe(260, strong={259: 90.0})
        h = self.budgeted(rows, max_tokens=10 ** 9)
        h.run()
        self.assertEqual(h.block["status"], "GLOBAL_SELECTION_COMPLETE")
        budget = h.block["budget"]
        self.assertTrue(budget["capped"] and budget["held"])
        self.assertEqual(budget["required_requests"], 7)   # six batches and one comparison
        self.assertEqual(h.inner.calls, 7)
        self.assertIsNone(h.budget.held(h.run_id))
        status = h.budget.status()
        self.assertEqual((status["held_tokens"], status["held_requests"]), (0, 0))
        self.assertEqual(status["requests"], 7)
        # Settled to the engine's reported usage: nothing of the reservation remains charged.
        self.assertEqual(status["tokens"], 7 * 1100)
        self.assertEqual((budget["tokens_input"], budget["tokens_output"]), (7000, 700))

    def test_exactly_enough_budget_completes_and_one_token_less_is_refused_before_any_call(self):
        rows = universe(160, strong={159: 90.0})
        need = self.required(rows)
        exact = self.budgeted(rows, max_tokens=need["tokens"], max_requests=need["requests"])
        exact.run()
        self.assertEqual(exact.block["status"], "GLOBAL_SELECTION_COMPLETE")

        short = self.budgeted(rows, max_tokens=need["tokens"] - 1, max_requests=need["requests"])
        short.run()
        reconciled(self, short.block, 160)
        self.assertEqual(short.block["status"], "AI_COVERAGE_BUDGET_INSUFFICIENT")
        self.assertEqual(short.block["reason"], "SYNTHESIS_DAILY_TOKEN_LIMIT")
        self.assertEqual(short.inner.calls, 0)
        budget = short.block["budget"]
        self.assertEqual((budget["required_tokens"], budget["available_tokens"]), (need["tokens"], need["tokens"] - 1))
        self.assertEqual(short.block["eligible_count"], 160)
        self.assertEqual(short.block["batches_planned"], 4)
        self.assertEqual(short.block["batches_completed"], 0)
        self.assertEqual(short.block["counts"]["unprocessed"], 160)
        self.assertEqual(short.block["counts"]["reasons"]["UNPROCESSED:BUDGET_INSUFFICIENT"], 160)
        self.assertEqual(short.result["state"], "INCOMPLETE")
        self.assertEqual(short.budget.status()["tokens"], 0)

        requests = self.budgeted(rows, max_tokens=need["tokens"], max_requests=need["requests"] - 1)
        requests.run()
        self.assertEqual(requests.block["reason"], "SYNTHESIS_DAILY_REQUEST_LIMIT")
        self.assertEqual(requests.inner.calls, 0)

    def test_budget_already_spent_by_other_ai_work_counts_against_the_run(self):
        rows = universe(160)
        need = self.required(rows)
        h = self.budgeted(rows, max_tokens=need["tokens"] + 5000)
        self.assertIsNone(h.budget.reserve(6000))          # another AI operation's call, still in flight
        h.run()
        self.assertEqual(h.block["status"], "AI_COVERAGE_BUDGET_INSUFFICIENT")
        self.assertEqual(h.block["budget"]["available_tokens"], need["tokens"] - 1000)
        self.assertEqual(h.inner.calls, 0)
        self.assertEqual(h.budget.status()["tokens"], 6000)   # never reset, never released by this run

    def test_other_ai_work_cannot_spend_what_a_run_in_progress_has_held(self):
        rows = universe(160)
        need = self.required(rows)
        seen = []

        class Watching(RankingProvider):
            def on_call(inner, call, packet):
                if call == 1:
                    seen.append((h.budget.reserve(need["tokens"] // 2), h.budget.status()))
                return inner.respond(packet)

        h = self.budgeted(rows, max_tokens=need["tokens"] + 100, inner=Watching())
        h.run()
        refusal, during = seen[0]
        self.assertEqual(refusal, "SYNTHESIS_DAILY_TOKEN_LIMIT")
        self.assertGreater(during["held_tokens"], 0)
        self.assertGreaterEqual(during["tokens"], during["held_tokens"])
        self.assertLessEqual(during["tokens"], h.budget.max_tokens)
        self.assertEqual(h.block["status"], "COMPLETE_NO_SELECTION")

    def test_a_run_that_outgrows_its_hold_ends_partial_and_never_exceeds_the_daily_limit(self):
        rows = universe(160, strong={159: 90.0})
        need = self.required(rows)

        class Growing(RankingProvider):
            # After the plan is held, every later row grows: each later request is larger than the one planned.
            def on_call(inner, call, packet):
                if call == 1:
                    for item in rows:
                        item["company"] = "X" * 120
                return inner.respond(packet)

        h = self.budgeted(rows, max_tokens=need["tokens"], inner=Growing())
        h.run()
        reconciled(self, h.block, 160)
        self.assertEqual(h.block["status"], "PROVISIONAL_PARTIAL_COVERAGE")
        self.assertIn("SYNTHESIS_RUN_HOLD_EXHAUSTED", h.block["reason"] + " " + " ".join(h.block["counts"]["reasons"]))
        self.assertFalse(h.block["selection_complete"])
        self.assertIsNone(h.budget.held(h.run_id))
        self.assertLessEqual(h.budget.status()["tokens"], h.budget.max_tokens)
        self.assertIsNone(action_repository().get("candidate_run", "CU-" + h.run_id))

    def test_a_hold_nobody_draws_from_lapses_instead_of_locking_the_shared_budget_all_day(self):
        from market_platform_foundation.intelligence.inference.anthropic_synthesis import HOLD_IDLE_SECONDS

        ticks = [NOW]
        budget = DailyBudget(None, max_requests=30, max_tokens=10_000, clock=lambda: ticks[0])
        self.assertTrue(budget.hold("gone", requests=5, tokens=8000)["held"])
        self.assertEqual(budget.reserve(3000), "SYNTHESIS_DAILY_TOKEN_LIMIT")
        ticks[0] += HOLD_IDLE_SECONDS - 1
        self.assertIsNone(budget.reserve(1000, hold="gone"))          # a live run's draw keeps its hold alive
        ticks[0] += HOLD_IDLE_SECONDS - 1
        self.assertEqual(budget.held("gone"), {"requests": 4, "tokens": 7000})
        ticks[0] += 2
        # Idle past the limit: the hold is gone, what it reserved stays charged, and the rest is open again.
        self.assertIsNone(budget.held("gone"))
        self.assertEqual(budget.reserve(500, hold="gone"), "SYNTHESIS_RUN_HOLD_MISSING")
        status = budget.status()
        self.assertEqual((status["tokens"], status["held_tokens"], status["requests"]), (1000, 0, 1))
        self.assertIsNone(budget.reserve(3000))

    def test_the_provider_count_raises_an_underestimated_plan_and_a_rejected_request_spends_nothing(self):
        rows = universe(160)

        class Counted(RankingProvider):
            def __init__(inner, check):
                super().__init__()
                inner.check = check

            def preflight(inner, packet, *, rendered_prompt, config):
                return inner.check(len(rendered_prompt))

        base = self.required(rows)
        under = self.budgeted(rows, max_tokens=10 ** 12, inner=Counted(lambda size: {
            "accepted": True, "input_tokens": size * 2, "context_window": 10 ** 9, "context_fit": True, "reason": None}))
        under.run()
        count = under.block["plan"]["provider_count"]
        self.assertGreater(count["plan_scaled_by"], 1.0)
        self.assertGreater(under.block["plan"]["required"]["tokens"], base["tokens"])
        self.assertGreater(count["input_tokens"], count["estimated_input_tokens"])

        over = self.budgeted(rows, max_tokens=10 ** 12, inner=Counted(lambda size: {
            "accepted": True, "input_tokens": 10, "context_window": 10 ** 9, "context_fit": True, "reason": None}))
        over.run()
        # A lower provider count never shrinks the reservation: the conservative estimate stands.
        self.assertEqual(over.block["plan"]["required"]["tokens"], base["tokens"])

        rejected = self.budgeted(rows, max_tokens=10 ** 12, inner=Counted(lambda size: {
            "accepted": False, "input_tokens": None, "context_window": None, "context_fit": None, "reason": "ANTHROPIC_SCHEMA_REJECTED"}))
        rejected.run()
        self.assertEqual((rejected.block["status"], rejected.block["reason"]), ("FAILED", "ANTHROPIC_SCHEMA_REJECTED"))
        self.assertEqual(rejected.inner.calls, 0)
        self.assertEqual(rejected.budget.status()["tokens"], 0)
        reconciled(self, rejected.block, 160)

        unreachable = self.budgeted(rows, max_tokens=10 ** 12, inner=Counted(lambda size: {
            "accepted": False, "input_tokens": None, "context_window": None, "context_fit": None, "reason": "ANTHROPIC_UNREACHABLE"}))
        unreachable.run()
        self.assertEqual(unreachable.block["status"], "COMPLETE_NO_SELECTION")


class RecoveryTests(unittest.TestCase):
    def test_a_run_killed_mid_call_is_closed_as_interrupted_and_only_its_unused_hold_is_released(self):
        ledger = CoverageLedger()
        ledger.append("dead-run", "run", {"account_id": "PAPER-1", "method_version": METHOD_VERSION})
        ledger.append("dead-run", "batch_started", {"call_id": "BATCH_INFERENCE:0:0", "instrument_ids": ["EQ:A"], "planned_tokens": 900})
        ledger.append("dead-run", "batch", {"call_id": "BATCH_INFERENCE:0:0", "outcome": "COMPLETED"})
        ledger.append("dead-run", "batch_started", {"call_id": "BATCH_INFERENCE:0:1", "instrument_ids": ["EQ:B"], "planned_tokens": 950})
        ledger.append("live-run", "run", {"account_id": "PAPER-1", "method_version": METHOD_VERSION})
        budget = DailyBudget(None, max_requests=30, max_tokens=10_000, clock=lambda: NOW)
        self.assertTrue(budget.hold("dead-run", requests=4, tokens=4000)["held"])
        self.assertIsNone(budget.reserve(900, hold="dead-run"))
        budget.settle(900, 700, 50)
        self.assertIsNone(budget.reserve(950, hold="dead-run"))      # the call the restart interrupted

        closed = interrupt_open_runs(ledger, tracked={"live-run"}, release=budget.release, clock=lambda: NOW)

        self.assertEqual(closed, ["dead-run"])
        terminal = ledger.terminal("dead-run")
        self.assertEqual((terminal["status"], terminal["reason"]), ("INTERRUPTED", "SERVER_RESTARTED_DURING_RUN"))
        self.assertEqual([item["call_id"] for item in terminal["unknown_provider_outcomes"]], ["BATCH_INFERENCE:0:1"])
        self.assertEqual(terminal["calls_completed"], 1)
        self.assertEqual(terminal["hold_released"], {"requests": 2, "tokens": 2150})
        self.assertFalse(terminal["universe_coverage"]["coverage_complete"])
        # Usage already billed and the interrupted call's reservation both stay charged; nothing is reset.
        status = budget.status()
        self.assertEqual((status["tokens"], status["requests"], status["held_tokens"]), (750 + 950, 2, 0))
        self.assertEqual(ledger.open_runs(), ["live-run"])
        self.assertEqual(interrupt_open_runs(ledger, tracked={"live-run"}, release=budget.release), [])
        with self.assertRaisesRegex(ValueError, "COVERAGE_RUN_ALREADY_TERMINAL"):
            ledger.append("dead-run", "batch", {"call_id": "late"})

    def test_ledger_records_are_append_only(self):
        ledger = CoverageLedger()
        ledger.append("r", "run", {"account_id": "PAPER-1"})
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_COVERAGE_RECORD_COLLISION"):
            ledger.append("r", "run", {"account_id": "PAPER-2"})
        with self.assertRaisesRegex(ValueError, "COVERAGE_RECORD_KIND_INVALID"):
            ledger.append("r", "anything", {})
        ledger.append("r", "terminal", {"account_id": "PAPER-1", "status": "STOPPED"})
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_COVERAGE_RECORD_COLLISION"):
            ledger.append("r", "terminal", {"account_id": "PAPER-1", "status": "FAILED"})
        self.assertEqual(ledger.latest_terminal("PAPER-1")["status"], "STOPPED")
        self.assertIsNone(ledger.latest_terminal("PAPER-9"))


class NewsEvidenceTests(unittest.TestCase):
    """Real S11 news projection (controlled receipts): one symbol with stories, the rest of the universe with none."""

    def harness(self, rows):
        from tests.platform.test_screener_s11 import NOW as NEWS_NOW, service

        provider = RankingProvider()
        h = Harness(rows, provider, clock=lambda: NEWS_NOW)
        h.service = ScreenerAiService(reader=h.reader, news=service(provider=provider), clock=lambda: NEWS_NOW)
        return h

    def rows(self, size=130):
        as_of = "2026-09-28T14:00:00Z"
        rows = [row(index, as_of=as_of) for index in range(size)]
        for position, (symbol, company, rsi) in {7: ("AAPL", "Apple Inc.", 91.0), 128: ("MSFT", "Microsoft Corp", 88.0)}.items():
            rows[position] = row(position, rsi=rsi, as_of=as_of)
            rows[position]["instrument"].update(instrument_id="EQ:" + symbol, symbol=symbol)
            rows[position].update(symbol=symbol, company=company)
        return rows

    def test_a_symbol_with_news_keeps_it_and_a_symbol_without_is_neither_favoured_nor_dropped(self):
        h = self.harness(self.rows())
        h.run()
        reconciled(self, h.block, 130)
        self.assertEqual(h.block["status"], "GLOBAL_SELECTION_COMPLETE")
        self.assertEqual(h.block["ai_evaluated_count"], 130)
        self.assertEqual(h.selected(), ["EQ:AAPL", "EQ:MSFT"])
        by_id = {item["instrument"]["instrument_id"]: item for item in h.result["evidence"]}
        apple = by_id["EQ:AAPL"]
        # Admitted news is in the final comparison's evidence with its own publication clock, not displaced by metadata.
        stories = [item for item in apple["reference_evidence"] if item["capability"] == "NEWS"]
        self.assertEqual(len(stories), 1)
        self.assertEqual(stories[0]["facts"]["source_count"], 2)
        self.assertLessEqual(stories[0]["as_of"], h.result["decision_cutoff"])
        self.assertEqual(apple["news"]["story_count"], 1)
        self.assertEqual(h.block["plan"]["reference_evidence_thinned"], 0)
        # Batch membership is the same universe order whether or not any news exists: verbosity moves no row.
        plain = Harness(self.rows(), clock=lambda: 1790604000.0)
        plain.run()
        first = lambda harness: [frozenset(call["instrument_ids"]) for call in harness.calls() if call["stage"] == "BATCH_INFERENCE"]
        self.assertEqual(first(h), first(plain))
        self.assertEqual(plain.selected(), ["EQ:AAPL", "EQ:MSFT"])

    def test_a_story_published_after_the_cutoff_never_enters_the_decision(self):
        from tests.platform.test_screener_s11 import FINVIZ, NOW as NEWS_NOW, finviz_row, service

        late = {**FINVIZ, "items": [*FINVIZ["items"], finviz_row("Apple guidance raised after the bell", ["AAPL"], "2026-09-28 10:30:00", "https://r.test/apple-late")]}
        provider = RankingProvider()
        h = Harness(self.rows(), provider, clock=lambda: NEWS_NOW)
        h.service = ScreenerAiService(reader=h.reader, news=service(provider=provider, finviz=late), clock=lambda: NEWS_NOW)
        h.run()
        apple = next(item for item in h.result["evidence"] if item["instrument"]["instrument_id"] == "EQ:AAPL")
        headlines = [item["facts"]["headline"] for item in apple["reference_evidence"] if item["capability"] == "NEWS"]
        # 10:30 ET is half an hour after this run's 14:00Z cutoff.
        self.assertEqual(headlines, ["Apple unveils M5 MacBook lineup"])
        for item in (*apple["current_market_evidence"], *apple["reference_evidence"]):
            self.assertLessEqual(item["as_of"], h.result["decision_cutoff"])


class ActionBoundaryTests(unittest.TestCase):
    def test_only_a_completed_global_selection_is_stored_as_a_candidate_run(self):
        h = Harness(universe(260, strong={3: 88.0, 259: 96.0}))
        h.run()
        stored = action_repository().get("candidate_run", h.result["run_id"])
        self.assertEqual(h.result["run_id"], "CU-" + h.run_id)
        self.assertEqual(stored["state"], "CURRENT")
        self.assertEqual([pick["instrument_id"] for pick in stored["candidates"]], [instrument_id(259), instrument_id(3)])
        self.assertTrue(stored["universe_coverage"]["coverage_complete"] and stored["universe_coverage"]["selection_complete"])
        self.assertEqual(stored["universe_coverage"]["method_version"], METHOD_VERSION)
        # The Action Decision layer loads a pick together with its evidence: both come from the final comparison.
        self.assertEqual({item["instrument"]["instrument_id"] for item in stored["evidence"]}, {instrument_id(259), instrument_id(3)})
        self.assertNotIn("origin", stored)
        # Batch answers were made and recorded, and none of them is loadable as a candidate run.
        for call in h.calls():
            self.assertIsNone(action_repository().get("candidate_run", call["reduction_run_id"]))
        self.assertEqual(sum(call["stage"] == "BATCH_INFERENCE" for call in h.calls()), 6)

    def test_the_single_request_method_still_reads_only_the_head_and_claims_no_coverage(self):
        h = Harness(universe(200, strong={150: 95.0}))
        legacy = h.service.run(SCOPE)
        self.assertEqual(legacy["intake_count"], MAX_INTAKE)
        self.assertEqual(legacy["matched_count"], 200)
        self.assertNotIn("universe_coverage", legacy)
        self.assertEqual(legacy["candidates"], [])


if __name__ == "__main__":
    unittest.main()
