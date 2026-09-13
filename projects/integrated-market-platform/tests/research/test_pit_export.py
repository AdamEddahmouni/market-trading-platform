"""PIT-A-001 unified research export manifest tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.research.dataset_manifest import build_dataset_manifest, materialize_dataset_rows
from market_platform_foundation.research.pit_export import (
    build_research_export_from_events,
    build_research_export_from_rows,
    build_research_export_manifest,
    research_export_fingerprint,
)


def _synthetic_events(count: int = 4) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    base = 2_000_000_000_000_000_000
    for index in range(count):
        available = base + index * 60_000_000_000
        events.append(
            {
                "available_time": available,
                "bar_payload": {"close": str(100 + index)},
                "event_type": "BAR_OHLCV_1M",
                "instrument_id": "EQ-1",
            }
        )
    return events


class PitExportManifestTests(unittest.TestCase):
    def test_export_fingerprint_stable(self) -> None:
        rows = materialize_dataset_rows(_synthetic_events(4))
        manifest_a = build_research_export_from_rows(
            rows,
            source_sha256="a" * 64,
            prediction_cutoff_ns=2_000_000_000_000_000_000,
            experiment_binding={
                "binding_kind": "DECISION_RESEARCH_CARD",
                "experiment_id": "SS-BASE",
                "card_hash": "b" * 64,
            },
        )
        manifest_b = build_research_export_from_rows(
            rows,
            source_sha256="a" * 64,
            prediction_cutoff_ns=2_000_000_000_000_000_000,
            experiment_binding={
                "binding_kind": "DECISION_RESEARCH_CARD",
                "experiment_id": "SS-BASE",
                "card_hash": "b" * 64,
            },
        )
        self.assertEqual(manifest_a["export_fingerprint"], manifest_b["export_fingerprint"])
        self.assertEqual(
            manifest_a["export_fingerprint"],
            research_export_fingerprint(manifest_a),
        )

    def test_cutoff_change_changes_fingerprint(self) -> None:
        rows = materialize_dataset_rows(_synthetic_events(2))
        base = build_research_export_from_rows(
            rows,
            source_sha256="c" * 64,
            prediction_cutoff_ns=100,
        )
        shifted = build_research_export_from_rows(
            rows,
            source_sha256="c" * 64,
            prediction_cutoff_ns=101,
        )
        self.assertNotEqual(base["export_fingerprint"], shifted["export_fingerprint"])

    def test_events_path_binds_dataset_hashes(self) -> None:
        events = _synthetic_events(3)
        export_manifest = build_research_export_from_events(
            events,
            source_sha256="d" * 64,
            prediction_cutoff_ns=int(events[-1]["available_time"]),
            experiment_binding={"binding_kind": "FTEP_CAMPAIGN", "campaign_slug": "FTEP-V1-001"},
        )
        dataset_summary = export_manifest["dataset_manifest"]
        self.assertIsInstance(dataset_summary["dataset_fingerprint"], str)
        self.assertGreater(int(dataset_summary["row_count"]), 0)
        self.assertEqual(export_manifest["experiment_binding"]["campaign_slug"], "FTEP-V1-001")

    def test_invalid_source_sha_fails_closed(self) -> None:
        rows = materialize_dataset_rows(_synthetic_events(1))
        dataset_manifest = build_dataset_manifest(rows)
        with self.assertRaises(ValueError):
            build_research_export_manifest(
                dataset_manifest,
                source_sha256="not-a-hash",
                prediction_cutoff_ns=1,
            )
