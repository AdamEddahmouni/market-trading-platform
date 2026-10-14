"""Live point-in-time feature corpus for the Path A PRODUCTION specialist."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.intelligence.production.identity import path_a_direction_target, path_a_horizon
from market_platform_foundation.intelligence.production.live_feature_corpus import (
    LiveFeatureCorpusRecorder,
    RollingEventWindow,
    compute_decision,
    load_training_examples,
    settle,
)
from market_platform_foundation.intelligence.production.model import fit_production_specialist
from tests.intelligence.test_signal_fixtures import INSTRUMENT, ONE_SEC, T, quote_event, trade_event

HORIZON = path_a_horizon().duration_ns


def populated_window(*, until_ns: int, drift: float = 0.01, buys: bool = True) -> RollingEventWindow:
    """One quote and one trade per second for the ten minutes ending at ``until_ns``."""
    window = RollingEventWindow(retain_ns=3600 * ONE_SEC, clock=lambda: until_ns)
    start = until_ns - 600 * ONE_SEC
    for i in range(601):
        at = start + i * ONE_SEC
        mid = 100.0 + drift * i
        window.dispatch(quote_event(f"q-{at}", event_time_ns=at, bid=mid - 0.05, ask=mid + 0.05))
        window.dispatch(trade_event(f"t-{at}", event_time_ns=at, price=mid, quantity=10,
                                    aggressor_side=("BUY" if (i % 3 != 0) == buys else "SELL")))
    return window


class RollingEventWindowTests(unittest.TestCase):
    def test_nothing_after_the_decision_time_is_visible(self):
        window = populated_window(until_ns=T + 300 * ONE_SEC)
        events = window.events(INSTRUMENT, available_from_ns=T - 300 * ONE_SEC, available_to_ns=T)
        self.assertTrue(events)
        self.assertTrue(all(e.available_time_ns <= T for e in events))
        reference = window.last_quote_at_or_before(INSTRUMENT, T)
        self.assertLessEqual(reference.available_time_ns, T)

    def test_duplicates_and_other_event_types_are_not_kept(self):
        window = RollingEventWindow(retain_ns=600 * ONE_SEC, clock=lambda: T)
        event = quote_event("q-1", event_time_ns=T)
        self.assertFalse(window.dispatch(event).duplicate)
        self.assertTrue(window.dispatch(event).duplicate)
        from tests.intelligence.test_signal_fixtures import book_event
        window.dispatch(book_event("b-1", event_time_ns=T, bids=[], asks=[]))
        self.assertEqual(window.counts(), {INSTRUMENT: 1})

    def test_duplicate_index_is_bounded_and_forgets_oldest_first(self):
        window = RollingEventWindow(retain_ns=3600 * ONE_SEC, max_events_per_instrument=3, clock=lambda: T)
        for name in ("a", "b", "c", "d"):
            self.assertFalse(window.dispatch(quote_event(name, event_time_ns=T)).duplicate)
        order, seen = window._seen[INSTRUMENT]
        self.assertEqual((list(order), seen), (["b", "c", "d"], {"b", "c", "d"}))
        self.assertTrue(window.dispatch(quote_event("d", event_time_ns=T)).duplicate)
        self.assertFalse(window.dispatch(quote_event("a", event_time_ns=T)).duplicate)

    def test_dispatch_cost_does_not_grow_with_the_window(self):
        # Regression: membership was a linear scan of a 120k-entry deque on the provider callback thread,
        # which starved the live feed (event lag grew past four minutes at the 2026-10-14 open).
        import time

        window = RollingEventWindow(retain_ns=3600 * ONE_SEC, clock=lambda: T)
        for i in range(100_000):
            window.dispatch(quote_event(f"fill-{i}", event_time_ns=T))
        started = time.perf_counter()
        for i in range(2_000):
            window.dispatch(quote_event(f"probe-{i}", event_time_ns=T))
        self.assertLess(time.perf_counter() - started, 1.0)

    def test_old_events_are_evicted_by_retention(self):
        window = RollingEventWindow(retain_ns=60 * ONE_SEC, clock=lambda: T)
        window.dispatch(quote_event("old", event_time_ns=T - 120 * ONE_SEC))
        window.dispatch(quote_event("new", event_time_ns=T))
        self.assertEqual(window.counts(), {INSTRUMENT: 1})


class DecisionAndSettlementTests(unittest.TestCase):
    def test_an_accepted_decision_carries_the_specialist_features_without_event_refs(self):
        window = populated_window(until_ns=T)
        row = compute_decision(window, INSTRUMENT, T)
        self.assertTrue(row["accepted"], row.get("reason"))
        self.assertEqual(set(row["features"]), {"momentum_simple", "net_signed_share"})
        self.assertFalse(row["snapshot"].get("source_event_refs"))
        self.assertTrue(row["snapshot"]["metadata"]["source_event_refs_omitted"])
        self.assertGreater(row["snapshot"]["metadata"]["source_event_count"], 0)

    def test_no_quote_means_no_decision(self):
        window = RollingEventWindow(retain_ns=600 * ONE_SEC, clock=lambda: T)
        window.dispatch(trade_event("t-1", event_time_ns=T - ONE_SEC, price=100.0, quantity=1, aggressor_side="BUY"))
        self.assertEqual(compute_decision(window, INSTRUMENT, T)["reason"], "NO_REFERENCE_QUOTE")

    def test_the_label_waits_for_the_horizon_and_uses_the_first_quote_after_it(self):
        window = populated_window(until_ns=T + HORIZON + 30 * ONE_SEC)
        decision = compute_decision(window, INSTRUMENT, T)
        self.assertIsNone(settle(window, decision, now_ns=T + HORIZON - ONE_SEC, horizon_ns=HORIZON))
        label = settle(window, decision, now_ns=T + HORIZON + 30 * ONE_SEC, horizon_ns=HORIZON)
        self.assertEqual((label["status"], label["label"]), ("SETTLED", 1))
        self.assertGreaterEqual(label["label_available_time_ns"], T + HORIZON)

    def test_a_falling_midpoint_is_class_zero_and_an_unchanged_one_is_unlabelable(self):
        down = populated_window(until_ns=T + HORIZON + 30 * ONE_SEC, drift=-0.01)
        decision = compute_decision(down, INSTRUMENT, T)
        self.assertEqual(settle(down, decision, now_ns=T + HORIZON + 30 * ONE_SEC, horizon_ns=HORIZON)["label"], 0)
        flat = populated_window(until_ns=T + HORIZON + 30 * ONE_SEC, drift=0.0)
        decision = compute_decision(flat, INSTRUMENT, T)
        label = settle(flat, decision, now_ns=T + HORIZON + 30 * ONE_SEC, horizon_ns=HORIZON)
        self.assertEqual((label["status"], label["reason"]), ("UNLABELABLE", "MIDPOINT_UNCHANGED"))

    def test_no_terminal_quote_inside_the_tolerance_is_unlabelable_never_invented(self):
        window = populated_window(until_ns=T)
        decision = compute_decision(window, INSTRUMENT, T)
        self.assertIsNone(settle(window, decision, now_ns=T + HORIZON + ONE_SEC, horizon_ns=HORIZON))
        label = settle(window, decision, now_ns=T + HORIZON + 3600 * ONE_SEC, horizon_ns=HORIZON)
        self.assertEqual((label["status"], label["label"]), ("UNLABELABLE", None))


class RecorderAndTrainingTests(unittest.TestCase):
    def test_recorded_rows_train_the_existing_specialist(self):
        with tempfile.TemporaryDirectory() as tmp:
            clock = {"now": T}
            rows = []
            for k, drift in enumerate((0.01, -0.01) * 6):
                at = T + k * 3600 * ONE_SEC
                window = populated_window(until_ns=at + HORIZON + 30 * ONE_SEC, drift=drift, buys=drift > 0)
                clock["now"] = at
                recorder = LiveFeatureCorpusRecorder(window=window, directory=Path(tmp), instruments=lambda: [INSTRUMENT],
                                                     session_open=lambda _ns: True, clock=lambda: clock["now"])
                recorder.tick()
                clock["now"] = at + HORIZON + 30 * ONE_SEC
                recorder.tick()
                rows.append(recorder.status)
            paths = sorted(Path(tmp).glob("*.jsonl"))
            lines = [json.loads(line) for path in paths for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertTrue(any(line["kind"] == "label" and line["status"] == "SETTLED" for line in lines))
            examples = [example for _key, example in load_training_examples(paths)]
            self.assertGreaterEqual(len(examples), 8)
            cutoff = max(e.label_available_time_ns for e in examples)
            model = fit_production_specialist(examples, target=path_a_direction_target(INSTRUMENT), horizon=path_a_horizon(),
                                              training_cutoff_ns=cutoff)
            self.assertIsNotNone(model)

    def test_a_closed_session_records_nothing_and_a_missed_grid_point_is_not_backfilled(self):
        with tempfile.TemporaryDirectory() as tmp:
            window = populated_window(until_ns=T)
            clock = {"now": T}
            recorder = LiveFeatureCorpusRecorder(window=window, directory=Path(tmp), instruments=lambda: [INSTRUMENT],
                                                 session_open=lambda _ns: False, clock=lambda: clock["now"])
            recorder.tick()
            self.assertEqual(list(Path(tmp).glob("*.jsonl")), [])
            recorder.session_open = lambda _ns: True
            clock["now"] = T + 95 * ONE_SEC  # three grid points later: only the current one is evaluated
            recorder.tick()
            self.assertEqual(recorder.status["decisions"], 1)


class FakeRuntime:
    def __init__(self, router=None):
        self.observation_ingress_router = router
        self.calls = []

    def attach_observation_ingress(self, router):
        self.observation_ingress_router = router

    def subscribe(self, *, instrument_id, capabilities, consumer_id):
        self.calls.append((instrument_id, tuple(capabilities), consumer_id))
        return [dict(accepted=instrument_id != "REFUSED", reason=None if instrument_id != "REFUSED" else "QUOTA") for _ in capabilities]


class CorpusServiceTests(unittest.TestCase):
    def service(self, tmp, runtime, symbols=("AAPL", "REFUSED")):
        from market_platform_foundation.ui_api.paper_forecast_corpus import PaperForecastCorpusService
        return PaperForecastCorpusService(directory=Path(tmp), symbols=list(symbols), runtime_getter=lambda: runtime)

    def test_disabled_by_default_and_only_in_live_mode(self):
        from types import SimpleNamespace
        from market_platform_foundation.ui_api.paper_forecast_corpus import start_paper_forecast_corpus
        live = SimpleNamespace(data_mode="LIVE_OBSERVATIONAL")
        self.assertEqual(start_paper_forecast_corpus(live, environ={})["reason"], "DISABLED")
        replay = SimpleNamespace(data_mode="FIXTURE_REPLAY")
        self.assertEqual(start_paper_forecast_corpus(replay, environ={"IMP_PAPER_FORECAST_CORPUS": "1"})["reason"],
                         "NOT_LIVE_OBSERVATIONAL")
        refused = start_paper_forecast_corpus(live, environ={"IMP_PAPER_FORECAST_CORPUS": "1", "IMP_PAPER_FORECAST_CORPUS_DIR": "rel"})
        self.assertFalse(refused["started"])

    def test_attach_subscribes_quotes_and_trades_and_records_refusals(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = FakeRuntime()
            service = self.service(tmp, runtime)
            self.assertTrue(service.attach())
            self.assertIs(runtime.observation_ingress_router, service.window)
            self.assertEqual(runtime.calls[0], ("AAPL", ("BASIC_QUOTE", "TRADES"), "paper-forecast-corpus"))
            self.assertFalse(service.subscriptions["REFUSED"][0]["accepted"])
            status = service.write_status()
            self.assertEqual((status["writes_canonical_store"], status["calls_models"], status["order_capability"]), (False, False, False))

    def test_an_existing_ingress_router_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = self.service(tmp, FakeRuntime(router=object()))
            with self.assertRaises(ValueError):
                service.attach()

    def test_symbol_configuration_is_bounded(self):
        from market_platform_foundation.ui_api.paper_forecast_corpus import configured_symbols
        self.assertEqual(configured_symbols({"IMP_PAPER_FORECAST_CORPUS_SYMBOLS": "aapl, NVDA,aapl"}), ["AAPL", "NVDA"])
        for bad in ("", ",".join(f"S{i}" for i in range(13)), "AAPL;rm"):
            with self.assertRaises(ValueError):
                configured_symbols({"IMP_PAPER_FORECAST_CORPUS_SYMBOLS": bad})

    def test_the_corpus_modules_import_no_order_broker_or_paper_route(self):
        import ast
        root = Path(__file__).resolve().parents[2] / "src" / "market_platform_foundation"
        for rel in ("intelligence/production/live_feature_corpus.py", "ui_api/paper_forecast_corpus.py"):
            tree = ast.parse((root / rel).read_text(encoding="utf-8"))
            names = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
            names |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
            for name in names:
                self.assertFalse(any(word in name for word in ("paper_projections", "broker", "order", "execution", "paper.")), (rel, name))


if __name__ == "__main__":
    unittest.main()
