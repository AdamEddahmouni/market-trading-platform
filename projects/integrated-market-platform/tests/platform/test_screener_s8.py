"""S8 Screener Short Squeeze: donor-adapted snapshot evaluator, publication sources, service truth, scope."""

from __future__ import annotations

import ast
import json
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tools" / "moomoo"))

import test_screener_s4 as s4  # noqa: E402  (real S4 runtime and projections)

from market_platform_foundation.platform.security.leak_audit import assert_no_secrets_in_payload  # noqa: E402
from market_platform_foundation.platform.security.route_policy import policy_for_route  # noqa: E402
from market_platform_foundation.short_intelligence.squeeze_state import (  # noqa: E402
    LIFECYCLE, THRESHOLDS, UNREACHABLE, OrderFlowInput, SqueezeInputs, SqueezeState, evaluate_snapshot,
)
from market_platform_foundation.ui_api.screener_config import validate_panel_layout, validate_screen  # noqa: E402
from market_platform_foundation.ui_api.screener_filters import builtin_presets, filter_catalog  # noqa: E402
from market_platform_foundation.ui_api.screener_query import field_capabilities, parse_query  # noqa: E402
from market_platform_foundation.ui_api.screener_specialist import PANEL_CAPABILITIES, TRADES  # noqa: E402
from market_platform_foundation.ui_api.screener_squeeze import SCHEMA_VERSION, ScreenerSqueezeService  # noqa: E402
from market_platform_foundation.ui_api.screener_squeeze_sources import (  # noqa: E402
    BackgroundCache, FinraShortData, SecFailsToDeliver, ThresholdAuthoritySource, ThresholdList, ThresholdLists,
)
from market_platform_foundation.ui_api.screener_universes import (  # noqa: E402
    FUTURES, US_EQUITIES, US_ETFS, canonical_view, universe_payload, universe_spec,
)

SRC = ROOT / "src" / "market_platform_foundation"
#: Sunday 2026-09-27 16:00 UTC (market closed).
NOW = datetime(2026, 9, 27, 16, 0, tzinfo=UTC).timestamp()
SNAPSHOT_AS_OF = "2026-09-27T15:58:00Z"


def codes(items) -> set[str]:
    return {item.code for item in items}


def flow(state="CURRENT", buy=9_000.0, sell=2_000.0, classified=90.0, recent=500.0, trades=300) -> OrderFlowInput:
    return OrderFlowInput(state=state, buy_volume=buy, sell_volume=sell, classified_volume_pct=classified,
                          recent_delta=recent, trade_count=trades)


