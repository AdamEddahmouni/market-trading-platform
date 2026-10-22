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
    def test_latest_scalar_exceeds_oldest_thousand_without_future_or_missing(self) -> None:
        from dataclasses import replace
        state = build_vertical_slice_state()
        repo = InMemoryCrossAssetCatalogRepository()
        persist_all_registries(repo, xa01_registry=state["xa01_registry"],
                               xa02_registry=state["xa02_registry"], xa03_registry=state["xa03_registry"])
        original = repo.list_scalar_observations_for_indicator("US_10Y_TREASURY_YIELD")[0]
        for index in range(1001):
            repo.put_scalar_observation(replace(original, observation_id=f"latest-{index:04}",
                available_time=f"2026-10-01T{index // 3600:02}:{index // 60 % 60:02}:{index % 60:02}Z"))
        repo.put_scalar_observation(replace(original, observation_id="missing",
            available_time="2026-10-02T00:00:00Z", normalized_value=None))
        repo.put_scalar_observation(replace(original, observation_id="future",
            available_time="2026-10-04T00:00:00Z"))
        latest = repo.latest_scalar_observation_as_of("2026-10-03T00:00:00Z",
            canonical_indicator_id=original.canonical_indicator_id)
        self.assertEqual(latest.observation_id, "latest-1000")
        self.assertIsNone(repo.latest_scalar_observation_as_of("2020-01-01T00:00:00Z",
            canonical_indicator_id=original.canonical_indicator_id))

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
