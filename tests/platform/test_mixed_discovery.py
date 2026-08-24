"""Offline tests for the mixed live discovery queue."""

from __future__ import annotations

import math
import os
import json
import sys
import threading
import tempfile
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.discovery.mixed import (  # noqa: E402
    LANES_BY_SCREEN,
    MixedCandidate,
    aggregate_candidate_sets,
)
from market_platform_foundation.discovery.live_enrichment import (  # noqa: E402
    MoomooCandidateEnricher,
    discovery_live_candidate_cap,
)
from market_platform_foundation.market_data.observational_state import (  # noqa: E402
    ObservationalStateStore,
    QuoteSnapshot,
)
from market_platform_foundation.market_data.subscription_manager import (  # noqa: E402
    LiveSubscriptionManager,
    SubscriptionPriority,
)
from market_platform_foundation.discovery.screens import SCREEN_LIBRARY  # noqa: E402
from market_platform_foundation.ui_api.mixed_discovery_projections import (  # noqa: E402
    MixedDiscoveryService,
)
from market_platform_foundation.ui_api.discovery_projections import (  # noqa: E402
    load_latest_capture_for_screen,
)
from market_platform_foundation.ui_api.server import UiApiHandler  # noqa: E402


def candidate_set(
    *,
    screen_id: str,
    symbol: str = "AAPL",
    available_time_ns: int = 1_000_000_000,
    received_at: str = "2026-08-24T13:00:00Z",
    reasons: list[str] | None = None,
    metrics: dict[str, object] | None = None,
    quality: str = "PASS",
) -> dict[str, object]:
    return {
        "run_id": f"run-{screen_id}-{available_time_ns}",
        "screen_id": screen_id,
        "screen_version": "1.0.0",
        "received_at": received_at,
        "available_time_ns": available_time_ns,
        "provider": "FINVIZ_ELITE",
        "quality": quality,
        "candidates": [
            {
                "instrument_id": symbol,
                "provider_symbol": symbol,
                "screen_id": screen_id,
                "screen_version": "1.0.0",
                "discovered_at": received_at,
                "available_time_ns": available_time_ns,
                "matched_reasons": reasons if reasons is not None else ["RVOL 2.0"],
                "metrics": metrics if metrics is not None else {"price": 100.0, "rel_volume": 2.0},
                "quality": quality,
                "provenance": {"provider": "FINVIZ_ELITE", "screen": screen_id},
            }
        ],
    }


