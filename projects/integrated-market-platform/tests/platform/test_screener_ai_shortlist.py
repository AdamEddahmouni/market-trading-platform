"""Opportunity shortlist in the AI Screener run: every eligible row scored, only the model-sized head sent, best
first, the rest accounted as NOT_SHORTLISTED, and the method recorded so runs are never pooled. Controlled engine."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.inference import opportunity_shortlist  # noqa: E402
from market_platform_foundation.intelligence.inference.coverage_plan import METHOD_VERSION as FULL_METHOD_VERSION  # noqa: E402
from market_platform_foundation.local_state.ai_screener_coverage import CoverageLedger  # noqa: E402
from market_platform_foundation.ui_api.screener_ai import ScreenerAiService  # noqa: E402
from market_platform_foundation.ui_api.screener_ai_coverage import ScreenerAiCoverage  # noqa: E402
from tests.support.coverage_universe import NOW, SCOPE, News, PagingReader, RankingProvider, instrument_id, row  # noqa: E402

SHA = "b" * 40
_SEQUENCE = [0]
# Liquid enough to clear the tradability floor at the fixture price of $100.
LIQUID = {"volume": 500_000.0}


def run_id() -> str:
    _SEQUENCE[0] += 1
    return f"sho{_SEQUENCE[0]:029d}"


class Local(RankingProvider):
    """The controlled engine as the local runtime: one row per request."""

    runtime = "LOCAL_MODEL"


class Harness:
    def __init__(self, rows, provider=None, *, shortlist=None, news=News) -> None:
        self.provider = provider if provider is not None else RankingProvider()
        self.service = ScreenerAiService(reader=PagingReader(rows), news=news(self.provider), clock=lambda: NOW)
        self.ledger = CoverageLedger()
        self.run_id = run_id()
        self.shortlist = shortlist

    def run(self, *, slice_plan=None, order_bounds=None):
        self.result = ScreenerAiCoverage(self.service, ledger=self.ledger, software_sha=SHA, shortlist=self.shortlist).run(
            SCOPE, run_id=self.run_id, account_id="PAPER-1", slice_plan=slice_plan, order_bounds=order_bounds)
        self.block = self.result["universe_coverage"]
        return self.result

    def sent(self) -> list[str]:
        return [key for record in self.ledger.records(self.run_id, "batch") if record["stage"] == "BATCH_INFERENCE"
                for key in record["instrument_ids"]]


def market(size, *, movers=None, strong=None, extra=None):
    """``size`` liquid rows moving 1%; ``movers`` maps a position to its move, ``strong`` to its controlled strength."""
    movers, strong = movers or {}, strong or {}
    return [row(index, rsi=strong.get(index, 50.0), change=movers.get(index, 1.0), extra={**LIQUID, **(extra or {}).get(index, {})})
            for index in range(size)]


def reconciled(test, block, size):
    counts = block["counts"]
    test.assertTrue(block["reconciled"])
    test.assertEqual(counts["evaluated"] + counts["ineligible"] + counts["evidence_blocked"] + counts["unprocessed"], size)


class PaidShortlistTests(unittest.TestCase):
    def test_only_the_top_fifty_are_sent_in_one_request_and_the_rest_are_accounted(self):
        h = Harness(market(200, movers={150: 9.0}, strong={150: 95.0}))
        h.run()
        self.assertEqual(h.provider.calls, 1)
        self.assertEqual(len(h.sent()), opportunity_shortlist.PAID_SIZE)
        self.assertEqual(h.sent()[0], instrument_id(150))
        self.assertEqual([pick["instrument_id"] for pick in h.result["candidates"]], [instrument_id(150)])
        self.assertEqual(h.block["status"], "GLOBAL_SELECTION_COMPLETE")
        self.assertEqual(h.block["counts"]["by_class"]["NOT_SHORTLISTED"], 150)
        self.assertEqual(h.block["counts"]["reasons"]["NOT_SHORTLISTED:BELOW_SHORTLIST_CUTOFF"], 150)
        reconciled(self, h.block, 200)

    def test_the_request_is_ordered_best_first(self):
        h = Harness(market(80, movers={70: 9.0, 10: 6.0, 40: 3.0}))
        h.run()
        self.assertEqual(h.sent()[:3], [instrument_id(70), instrument_id(10), instrument_id(40)])
        ranked = h.block["plan"]["shortlist"]["ranked"]
        self.assertEqual([item["instrument_id"] for item in ranked[:3]], h.sent()[:3])
        self.assertEqual([item["rank"] for item in ranked[:3]], [1, 2, 3])
        self.assertEqual(h.block["plan"]["order"], "opportunity_score_desc_then_sha256(result_set|instrument_id)")

    def test_the_method_and_policy_are_recorded_so_runs_are_never_pooled(self):
        h = Harness(market(60))
        h.run()
        head = h.ledger.records(h.run_id, "run")[0]
        self.assertEqual((head["method_version"], head["method_name"]),
                         (opportunity_shortlist.METHOD_VERSION, opportunity_shortlist.METHOD_NAME))
        self.assertEqual(head["shortlist"], {"policy_id": opportunity_shortlist.POLICY_ID, "size": 50})
        self.assertEqual(h.block["method_version"], opportunity_shortlist.METHOD_VERSION)
        self.assertEqual({key: h.block["shortlist"][key] for key in ("policy_id", "size", "eligible_before_shortlist", "shortlisted")},
                         {"policy_id": opportunity_shortlist.POLICY_ID, "size": 50, "eligible_before_shortlist": 60, "shortlisted": 50})
        self.assertNotIn("ranked", h.block["shortlist"])
        plan = h.ledger.records(h.run_id, "plan")[0]["plan"]
        self.assertEqual(len(plan["shortlist"]["ranked"]), 50)

    def test_rows_under_the_tradability_floor_are_never_sent(self):
        thin = {index: {"volume": 1_000.0} for index in range(5)}
        h = Harness(market(30, movers={index: 20.0 for index in range(5)}, extra=thin))
        h.run()
        self.assertEqual(len(h.sent()), 25)
        self.assertTrue(set(h.sent()).isdisjoint(instrument_id(index) for index in range(5)))
        self.assertEqual(h.block["counts"]["reasons"]["NOT_SHORTLISTED:BELOW_TRADABILITY_FLOOR"], 5)
        self.assertEqual(h.block["shortlist"]["below_tradability_floor"], 5)

    def test_nothing_above_the_floor_calls_no_model(self):
        h = Harness(market(4, extra={index: {"volume": 10.0} for index in range(4)}))
        h.run()
        self.assertEqual(h.provider.calls, 0)
        self.assertEqual((h.block["status"], h.block["reason"]), ("NO_ELIGIBLE_ROWS", "NO_ROW_ABOVE_TRADABILITY_FLOOR"))
        reconciled(self, h.block, 4)

    def test_news_is_read_from_the_cache_only_and_only_where_it_could_change_the_shortlist(self):
        asked = []

        class CachedNews(News):
            def candidate_evidence(self, *, universe, rows, refresh):
                asked.append((refresh, [r["instrument"]["instrument_id"] for r in rows]))
                return {}

        h = Harness(market(300, movers={index: 10.0 for index in range(5)}), news=CachedNews)
        h.run()
        shortlist_reads = [ids for refresh, ids in asked if refresh is False]
        self.assertTrue(shortlist_reads)
        read = [key for ids in shortlist_reads for key in ids]
        self.assertLessEqual(len(read), opportunity_shortlist.PAID_SIZE * opportunity_shortlist.NEWS_READ_FACTOR)
        self.assertEqual(h.block["shortlist"]["news_read"], len(read))
        self.assertTrue(all(len(ids) <= 50 for ids in shortlist_reads))

    def test_switched_off_every_eligible_row_is_sent_as_before(self):
        h = Harness(market(120), shortlist=False)
        h.run()
        self.assertEqual(len(h.sent()), 120)
        self.assertEqual(h.block["method_version"], FULL_METHOD_VERSION)
        self.assertIsNone(h.block["shortlist"])
        with mock.patch.dict(os.environ, {"IMP_AI_SCREENER_SHORTLIST": "0"}):
            self.assertFalse(ScreenerAiCoverage(h.service).shortlist)


# The automation's live caps on 2026-10-28: $5,000 a position, 100 units an order.
ORDER_BOUNDS = {"risk": {"max_position_notional_minor": 500_000, "max_per_trade_risk_minor": 50_000, "assumed_adverse_move_bps": 200,
                         "max_aggregate_exposure_minor": 7_500_000},
                "paper_account": {"max_order_shares": 100, "max_position_shares": 500, "price_scale": 100}}


def pair(item, *, minimum):
    """A fixture row as a Kraken spot pair carrying the venue's order rules, as the crypto Screener row does."""
    item["instrument"]["instrument_kind"] = "CRYPTO_PAIR"
    item.update(min_order_size=minimum, min_order_notional="0.5", base_increment="0.00000001", price_decimals=2)
    return item


