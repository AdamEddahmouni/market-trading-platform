"""Tests for Paper decision-source snapshot validation."""

from __future__ import annotations

import unittest

from market_platform_foundation.paper.decision_source import (
    parse_decision_source_snapshot,
    snapshot_matches_correlation,
    validate_snapshot_against_correlation,
)


class PaperDecisionSourceSnapshotTests(unittest.TestCase):
    def test_parse_attention_snapshot_optional_fields(self) -> None:
        snapshot = parse_decision_source_snapshot(
            {
                "source_type": "paper_command_attention",
                "source_id": "ATT-123",
                "headline": "Short interest elevated into catalyst window",
                "tier": 1,
                "reasons": [{"code": "SI", "label": "Short interest elevated"}],
                "source_time": 1_700_000_000_000,
            }
        )
        self.assertEqual(snapshot["source_type"], "paper_command_attention")
        self.assertEqual(snapshot["source_id"], "ATT-123")
        self.assertEqual(snapshot["headline"], "Short interest elevated into catalyst window")
        self.assertEqual(snapshot["tier"], 1)
        self.assertEqual(snapshot["source_time"], 1_700_000_000_000)
        self.assertEqual(len(snapshot["reasons"]), 1)

    def test_rejects_invalid_source_time(self) -> None:
        snapshot = parse_decision_source_snapshot(
            {
                "source_type": "paper_command_attention",
                "source_id": "ATT-1",
                "source_time": -1,
            }
        )
        self.assertNotIn("source_time", snapshot)

        snapshot_float = parse_decision_source_snapshot(
            {
                "source_type": "paper_command_attention",
                "source_id": "ATT-1",
                "source_time": 1.5,
            }
        )
        self.assertNotIn("source_time", snapshot_float)

    def test_parse_lane_snapshot(self) -> None:
        snapshot = parse_decision_source_snapshot(
            {
                "source_type": "workspace_lane",
                "source_id": "squeeze",
                "source_module": "squeeze",
            }
        )
        self.assertEqual(snapshot["source_type"], "workspace_lane")
        self.assertEqual(snapshot["source_module"], "squeeze")

    def test_reason_list_bounded(self) -> None:
        reasons = [{"code": f"C{i}", "label": f"Reason {i}"} for i in range(10)]
        snapshot = parse_decision_source_snapshot(
            {
                "source_type": "paper_command_attention",
                "source_id": "ATT-1",
                "reasons": reasons,
            }
        )
        self.assertEqual(len(snapshot["reasons"]), 5)

    def test_rejects_invalid_type(self) -> None:
        with self.assertRaises(ValueError):
            parse_decision_source_snapshot({"source_type": "manual", "source_id": "x"})

    def test_rejects_missing_source_id(self) -> None:
        with self.assertRaises(ValueError):
            parse_decision_source_snapshot({"source_type": "paper_command_attention", "source_id": ""})

    def test_validate_lane_correlation_match(self) -> None:
        snapshot = parse_decision_source_snapshot(
            {
                "source_type": "workspace_lane",
                "source_id": "squeeze",
                "source_module": "squeeze",
            }
        )
        validated = validate_snapshot_against_correlation(
            snapshot=snapshot,
            correlation_id="lane:squeeze",
        )
        self.assertEqual(validated["source_id"], "squeeze")

    def test_validate_attention_correlation_match(self) -> None:
        snapshot = parse_decision_source_snapshot(
            {
                "source_type": "paper_command_attention",
                "source_id": "attention-biya",
                "headline": "BIYA setup",
            }
        )
        validated = validate_snapshot_against_correlation(
            snapshot=snapshot,
            correlation_id="attention-biya",
        )
        self.assertEqual(validated["headline"], "BIYA setup")

    def test_rejects_correlation_mismatch(self) -> None:
        snapshot = parse_decision_source_snapshot(
            {
                "source_type": "paper_command_attention",
                "source_id": "ATT-1",
            }
        )
        with self.assertRaises(ValueError):
            validate_snapshot_against_correlation(snapshot=snapshot, correlation_id="lane:squeeze")

    def test_snapshot_matches_correlation_helper(self) -> None:
        snapshot = parse_decision_source_snapshot(
            {
                "source_type": "workspace_lane",
                "source_id": "order-flow",
                "source_module": "order-flow",
            }
        )
        self.assertTrue(
            snapshot_matches_correlation(snapshot=snapshot, correlation_id="lane:order-flow")
        )
        self.assertFalse(
            snapshot_matches_correlation(snapshot=snapshot, correlation_id="attention-biya")
        )


if __name__ == "__main__":
    unittest.main()