# ----------------------------------------------------------------- evaluator
class DonorAdaptedStateTests(unittest.TestCase):
    """Ported from donor tests/intelligence/test_causal_evaluator.py where the semantics carry over."""

    def test_baseline_when_evaluable_and_nothing_is_met(self):
        result = evaluate_snapshot(SqueezeInputs(short_float_pct=3, short_ratio_days=1, float_shares=9e8,
                                                 change_pct=0.4, rel_volume=0.9))
        self.assertEqual(result.state, SqueezeState.BASELINE)
        self.assertFalse(result.supporting)

    def test_vulnerable_structure_without_constraint(self):
        result = evaluate_snapshot(SqueezeInputs(short_float_pct=28, short_ratio_days=1.2, float_shares=40e6,
                                                 change_pct=1, rel_volume=2))
        self.assertEqual(result.state, SqueezeState.VULNERABLE)
        self.assertIn("SI_ELEVATED", codes(result.supporting))

    def test_armed_needs_crowding_plus_days_to_cover_or_lending(self):
        armed = evaluate_snapshot(SqueezeInputs(short_float_pct=28, short_ratio_days=3.1, change_pct=1, rel_volume=2))
        self.assertEqual(armed.state, SqueezeState.ARMED)
        lender = evaluate_snapshot(SqueezeInputs(short_float_pct=28, borrow_fee_pct=40, change_pct=1, rel_volume=2))
        self.assertEqual(lender.state, SqueezeState.ARMED)
        self.assertIn("LENDER_SQUEEZE", lender.mechanism_labels)
        self.assertIn("LENDING_CONSTRAINT", codes(lender.supporting))

    def test_high_short_interest_without_ignition_is_not_active(self):
        # Donor: test_high_si_no_ignition_is_vulnerable_not_buy_signal.
        result = evaluate_snapshot(SqueezeInputs(short_float_pct=60, short_ratio_days=9, float_shares=5e6,
                                                 change_pct=0.2, rel_volume=0.7))
        self.assertIn(result.state, (SqueezeState.VULNERABLE, SqueezeState.ARMED))
        self.assertNotEqual(result.state, SqueezeState.ACTIVE_SQUEEZE)
        self.assertIn("NO_VOLUME_PARTICIPATION", codes(result.contradicting))

    def test_ignition_watch_with_and_without_structural_fuel(self):
        fueled = evaluate_snapshot(SqueezeInputs(short_float_pct=30, short_ratio_days=3, change_pct=14, rel_volume=6))
        self.assertEqual(fueled.state, SqueezeState.IGNITION_WATCH)
        self.assertIn("MARKET_SQUEEZE", fueled.mechanism_labels)
        # Donor: test_low_si_high_momentum_flags_non_squeeze_momentum.
        momentum = evaluate_snapshot(SqueezeInputs(short_float_pct=2, short_ratio_days=0.5, change_pct=25, rel_volume=9))
        self.assertEqual(momentum.state, SqueezeState.IGNITION_WATCH)
        self.assertIn("NON_SQUEEZE_MOMENTUM", momentum.mechanism_labels)
        self.assertIn("LOW_STRUCTURAL_FUEL", codes(momentum.contradicting))

    def test_single_field_spikes_do_not_create_states(self):
        rvol_only = evaluate_snapshot(SqueezeInputs(short_float_pct=4, short_ratio_days=1, change_pct=1, rel_volume=30))
        self.assertEqual(rvol_only.state, SqueezeState.BASELINE)
        lone_short_float = evaluate_snapshot(SqueezeInputs(short_float_pct=80))
        self.assertEqual(lone_short_float.state, SqueezeState.UNEVALUABLE)
        lone_with_ignition_inputs = evaluate_snapshot(SqueezeInputs(short_float_pct=80, change_pct=1, rel_volume=1))
        self.assertEqual(lone_with_ignition_inputs.state, SqueezeState.BASELINE)  # no corroborating structural input

    def test_live_confirmation_needs_ignition_and_current_buy_aggression(self):
        live = evaluate_snapshot(SqueezeInputs(short_float_pct=30, short_ratio_days=3, change_pct=18, rel_volume=7,
                                               order_flow=flow()))
        self.assertEqual(live.state, SqueezeState.LIVE_CONFIRMATION)
        self.assertTrue({"SHORT_CROWDING", "IGNITION", "ORDER_FLOW"} <= set(live.classes_supporting))
        # Donor: order-flow confirmation without ignition stays below confirmation.
        no_ignition = evaluate_snapshot(SqueezeInputs(short_float_pct=30, short_ratio_days=3, change_pct=2, rel_volume=2,
                                                      order_flow=flow()))
        self.assertEqual(no_ignition.state, SqueezeState.ARMED)
        closed = evaluate_snapshot(SqueezeInputs(short_float_pct=30, short_ratio_days=3, change_pct=18, rel_volume=7,
                                                 order_flow=flow(state="SESSION_CLOSED")))
        self.assertEqual(closed.state, SqueezeState.IGNITION_WATCH)
        self.assertIn("ORDER_FLOW_SESSION_CLOSED", closed.quality_flags)

    def test_active_squeeze_is_unreachable_without_dealer_positioning(self):
        maxed = evaluate_snapshot(SqueezeInputs(short_float_pct=90, short_ratio_days=12, float_shares=3e6,
                                                official_short_interest_available=True, official_days_to_cover=12,
                                                official_short_interest_change_pct=60, borrow_fee_pct=300,
                                                borrow_available_shares=0, change_pct=150, rel_volume=80,
                                                catalyst_present=True, order_flow=flow(buy=1e7, sell=1e5)))
        self.assertEqual(maxed.state, SqueezeState.LIVE_CONFIRMATION)
        self.assertIn(SqueezeState.ACTIVE_SQUEEZE, UNREACHABLE)
        lifecycle = {item["state"]: item for item in maxed.to_dict()["lifecycle"]}
        self.assertFalse(lifecycle["ACTIVE_SQUEEZE"]["reachable"])
        self.assertIn("dealer", lifecycle["ACTIVE_SQUEEZE"]["unreachable_reason"])
        self.assertEqual([item["state"] for item in maxed.to_dict()["lifecycle"]], [state.value for state in LIFECYCLE])

    def test_exhaustion_is_evidence_only_from_a_snapshot(self):
        result = evaluate_snapshot(SqueezeInputs(short_float_pct=30, short_ratio_days=3, change_pct=18, rel_volume=7,
                                                 order_flow=flow(recent=-800.0)))
        self.assertNotEqual(result.state, SqueezeState.EXHAUSTION)
        self.assertTrue({"EXHAUSTION_SIGNAL", "CVD_DIVERGENCE"} <= codes(result.contradicting))
        self.assertIn(SqueezeState.EXHAUSTION, UNREACHABLE)
        self.assertIn(SqueezeState.POST_SQUEEZE, UNREACHABLE)

    def test_provider_conflict_and_missing_everything_are_unevaluable(self):
        # Donor: test_provider_conflict_is_unevaluable.
        conflicted = evaluate_snapshot(SqueezeInputs(short_float_pct=30, short_ratio_days=3, change_pct=18, rel_volume=7,
                                                     provider_conflict=True))
        self.assertEqual(conflicted.state, SqueezeState.UNEVALUABLE)
        self.assertIn("CAPABILITY_CONFLICTED", conflicted.quality_flags)
        empty = evaluate_snapshot(SqueezeInputs())
        self.assertEqual(empty.state, SqueezeState.UNEVALUABLE)
        self.assertIn("CAPABILITY_UNAVAILABLE", empty.quality_flags)

    def test_missing_borrow_stays_missing_not_negative(self):
        result = evaluate_snapshot(SqueezeInputs(short_float_pct=30, short_ratio_days=1, float_shares=1e7, change_pct=1, rel_volume=2))
        self.assertIn("BORROW", result.missing)
        self.assertFalse([item for item in result.contradicting if item.evidence_class.value == "SECURITIES_LENDING"])
        self.assertNotIn("LENDER_SQUEEZE", result.mechanism_labels)

    def test_stale_short_interest_is_flagged(self):
        # Donor: test_stale_short_interest_adds_quality_flag.
        result = evaluate_snapshot(SqueezeInputs(short_float_pct=30, short_ratio_days=3, change_pct=1, rel_volume=2,
                                                 stale_inputs=("SHORT_FLOAT_PCT_STALE",)))
        self.assertIn("SHORT_FLOAT_PCT_STALE", result.quality_flags)

    def test_conflicting_evidence_is_explicit(self):
        selling = evaluate_snapshot(SqueezeInputs(short_float_pct=30, short_ratio_days=3, change_pct=18, rel_volume=7,
                                                  order_flow=flow(buy=1_000, sell=8_000, recent=-300.0)))
        self.assertEqual(selling.state, SqueezeState.IGNITION_WATCH)
        self.assertIn("CVD_AGGRESSIVE_SELL", codes(selling.contradicting))
        falling = evaluate_snapshot(SqueezeInputs(short_float_pct=30, float_shares=1e7, change_pct=1, rel_volume=2,
                                                  official_short_interest_available=True,
                                                  official_short_interest_change_pct=-25))
        self.assertIn("SI_FALLING", codes(falling.contradicting))

    def test_low_aggressor_coverage_is_not_asserted(self):
        result = evaluate_snapshot(SqueezeInputs(short_float_pct=30, short_ratio_days=3, change_pct=18, rel_volume=7,
                                                 order_flow=flow(classified=20.0)))
        self.assertEqual(result.state, SqueezeState.IGNITION_WATCH)
        self.assertIn("ORDER_FLOW_AGGRESSOR_COVERAGE_LOW", result.quality_flags)

    def test_finra_days_to_cover_is_preferred_and_attributed(self):
        result = evaluate_snapshot(SqueezeInputs(short_float_pct=30, short_ratio_days=0.5, official_days_to_cover=4.2,
                                                 official_short_interest_available=True, change_pct=1, rel_volume=2))
        rule = next(rule for rule in result.rules if rule.rule_id == "DAYS_TO_COVER_MINIMUM")
        self.assertEqual((rule.source, rule.observed, rule.outcome), ("FINRA", 4.2, "PASS"))
        self.assertEqual(result.state, SqueezeState.ARMED)

    def test_output_has_no_score_probability_or_transition(self):
        payload = evaluate_snapshot(SqueezeInputs(short_float_pct=30, short_ratio_days=3, change_pct=1, rel_volume=2)).to_dict()
        self.assertIsNone(payload["probability"])
        self.assertIsNone(payload["score"])
        self.assertIsNone(payload["transition"])
        self.assertEqual(payload["state_basis"], "SNAPSHOT_ASSESSMENT")
        self.assertEqual(payload["hysteresis"], "NOT_APPLIED_NO_STATE_HISTORY")
        text = json.dumps(payload).lower()
        for word in ("prime", "subprime", "buy signal", "target", "stop"):
            self.assertNotIn(word, text)

    def test_thresholds_are_the_donor_rules_and_imp_discovery(self):
        self.assertEqual(THRESHOLDS["DAYS_TO_COVER_MINIMUM"].value, 2.0)
        self.assertEqual(THRESHOLDS["RELATIVE_VOLUME_MINIMUM"].value, 5.0)
        self.assertEqual(THRESHOLDS["PERCENTAGE_CHANGE_MINIMUM"].value, 10.0)
        self.assertEqual(THRESHOLDS["SHORT_FLOAT_ELEVATED"].value, 20.0)
        preset = next(item for item in builtin_presets() if item["id"] == "SHORT_SQUEEZE_DISCOVERY")
        short_float = next(rule for rule in preset["filters"] if rule["field"] == "short_float_pct")
        self.assertEqual((short_float["operator"], short_float["value"]), ("gt", THRESHOLDS["SHORT_FLOAT_ELEVATED"].value))


