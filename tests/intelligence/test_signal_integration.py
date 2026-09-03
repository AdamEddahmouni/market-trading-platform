"""Full BUILD 01–06 intelligence lifecycle integration test."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence import (  # noqa: E402
    eligible_as_of,
    require_temporally_usable,
)
from market_platform_foundation.intelligence.normalization import (  # noqa: E402
    IngestionMode,
    NormalizationContext,
    require_normalized_event,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository  # noqa: E402
from market_platform_foundation.intelligence.quality import assess_capabilities, RequirementSet  # noqa: E402
from market_platform_foundation.intelligence.signals import (  # noqa: E402
    FastSignalEngine,
    SignalComputationRequest,
    compute_from_snapshot,
)
from market_platform_foundation.intelligence.snapshots import (  # noqa: E402
    SnapshotBuildRequest,
    SnapshotCompositionPolicy,
    build_snapshot,
    resolve_snapshot,
)
from tests.intelligence.test_snapshot_fixtures import INSTRUMENT, SCOPE, T  # noqa: E402

FIVE_SEC = 5 * 1_000_000_000
WINDOW = 300 * 1_000_000_000


def _moomoo_quote_fixture(event_time_ns: int) -> dict:
    return {
        "provider": "moomoo.opend.observational",
        "capability": "QUOTE",
        "provider_symbol": "US.NVDA",
        "sequence": 42,
        "clocks": {
            "event_time_ns": event_time_ns,
            "provider_time_ns": event_time_ns + 5_000_000,
            "received_time_ns": event_time_ns + FIVE_SEC,
        },
        "raw_payload": {
            "bid_price": 100.0,
            "ask_price": 100.10,
            "bid_vol": 500,
            "ask_vol": 400,
        },
    }


def _moomoo_trade_fixture(event_time_ns: int, *, sequence: int, side: str, qty: float) -> dict:
    return {
        "provider": "moomoo.opend.observational",
        "capability": "TICKER",
        "provider_symbol": "US.NVDA",
        "sequence": sequence,
        "clocks": {
            "event_time_ns": event_time_ns,
            "provider_time_ns": event_time_ns + 1_000_000,
            "received_time_ns": event_time_ns + FIVE_SEC,
        },
        "raw_payload": {
            "price": 100.0 + sequence * 0.01,
            "volume": qty,
            "ticker_direction": side,
        },
    }


class SignalIntegrationTests(unittest.TestCase):
    def test_full_build_01_to_06_lifecycle(self) -> None:
        decision_time = T + 30 * 1_000_000_000
        ctx = NormalizationContext(
            received_time_ns=decision_time,
            ingestion_mode=IngestionMode.LIVE_OBSERVED,
        )
        quote = require_normalized_event(
            _moomoo_quote_fixture(T + 2 * 1_000_000_000),
            context=ctx,
            source_key="moomoo.capture",
        )
        trades = []
        for index in range(12):
            event_time = T + (3 + index) * 1_000_000_000
            side = "BUY" if index % 2 == 0 else "SELL"
            trades.append(
                require_normalized_event(
                    _moomoo_trade_fixture(event_time, sequence=index + 1, side=side, qty=10),
                    context=ctx,
                    source_key="moomoo.capture",
                )
            )

        for event in (quote, *trades):
            require_temporally_usable(event, decision_time_ns=decision_time)
            self.assertIn(event, eligible_as_of([event], decision_time))

        repo = InMemoryIntelligenceRepository()
        for event in (quote, *trades):
            repo.put_event(event)

        quality = assess_capabilities(
            events=[quote, *trades],
            decision_time_ns=decision_time,
            requirements=RequirementSet(),
        )
        request = SnapshotBuildRequest(
            decision_time_ns=decision_time,
            scope=SCOPE,
            composition_policy=SnapshotCompositionPolicy(max_events=50, max_signals=5),
            capability_requirements=RequirementSet(),
        )
        built = build_snapshot(repo, request, quality_decision=quality)
        self.assertTrue(built.snapshot.snapshot_id.startswith("SNAP-"))
        repo.put_snapshot(built.snapshot)

        resolved = resolve_snapshot(built.snapshot, repo)
        signal_request = SignalComputationRequest(
            window_ns=WINDOW,
            signal_types=frozenset({"spread_abs", "spread_bps", "cvd", "net_signed_share"}),
            persist=True,
        )
        result = compute_from_snapshot(built.snapshot, repo, signal_request)
        self.assertGreaterEqual(len(result.signals), 3)
        for signal in result.signals:
            self.assertTrue(signal.signal_id.startswith("SIG-"))
            self.assertIsNotNone(signal.source_snapshot_ref)
            self.assertEqual(signal.source_snapshot_ref.id, built.snapshot.snapshot_id)
            self.assertEqual(signal.as_of_time_ns, decision_time)
            reloaded = repo.get_signal(signal.signal_id)
            self.assertIsNotNone(reloaded)
            self.assertAlmostEqual(reloaded.value, signal.value)

        spread = next(row for row in result.signals if row.signal_type == "spread_abs")
        self.assertAlmostEqual(spread.value, 0.10)

        engine = FastSignalEngine()
        replay = engine.compute_and_persist(
            resolved,
            repo,
            SignalComputationRequest(
                window_ns=WINDOW,
                signal_types=frozenset({"spread_abs"}),
                persist=True,
            ),
        )
        self.assertEqual(replay.signals[0].signal_id, spread.signal_id)


if __name__ == "__main__":
    unittest.main()
