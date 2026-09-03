"""Persistence codec tests (BUILD 04.5)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.persistence.codec import (  # noqa: E402
    BSON_MAX_INT64,
    BSON_MIN_INT64,
    canonical_semantic_equal,
    encode_document,
)
from market_platform_foundation.intelligence.persistence.errors import (  # noqa: E402
    RepositorySerializationError,
)
from market_platform_foundation.intelligence.persistence.mongo.config import (  # noqa: E402
    MongoRepositoryConfig,
    redact_mongo_uri,
)
from tests.intelligence.test_persistence_fixtures import sample_event, sample_forecast  # noqa: E402


class CodecTests(unittest.TestCase):
    def test_encode_uses_domain_id_as_mongo_id(self) -> None:
        document = encode_document(sample_event("evt-codec"))
        self.assertEqual(document["_id"], "evt-codec")
        self.assertEqual(document["event_id"], "evt-codec")

    def test_canonical_semantic_equal_ignores_id_metadata(self) -> None:
        left = encode_document(sample_forecast(probability=0.5))
        right = dict(left)
        right["_id"] = left["forecast_id"]
        self.assertTrue(canonical_semantic_equal(left, right))

    def test_bson_integer_out_of_range(self) -> None:
        event = sample_event()
        document = encode_document(event)
        document["available_time_ns"] = BSON_MAX_INT64 + 1
        with self.assertRaises(RepositorySerializationError):
            from market_platform_foundation.intelligence.persistence.codec import _walk_integers

            _walk_integers(document)

    def test_bson_integer_boundary_ok(self) -> None:
        from market_platform_foundation.intelligence.persistence.codec import _walk_integers

        _walk_integers(BSON_MAX_INT64)
        _walk_integers(BSON_MIN_INT64)


class ConfigRedactionTests(unittest.TestCase):
    def test_uri_redaction(self) -> None:
        redacted = redact_mongo_uri("mongodb://user:supersecret@host:27017/db")
        self.assertNotIn("supersecret", redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_config_repr_redacts_credentials(self) -> None:
        config = MongoRepositoryConfig(
            uri="mongodb://user:supersecret@host:27017/db",
            database_name="imp_test_demo",
        )
        text = repr(config)
        self.assertNotIn("supersecret", text)


if __name__ == "__main__":
    unittest.main()
