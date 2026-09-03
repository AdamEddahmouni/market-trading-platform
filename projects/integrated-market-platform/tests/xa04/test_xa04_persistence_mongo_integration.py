"""Opt-in Mongo integration tests for XA catalog persistence (IMP-XA-04)."""

from __future__ import annotations

import os
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.xa04.mongo import (  # noqa: E402
    MongoCatalogRepositoryConfig,
    MongoCrossAssetCatalogRepository,
    TEST_DATABASE_PREFIX,
    assert_safe_test_database_name,
)
from tests.xa04.test_xa04_persistence_conformance import CatalogRepositoryConformanceTests  # noqa: E402


def _mongo_integration_enabled() -> bool:
    return bool(os.environ.get("IMP_TEST_MONGODB_URI", "").strip())


@unittest.skipUnless(
    _mongo_integration_enabled(),
    "SKIPPED_ENVIRONMENT_UNAVAILABLE",
)
class MongoCatalogRepositoryConformanceTests(CatalogRepositoryConformanceTests):
    backend_name = "mongo"

    def setUp(self) -> None:
        uri = os.environ["IMP_TEST_MONGODB_URI"].strip()
        database_name = os.environ.get(
            "IMP_TEST_MONGODB_DATABASE",
            f"{TEST_DATABASE_PREFIX}{uuid.uuid4().hex}",
        ).strip()
        assert_safe_test_database_name(database_name)
        config = MongoCatalogRepositoryConfig(uri=uri, database_name=database_name)
        self._database_name = database_name
        self.repo = MongoCrossAssetCatalogRepository.from_config(config)
        self.repo.ensure_schema()
        self._client = self.repo._client  # noqa: SLF001
        from tests.xa04.test_xa04_fixtures import populate_vertical_slice_repository

        _, self.state = populate_vertical_slice_repository(self.repo)

    def tearDown(self) -> None:
        assert_safe_test_database_name(self._database_name)
        self._client.drop_database(self._database_name)
        self.repo.close()


@unittest.skipUnless(
    _mongo_integration_enabled(),
    "SKIPPED_ENVIRONMENT_UNAVAILABLE",
)
class MongoRestartDurabilityTests(unittest.TestCase):
    def test_restart_preserves_semantic_state(self) -> None:
        uri = os.environ["IMP_TEST_MONGODB_URI"].strip()
        database_name = os.environ.get(
            "IMP_TEST_MONGODB_DATABASE",
            f"{TEST_DATABASE_PREFIX}{uuid.uuid4().hex}",
        ).strip()
        assert_safe_test_database_name(database_name)
        config = MongoCatalogRepositoryConfig(uri=uri, database_name=database_name)
        first = MongoCrossAssetCatalogRepository.from_config(config)
        first.ensure_schema()
        from tests.xa04.test_xa04_fixtures import populate_vertical_slice_repository

        repo, state = populate_vertical_slice_repository(first)
        gc_id = str(state["gc_canonical_id"])
        fred_id = state["fred"]["observation_ids"][0]  # type: ignore[index]
        first.close()
        second = MongoCrossAssetCatalogRepository.from_config(config)
        second.ensure_schema()
        self.assertIsNotNone(second.get_instrument(gc_id))
        self.assertIsNotNone(second.get_scalar_observation(fred_id))
        second.close()
        first._client.drop_database(database_name)  # noqa: SLF001


if __name__ == "__main__":
    unittest.main()
