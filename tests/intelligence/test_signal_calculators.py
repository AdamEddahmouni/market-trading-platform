"""BUILD 06 calculator unit tests."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.contracts import QualityState, QualitySummary  # noqa: E402
from market_platform_foundation.intelligence.signals import SignalComputationRequest  # noqa: E402
from market_platform_foundation.intelligence.signals.calculators.base import CalculatorContext  # noqa: E402
from market_platform_foundation.intelligence.signals.calculators.depth import DepthImbalanceCalculator  # noqa: E402
from market_platform_foundation.intelligence.signals.calculators.momentum import MomentumSimpleCalculator  # noqa: E402
from market_platform_foundation.intelligence.signals.calculators.order_flow import (  # noqa: E402
    CvdCalculator,
    NetSignedShareCalculator,
)
from market_platform_foundation.intelligence.signals.calculators.spread import (  # noqa: E402
    SpreadAbsCalculator,
    SpreadBpsCalculator,
)
from market_platform_foundation.intelligence.signals.calculators.volatility import RealizedVolCalculator  # noqa: E402
from market_platform_foundation.intelligence.signals.calculators.volume import RelativeVolumeCalculator  # noqa: E402
from market_platform_foundation.intelligence.signals.models import ComputationDiagnosticCode  # noqa: E402
from market_platform_foundation.intelligence.signals.prepared import PreparedSnapshotState  # noqa: E402
from tests.intelligence.test_signal_fixtures import (  # noqa: E402
    ONE_SEC,
    T,
    WINDOW,
    book_event,
    quote_event,
    resolved_snapshot,
    trade_event,
)


def _ctx(resolved, window_ns: int = WINDOW) -> CalculatorContext:
    prepared = PreparedSnapshotState.from_resolved(resolved)
    request = SignalComputationRequest(window_ns=window_ns)
    return CalculatorContext(prepared=prepared, request=request)


class SpreadCalculatorTests(unittest.TestCase):
    def test_spread_abs_valid_quote(self) -> None:
        resolved = resolved_snapshot(
            "snap-spread",
            events=(quote_event("q1", event_time_ns=T, bid=100.0, ask=100.10),),
        )
        output = SpreadAbsCalculator().compute(_ctx(resolved))
        self.assertIsNotNone(output.signal)
        self.assertAlmostEqual(output.signal.value, 0.10)
        self.assertEqual(output.signal.unit, "USD/share")

    def test_spread_locked_quote_zero(self) -> None:
        resolved = resolved_snapshot(
            "snap-locked",
            events=(quote_event("q1", event_time_ns=T, bid=100.0, ask=100.0),),
        )
        output = SpreadAbsCalculator().compute(_ctx(resolved))
        self.assertIsNotNone(output.signal)
        self.assertAlmostEqual(output.signal.value, 0.0)

    def test_spread_crossed_quote_skipped(self) -> None:
        resolved = resolved_snapshot(
            "snap-crossed",
            events=(quote_event("q1", event_time_ns=T, bid=100.10, ask=100.0),),
        )
        output = SpreadAbsCalculator().compute(_ctx(resolved))
        self.assertIsNone(output.signal)
        self.assertEqual(output.diagnostic.code, ComputationDiagnosticCode.INPUT_QUALITY_REJECTED)

    def test_spread_bps(self) -> None:
        resolved = resolved_snapshot(
            "snap-bps",
            events=(quote_event("q1", event_time_ns=T, bid=100.0, ask=100.10),),
        )
        output = SpreadBpsCalculator().compute(_ctx(resolved))
        self.assertIsNotNone(output.signal)
        mid = 100.05
        expected = (0.10 / mid) * 10_000
        self.assertAlmostEqual(output.signal.value, expected, places=6)


class CvdCalculatorTests(unittest.TestCase):
    def test_cvd_buy_only(self) -> None:
        trades = tuple(
            trade_event(f"t{i}", event_time_ns=T - (10 - i) * ONE_SEC, price=100 + i, quantity=10, aggressor_side="BUY")
            for i in range(10)
        )
        resolved = resolved_snapshot("snap-cvd-buy", events=trades)
        output = CvdCalculator().compute(_ctx(resolved))
        self.assertIsNotNone(output.signal)
        self.assertAlmostEqual(output.signal.value, 100.0)

    def test_cvd_sell_only(self) -> None:
        trades = tuple(
            trade_event(
                f"t{i}",
                event_time_ns=T - (10 - i) * ONE_SEC,
                price=100 + i,
                quantity=5,
                aggressor_side="SELL",
            )
            for i in range(10)
        )
        resolved = resolved_snapshot("snap-cvd-sell", events=trades)
        output = CvdCalculator().compute(_ctx(resolved))
        self.assertIsNotNone(output.signal)
        self.assertAlmostEqual(output.signal.value, -50.0)

    def test_cvd_mixed_sequence(self) -> None:
        trades = (
            trade_event("t1", event_time_ns=T - 3 * ONE_SEC, price=100, quantity=10, aggressor_side="BUY"),
            trade_event("t2", event_time_ns=T - 2 * ONE_SEC, price=101, quantity=4, aggressor_side="SELL"),
            trade_event("t3", event_time_ns=T - ONE_SEC, price=102, quantity=6, aggressor_side="BUY"),
        )
        resolved = resolved_snapshot("snap-cvd-mix", events=trades)
        output = CvdCalculator().compute(_ctx(resolved))
        self.assertIsNotNone(output.signal)
        self.assertAlmostEqual(output.signal.value, 10.0 - 4.0 + 6.0)

    def test_unknown_trade_side_excluded(self) -> None:
        trades = (
            trade_event("t1", event_time_ns=T - 2 * ONE_SEC, price=100, quantity=10, aggressor_side="BUY"),
            trade_event("t2", event_time_ns=T - ONE_SEC, price=100, quantity=20),
        )
        resolved = resolved_snapshot("snap-unknown", events=trades)
        output = CvdCalculator().compute(_ctx(resolved))
        self.assertIsNotNone(output.signal)
        self.assertAlmostEqual(output.signal.value, 10.0)


class NetSignedShareTests(unittest.TestCase):
    def test_nss_positive_boundary(self) -> None:
        trades = tuple(
            trade_event(f"t{i}", event_time_ns=T - i * ONE_SEC, price=100, quantity=10, aggressor_side="BUY")
            for i in range(1, 6)
        )
        resolved = resolved_snapshot("snap-nss-pos", events=trades)
        output = NetSignedShareCalculator().compute(_ctx(resolved))
        self.assertIsNotNone(output.signal)
        self.assertAlmostEqual(output.signal.value, 1.0)

    def test_nss_negative_boundary(self) -> None:
        trades = tuple(
            trade_event(f"t{i}", event_time_ns=T - i * ONE_SEC, price=100, quantity=10, aggressor_side="SELL")
            for i in range(1, 6)
        )
        resolved = resolved_snapshot("snap-nss-neg", events=trades)
        output = NetSignedShareCalculator().compute(_ctx(resolved))
        self.assertIsNotNone(output.signal)
        self.assertAlmostEqual(output.signal.value, -1.0)

    def test_nss_zero_classified_volume_skipped(self) -> None:
        trades = (trade_event("t1", event_time_ns=T - ONE_SEC, price=100, quantity=10),)
        resolved = resolved_snapshot("snap-nss-zero", events=trades)
        output = NetSignedShareCalculator().compute(_ctx(resolved))
        self.assertIsNone(output.signal)
        self.assertEqual(output.diagnostic.code, ComputationDiagnosticCode.ZERO_DENOMINATOR)


class DepthImbalanceTests(unittest.TestCase):
    def test_balanced_depth_zero(self) -> None:
        book = book_event(
            "b1",
            event_time_ns=T,
            bids=[{"price": 100, "size": 100}],
            asks=[{"price": 100.1, "size": 100}],
        )
        resolved = resolved_snapshot("snap-depth-bal", events=(book,))
        output = DepthImbalanceCalculator().compute(_ctx(resolved))
        self.assertIsNotNone(output.signal)
        self.assertAlmostEqual(output.signal.value, 0.0)

    def test_bid_heavy_positive(self) -> None:
        book = book_event(
            "b1",
            event_time_ns=T,
            bids=[{"price": 100, "size": 300}],
            asks=[{"price": 100.1, "size": 100}],
        )
        resolved = resolved_snapshot("snap-depth-bid", events=(book,))
        output = DepthImbalanceCalculator().compute(_ctx(resolved))
        self.assertIsNotNone(output.signal)
        self.assertGreater(output.signal.value, 0)

    def test_zero_depth_skipped(self) -> None:
        book = book_event("b1", event_time_ns=T, bids=[], asks=[])
        resolved = resolved_snapshot("snap-depth-zero", events=(book,))
        output = DepthImbalanceCalculator().compute(_ctx(resolved))
        self.assertIsNone(output.signal)


class MomentumTests(unittest.TestCase):
    def test_momentum_positive(self) -> None:
        trades = (
            trade_event("t1", event_time_ns=T - 2 * ONE_SEC, price=100, quantity=1, aggressor_side="BUY"),
            trade_event("t2", event_time_ns=T - ONE_SEC, price=110, quantity=1, aggressor_side="BUY"),
        )
        resolved = resolved_snapshot("snap-mom-pos", events=trades)
        output = MomentumSimpleCalculator().compute(_ctx(resolved))
        self.assertIsNotNone(output.signal)
        self.assertAlmostEqual(output.signal.value, 0.10)

    def test_momentum_insufficient_data(self) -> None:
        trades = (trade_event("t1", event_time_ns=T - ONE_SEC, price=100, quantity=1, aggressor_side="BUY"),)
        resolved = resolved_snapshot("snap-mom-ins", events=trades)
        output = MomentumSimpleCalculator().compute(_ctx(resolved))
        self.assertIsNone(output.signal)
        self.assertEqual(output.diagnostic.code, ComputationDiagnosticCode.INSUFFICIENT_INPUT)


class RealizedVolTests(unittest.TestCase):
    def test_constant_price_zero_vol(self) -> None:
        trades = tuple(
            trade_event(f"t{i}", event_time_ns=T - (5 - i) * ONE_SEC, price=100, quantity=1, aggressor_side="BUY")
            for i in range(1, 6)
        )
        resolved = resolved_snapshot("snap-vol-const", events=trades)
        output = RealizedVolCalculator().compute(_ctx(resolved))
        self.assertIsNotNone(output.signal)
        self.assertAlmostEqual(output.signal.value, 0.0)

    def test_hand_computable_vol(self) -> None:
        prices = [100.0, 110.0, 99.0]
        trades = tuple(
            trade_event(f"t{i}", event_time_ns=T - (3 - i) * ONE_SEC, price=prices[i], quantity=1, aggressor_side="BUY")
            for i in range(3)
        )
        resolved = resolved_snapshot("snap-vol-hand", events=trades)
        output = RealizedVolCalculator().compute(_ctx(resolved))
        self.assertIsNotNone(output.signal)
        log_returns = [math.log(110 / 100), math.log(99 / 110)]
        mean = sum(log_returns) / 2
        variance = sum((ret - mean) ** 2 for ret in log_returns) / 1
        expected = math.sqrt(variance)
        self.assertAlmostEqual(output.signal.value, expected, places=10)


class RelativeVolumeTests(unittest.TestCase):
    def test_relative_volume_ratio(self) -> None:
        baseline = tuple(
            trade_event(
                f"b{i}",
                event_time_ns=T - WINDOW - i * ONE_SEC,
                price=100,
                quantity=10,
                aggressor_side="BUY",
            )
            for i in range(1, 6)
        )
        current = tuple(
            trade_event(
                f"c{i}",
                event_time_ns=T - i * ONE_SEC,
                price=100,
                quantity=20,
                aggressor_side="BUY",
            )
            for i in range(1, 6)
        )
        resolved = resolved_snapshot("snap-rvol", events=baseline + current)
        output = RelativeVolumeCalculator().compute(_ctx(resolved))
        self.assertIsNotNone(output.signal)
        self.assertAlmostEqual(output.signal.value, 2.0)

    def test_zero_baseline_skipped(self) -> None:
        current = (trade_event("c1", event_time_ns=T - ONE_SEC, price=100, quantity=10, aggressor_side="BUY"),)
        resolved = resolved_snapshot("snap-rvol-zero", events=current)
        output = RelativeVolumeCalculator().compute(_ctx(resolved))
        self.assertIsNone(output.signal)
        self.assertEqual(output.diagnostic.code, ComputationDiagnosticCode.ZERO_DENOMINATOR)


class DegradedSnapshotTests(unittest.TestCase):
    def test_degraded_snapshot_preserves_quality(self) -> None:
        quote = quote_event("q1", event_time_ns=T, bid=100, ask=100.10)
        degraded = QualitySummary(state=QualityState.DEGRADED, flags=("degraded",))
        resolved = resolved_snapshot("snap-degraded", events=(quote,), quality=degraded)
        output = SpreadAbsCalculator().compute(_ctx(resolved))
        self.assertIsNotNone(output.signal)
        self.assertEqual(output.signal.quality.state, QualityState.DEGRADED)


if __name__ == "__main__":
    unittest.main()
