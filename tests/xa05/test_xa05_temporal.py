"""XA-05 temporal and PIT exclusion tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.xa02.fixtures import admit_fixture as admit_xa02_fixture
from market_platform_foundation.xa03.fixtures import admit_fixture as admit_xa03_fixture
from market_platform_foundation.xa04.adapters import persist_all_registries
from market_platform_foundation.xa05.engine import CrossAssetStateEngine

from tests.xa04.test_xa04_fixtures import build_vertical_slice_state
from tests.xa05.test_xa05_fixtures import populate_repository


class Xa05TemporalTests(unittest.TestCase):
    def test_later_fred_revision_excluded_from_earlier_state(self) -> None:
        state = build_vertical_slice_state()
        xa02 = state["xa02_registry"]  # type: ignore[assignment]
        admit_xa02_fixture(fixture_name="rates_revision_sequence.json", registry=xa02)
        repo, _ = populate_repository()
        persist_all_registries(
            repo,
            xa01_registry=state["xa01_registry"],  # type: ignore[arg-type]
            xa02_registry=xa02,
            xa03_registry=state["xa03_registry"],  # type: ignore[arg-type]
        )
        engine = CrossAssetStateEngine(repo)
        early = engine.construct_state(
            decision_time="2020-02-01T00:00:00Z",
            construction_time="2020-02-01T00:00:00Z",
        )
        late = engine.construct_state(
            decision_time="2020-03-20T00:00:00Z",
            construction_time="2020-03-20T00:00:00Z",
        )
        early_values = {
            repo.get_scalar_observation(ref.observation_id).normalized_value
            for ref in early.evidence_references
            if repo.get_scalar_observation(ref.observation_id) is not None
        }
        late_values = {
            repo.get_scalar_observation(ref.observation_id).normalized_value
            for ref in late.evidence_references
            if repo.get_scalar_observation(ref.observation_id) is not None
        }
        self.assertIn(1.88, early_values)
        self.assertIn(1.80, late_values)
        self.assertNotIn(1.80, early_values)
        self.assertNotEqual(early.provenance.semantic_fingerprint, late.provenance.semantic_fingerprint)

    def test_later_cftc_correction_excluded_from_earlier_state(self) -> None:
        state = build_vertical_slice_state()
        xa03 = state["xa03_registry"]  # type: ignore[assignment]
        admit_xa03_fixture(fixture_name="source_revision.json", registry=xa03)
        repo, _ = populate_repository()
        persist_all_registries(
            repo,
            xa01_registry=state["xa01_registry"],  # type: ignore[arg-type]
            xa02_registry=state["xa02_registry"],  # type: ignore[arg-type]
            xa03_registry=xa03,
        )
        engine = CrossAssetStateEngine(repo)
        early = engine.construct_state(
            decision_time="2026-08-14T20:00:00Z",
            construction_time="2026-08-14T20:00:00Z",
        )
        late = engine.construct_state(
            decision_time="2026-08-15T20:00:00Z",
            construction_time="2026-08-15T20:00:00Z",
        )
        early_ids = {ref.observation_id for ref in early.evidence_references}
        late_ids = {ref.observation_id for ref in late.evidence_references}
        self.assertTrue(late_ids - early_ids)
        self.assertNotEqual(early.provenance.semantic_fingerprint, late.provenance.semantic_fingerprint)


if __name__ == "__main__":
    unittest.main()