class MixedDomainTests(unittest.TestCase):
    def test_all_versioned_screens_have_approved_lanes(self) -> None:
        self.assertEqual(
            LANES_BY_SCREEN,
            {
                "SHORT_SQUEEZE_DISCOVERY": ("SQUEEZE",),
                "UNUSUAL_VOLUME_DISCOVERY": ("MOMENTUM",),
                "MOMENTUM_IGNITION_DISCOVERY": ("MOMENTUM",),
                "GAP_CATALYST_DISCOVERY": ("MOMENTUM", "CATALYST"),
                "EARNINGS_MOVER_DISCOVERY": ("CATALYST", "SWING"),
                "ANALYST_EVENT_DISCOVERY": ("CATALYST", "SWING"),
                "INSIDER_ACTIVITY_DISCOVERY": ("CATALYST", "SWING"),
                "TECHNICAL_BREAKOUT_DISCOVERY": ("MOMENTUM", "SWING"),
            },
        )

    def test_deduplicates_symbol_and_newest_metric_wins(self) -> None:
        older = candidate_set(
            screen_id="SHORT_SQUEEZE_DISCOVERY",
            available_time_ns=1_000_000_000,
            metrics={"price": 99.0, "rel_volume": 2.0, "short_float_pct": 25.0},
            reasons=["Short Float 25.0%"],
        )
        newer = candidate_set(
            screen_id="UNUSUAL_VOLUME_DISCOVERY",
            available_time_ns=1_500_000_000,
            metrics={"price": 100.0, "rel_volume": 4.0, "volume": 2_000_000},
            reasons=["RVOL 4.00"],
        )

        mixed = aggregate_candidate_sets([older, newer], now_ns=2_000_000_000)

        self.assertEqual(len(mixed), 1)
        self.assertEqual(mixed[0].instrument_id, "AAPL")
        self.assertEqual(mixed[0].lanes, ["MOMENTUM", "SQUEEZE"])
        self.assertEqual(mixed[0].screen_matches, ["SHORT_SQUEEZE_DISCOVERY", "UNUSUAL_VOLUME_DISCOVERY"])
        self.assertEqual(mixed[0].matched_reasons, ["RVOL 4.00", "Short Float 25.0%"])
        self.assertEqual(mixed[0].metrics["rel_volume"], 4.0)
        self.assertEqual(mixed[0].metrics["short_float_pct"], 25.0)
        self.assertEqual(len(mixed[0].provenance), 2)
        self.assertEqual(mixed[0].candidate_role, "INVESTIGATE")

    def test_quality_gates_reject_invalid_symbols_prices_and_missing_reasons(self) -> None:
        sets = [
            candidate_set(screen_id="UNUSUAL_VOLUME_DISCOVERY", symbol="../BAD"),
            candidate_set(screen_id="UNUSUAL_VOLUME_DISCOVERY", symbol="1234"),
            candidate_set(screen_id="UNUSUAL_VOLUME_DISCOVERY", symbol="ZERO", metrics={"price": 0.0}),
            candidate_set(screen_id="UNUSUAL_VOLUME_DISCOVERY", symbol="NEG", metrics={"price": -1.0}),
            candidate_set(screen_id="UNUSUAL_VOLUME_DISCOVERY", symbol="NAN", metrics={"price": math.nan}),
            candidate_set(screen_id="UNUSUAL_VOLUME_DISCOVERY", symbol="WHY", reasons=[]),
            candidate_set(screen_id="UNUSUAL_VOLUME_DISCOVERY", symbol="GOOD", metrics={"price": None}),
        ]

        mixed = aggregate_candidate_sets(sets, now_ns=2_000_000_000)

        self.assertEqual([row.instrument_id for row in mixed], ["GOOD"])
        self.assertIsNone(mixed[0].metrics["price"])

    def test_missing_optional_metrics_stay_null_and_score_components_are_capped(self) -> None:
        sparse = candidate_set(
            screen_id="TECHNICAL_BREAKOUT_DISCOVERY",
            symbol="SPARSE",
            metrics={"price": None, "rel_volume": None, "volume": None, "change_pct": None},
        )
        extreme = candidate_set(
            screen_id="SHORT_SQUEEZE_DISCOVERY",
            symbol="MAX",
            metrics={
                "price": 10.0,
                "rel_volume": 1000.0,
                "volume": 10_000_000_000,
                "change_pct": 500.0,
                "short_float_pct": 100.0,
            },
        )

        mixed = aggregate_candidate_sets([sparse, extreme], now_ns=1_000_000_000)
        by_symbol = {row.instrument_id: row for row in mixed}

        self.assertIsNone(by_symbol["SPARSE"].metrics["volume"])
        self.assertEqual(by_symbol["SPARSE"].attention_components["live_confirmation"], 0.0)
        self.assertLessEqual(by_symbol["MAX"].attention_components["setup_strength"], 45.0)
        self.assertLessEqual(by_symbol["MAX"].attention_components["freshness"], 20.0)
        self.assertLessEqual(by_symbol["MAX"].attention_components["liquidity_marketability"], 20.0)
        self.assertLessEqual(by_symbol["MAX"].attention_components["live_confirmation"], 15.0)

    def test_stale_and_crossed_market_apply_explicit_penalties(self) -> None:
        base = candidate_set(screen_id="UNUSUAL_VOLUME_DISCOVERY", metrics={"price": 10.0, "rel_volume": 3.0})
        market = {
            "AAPL": {
                "provider": "MOOMOO",
                "status": "STALE",
                "quality": "DEGRADED",
                "freshness_ms": 10_000,
                "last_price": 10.1,
                "bid_price": 10.2,
                "ask_price": 10.1,
                "spread_pct": None,
                "volume": 1_000_000.0,
                "reason": "CROSSED_MARKET",
            }
        }

        row = aggregate_candidate_sets([base], now_ns=2_000_000_000, market_by_symbol=market)[0]

        self.assertLess(row.attention_components["quality_penalty"], 0)
        self.assertIn("STALE_MARKET_DATA", row.ranking_reasons)
        self.assertIn("CROSSED_MARKET", row.ranking_reasons)

    def test_ties_break_by_newest_then_screen_count_then_symbol(self) -> None:
        same_metrics = {"price": 10.0, "rel_volume": 2.0}
        sets = [
            candidate_set(
                screen_id="UNUSUAL_VOLUME_DISCOVERY",
                symbol="ZZZ",
                available_time_ns=1_000_000_000,
                metrics=same_metrics,
            ),
            candidate_set(
                screen_id="UNUSUAL_VOLUME_DISCOVERY",
                symbol="BBB",
                available_time_ns=1_500_000_000,
                metrics=same_metrics,
            ),
            candidate_set(
                screen_id="UNUSUAL_VOLUME_DISCOVERY",
                symbol="AAA",
                available_time_ns=1_500_000_000,
                metrics=same_metrics,
            ),
            candidate_set(
                screen_id="TECHNICAL_BREAKOUT_DISCOVERY",
                symbol="BBB",
                available_time_ns=1_500_000_000,
                metrics=same_metrics,
            ),
        ]

        mixed = aggregate_candidate_sets(sets, now_ns=2_000_000_000)

        self.assertEqual([row.instrument_id for row in mixed], ["BBB", "AAA", "ZZZ"])
        self.assertEqual([row.queue_rank for row in mixed], [1, 2, 3])