# ------------------------------------------------------------------ sources
class Jobs:
    """Deferred background jobs: tests decide when a fetch completes."""

    def __init__(self):
        self.pending = []

    def spawn(self, job):
        self.pending.append(job)

    def run(self):
        jobs, self.pending = self.pending, []
        for job in jobs:
            job()


def listing(authority, symbols, day="2026-09-25"):
    return ThresholdList(authority, day, f"{day}T23:00:00Z", frozenset(symbols))


def lists_with(fetchers, *, env=None, clock=lambda: NOW):
    jobs = Jobs()
    authorities = tuple(ThresholdAuthoritySource(name, name.title(), f"FLAG_{name}", fetch) for name, fetch in fetchers.items())
    flags = env if env is not None else {f"FLAG_{name}": "1" for name in fetchers}
    source = ThresholdLists(authorities=authorities, cache=BackgroundCache(clock=clock, spawn=jobs.spawn), clock=clock,
                            env=flags.get)
    return source, jobs


def missing_before(day):
    def fetch(requested):
        if requested > day:
            raise OSError("NASDAQ_THRESHOLD_FILE_MISSING")
        return listing("X", {"GME"}, requested)
    return fetch


class ThresholdListTests(unittest.TestCase):
    def test_not_configured_without_flags(self):
        source, jobs = lists_with({"NASDAQ": lambda day: listing("NASDAQ", {"GME"})}, env={})
        status = source.status("GME")
        self.assertEqual((status["state"], status["member"]), ("NOT_CONFIGURED", None))
        self.assertFalse(jobs.pending)

    def test_pending_then_membership_with_trade_date(self):
        source, jobs = lists_with({"NASDAQ": lambda day: listing("NASDAQ", {"GME"}, day),
                                   "NYSE_GROUP": lambda day: listing("NYSE_GROUP", set(), day)})
        self.assertEqual(source.status("GME")["state"], "PENDING")
        jobs.run()
        status = source.status("gme")
        self.assertEqual((status["state"], status["member"], status["member_of"]), ("PUBLICATION_CURRENT", True, ["NASDAQ"]))
        self.assertEqual(status["trade_date"], "2026-09-25")  # Friday: latest weekday list on a Sunday

    def test_not_member_only_when_every_list_was_read(self):
        source, jobs = lists_with({"NASDAQ": lambda day: listing("NASDAQ", set(), day),
                                   "CBOE_BZX": lambda day: (_ for _ in ()).throw(OSError("SOURCE_UNAVAILABLE"))})
        source.status("AAPL")
        jobs.run()
        status = source.status("AAPL")
        self.assertEqual((status["state"], status["member"]), ("PARTIAL", None))  # unavailable is not "not on list"
        both, jobs = lists_with({"NASDAQ": lambda day: listing("NASDAQ", set(), day),
                                 "CBOE_BZX": lambda day: listing("CBOE_BZX", set(), day)})
        both.status("AAPL")
        jobs.run()
        self.assertEqual(both.status("AAPL")["member"], False)

    def test_walks_back_to_the_latest_published_list(self):
        source, jobs = lists_with({"NASDAQ": missing_before("2026-09-24")})
        source.status("GME")
        jobs.run()
        self.assertEqual(source.status("GME")["trade_date"], "2026-09-24")

    def test_every_source_failing_is_unavailable_and_old_lists_are_stale(self):
        source, jobs = lists_with({"NASDAQ": lambda day: (_ for _ in ()).throw(OSError("SOURCE_UNAVAILABLE"))})
        source.status("GME")
        jobs.run()
        self.assertEqual(source.status("GME")["state"], "PROVIDER_UNAVAILABLE")
        old, jobs = lists_with({"NASDAQ": lambda day: listing("NASDAQ", {"GME"}, "2026-09-10")})
        old.status("GME")
        jobs.run()
        self.assertEqual(old.status("GME")["state"], "STALE")

    def test_one_download_serves_every_symbol(self):
        calls = []
        source, jobs = lists_with({"NASDAQ": lambda day: calls.append(day) or listing("NASDAQ", {"GME"}, day)})
        for symbol in ("GME", "AMC", "AAPL"):
            source.status(symbol)
        jobs.run()
        for symbol in ("GME", "AMC", "AAPL"):
            source.status(symbol)
        self.assertEqual(len(calls), 1)


