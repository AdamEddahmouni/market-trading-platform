"""Precomputed edge-stats catalog hardening (runtime path, not test fixtures)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.canonical import load_json_strict
from market_platform_foundation.research.edge_stats.precomputed_catalog import (
    list_precomputed_edge_stats_artifacts,
    runtime_precomputed_catalog_path,
)

FIXTURE = ROOT / "tests" / "fixtures" / "research" / "edge_stats_golden_artifact.json"


class EdgeStatsPrecomputedCatalogTests(unittest.TestCase):
    def test_runtime_catalog_matches_golden_fixture_bytes(self) -> None:
        catalog_path = runtime_precomputed_catalog_path()
        self.assertEqual(catalog_path.read_bytes(), FIXTURE.read_bytes())

    def test_catalog_artifact_pit_class_is_historical(self) -> None:
        artifact = list_precomputed_edge_stats_artifacts()[0]
        self.assertEqual(artifact.get("pit_class"), "HISTORICAL_BAR_END_PIT")
        self.assertEqual(artifact.get("authority_class"), "EVIDENCE_NOT_PREDICTION")

    def test_catalog_content_sha256_matches_fixture(self) -> None:
        expected = load_json_strict(FIXTURE)
        loaded = list_precomputed_edge_stats_artifacts()[0]
        self.assertEqual(loaded.get("content_sha256"), expected.get("content_sha256"))


if __name__ == "__main__":
    unittest.main()
