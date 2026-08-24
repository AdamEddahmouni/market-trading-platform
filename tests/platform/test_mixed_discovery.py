"""Offline tests for the mixed live discovery queue."""

from __future__ import annotations

import math
import os
import sys
import unittest
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


if __name__ == "__main__":
    unittest.main()