class FinraAndFtdTests(unittest.TestCase):
    def finra(self, fetch, *, env=None, creds=True):
        jobs = Jobs()
        source = FinraShortData(cache=BackgroundCache(clock=lambda: NOW, spawn=jobs.spawn), fetch=fetch,
                                env=(env if env is not None else {"IMP_FINRA_LIVE": "1"}).get, credentials_present=lambda: creds)
        return source, jobs

    def test_finra_configuration_states(self):
        self.assertEqual(self.finra(lambda s: {}, env={})[0].status("GME")["reason"], "IMP_FINRA_LIVE_NOT_SET")
        missing = self.finra(lambda s: {}, creds=False)[0].status("GME")
        self.assertEqual((missing["state"], missing["reason"]), ("NOT_CONFIGURED", "FINRA_CREDENTIALS_MISSING"))
        self.assertIsNone(missing["short_interest"])

    def test_finra_auth_failure_is_not_entitled_and_outage_is_unavailable(self):
        source, jobs = self.finra(lambda s: (_ for _ in ()).throw(RuntimeError("FINRA_HTTP_403 https://x?token=abc")))
        source.status("GME")
        jobs.run()
        status = source.status("GME")
        self.assertEqual((status["state"], status["reason"]), ("NOT_ENTITLED", "FINRA_HTTP_403"))
        self.assertNotIn("token", json.dumps(status))
        down, jobs = self.finra(lambda s: (_ for _ in ()).throw(OSError("timed out")))
        down.status("GME")
        jobs.run()
        self.assertEqual(down.status("GME")["state"], "PROVIDER_UNAVAILABLE")

    def test_finra_values_keep_interest_and_flow_separate(self):
        payload = {"short_interest": {"settlement_date": "2026-09-15", "publication_date": "2026-09-24", "current": 60_000_000,
                                      "previous": 50_000_000, "change": 10_000_000, "change_pct": 20.0, "days_to_cover": 3.5,
                                      "revision_flag": None},
                   "short_sale_volume": {"trade_report_date": "2026-09-25", "short_sale_volume": 4_000_000,
                                         "total_volume": 9_000_000, "short_sale_ratio": 0.44}}
        source, jobs = self.finra(lambda s: payload)
        source.status("GME")
        jobs.run()
        status = source.status("GME")
        self.assertEqual(status["state"], "PUBLICATION_CURRENT")
        self.assertEqual(status["short_interest"]["current"], 60_000_000)
        self.assertEqual(status["short_sale_volume"]["short_sale_volume"], 4_000_000)

    def test_failed_refresh_keeps_last_good_marked(self):
        clock = {"now": NOW}
        results = [{"short_interest": None, "short_sale_volume": None}]
        jobs = Jobs()

        def fetch(symbol):
            if not results:
                raise OSError("down")
            return results.pop()
        source = FinraShortData(cache=BackgroundCache(clock=lambda: clock["now"], spawn=jobs.spawn), fetch=fetch,
                                env={"IMP_FINRA_LIVE": "1"}.get, credentials_present=lambda: True)
        source.status("GME")
        jobs.run()
        clock["now"] += 7 * 3600
        source.status("GME")
        jobs.run()
        status = source.status("GME")
        self.assertEqual((status["state"], status["reason"]), ("STALE", "SOURCE_UNAVAILABLE"))

    def test_ftd_configuration_no_record_and_balance(self):
        self.assertEqual(SecFailsToDeliver(env={}.get).status("GME")["reason"], "IMP_SEC_FTD_LIVE_NOT_SET")
        self.assertEqual(SecFailsToDeliver(env={"IMP_SEC_FTD_LIVE": "1"}.get).status("GME")["reason"], "SEC_USER_AGENT_NOT_SET")
        jobs = Jobs()
        source = SecFailsToDeliver(cache=BackgroundCache(clock=lambda: NOW, spawn=jobs.spawn),
                                   fetch=lambda: {"period": "202609a", "period_label": "2026-09_first_half",
                                                  "period_end": "2026-09-15",
                                                  "by_symbol": {"GME": [("2026-09-11", 1200), ("2026-09-14", 3400)]}},
                                   env={"IMP_SEC_FTD_LIVE": "1", "SEC_USER_AGENT": "research contact"}.get)
        self.assertEqual(source.status("GME")["state"], "PENDING")
        jobs.run()
        gme = source.status("GME")
        self.assertEqual((gme["balance"], gme["settlement_date"], gme["settlement_days_with_fails"]), (3400, "2026-09-14", 2))
        aapl = source.status("AAPL")
        self.assertEqual((aapl["state"], aapl["balance"]), ("NO_RECORD", None))  # absence is not a zero balance

    def test_background_cache_runs_one_job_per_key(self):
        jobs = Jobs()
        cache = BackgroundCache(clock=lambda: NOW, spawn=jobs.spawn)
        for _ in range(4):
            self.assertIsNone(cache.get("k", lambda: 1, ttl_s=60))
        self.assertEqual((len(jobs.pending), cache.jobs_started), (1, 1))


