"""Tests for lane-specific provenance envelopes (TD-002)."""

from __future__ import annotations

import unittest

from market_platform_foundation.ui_api.lane_provenance import (
    SOURCE_KIND_CONTEXT_AS_OF,
    SOURCE_KIND_LANE_PAYLOAD,
    SOURCE_KIND_UNKNOWN,
    attach_lane_provenance,
    extract_lane_source_time,
)


class LaneProvenanceTests(unittest.TestCase):
    def test_extracts_observation_time_from_lane_payload(self) -> None:
        payload = {"observation_time": 1_700_000_000_000_000_000}
        source_time, kind = extract_lane_source_time(payload)
        self.assertEqual(source_time, 1_700_000_000_000_000_000)
        self.assertEqual(kind, SOURCE_KIND_LANE_PAYLOAD)

    def test_falls_back_to_context_as_of(self) -> None:
        payload = {"as_of_context": {"as_of_time": "2024-06-01T12:00:00.000000000Z"}}
        source_time, kind = extract_lane_source_time(payload)
        self.assertIsNotNone(source_time)
        self.assertEqual(kind, SOURCE_KIND_CONTEXT_AS_OF)

    def test_unknown_when_no_trustworthy_timestamp(self) -> None:
        _source_time, kind = extract_lane_source_time({})
        self.assertEqual(kind, SOURCE_KIND_UNKNOWN)

    def test_attach_lane_provenance_preserves_payload(self) -> None:
        payload = {"available": True, "symbol": "BIYA"}
        enriched = attach_lane_provenance(payload, lane_id="squeeze", retrieved_at_ns=1_800_000_000_000_000_000)
        self.assertEqual(enriched["symbol"], "BIYA")
        self.assertEqual(enriched["lane_provenance"]["lane_id"], "squeeze")
        self.assertEqual(enriched["lane_provenance"]["retrieved_at"], 1_800_000_000_000_000_000)


if __name__ == "__main__":
    unittest.main()