class OrderFloorTests(unittest.TestCase):
    def market(self):
        rows = market(10, movers={0: 9.0, 1: 5.0})
        rows[0], rows[1], rows[2] = pair(rows[0], minimum="150"), pair(rows[1], minimum="40"), pair(rows[2], minimum="0.0001")
        rows[3] = pair(row(3, price=8_000.0, extra=LIQUID), minimum="0.0001")
        return rows

    def test_a_pair_no_entry_could_size_is_ineligible_and_never_sent(self):
        h = Harness(self.market(), Local())
        h.run(order_bounds=ORDER_BOUNDS)
        # Row 0 moves most but its venue minimum (150) is above the $5,000 position (50 units at $100).
        self.assertNotIn(instrument_id(0), h.sent())
        self.assertNotIn(instrument_id(3), h.sent())  # 0.625 units: below one whole unit
        self.assertEqual(h.sent()[0], instrument_id(1))
        self.assertIn(instrument_id(2), h.sent())
        reasons = h.block["counts"]["reasons"]
        self.assertEqual(reasons["INELIGIBLE:BELOW_ORDER_MINIMUM"], 2)
        self.assertEqual(reasons["INELIGIBLE:MAX_POSITION_NOTIONAL"], 2)
        self.assertEqual(h.block["shortlist"]["eligible_before_shortlist"], 8)
        head = h.ledger.records(h.run_id, "run")[0]
        self.assertEqual(head["order_floor"]["paper_account"]["max_order_shares"], 100)
        reconciled(self, h.block, 10)

    def test_an_operator_run_without_caps_sends_every_pair_as_before(self):
        h = Harness(self.market(), Local())
        h.run()
        self.assertEqual(h.sent()[0], instrument_id(0))
        self.assertNotIn("order_floor", h.ledger.records(h.run_id, "run")[0])

    def test_no_sizeable_row_calls_no_model(self):
        rows = [pair(item, minimum="1000") for item in market(3)]
        h = Harness(rows, Local())
        h.run(order_bounds=ORDER_BOUNDS)
        self.assertEqual(h.provider.calls, 0)
        self.assertEqual((h.block["status"], h.block["reason"]), ("NO_ELIGIBLE_ROWS", "NO_ROW_SIZEABLE_UNDER_ORDER_CAPS"))
        reconciled(self, h.block, 3)


