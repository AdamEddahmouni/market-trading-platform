"""Phase 5 capability-supported feature tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.features.bar_features import BAR_FEATURE_IDS, derive_bar_features
from market_platform_foundation.features.institutional import WHALE_FAMILIES, query_all_institutional
from market_platform_foundation.features.snapshot import build_feature_snapshot
from market_platform_foundation.replay.feature_lifecycle import (
    run_feature_replay,
    run_feature_root_hash,
    verify_capability_surface,
    verify_pit_surface,
)


class FeatureTests(unittest.TestCase):
    def test_bar_features_respect_cutoff(self) -> None:
        bars = {
            "EQ-1": {
                "available_time": 100,
                "bar_payload": {
                    "close": "10",
                    "high": "11",
                    "low": "9",
                    "open": "10",
                    "volume": 100,
                },
                "normalized_event_id": "evt-1",
            }
        }
        features, reasons = derive_bar_features(bars, prediction_cutoff=100)
        self.assertEqual(reasons, [])
        self.assertEqual(len(features), len(BAR_FEATURE_IDS))
        features_future, reasons_future = derive_bar_features(bars, prediction_cutoff=99)
        self.assertEqual(features_future, [])
        self.assertIn("PIT_FEATURE_FUTURE_INPUT", reasons_future)

    def test_institutional_families_unavailable(self) -> None:
        rows = query_all_institutional(prediction_cutoff=100)
        self.assertEqual(len(rows), len(WHALE_FAMILIES))
        self.assertTrue(all(row["status"] == "unavailable" for row in rows))

    def test_feature_replay_deterministic(self) -> None:
        event = {
            "available_time": 100,
            "bar_payload": {
                "close": "10",
                "high": "11",
                "low": "9",
                "open": "10",
                "volume": 100,
            },
            "channel_id": "CH-1",
            "event_time": 99,
            "event_type": "BAR_OHLCV_1M",
            "historical_ingested_time": 100,
            "ingest_run_id": "RUN-1",
            "instrument_id": "EQ-1",
            "normalization_version": "test/1.0.0",
            "normalized_event_id": "evt-1",
            "operation": "UPSERT",
            "publisher_id": "PUB-1",
            "quality_observation_refs": [],
            "raw_reference": "test://bar",
            "schema_version": "1.0.0",
            "source_instance_id": "SRC-1",
            "source_record_id": "REC-1",
            "source_revision_id": "1",
            "venue_id": "VEN-1",
        }
        state_a = run_feature_replay([event], clocks=[100], decision_times=[100], prediction_cutoff=100)
        state_b = run_feature_replay([event], clocks=[100], decision_times=[100], prediction_cutoff=100)
        self.assertEqual(run_feature_root_hash(state_a), run_feature_root_hash(state_b))
        snapshot = build_feature_snapshot(
            prediction_cutoff=100,
            bar_features=state_a.feature_snapshots[0]["bar_features"],
            institutional_evidence=state_a.feature_snapshots[0]["institutional_evidence"],
        )
        cap_status, _ = verify_capability_surface(snapshot)
        pit_status, _ = verify_pit_surface(snapshot)
        self.assertEqual(cap_status, "PASS")
        self.assertEqual(pit_status, "PASS")


if __name__ == "__main__":
    unittest.main()
