"""BUILD 06 engine, identity, and persistence tests."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.contracts import (  # noqa: E402
    QualityState,
    QualitySummary,
    signal_v1_from_dict,
    signal_v1_to_dict,
)
from market_platform_foundation.intelligence.persistence import (  # noqa: E402
    InMemoryIntelligenceRepository,
    RepositoryConflictError,
    RepositoryPutResult,
)
from market_platform_foundation.intelligence.signals import (  # noqa: E402
    FastSignalEngine,
    SignalComputationRequest,
    compute_fast_signals,
    derive_signal_id,
)
from market_platform_foundation.intelligence.signals.calculators.spread import SpreadAbsCalculator  # noqa: E402
from market_platform_foundation.intelligence.signals.errors import SignalComputationError  # noqa: E402
from market_platform_foundation.intelligence.snapshots.resolver import SnapshotResolvedState  # noqa: E402
from tests.intelligence.test_persistence_fixtures import SCOPE  # noqa: E402
from tests.intelligence.test_signal_fixtures import (  # noqa: E402
    ONE_SEC,
    T,
    WINDOW,
    quote_event,
    resolved_snapshot,
    trade_event,
)


class SignalIdentityTests(unittest.TestCase):
    def test_same_snapshot_same_signal_id(self) -> None:
        resolved = resolved_snapshot(
            "snap-id-1",
            events=(quote_event("q1", event_time_ns=T, bid=100, ask=100.10),),
        )
        request = SignalComputationRequest(
            window_ns=WINDOW,
            signal_types=frozenset({"spread_abs"}),
        )
        first = compute_fast_signals(resolved, request)
        second = compute_fast_signals(resolved, request)
        self.assertEqual(first.signals[0].signal_id, second.signals[0].signal_id)
        self.assertAlmostEqual(first.signals[0].value, second.signals[0].value)

    def test_window_change_changes_id(self) -> None:
        resolved = resolved_snapshot(
            "snap-id-2",
            events=(
                trade_event("t1", event_time_ns=T - ONE_SEC, price=100, quantity=10, aggressor_side="BUY"),
                trade_event("t2", event_time_ns=T, price=101, quantity=10, aggressor_side="BUY"),
            ),
        )
        short = compute_fast_signals(
            resolved,
            SignalComputationRequest(window_ns=60 * ONE_SEC, signal_types=frozenset({"cvd"})),
        )
        long_window = compute_fast_signals(
            resolved,
            SignalComputationRequest(window_ns=WINDOW, signal_types=frozenset({"cvd"})),
        )
        self.assertNotEqual(short.signals[0].signal_id, long_window.signals[0].signal_id)

    def test_calculator_version_in_lineage(self) -> None:
        resolved = resolved_snapshot(
            "snap-id-3",
            events=(quote_event("q1", event_time_ns=T, bid=100, ask=100.10),),
        )
        result = compute_fast_signals(
            resolved,
            SignalComputationRequest(signal_types=frozenset({"spread_abs"})),
        )
        lineage = result.signals[0].calculation_lineage
        self.assertEqual(lineage["calculator_id"], "spread-calculator")
        self.assertEqual(lineage["calculator_version"], "1")

    def test_derive_signal_id_excludes_value(self) -> None:
        id_a = derive_signal_id(
            source_snapshot_id="SNAP-abc",
            signal_type="spread_abs",
            scope=SCOPE,
            window_ns=None,
            calculator_id="spread-calculator",
            calculator_version="1",
        )
        id_b = derive_signal_id(
            source_snapshot_id="SNAP-abc",
            signal_type="spread_abs",
            scope=SCOPE,
            window_ns=None,
            calculator_id="spread-calculator",
            calculator_version="1",
        )
        self.assertEqual(id_a, id_b)


class EngineOrchestrationTests(unittest.TestCase):
    def test_input_order_independence(self) -> None:
        trades = (
            trade_event("t1", event_time_ns=T - 3 * ONE_SEC, price=100, quantity=10, aggressor_side="BUY"),
            trade_event("t2", event_time_ns=T - 2 * ONE_SEC, price=101, quantity=4, aggressor_side="SELL"),
            trade_event("t3", event_time_ns=T - ONE_SEC, price=102, quantity=6, aggressor_side="BUY"),
        )
        resolved_ordered = resolved_snapshot("snap-order-1", events=trades)
        resolved_shuffled = resolved_snapshot(
            "snap-order-2",
            events=(trades[2], trades[0], trades[1]),
        )
        request = SignalComputationRequest(signal_types=frozenset({"cvd"}))
        ordered = compute_fast_signals(resolved_ordered, request).signals[0].value
        shuffled = compute_fast_signals(resolved_shuffled, request).signals[0].value
        self.assertAlmostEqual(ordered, shuffled)

    def test_invalid_snapshot_rejected(self) -> None:
        resolved = resolved_snapshot(
            "snap-invalid",
            events=(quote_event("q1", event_time_ns=T),),
            quality=QualitySummary(state=QualityState.INVALID),
        )
        result = compute_fast_signals(resolved, SignalComputationRequest())
        self.assertEqual(len(result.signals), 0)

    def test_require_all_fails_on_skip(self) -> None:
        resolved = resolved_snapshot("snap-req-all", events=())
        with self.assertRaises(SignalComputationError):
            compute_fast_signals(
                resolved,
                SignalComputationRequest(signal_types=frozenset({"spread_abs"}), require_all=True),
            )

    def test_best_effort_reports_skipped(self) -> None:
        resolved = resolved_snapshot("snap-best", events=())
        result = compute_fast_signals(
            resolved,
            SignalComputationRequest(signal_types=frozenset({"spread_abs"})),
        )
        self.assertIn("spread_abs", result.skipped_signal_types)

    def test_signal_round_trip(self) -> None:
        resolved = resolved_snapshot(
            "snap-rt",
            events=(quote_event("q1", event_time_ns=T, bid=100, ask=100.10),),
        )
        signal = compute_fast_signals(
            resolved,
            SignalComputationRequest(signal_types=frozenset({"spread_abs"})),
        ).signals[0]
        restored = signal_v1_from_dict(signal_v1_to_dict(signal))
        self.assertEqual(signal.signal_id, restored.signal_id)
        self.assertAlmostEqual(signal.value, restored.value)


class PersistenceTests(unittest.TestCase):
    def test_persist_idempotent(self) -> None:
        repo = InMemoryIntelligenceRepository()
        resolved = resolved_snapshot(
            "snap-persist",
            events=(quote_event("q1", event_time_ns=T, bid=100, ask=100.10),),
        )
        request = SignalComputationRequest(signal_types=frozenset({"spread_abs"}), persist=True)
        engine = FastSignalEngine()
        first = engine.compute_and_persist(resolved, repo, request)
        second = engine.compute_and_persist(resolved, repo, request)
        self.assertEqual(first.signals[0].signal_id, second.signals[0].signal_id)
        self.assertEqual(repo.put_signal(first.signals[0]), RepositoryPutResult.ALREADY_PRESENT)

    def test_nondeterminism_conflict(self) -> None:
        repo = InMemoryIntelligenceRepository()
        resolved = resolved_snapshot(
            "snap-conflict",
            events=(quote_event("q1", event_time_ns=T, bid=100, ask=100.10),),
        )
        signal = compute_fast_signals(
            resolved,
            SignalComputationRequest(signal_types=frozenset({"spread_abs"})),
        ).signals[0]
        repo.put_signal(signal)
        mutated = copy.deepcopy(signal)
        object.__setattr__(mutated, "value", signal.value + 1.0)
        with self.assertRaises(RepositoryConflictError):
            repo.put_signal(mutated)

    def test_snapshot_not_mutated(self) -> None:
        resolved = resolved_snapshot(
            "snap-immutable",
            events=(quote_event("q1", event_time_ns=T, bid=100, ask=100.10),),
        )
        before_refs = len(resolved.snapshot.source_event_refs)
        compute_fast_signals(
            resolved,
            SignalComputationRequest(signal_types=frozenset({"spread_abs", "spread_bps"})),
        )
        self.assertEqual(len(resolved.snapshot.source_event_refs), before_refs)


if __name__ == "__main__":
    unittest.main()