# ------------------------------------------------------------------ service
def finviz_row(symbol="GME", **values):
    defaults = {"price": 24.1, "change_pct": 1.2, "volume": 3_400_000, "rel_volume": 0.9, "float_shares": 38e6,
                "shares_outstanding": 42e6, "short_float_pct": 24.8, "short_ratio": 3.7, "market_cap": 1e9}
    defaults.update(values)
    return {"instrument": {"instrument_id": symbol, "asset_class": "EQUITY"}, "symbol": symbol, "company": f"{symbol} Inc",
            "fields": {name: {"value": value, "source": "FINVIZ_ELITE", "state": "SNAPSHOT" if value is not None else "UNAVAILABLE",
                              "as_of": SNAPSHOT_AS_OF} for name, value in defaults.items()}}


class Calls:
    def __init__(self):
        self.options = 0
        self.news = 0


def service_for(rows, *, flow_service=None, options=None, news=None, threshold=None, finra=None, ftd=None, clock=lambda: NOW):
    calls = Calls()
    blocked = {"state": "CONNECTING", "reason": "NOT_SUBSCRIBED", "summary": None, "window": None, "imbalance": []}

    def options_getter(instrument):
        calls.options += 1
        return options

    def news_getter():
        calls.news += 1
        if isinstance(news, Exception):
            raise news
        return news if news is not None else {"success": True, "items": []}

    service = ScreenerSqueezeService(
        row_getter=lambda instrument: rows.get(instrument),
        quote_getter=lambda instrument: {"state": "UNAVAILABLE", "fields": {}},
        order_flow_getter=flow_service.order_flow if flow_service else (lambda i: dict(blocked)),
        cvd_getter=flow_service.cvd if flow_service else (lambda i: dict(blocked)),
        depth_getter=flow_service.depth if flow_service else (lambda i: dict(blocked)),
        options_getter=options_getter, news_getter=news_getter,
        threshold=threshold or ThresholdLists(env={}.get), finra=finra or FinraShortData(env={}.get),
        ftd=ftd or SecFailsToDeliver(env={}.get), clock=clock, session_label=lambda: "CLOSED")
    return service, calls


def section(payload, name):
    return {item["id"]: item for item in payload["sections"][name]}


