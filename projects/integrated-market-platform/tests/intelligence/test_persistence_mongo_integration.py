"""Opt-in Mongo integration tests (BUILD 04.5)."""

from __future__ import annotations

import os
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.persistence import (  # noqa: E402
    InMemoryIntelligenceRepository,
    RepositoryConflictError,
    RepositoryPutResult,
)
from market_platform_foundation.intelligence.persistence.mongo import (  # noqa: E402
    MongoIntelligenceRepository,
    MongoRepositoryConfig,
    TEST_DATABASE_PREFIX,
    assert_safe_test_database_name,
)
from tests.intelligence.test_persistence_conformance import RepositoryConformanceTests  # noqa: E402
from tests.intelligence.test_persistence_fixtures import (  # noqa: E402
    DECISION_NS,
    populate_all_record_types,
    sample_event,
    sample_forecast,
)


def _mongo_integration_enabled() -> bool:
    return bool(os.environ.get("IMP_TEST_MONGODB_URI", "").strip())


@unittest.skipUnless(
    _mongo_integration_enabled(),
    "IMP_TEST_MONGODB_URI not configured",
)
class MongoRepositoryConformanceTests(RepositoryConformanceTests):
    backend_name = "mongo"

    def setUp(self) -> None:
        uri = os.environ["IMP_TEST_MONGODB_URI"].strip()
        database_name = os.environ.get(
            "IMP_TEST_MONGODB_DATABASE",
            f"{TEST_DATABASE_PREFIX}{uuid.uuid4().hex}",
        ).strip()
        assert_safe_test_database_name(database_name)
        config = MongoRepositoryConfig(uri=uri, database_name=database_name)
        self._database_name = database_name
        self.repo = MongoIntelligenceRepository.from_config(config)
        self.repo.ensure_schema()
        self._client = self.repo._client  # noqa: SLF001

    def tearDown(self) -> None:
        assert_safe_test_database_name(self._database_name)
        self._client.drop_database(self._database_name)
        self.repo.close()


@unittest.skipUnless(
    _mongo_integration_enabled(),
    "IMP_TEST_MONGODB_URI not configured",
)
class MongoIntegrationExtras(unittest.TestCase):
    def setUp(self) -> None:
        uri = os.environ["IMP_TEST_MONGODB_URI"].strip()
        self._database_name = os.environ.get(
            "IMP_TEST_MONGODB_DATABASE",
            f"{TEST_DATABASE_PREFIX}{uuid.uuid4().hex}",
        ).strip()
        assert_safe_test_database_name(self._database_name)
        config = MongoRepositoryConfig(uri=uri, database_name=self._database_name)
        self.repo = MongoIntelligenceRepository.from_config(config)
        self.repo.ensure_schema()
        self._client = self.repo._client  # noqa: SLF001

    def tearDown(self) -> None:
        assert_safe_test_database_name(self._database_name)
        self._client.drop_database(self._database_name)
        self.repo.close()

    def test_schema_bootstrap_twice(self) -> None:
        self.repo.ensure_schema()
        self.repo.ensure_schema()

    def test_malformed_direct_insert_rejected(self) -> None:
        collection = self.repo._database["events"]  # noqa: SLF001
        with self.assertRaises(Exception):
            collection.insert_one({"schema_version": 1})

    def test_duplicate_key_idempotency(self) -> None:
        forecast = sample_forecast(probability=0.55)
        self.assertEqual(self.repo.put_forecast(forecast), RepositoryPutResult.INSERTED)
        self.assertEqual(self.repo.put_forecast(forecast), RepositoryPutResult.ALREADY_PRESENT)

    def test_inmemory_mongo_parity(self) -> None:
        memory = InMemoryIntelligenceRepository()
        populate_all_record_types(memory)
        populate_all_record_types(self.repo)
        memory_ids = [
            event.event_id
            for event in memory.query_events_as_of(DECISION_NS, instrument_id="NVDA")
        ]
        mongo_ids = [
            event.event_id
            for event in self.repo.query_events_as_of(DECISION_NS, instrument_id="NVDA")
        ]
        self.assertEqual(memory_ids, mongo_ids)

    def test_indexes_exist(self) -> None:
        indexes = list(self.repo._database["events"].list_indexes())  # noqa: SLF001
        names = {index["name"] for index in indexes}
        self.assertIn("idx_events_available_time", names)


class SafeDatabaseGuardTests(unittest.TestCase):
    def test_drop_requires_prefix(self) -> None:
        with self.assertRaises(ValueError):
            assert_safe_test_database_name("production")


if __name__ == "__main__":
    unittest.main()
