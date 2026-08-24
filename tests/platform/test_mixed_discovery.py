"""Offline tests for the mixed live discovery queue."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.discovery.mixed import (  # noqa: E402
    LANES_BY_SCREEN,
    aggregate_candidate_sets,
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


if __name__ == "__main__":
    unittest.main()
