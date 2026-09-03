"""BUILD 09 persistence parity and immutability tests."""

from __future__ import annotations

import dataclasses
import unittest

from market_platform_foundation.intelligence.contracts import DetectionSeverity, RoutingPriority
from market_platform_foundation.intelligence.persistence import (
    InMemoryIntelligenceRepository,
    RepositoryConflictError,
    RepositoryPutResult,
)
from market_platform_foundation.intelligence.persistence.codec import (
    codec_for_record,
    decode_document,
    encode_document,
)
from tests.intelligence.test_routing_contracts import sample_detection, sample_route


class RoutingPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = InMemoryIntelligenceRepository()

    def test_detection_round_trip_idempotency_and_snapshot_query(self) -> None:
        record = sample_detection()
        self.assertEqual(self.repo.put_detection(record), RepositoryPutResult.INSERTED)
        self.assertEqual(self.repo.put_detection(record), RepositoryPutResult.ALREADY_PRESENT)
        self.assertEqual(self.repo.get_detection(record.detection_id), record)
        self.assertEqual(self.repo.get_detections_by_snapshot("snap-1"), (record,))

    def test_route_round_trip_idempotency_and_detection_query(self) -> None:
        record = sample_route()
        self.assertEqual(self.repo.put_routing_decision(record), RepositoryPutResult.INSERTED)
        self.assertEqual(self.repo.put_routing_decision(record), RepositoryPutResult.ALREADY_PRESENT)
        self.assertEqual(self.repo.get_routing_decision(record.routing_decision_id), record)
        self.assertEqual(self.repo.get_routes_by_detection("DET-abc"), (record,))

    def test_same_detection_id_with_changed_output_conflicts(self) -> None:
        record = sample_detection()
        self.repo.put_detection(record)
        with self.assertRaises(RepositoryConflictError):
            self.repo.put_detection(dataclasses.replace(record, severity=DetectionSeverity.CRITICAL))

    def test_same_route_id_with_changed_output_conflicts(self) -> None:
        record = sample_route()
        self.repo.put_routing_decision(record)
        with self.assertRaises(RepositoryConflictError):
            self.repo.put_routing_decision(dataclasses.replace(record, priority=RoutingPriority.CRITICAL))

    def test_codec_document_round_trip(self) -> None:
        for record in (sample_detection(), sample_route()):
            document = encode_document(record)
            restored = decode_document(document, codec_for_record(record))
            self.assertEqual(restored, record)

    def test_nested_metadata_is_isolated_from_callers_and_reads(self) -> None:
        record = dataclasses.replace(sample_detection(), metadata={"nested": {"value": 1}})
        self.repo.put_detection(record)
        record.metadata["nested"]["value"] = 9
        first = self.repo.get_detection(record.detection_id)
        self.assertEqual(first.metadata["nested"]["value"], 1)
        first.metadata["nested"]["value"] = 7
        second = self.repo.get_detection(record.detection_id)
        self.assertEqual(second.metadata["nested"]["value"], 1)


if __name__ == "__main__":
    unittest.main()