class ServiceTests(unittest.TestCase):
    def test_universe_view_and_instrument_guards(self):
        service, _ = service_for({"GME": finviz_row()})
        for universe in (FUTURES, US_ETFS):
            with self.assertRaisesRegex(ValueError, "SQUEEZE_UNAVAILABLE_FOR_UNIVERSE"):
                service.read("GME", universe=universe)
        with self.assertRaisesRegex(ValueError, "INVALID_SQUEEZE_VIEW"):
            service.read("GME", view="chain")
        self.assertIsNone(service.read("NOPE"))

    def test_contract_shape_state_and_capability(self):
        payload = service_for({"GME": finviz_row()})[0].read("GME")
        self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
        self.assertEqual(payload["assessment"]["state"], "ARMED")  # 24.8% short float + 3.7 d short ratio
        self.assertEqual(payload["capability"]["SQUEEZE_PROBABILITY"], "NOT_SUPPORTED")
        self.assertEqual(payload["capability"]["TEMPORAL_LIFECYCLE"], "NOT_SUPPORTED")
        self.assertIsNone(payload["historical_context"])
        self.assertEqual(payload["source_state"], "PARTIAL")
        self.assertIn("NO_VOLUME_PARTICIPATION", {item["code"] for item in payload["evidence"]["conflicting"]})

    def test_source_semantics_are_never_conflated(self):
        payload = service_for({"GME": finviz_row()})[0].read("GME")
        structural = section(payload, "structural_pressure")
        self.assertEqual(structural["short_float_pct"]["source"], "FINVIZ_ELITE")
        self.assertIn("not a borrow measure", structural["short_float_pct"]["note"])
        self.assertIn("not short interest", structural["short_sale_volume"]["note"])
        self.assertNotEqual(structural["short_sale_volume"]["id"], structural["official_short_interest"]["id"])
        self.assertEqual(structural["threshold_status"]["unit"], "boolean")
        self.assertIn("not short interest", structural["threshold_status"]["note"])
        self.assertIn("not proof of naked shorting", structural["ftd_balance"]["note"])
        self.assertEqual(structural["borrow_fee"]["source"], "LENDING")
        self.assertEqual(structural["short_float_pct"]["clock"]["kind"], "SNAPSHOT")
        self.assertEqual(structural["official_short_interest"]["clock"]["kind"], "PUBLICATION")
        self.assertEqual(structural["threshold_status"]["clock"]["kind"], "DAILY_LIST")

    def test_unavailable_is_null_never_zero(self):
        payload = service_for({"GME": finviz_row(short_ratio=None)})[0].read("GME")
        structural = section(payload, "structural_pressure")
        for name in ("official_short_interest", "short_sale_volume", "borrow_fee", "borrow_available", "threshold_status", "ftd_balance"):
            self.assertIsNone(structural[name]["value"], name)
            self.assertEqual(structural[name]["quality"], "NOT_CONFIGURED", name)
        self.assertEqual((structural["short_ratio"]["value"], structural["short_ratio"]["quality"]), (None, "MISSING"))
        self.assertGreaterEqual(payload["coverage"]["unavailable"], 7)
        missing = {item["code"]: item["reason"] for item in payload["evidence"]["missing"]}
        self.assertEqual(missing["BORROW"], "NO_CURRENT_LENDING_SOURCE")
        self.assertEqual(missing["OFFICIAL_SHORT_INTEREST"], "IMP_FINRA_LIVE_NOT_SET")

    def test_outages_are_not_negative_evidence(self):
        payload = service_for({"GME": finviz_row(change_pct=15, rel_volume=6)}, news=OSError("down"))[0].read("GME")
        ignition = section(payload, "ignition")
        self.assertEqual((ignition["catalyst"]["value"], ignition["catalyst"]["quality"]), (None, "PROVIDER_UNAVAILABLE"))
        conflicting = {item["code"] for item in payload["evidence"]["conflicting"]}
        self.assertFalse(conflicting & {"CVD_AGGRESSIVE_SELL", "CVD_DIVERGENCE", "SI_FALLING"})
        self.assertEqual(payload["assessment"]["state"], "IGNITION_WATCH")

    def test_live_confirmation_from_real_s4_projections_without_new_subscription(self):
        clock = s4.Clock()
        runtime = s4.make_runtime(clock)
        specialist, session = s4.make_service(clock, runtime)
        # The Short Squeeze panel's own demand shares the order-flow trades feed.
        specialist.demand("c1", "NVDA", ["order_flow", "short_squeeze"])
        self.assertEqual(s4.provider_keys(runtime), {"NVDA:US_EQUITY_TICKS"})
        self.assertEqual(runtime.subscriptions.ref_count(instrument_id="NVDA", capability=TRADES), 2)
        base = clock.now
        for seq in range(40):
            s4.tick(runtime, "NVDA", seq=seq, price=100 + seq * 0.05, volume=300 if seq % 4 else 100,
                    direction="BUY" if seq % 4 else "SELL", event_ns=base + seq * s4.SECOND)
        clock.advance(41)
        runtime.lifecycle.last_received_ns = clock.now
        keys_before = set(runtime.subscriptions.active_keys)
        payload = service_for({"NVDA": finviz_row("NVDA", short_float_pct=25, change_pct=12, rel_volume=6)},
                              flow_service=specialist)[0].read("NVDA")
        self.assertEqual(set(runtime.subscriptions.active_keys), keys_before)  # read only: nothing subscribed
        confirmation = section(payload, "live_confirmation")
        self.assertEqual(confirmation["order_flow_net"]["quality"], "CURRENT")
        self.assertGreater(confirmation["order_flow_net"]["value"], 0)
        self.assertEqual(payload["assessment"]["state"], "LIVE_CONFIRMATION")
        specialist.demand("c1", "NVDA", [])
        self.assertEqual(s4.provider_keys(runtime), set())

    def test_order_flow_without_subscription_is_missing(self):
        payload = service_for({"GME": finviz_row(change_pct=15, rel_volume=6)})[0].read("GME")
        confirmation = section(payload, "live_confirmation")
        self.assertEqual((confirmation["order_flow_net"]["value"], confirmation["order_flow_net"]["quality"]), (None, "NOT_SUBSCRIBED"))
        self.assertIn("ORDER_FLOW", {item["code"] for item in payload["evidence"]["missing"]})
        self.assertEqual(confirmation["dealer_positioning"]["quality"], "NOT_CONFIGURED")

    def test_summary_view_never_requests_options_and_detail_reads_the_s7_cache(self):
        chain = {"state": "MARKET_CLOSED", "clock": {"fetched_at": "2026-09-27T15:00:00Z"},
                 "summary": {"call_put_volume_ratio": 2.4, "call_volume": 12000, "put_volume": 5000}}
        service, calls = service_for({"GME": finviz_row()}, options=chain)
        summary = service.read("GME", view="summary")
        self.assertEqual(calls.options, 0)
        self.assertEqual(section(summary, "live_confirmation")["options_call_put_volume"]["quality"], "NOT_REQUESTED")
        detail = service.read("GME", view="detail")
        self.assertEqual(calls.options, 1)
        options = section(detail, "live_confirmation")["options_call_put_volume"]
        self.assertEqual((options["value"], options["quality"]), (2.4, "SNAPSHOT"))
        self.assertIn("opening or closing", options["note"])
        rendered = json.dumps(detail).lower()
        self.assertNotIn("gamma squeeze", rendered)

    def test_why_listed_uses_the_exact_screener_predicates(self):
        preset = next(item for item in builtin_presets() if item["id"] == "SHORT_SQUEEZE_DISCOVERY")
        payload = service_for({"GME": finviz_row(rel_volume=3.2)})[0].read("GME", filters=preset["filters"])
        why = payload["why_listed"]
        self.assertEqual(why["state"], "MATCHED")
        self.assertIn("Short Float % 24.80% is above 20.00%", [item["text"] for item in why["items"]])
        self.assertEqual(service_for({"GME": finviz_row()})[0].read("GME")["why_listed"]["state"], "NO_ACTIVE_FILTERS")

    def test_publication_sources_flow_into_the_payload(self):
        jobs = Jobs()
        threshold = ThresholdLists(
            authorities=(ThresholdAuthoritySource("NASDAQ", "Nasdaq", "F", lambda day: listing("NASDAQ", {"GME"}, day)),),
            cache=BackgroundCache(clock=lambda: NOW, spawn=jobs.spawn), clock=lambda: NOW, env={"F": "1"}.get)
        finra = FinraShortData(cache=BackgroundCache(clock=lambda: NOW, spawn=jobs.spawn), env={"IMP_FINRA_LIVE": "1"}.get,
                               credentials_present=lambda: True,
                               fetch=lambda s: {"short_interest": {"settlement_date": "2026-09-15", "publication_date": "2026-09-24",
                                                                   "current": 9_000_000, "previous": 7_000_000, "change": 2_000_000,
                                                                   "change_pct": 28.6, "days_to_cover": 4.1, "revision_flag": None},
                                                "short_sale_volume": None})
        service, _ = service_for({"GME": finviz_row()}, threshold=threshold, finra=finra)
        pending = service.read("GME")
        self.assertEqual(section(pending, "structural_pressure")["threshold_status"]["quality"], "PENDING")
        self.assertEqual(pending["coverage"]["pending"], 5)
        jobs.run()
        payload = service.read("GME")
        structural = section(payload, "structural_pressure")
        self.assertEqual((structural["threshold_status"]["value"], structural["threshold_status"]["clock"]["as_of"]), (True, "2026-09-25"))
        self.assertEqual(structural["official_days_to_cover"]["value"], 4.1)
        self.assertEqual(structural["short_sale_volume"]["quality"], "NO_RECORD")
        self.assertIn("SI_RISING", {item["code"] for item in payload["evidence"]["supporting"]})
        self.assertIn("THRESHOLD_LIST", {item["code"] for item in payload["evidence"]["context"]})
        rule = next(rule for rule in payload["assessment"]["rules"] if rule["rule_id"] == "DAYS_TO_COVER_MINIMUM")
        self.assertEqual(rule["source"], "FINRA")

    def test_stale_finviz_snapshot_is_labelled(self):
        payload = service_for({"GME": finviz_row()}, clock=lambda: NOW + 3600)[0].read("GME")
        self.assertEqual(section(payload, "structural_pressure")["short_float_pct"]["quality"], "STALE")
        self.assertIn("SHORT_FLOAT_PCT_STALE", payload["assessment"]["quality_flags"])

    def test_payload_passes_secret_leak_audit(self):
        payload = service_for({"GME": finviz_row()})[0].read("GME")
        assert_no_secrets_in_payload(payload, context="screener squeeze")
        json.dumps(payload, allow_nan=False)


