"""Full BUILD 01–05 snapshot composition integration test."""

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
from market_platform_foundation.intelligence.snapshots import (  # noqa: E402
    SnapshotBuildRequest,
    SnapshotCompositionPolicy,
    build_snapshot,
    resolve_snapshot,
    verify_snapshot_integrity,
)
from tests.intelligence.test_snapshot_fixtures import INSTRUMENT, SCOPE, T  # noqa: E402

FIVE_SEC = 5 * 1_000_000_000


def _moomoo_quote_fixture() -> dict:
    return {
        "provider": "moomoo.opend.observational",
        "capability": "QUOTE",
        "provider_symbol": "US.NVDA",
        "sequence": 42,
        "clocks": {
            "event_time_ns": T,
            "provider_time_ns": T + 5_000_000,
            "received_time_ns": T + FIVE_SEC,
        },
        "raw_payload": {
            "bid_price": 100.0,
            "ask_price": 100.05,
            "bid_vol": 500,
            "ask_vol": 400,
        },
    }


class SnapshotIntegrationTests(unittest.TestCase):
    def test_full_build_01_to_05_lifecycle(self) -> None:
        ctx = NormalizationContext(received_time_ns=T + FIVE_SEC, ingestion_mode=IngestionMode.LIVE_OBSERVED)
        event = require_normalized_event(_moomoo_quote_fixture(), context=ctx, source_key="moomoo.capture")
        decision_time = T + 6 * 1_000_000_000
        require_temporally_usable(event, decision_time_ns=decision_time)
        self.assertIn(event, eligible_as_of([event], decision_time))

        repo = InMemoryIntelligenceRepository()
        repo.put_event(event)

        quality = assess_capabilities(
            events=[event],
            decision_time_ns=decision_time,
            requirements=RequirementSet(),
        )

        request = SnapshotBuildRequest(
            decision_time_ns=decision_time,
            scope=SCOPE,
            composition_policy=SnapshotCompositionPolicy(max_events=10, max_signals=5),
            capability_requirements=RequirementSet(),
        )
        built = build_snapshot(repo, request, quality_decision=quality)
        self.assertTrue(built.snapshot.snapshot_id.startswith("SNAP-"))
        self.assertEqual(repo.get_snapshot(built.snapshot.snapshot_id).snapshot_id, built.snapshot.snapshot_id)

        resolved = resolve_snapshot(built.snapshot, repo)
        self.assertEqual(len(resolved.events), 1)
        self.assertEqual(resolved.events[0].event_id, event.event_id)
        verify_snapshot_integrity(built.snapshot, repo)


if __name__ == "__main__":
    unittest.main()