class LocalShortlistTests(unittest.TestCase):
    def test_the_october_23_universe_is_twenty_requests_and_one_comparison(self):
        # 2,524 eligible rows overflowed the local window on 2026-10-23 (171 finalists). Now twenty rows are sent.
        movers = {index: 2.0 + index / 1000 for index in range(0, 2524, 97)}
        strong = {2522: 95.0, 2425: 92.0, 2328: 90.0, 0: 99.0}  # row 0 moves least of the movers: never sent
        h = Harness(market(2524, movers=movers, strong=strong), Local())
        h.run()
        self.assertEqual(len(h.sent()), opportunity_shortlist.LOCAL_SIZE)
        self.assertEqual(h.sent()[0], instrument_id(2522))
        self.assertEqual(h.block["reduction"]["rounds_completed"], 1)
        self.assertIsNone(h.block["reduction"]["smallest_refused_group"])
        self.assertEqual(h.block["status"], "GLOBAL_SELECTION_COMPLETE")
        self.assertEqual([pick["instrument_id"] for pick in h.result["candidates"]],
                         [instrument_id(2522), instrument_id(2425), instrument_id(2328)])
        self.assertEqual(h.block["counts"]["by_class"]["NOT_SHORTLISTED"], 2524 - 20)
        reconciled(self, h.block, 2524)

    def test_the_size_override_applies_and_an_invalid_one_refuses_the_run(self):
        with mock.patch.dict(os.environ, {"IMP_AI_SCREENER_SHORTLIST_SIZE": "5"}):
            h = Harness(market(40), Local())
            h.run()
        self.assertEqual(len(h.sent()), 5)
        with mock.patch.dict(os.environ, {"IMP_AI_SCREENER_SHORTLIST_SIZE": "500"}):
            bad = Harness(market(40), Local())
            with self.assertRaisesRegex(ValueError, "SHORTLIST_SIZE_INVALID"):
                bad.run()
        self.assertEqual(bad.ledger.records(bad.run_id, "run"), [])

    def test_a_slice_takes_rows_without_a_recent_turn_first_then_the_score_order(self):
        movers = {index: 10.0 - index for index in range(6)}
        h = Harness(market(30, movers=movers), Local())
        last = {instrument_id(0): NOW - 100, instrument_id(1): NOW - 900}
        h.run(slice_plan={"deadline_epoch": NOW + 10_000, "epoch": 1, "last_evaluated": last})
        # Rows 0 and 1 score highest but had recent turns: they go last, the older turn first.
        self.assertEqual(h.sent()[:4], [instrument_id(2), instrument_id(3), instrument_id(4), instrument_id(5)])
        self.assertEqual(h.sent()[-2:], [instrument_id(1), instrument_id(0)])
        self.assertEqual(h.block["plan"]["slice"]["order"], "NO_RECENT_TURN_FIRST_THEN_OLDEST_TURN_THEN_OPPORTUNITY_SCORE")


if __name__ == "__main__":
    unittest.main()