class CurrentFrozenBoundaryTests(unittest.TestCase):
    FILES = ("ui_api/screener_squeeze.py", "ui_api/screener_squeeze_sources.py", "short_intelligence/squeeze_state.py")

    def test_current_modules_import_no_frozen_fixture_or_cohort_source(self):
        for relative in self.FILES:
            tree = ast.parse((SRC / relative).read_text(encoding="utf-8"))
            modules = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
            modules += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
            for module in modules:
                for banned in ("donor_bridge", "fixture", "frozen", "historical_cohort", "replay", "workspace_evidence"):
                    self.assertNotIn(banned, module, f"{relative} imports {module}")

    def test_service_never_touches_the_donor_bridge(self):
        from market_platform_foundation.donor_bridge import historical_cohort, squeeze_client

        def refuse(*_args, **_kwargs):
            raise AssertionError("current squeeze read touched a donor/frozen source")

        originals = (squeeze_client.fetch_json, historical_cohort.__dict__.copy())
        squeeze_client.fetch_json = refuse
        try:
            payload = service_for({"GME": finviz_row()})[0].read("GME")
        finally:
            squeeze_client.fetch_json = originals[0]
        self.assertNotIn("FROZEN", json.dumps(payload))


# -------------------------------------------------------------------- scope
class ScopeTests(unittest.TestCase):
    def test_short_squeeze_view_is_a_us_equities_view_not_a_universe(self):
        spec = universe_spec(US_EQUITIES)
        self.assertEqual(spec.views["Short Squeeze"], ("symbol", "price", "change_pct", "rel_volume", "volume", "float_shares",
                                                       "short_float_pct", "short_ratio", "bid", "ask", "spread_pct"))
        self.assertNotIn("Short", spec.views)
        self.assertNotIn("Short Squeeze", universe_spec(US_ETFS).views)
        self.assertNotIn("Short Squeeze", universe_spec(FUTURES).views)
        self.assertEqual({item["id"] for item in universe_payload()}, {US_EQUITIES, FUTURES, US_ETFS, "BONDS"})
        self.assertNotIn("Short Squeeze", universe_spec("BONDS").views)
        payload = next(item for item in universe_payload() if item["id"] == US_EQUITIES)
        self.assertEqual(payload["view_order"][4], "Short Squeeze")
        self.assertEqual(payload["view_aliases"], {"Short": "Short Squeeze"})

    def test_field_capabilities_are_truthful(self):
        caps = field_capabilities(US_EQUITIES)
        for field in ("short_float_pct", "short_ratio", "float_shares", "rel_volume", "change_pct"):
            self.assertEqual((caps[field]["execution"], caps[field]["sortable"], caps[field]["filterable"]), ("SNAPSHOT", True, True), field)
        for field in ("bid", "ask", "spread_pct"):
            self.assertEqual((caps[field]["execution"], caps[field]["sortable"], caps[field]["filterable"]), ("LIVE_WINDOW", False, False), field)
        self.assertEqual(parse_query(universe=US_EQUITIES, sort="short_float_pct").sort, "short_float_pct")

    def test_selected_only_evidence_is_never_a_filter_sort_or_column(self):
        words = ("borrow", "threshold", "ftd", "fail", "finra", "short_interest", "short_sale", "cvd", "order_flow",
                 "squeeze", "call", "put", "gamma", "days_to_cover", "state")
        fields = {item["field"] for item in filter_catalog(US_EQUITIES)} | set(universe_spec(US_EQUITIES).columns)
        self.assertFalse([field for field in fields if any(word in field for word in words)])
        with self.assertRaises(ValueError):
            parse_query(universe=US_EQUITIES, filters=[{"id": "x", "field": "borrow_fee", "operator": "gt", "value": 10}])

    def test_saved_screens_accept_the_view_and_migrate_the_old_name(self):
        screen = {"name": "Squeeze watch", "universe": US_EQUITIES, "view": "Short", "filters": [],
                  "sort": {"field": "short_float_pct", "descending": True},
                  "columns": {"visible": ["symbol", "short_float_pct"], "order": ["symbol", "short_float_pct"], "widths": {}, "pinned": []}}
        self.assertEqual(validate_screen(screen)["view"], "Short Squeeze")
        self.assertEqual(validate_screen({**screen, "view": "Short Squeeze"})["view"], "Short Squeeze")
        self.assertNotIn("state", validate_screen(screen))  # observations never become configuration
        with self.assertRaisesRegex(ValueError, "INVALID_SCREEN_VIEW"):
            validate_screen({**screen, "universe": US_ETFS, "view": "Short", "sort": {"field": "symbol", "descending": False},
                             "columns": {"visible": ["symbol"], "order": ["symbol"], "widths": {}, "pinned": []}})
        self.assertEqual(canonical_view(US_ETFS, "Short"), "Short")

    def test_existing_discovery_preset_is_unchanged(self):
        preset = next(item for item in builtin_presets() if item["id"] == "SHORT_SQUEEZE_DISCOVERY")
        self.assertEqual([(rule["field"], rule["operator"], rule["value"]) for rule in preset["filters"]],
                         [("float_shares", "lt", 50_000_000), ("price", "lt", 50), ("short_float_pct", "gt", 20), ("rel_volume", "gt", 1.5)])
        self.assertEqual(preset["name"], "Short Squeeze Discovery")

    def test_panel_capability_matrix_and_layout(self):
        self.assertIn("short_squeeze", universe_spec(US_EQUITIES).panels)
        self.assertNotIn("short_squeeze", universe_spec(US_ETFS).panels)
        self.assertNotIn("short_squeeze", universe_spec(FUTURES).panels)
        self.assertEqual(PANEL_CAPABILITIES["short_squeeze"], (TRADES,))
        layout = validate_panel_layout({"version": 1, "open_panels": ["options", "short_squeeze"], "active_panel": "short_squeeze",
                                        "dock_height": 300, "dockview_layout": None})
        self.assertEqual(layout["open_panels"], ["options", "short_squeeze"])
        with self.assertRaises(ValueError):
            validate_panel_layout({"version": 1, "open_panels": ["short_squeeze", "short_squeeze"], "active_panel": None,
                                   "dock_height": 300, "dockview_layout": None})

    def test_route_is_read_scoped(self):
        self.assertEqual(policy_for_route("GET", "/screener/squeeze").capability, "state.read")


if __name__ == "__main__":
    unittest.main()
