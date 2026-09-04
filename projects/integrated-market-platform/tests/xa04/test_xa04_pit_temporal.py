"""XA-04 PIT and temporal query tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.xa04.memory import InMemoryCrossAssetCatalogRepository  # noqa: E402
from tests.xa04.test_xa04_fixtures import build_vertical_slice_state  # noqa: E402
from market_platform_foundation.xa04.adapters import persist_all_registries  # noqa: E402
from market_platform_foundation.xa02.fixtures import admit_fixture  # noqa: E402


class Xa04PitTemporalTests(unittest.TestCase):
    def test_future_available_scalar_observation_excluded(self) -> None:
        state = build_vertical_slice_state()
        repo = InMemoryCrossAssetCatalogRepository()
        persist_all_registries(
            repo,
            xa01_registry=state["xa01_registry"],  # type: ignore[arg-type]
            xa02_registry=state["xa02_registry"],  # type: ignore[arg-type]
            xa03_registry=state["xa03_registry"],  # type: ignore[arg-type]
        )
        admit_fixture(
            fixture_name="rates_revision_sequence.json",
            registry=state["xa02_registry"],  # type: ignore[arg-type]
        )
        persist_all_registries(
            repo,
            xa01_registry=state["xa01_registry"],  # type: ignore[arg-type]
            xa02_registry=state["xa02_registry"],  # type: ignore[arg-type]
            xa03_registry=state["xa03_registry"],  # type: ignore[arg-type]
        )
        early = repo.query_scalar_observations_as_of("2020-01-01T00:00:00Z")
        self.assertEqual(early, ())

    def test_revision_rows_do_not_collapse(self) -> None:
        state = build_vertical_slice_state()
        xa02 = state["xa02_registry"]  # type: ignore[assignment]
        admit_fixture(fixture_name="rates_revision_sequence.json", registry=xa02)
        repo = InMemoryCrossAssetCatalogRepository()
        persist_all_registries(
            repo,
            xa01_registry=state["xa01_registry"],  # type: ignore[arg-type]
            xa02_registry=xa02,
            xa03_registry=state["xa03_registry"],  # type: ignore[arg-type]
        )
        rows = repo.list_scalar_observations_for_indicator("US_10Y_TREASURY_YIELD")
        self.assertGreaterEqual(len(rows), 2)


if __name__ == "__main__":
    unittest.main()