def ranked_candidate(symbol: str, rank: int) -> MixedCandidate:
    return MixedCandidate(
        instrument_id=symbol,
        lanes=["MOMENTUM"],
        screen_matches=["UNUSUAL_VOLUME_DISCOVERY"],
        matched_reasons=["RVOL 2.0"],
        metrics={"price": 10.0, "rel_volume": 2.0},
        discovery_as_of="2026-08-24T13:00:00Z",
        available_time_ns=1_000_000_000,
        quality="PASS",
        provenance=[],
        attention_score=float(100 - rank),
        queue_rank=rank,
    )


class FakeRuntime:
    def __init__(self, *, quota: int = 100) -> None:
        self.subscriptions = LiveSubscriptionManager(max_quota=quota)
        self.state = ObservationalStateStore()
        self.subscribe_calls: list[dict[str, object]] = []
        self.unsubscribe_calls: list[dict[str, object]] = []

    def subscribe(self, **kwargs: object) -> list[dict[str, object]]:
        self.subscribe_calls.append(dict(kwargs))
        results = []
        for capability in kwargs["capabilities"]:
            result = self.subscriptions.acquire(
                instrument_id=str(kwargs["instrument_id"]),
                capability=str(capability),
                consumer_id=str(kwargs["consumer_id"]),
                priority=int(kwargs["priority"]),
            )
            results.append(
                {
                    "accepted": result.accepted,
                    "instrument_id": result.key.instrument_id,
                    "capability": result.key.capability,
                    "reason": result.reason,
                }
            )
        return results

    def unsubscribe(self, **kwargs: object) -> list[dict[str, object]]:
        self.unsubscribe_calls.append(dict(kwargs))
        results = []
        for capability in kwargs["capabilities"]:
            result = self.subscriptions.release(
                instrument_id=str(kwargs["instrument_id"]),
                capability=str(capability),
                consumer_id=str(kwargs["consumer_id"]),
            )
            results.append(
                {
                    "accepted": result.accepted,
                    "instrument_id": result.key.instrument_id,
                    "capability": result.key.capability,
                }
            )
        return results


