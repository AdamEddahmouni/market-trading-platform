"""Phase 5R research/model infrastructure tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.research.baseline_naive import NaiveLastValueModel
from market_platform_foundation.research.dataset_manifest import build_dataset_manifest, materialize_dataset_rows
from market_platform_foundation.research.evaluation import evaluation_root_hash, run_walk_forward_evaluation
from market_platform_foundation.research.forecast import verify_forecast_interface
from market_platform_foundation.research.targets import build_target_rows, verify_label_availability
from market_platform_foundation.research.serialization import artifacts_equal, load_artifact, serialize_artifact


def _synthetic_events(count: int = 6) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    base = 2000000000000000000
    for index in range(count):
        available = base + index * 60_000_000_000
        events.append(
            {
                "available_time": available,
                "bar_payload": {
                    "close": str(100 + index),
                    "high": str(101 + index),
                    "low": str(99 + index),
                    "open": str(100 + index),
                    "timeframe": "1_MINUTE",
                    "volume": 100 + index,
                },
                "channel_id": "EQ-1",
                "event_time": available - 1,
                "event_type": "BAR_OHLCV_1M",
                "historical_ingested_time": available,
                "ingest_run_id": "RUN-SYNTH",
                "instrument_id": "EQ-1",
                "normalization_version": "test/1.0.0",
                "normalized_event_id": f"evt-{index}",
                "operation": "UPSERT",
                "publisher_id": "PUB-1",
                "quality_observation_refs": [],
                "raw_reference": f"test://{index}",
                "schema_version": "1.0.0",
                "source_instance_id": "SRC-1",
                "source_record_id": f"REC-{index}",
                "source_revision_id": "1",
                "venue_id": "VEN-1",
            }
        )
    return events


class ResearchTests(unittest.TestCase):
    def test_dataset_manifest_fingerprint_stable(self) -> None:
        rows = materialize_dataset_rows(_synthetic_events())
        manifest_a = build_dataset_manifest(rows)
        manifest_b = build_dataset_manifest(rows)
        self.assertEqual(manifest_a["dataset_fingerprint"], manifest_b["dataset_fingerprint"])
        self.assertEqual(len(rows), 6)

    def test_label_availability_passes(self) -> None:
        rows = materialize_dataset_rows(_synthetic_events())
        targets = build_target_rows(rows)
        status, reasons = verify_label_availability(targets)
        self.assertEqual(status, "PASS")
        self.assertEqual(reasons, [])

    def test_walk_forward_evaluation_deterministic(self) -> None:
        events = _synthetic_events(8)
        result_a = run_walk_forward_evaluation(events)
        result_b = run_walk_forward_evaluation(events)
        self.assertEqual(evaluation_root_hash(result_a), evaluation_root_hash(result_b))
        self.assertGreater(result_a["fold_count"], 0)
        self.assertEqual(result_a["label_status"], "PASS")

    def test_naive_model_forecast_interface(self) -> None:
        model = NaiveLastValueModel()
        model.fit([{"instrument_id": "EQ-1", "value": "10"}])
        forecast = model.predict(
            {"instrument_id": "EQ-1", "prediction_cutoff": 100, "observation_time": 100},
            horizon_ns=60_000_000_000,
        )
        status, _ = verify_forecast_interface(forecast)
        self.assertEqual(status, "PASS")
        self.assertIsNone(forecast["probability"])

    def test_artifact_round_trip(self) -> None:
        import tempfile
        from pathlib import Path

        model = NaiveLastValueModel()
        model.fit([{"instrument_id": "EQ-1", "value": "42"}])
        artifact = model.artifact_body(dataset_fingerprint="fp-1")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.json"
            serialize_artifact(path, artifact)
            loaded = load_artifact(path)
        self.assertTrue(artifacts_equal(artifact, loaded))


if __name__ == "__main__":
    unittest.main()
