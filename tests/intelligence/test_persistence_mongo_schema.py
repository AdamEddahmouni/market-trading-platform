"""Mongo schema plan unit tests (BUILD 04.5)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.persistence.codec import RECORD_CODECS  # noqa: E402
from market_platform_foundation.intelligence.persistence.mongo.config import (  # noqa: E402
    assert_safe_test_database_name,
    TEST_DATABASE_PREFIX,
)
from market_platform_foundation.intelligence.persistence.mongo.schema import (  # noqa: E402
    ALLOCATION_DECISION_INDEXES,
    ALLOCATION_DECISION_VALIDATOR,
    COLLECTION_SPECS,
    MONGO_SCHEMA_PLAN_VERSION,
    MongoSchemaManager,
)


class SchemaPlanTests(unittest.TestCase):
    def test_schema_plan_version(self) -> None:
        self.assertEqual(MONGO_SCHEMA_PLAN_VERSION, 5)

    def test_routing_collections_have_no_ttl_deletion_indexes(self) -> None:
        specs = {spec.codec.collection_name: spec for spec in COLLECTION_SPECS}
        self.assertIn("detections", specs)
        self.assertIn("routing_decisions", specs)
        self.assertIn("inference_jobs", specs)
        route_indexes = specs["routing_decisions"].indexes
        job_indexes = specs["inference_jobs"].indexes
        self.assertIn("idx_routes_expires_at", {index.name for index in route_indexes})
        self.assertIn("idx_inference_jobs_expires_at", {index.name for index in job_indexes})
        for index in (*route_indexes, *job_indexes):
            self.assertFalse(hasattr(index, "expire_after_seconds"))

    def test_all_codecs_have_collection_specs(self) -> None:
        spec_names = {spec.codec.collection_name for spec in COLLECTION_SPECS}
        codec_names = {codec.collection_name for codec in RECORD_CODECS}
        self.assertEqual(spec_names, codec_names)

    def test_each_spec_has_validator_and_indexes(self) -> None:
        for spec in COLLECTION_SPECS:
            self.assertIn("bsonType", spec.validator)
            self.assertTrue(spec.validator.get("required"))

    def test_events_have_point_in_time_indexes(self) -> None:
        event_spec = next(spec for spec in COLLECTION_SPECS if spec.codec.collection_name == "events")
        names = {index.name for index in event_spec.indexes}
        self.assertIn("idx_events_available_time", names)
        self.assertIn("idx_events_point_in_time_sort", names)

    def test_strategy_matches_have_identity_and_expiry_indexes(self) -> None:
        match_spec = next(
            spec for spec in COLLECTION_SPECS if spec.codec.collection_name == "strategy_matches"
        )
        self.assertIn("match_identity_hash", match_spec.validator["required"])
        names = {index.name for index in match_spec.indexes}
        self.assertIn("idx_strategy_matches_strategy_decision", names)
        self.assertIn("idx_strategy_matches_expires_at", names)

    def test_allocation_decision_sidecar_has_validator_and_indexes(self) -> None:
        self.assertIn("allocation_decision_id", ALLOCATION_DECISION_VALIDATOR["required"])
        self.assertEqual(
            {index.name for index in ALLOCATION_DECISION_INDEXES},
            {
                "idx_allocation_decisions_decision_set",
                "idx_allocation_decisions_account_mode",
            },
        )

    def test_test_database_prefix_guard(self) -> None:
        assert_safe_test_database_name(f"{TEST_DATABASE_PREFIX}abc")
        with self.assertRaises(ValueError):
            assert_safe_test_database_name("production_db")


class FakeDatabase:
    def __init__(self) -> None:
        self.collections: dict[str, dict] = {}
        self.created: list[tuple[str, dict]] = []

    def list_collection_names(self) -> list[str]:
        return list(self.collections.keys())

    def create_collection(self, name: str, **options: object) -> None:
        self.collections[name] = {"options": options, "indexes": {}}
        self.created.append((name, options))

    def command(self, command: str, **kwargs: object) -> dict:
        if command == "listCollections":
            name = kwargs["filter"]["name"]
            options = self.collections.get(name, {}).get("options", {})
            return {
                "cursor": {
                    "firstBatch": [{"name": name, "options": options}],
                }
            }
        raise AssertionError(command)

    def __getitem__(self, name: str) -> FakeCollection:
        return FakeCollection(self, name)


class FakeCollection:
    def __init__(self, database: FakeDatabase, name: str) -> None:
        self._database = database
        self._name = name
        if name not in database.collections:
            database.collections[name] = {"options": {}, "indexes": {}}

    def list_indexes(self) -> list[dict]:
        indexes = self._database.collections[self._name]["indexes"]
        return [{"name": " _id_", "key": {"_id": 1}, "unique": True}] + [
            {"name": name, "key": dict(keys), "unique": False}
            for name, keys in indexes.items()
        ]

    def create_index(self, keys: list, name: str, unique: bool = False) -> str:
        self._database.collections[self._name]["indexes"][name] = keys
        return name


class SchemaBootstrapTests(unittest.TestCase):
    def test_ensure_schema_idempotent_on_fake_database(self) -> None:
        database = FakeDatabase()
        manager = MongoSchemaManager(database)
        manager.ensure_schema()
        manager.ensure_schema()
        self.assertEqual(len(database.created), len(COLLECTION_SPECS) + 1)
        self.assertIn("allocation_decisions", database.collections)
        allocation_options = dict(database.created)["allocation_decisions"]
        self.assertEqual(
            allocation_options["validator"],
            {"$jsonSchema": ALLOCATION_DECISION_VALIDATOR},
        )
        self.assertEqual(
            set(database.collections["allocation_decisions"]["indexes"]),
            {index.name for index in ALLOCATION_DECISION_INDEXES},
        )


if __name__ == "__main__":
    unittest.main()