def quote(
    symbol: str,
    *,
    received_ns: int,
    bid: float = 9.99,
    ask: float = 10.01,
    last: float = 10.0,
) -> QuoteSnapshot:
    return QuoteSnapshot(
        instrument_id=symbol,
        bid_price=bid,
        ask_price=ask,
        bid_size=100.0,
        ask_size=100.0,
        last_price=last,
        volume=1_000_000.0,
        event_time_ns=received_ns,
        available_time_ns=received_ns,
        received_ns=received_ns,
        quality="PASS",
        provider="moomoo",
        admission="DISPLAY",
    )


class MoomooEnrichmentTests(unittest.TestCase):
    def test_reconcile_uses_quote_only_dedicated_consumer_and_background_priority(self) -> None:
        runtime = FakeRuntime()
        enricher = MoomooCandidateEnricher(runtime, cap=2, now_ns=lambda: 2_000_000_000)

        outcomes = enricher.reconcile([ranked_candidate("AAPL", 1), ranked_candidate("MSFT", 2)])

        self.assertTrue(all(row["accepted"] for row in outcomes))
        self.assertEqual(len(runtime.subscribe_calls), 2)
        self.assertEqual(runtime.subscribe_calls[0]["capabilities"], ["BASIC_QUOTE"])
        self.assertEqual(runtime.subscribe_calls[0]["consumer_id"], "discover-live-screener")
        self.assertEqual(
            runtime.subscribe_calls[0]["priority"],
            int(SubscriptionPriority.BACKGROUND_RESEARCH),
        )

    def test_reconcile_respects_cap_and_remaining_provider_quota(self) -> None:
        runtime = FakeRuntime(quota=2)
        runtime.subscriptions.acquire(
            instrument_id="SPY",
            capability="BASIC_QUOTE",
            consumer_id="workspace",
        )
        enricher = MoomooCandidateEnricher(runtime, cap=3)

        outcomes = enricher.reconcile(
            [ranked_candidate("AAPL", 1), ranked_candidate("MSFT", 2), ranked_candidate("NVDA", 3)]
        )

        self.assertEqual([row["instrument_id"] for row in outcomes if row["accepted"]], ["AAPL"])
        self.assertEqual(enricher.subscribed_symbols, {"AAPL"})
        self.assertEqual(len(runtime.subscriptions.active_keys), 2)

    def test_hysteresis_retains_incumbent_within_three_places_of_cutoff(self) -> None:
        runtime = FakeRuntime()
        enricher = MoomooCandidateEnricher(runtime, cap=2)
        enricher.reconcile([ranked_candidate("AAPL", 1), ranked_candidate("MSFT", 2)])

        enricher.reconcile(
            [
                ranked_candidate("NVDA", 1),
                ranked_candidate("TSLA", 2),
                ranked_candidate("META", 3),
                ranked_candidate("AAPL", 4),
                ranked_candidate("MSFT", 7),
            ]
        )

        self.assertEqual(enricher.subscribed_symbols, {"AAPL", "NVDA"})
        self.assertTrue(any(call["instrument_id"] == "MSFT" for call in runtime.unsubscribe_calls))

    def test_release_removes_only_screener_consumer_reference(self) -> None:
        runtime = FakeRuntime()
        runtime.subscriptions.acquire(
            instrument_id="AAPL",
            capability="BASIC_QUOTE",
            consumer_id="workspace",
        )
        enricher = MoomooCandidateEnricher(runtime, cap=1)
        enricher.reconcile([ranked_candidate("AAPL", 1)])

        enricher.reconcile([ranked_candidate("MSFT", 1)])

        key = "AAPL:US_EQUITY_L1"
        self.assertIn(key, runtime.subscriptions.active_keys)
        self.assertEqual(set(runtime.subscriptions.refs[key]), {"workspace"})

    def test_unavailable_runtime_and_awaiting_first_event_are_explicit(self) -> None:
        candidate = ranked_candidate("AAPL", 1)
        unavailable = MoomooCandidateEnricher(None).enrich([candidate])["AAPL"]
        runtime = FakeRuntime()
        awaiting_enricher = MoomooCandidateEnricher(runtime)
        awaiting_enricher.reconcile([candidate])
        awaiting = awaiting_enricher.enrich([candidate])["AAPL"]

        self.assertEqual(unavailable["status"], "UNAVAILABLE")
        self.assertEqual(unavailable["reason"], "MOOMOO_RUNTIME_UNAVAILABLE")
        self.assertIsNone(unavailable["last_price"])
        self.assertEqual(awaiting["status"], "SNAPSHOT")
        self.assertEqual(awaiting["reason"], "AWAITING_FIRST_EVENT")

    def test_quote_status_spread_and_crossed_market_quality(self) -> None:
        now_ns = 10_000_000_000
        runtime = FakeRuntime()
        runtime.state.quotes["AAPL"] = quote("AAPL", received_ns=now_ns - 1_000_000_000)
        runtime.state.quotes["MSFT"] = quote("MSFT", received_ns=now_ns - 6_000_000_000)
        runtime.state.quotes["NVDA"] = quote(
            "NVDA",
            received_ns=now_ns - 1_000_000_000,
            bid=10.1,
            ask=10.0,
        )
        enricher = MoomooCandidateEnricher(runtime, now_ns=lambda: now_ns)

        market = enricher.enrich(
            [ranked_candidate("AAPL", 1), ranked_candidate("MSFT", 2), ranked_candidate("NVDA", 3)]
        )

        self.assertEqual(market["AAPL"]["status"], "LIVE")
        self.assertAlmostEqual(market["AAPL"]["spread_pct"], 0.2)
        self.assertEqual(market["MSFT"]["status"], "STALE")
        self.assertEqual(market["NVDA"]["quality"], "DEGRADED")
        self.assertEqual(market["NVDA"]["reason"], "CROSSED_MARKET")
        self.assertIsNone(market["NVDA"]["spread_pct"])

    def test_candidate_cap_configuration_is_positive_and_fail_closed(self) -> None:
        with patch.dict(os.environ, {"IMP_DISCOVERY_LIVE_CANDIDATES": "7"}):
            self.assertEqual(discovery_live_candidate_cap(), 7)
        for bad in ("", "0", "-2", "abc"):
            with self.subTest(value=bad), patch.dict(
                os.environ,
                {"IMP_DISCOVERY_LIVE_CANDIDATES": bad},
            ):
                self.assertEqual(discovery_live_candidate_cap(), 12)


