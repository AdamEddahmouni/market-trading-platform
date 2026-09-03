"""XA-04 idempotency and conflict tests."""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.xa04 import RepositoryConflictError, RepositoryPutResult  # noqa: E402
from market_platform_foundation.xa04.memory import InMemoryCrossAssetCatalogRepository  # noqa: E402
from tests.xa04.test_xa04_fixtures import populate_vertical_slice_repository  # noqa: E402


class Xa04IdempotencyConflictTests(unittest.TestCase):
    def test_duplicate_relationship_idempotent(self) -> None:
        repo, state = populate_vertical_slice_repository()
        relationships = repo.list_cross_asset_relationships_for_target(str(state["gc_canonical_id"]))
        self.assertTrue(relationships)
        rel = relationships[0]
        self.assertEqual(repo.put_cross_asset_relationship(rel), RepositoryPutResult.ALREADY_PRESENT)

    def test_duplicate_scalar_observation_idempotent(self) -> None:
        repo, state = populate_vertical_slice_repository()
        obs_id = state["fred"]["observation_ids"][0]  # type: ignore[index]
        obs = repo.get_scalar_observation(obs_id)
        assert obs is not None
        self.assertEqual(repo.put_scalar_observation(obs), RepositoryPutResult.ALREADY_PRESENT)

    def test_changed_relationship_conflicts(self) -> None:
        repo, state = populate_vertical_slice_repository()
        relationships = repo.list_cross_asset_relationships_for_target(str(state["gc_canonical_id"]))
        rel = relationships[0]
        mutated = replace(rel, provenance_ref="mutated")
        with self.assertRaises(RepositoryConflictError):
            repo.put_cross_asset_relationship(mutated)


if __name__ == "__main__":
    unittest.main()
