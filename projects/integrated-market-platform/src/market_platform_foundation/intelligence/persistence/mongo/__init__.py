"""Mongo persistence backend (BUILD 04.5)."""

from .config import (
    MongoRepositoryConfig,
    TEST_DATABASE_PREFIX,
    assert_safe_test_database_name,
    redact_mongo_uri,
)
from .repository import MongoIntelligenceRepository
from .schema import COLLECTION_SPECS, MONGO_SCHEMA_PLAN_VERSION, MongoSchemaManager

__all__ = [
    "COLLECTION_SPECS",
    "MONGO_SCHEMA_PLAN_VERSION",
    "MongoIntelligenceRepository",
    "MongoRepositoryConfig",
    "MongoSchemaManager",
    "TEST_DATABASE_PREFIX",
    "assert_safe_test_database_name",
    "redact_mongo_uri",
]