class FakeEngine:
    def __init__(self, results: dict[str, object]) -> None:
        self.results = results
        self.calls: list[dict[str, object]] = []

    def run_screen(self, screen_id: str, **kwargs: object) -> object:
        self.calls.append({"screen_id": screen_id, **kwargs})
        result = self.results[screen_id]
        if isinstance(result, Exception):
            raise result
        return result


class RuntimeGetterSpy:
    def __init__(self, runtime: object | None) -> None:
        self.runtime = runtime
        self.calls: list[dict[str, bool]] = []

    def __call__(self, *, create: bool = True) -> object | None:
        self.calls.append({"create": create})
        return self.runtime


class MixedProjectionTests(unittest.TestCase):
    def make_service(
        self,
        *,
        engine: FakeEngine,
        captures: dict[str, dict[str, object] | None] | None = None,
        runtime: FakeRuntime | None = None,
    ) -> tuple[MixedDiscoveryService, RuntimeGetterSpy, list[str]]:
        capture_calls: list[str] = []

        def capture_loader(screen_id: str) -> dict[str, object] | None:
            capture_calls.append(screen_id)
            return (captures or {}).get(screen_id)

        runtime_getter = RuntimeGetterSpy(runtime)
        service = MixedDiscoveryService(
            engine_factory=lambda: engine,
            capture_loader=capture_loader,
            runtime_getter=runtime_getter,
            now_ns=lambda: 2_000_000_000,
            generated_at=lambda: "2026-08-24T13:00:02Z",
        )
        return service, runtime_getter, capture_calls

    def test_refresh_runs_all_screens_deduplicates_and_reports_outcomes(self) -> None:
        results = {
            screen_id: candidate_set(
                screen_id=screen_id,
                available_time_ns=1_000_000_000 + index,
                reasons=[f"Matched {screen_id}"],
            )
            for index, screen_id in enumerate(SCREEN_LIBRARY)
        }
        engine = FakeEngine(results)
        service, runtime_getter, _ = self.make_service(engine=engine)

        payload = service.refresh()

        self.assertEqual([call["screen_id"] for call in engine.calls], list(SCREEN_LIBRARY))
        self.assertTrue(all(call["force"] and call["persist"] for call in engine.calls))
        self.assertEqual(len(payload["candidates"]), 1)
        self.assertEqual(len(payload["candidates"][0]["screen_matches"]), 8)
        self.assertEqual({row["status"] for row in payload["screen_outcomes"]}, {"PASS"})
        self.assertEqual(runtime_getter.calls[0], {"create": True})
        self.assertEqual(payload["candidate_role"], "INVESTIGATE")
        self.assertEqual(payload["refresh_interval_seconds"], 120)
        self.assertEqual(payload["poll_interval_seconds"], 3)

    def test_partial_failure_uses_capture_and_all_failure_is_unavailable(self) -> None:
        first, second = list(SCREEN_LIBRARY)[:2]
        engine = FakeEngine(
            {
                first: RuntimeError("FINVIZ_AUTH_REQUIRED"),
                second: candidate_set(screen_id=second, symbol="MSFT"),
            }
        )
        service, _, _ = self.make_service(
            engine=engine,
            captures={first: candidate_set(screen_id=first, symbol="AAPL")},
        )

        payload = service.refresh([first, second])

        self.assertTrue(payload["available"])
        self.assertEqual({row["instrument_id"] for row in payload["candidates"]}, {"AAPL", "MSFT"})
        outcomes = {row["screen_id"]: row for row in payload["screen_outcomes"]}
        self.assertEqual(outcomes[first]["status"], "FALLBACK")
        self.assertIn("FINVIZ_AUTH_REQUIRED", outcomes[first]["reason"])
        self.assertEqual(outcomes[second]["status"], "PASS")

        unavailable_engine = FakeEngine({first: RuntimeError("DOWN")})
        unavailable, _, _ = self.make_service(engine=unavailable_engine)
        empty = unavailable.refresh([first])
        self.assertFalse(empty["available"])
        self.assertEqual(empty["candidates"], [])
        self.assertEqual(empty["screen_outcomes"][0]["status"], "UNAVAILABLE")

    def test_read_uses_current_runtime_without_finviz_or_subscription_side_effects(self) -> None:
        screen_id = "UNUSUAL_VOLUME_DISCOVERY"
        engine = FakeEngine({screen_id: candidate_set(screen_id=screen_id)})
        runtime = FakeRuntime()
        service, runtime_getter, _ = self.make_service(engine=engine, runtime=runtime)
        service.refresh([screen_id])
        engine.calls.clear()
        runtime_getter.calls.clear()
        runtime.subscribe_calls.clear()
        runtime.unsubscribe_calls.clear()

        payload = service.read()

        self.assertEqual(engine.calls, [])
        self.assertEqual(runtime_getter.calls, [{"create": False}])
        self.assertEqual(runtime.subscribe_calls, [])
        self.assertEqual(runtime.unsubscribe_calls, [])
        self.assertEqual(payload["candidates"][0]["candidate_role"], "INVESTIGATE")

    def test_read_reconstructs_latest_captures_without_starting_finviz(self) -> None:
        screen_id = "SHORT_SQUEEZE_DISCOVERY"
        engine = FakeEngine({})
        service, runtime_getter, capture_calls = self.make_service(
            engine=engine,
            captures={screen_id: candidate_set(screen_id=screen_id)},
        )

        payload = service.read()

        self.assertEqual(engine.calls, [])
        self.assertEqual(capture_calls, list(SCREEN_LIBRARY))
        self.assertEqual(runtime_getter.calls, [{"create": False}])
        self.assertTrue(payload["available"])
        self.assertEqual(payload["screen_outcomes"][0]["status"], "FALLBACK")

    def test_refresh_is_single_flight_and_second_caller_gets_current_result(self) -> None:
        screen_id = "UNUSUAL_VOLUME_DISCOVERY"
        entered = threading.Event()
        release = threading.Event()

        class BlockingEngine(FakeEngine):
            def run_screen(self, screen_id: str, **kwargs: object) -> object:
                self.calls.append({"screen_id": screen_id, **kwargs})
                entered.set()
                release.wait(timeout=5)
                return candidate_set(screen_id=screen_id)

        engine = BlockingEngine({})
        service, _, _ = self.make_service(engine=engine)
        first_result: list[dict[str, object]] = []
        worker = threading.Thread(target=lambda: first_result.append(service.refresh([screen_id])))
        worker.start()
        self.assertTrue(entered.wait(timeout=2))

        concurrent = service.refresh([screen_id])
        release.set()
        worker.join(timeout=5)

        self.assertEqual(len(engine.calls), 1)
        self.assertTrue(concurrent["refresh_in_progress"])
        self.assertFalse(first_result[0]["refresh_in_progress"])

    def test_unknown_requested_screen_is_rejected(self) -> None:
        service, _, _ = self.make_service(engine=FakeEngine({}))
        with self.assertRaisesRegex(ValueError, "UNKNOWN_SCREEN"):
            service.refresh(["NOT_A_SCREEN"])

    def test_capture_loader_returns_newest_artifact(self) -> None:
        screen_id = "SHORT_SQUEEZE_DISCOVERY"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            older = root / "2026-08-23" / screen_id / "run-old" / "candidate-set.json"
            newer = root / "2026-08-24" / screen_id / "run-new" / "candidate-set.json"
            older.parent.mkdir(parents=True)
            newer.parent.mkdir(parents=True)
            older.write_text(json.dumps({"run_id": "old"}), encoding="utf-8")
            newer.write_text(json.dumps({"run_id": "new"}), encoding="utf-8")
            with patch.dict(os.environ, {"IMP_FINVIZ_CAPTURE_DIR": temporary}):
                loaded = load_latest_capture_for_screen(screen_id)

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["run_id"], "new")


class MixedRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.handler = type("MixedBoundHandler", (UiApiHandler,), {"store": object()})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def test_mixed_get_and_refresh_routes_return_projection_payload(self) -> None:
        expected = {
            "available": True,
            "candidate_role": "INVESTIGATE",
            "candidates": [],
        }
        target = "market_platform_foundation.ui_api.mixed_discovery_projections"
        with patch(f"{target}.build_mixed_discover_payload", return_value=expected) as read_mock:
            with urllib.request.urlopen(f"{self.base_url}/discover/mixed", timeout=5) as response:
                get_payload = json.loads(response.read())
        request = urllib.request.Request(
            f"{self.base_url}/discover/mixed/refresh",
            data=json.dumps({"screen_ids": ["SHORT_SQUEEZE_DISCOVERY"]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with patch(f"{target}.refresh_mixed_discovery", return_value=expected) as refresh_mock:
            with urllib.request.urlopen(request, timeout=5) as response:
                post_payload = json.loads(response.read())

        self.assertEqual(get_payload, expected)
        self.assertEqual(post_payload, expected)
        read_mock.assert_called_once_with()
        refresh_mock.assert_called_once_with(["SHORT_SQUEEZE_DISCOVERY"])

    def test_mixed_refresh_rejects_invalid_screen_ids(self) -> None:
        request = urllib.request.Request(
            f"{self.base_url}/discover/mixed/refresh",
            data=json.dumps({"screen_ids": "NOT_A_LIST"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as captured:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(captured.exception.code, 400)
        payload = json.loads(captured.exception.read())
        self.assertEqual(payload["reason_code"], "UI_REQUEST_INVALID")


if __name__ == "__main__":
    unittest.main()
