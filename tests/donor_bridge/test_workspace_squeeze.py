"""Tests for workspace squeeze bridge."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.donor_bridge.projections import (  # noqa: E402
    ADMITTED_REPLAY_INSTRUMENT_ID,
    FROZEN_DEMO_REFERENCE_SYMBOL,
    build_workspace_squeeze_payload,
)

_SAMPLE_DETAIL = {
    "identity": {"symbol": "BIYA", "mode_label": "FROZEN_RESEARCH"},
    "available": True,
    "freshness": "FROZEN",
    "phase3a": {"summary": "10 PASS / 5 FAIL / 10 UNKNOWN", "counts": {"PASS": 10, "FAIL": 5, "UNKNOWN": 10}},
    "research_detection": {"status": "INSUFFICIENT_EVIDENCE"},
    "outcome": {"status": "UNKNOWN", "reasons": ["No forward outcome in sanitized demo."]},
    "evidence_coverage": {"label": "15 / 25 rules supported"},
    "provenance": {"source_kind": "SANITIZED_AGGREGATE"},
}


class WorkspaceSqueezeBridgeTests(unittest.TestCase):
    def test_unavailable_when_server_down(self) -> None:
        payload = build_workspace_squeeze_payload("BIYA", base_url="http://127.0.0.1:59999")
        self.assertFalse(payload["available"])
        self.assertTrue(payload["replay_chart_available"])
        self.assertIn("not reachable", payload["reason"] or "")

    def test_replay_chart_only_for_admitted_symbol(self) -> None:
        with patch(
            "market_platform_foundation.donor_bridge.projections.is_available",
            return_value=True,
        ), patch(
            "market_platform_foundation.donor_bridge.projections.fetch_frozen_candidate_detail",
            return_value=_SAMPLE_DETAIL,
        ):
            biya = build_workspace_squeeze_payload("BIYA")
            avtx = build_workspace_squeeze_payload("AVTX")

        self.assertTrue(biya["replay_chart_available"])
        self.assertFalse(avtx["replay_chart_available"])
        self.assertEqual(biya["symbol"], ADMITTED_REPLAY_INSTRUMENT_ID)

    def test_symbol_not_found_when_server_up(self) -> None:
        with patch(
            "market_platform_foundation.donor_bridge.projections.is_available",
            return_value=True,
        ), patch(
            "market_platform_foundation.donor_bridge.projections.fetch_frozen_candidate_detail",
            return_value={"available": False, "error": "ZZZZ is not one of the 13 frozen research cases."},
        ):
            payload = build_workspace_squeeze_payload("ZZZZ")

        self.assertFalse(payload["available"])
        self.assertIn("ZZZZ", payload["reason"] or "")

    def test_projects_detail_fields_when_available(self) -> None:
        with patch(
            "market_platform_foundation.donor_bridge.projections.is_available",
            return_value=True,
        ), patch(
            "market_platform_foundation.donor_bridge.projections.fetch_frozen_candidate_detail",
            return_value={**_SAMPLE_DETAIL, "rules": [{"rule_id": "R1", "category": "SHORT_PRESSURE_CONFIRMATION", "outcome": "PASS", "reason": "x"}]},
        ):
            payload = build_workspace_squeeze_payload("BIYA")

        self.assertTrue(payload["available"])
        self.assertEqual(payload["outcome_status"], "UNKNOWN: No forward outcome in sanitized demo.")
        self.assertEqual(payload["evidence_coverage"], "15 / 25 rules supported")
        self.assertEqual(payload["research_detection"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(payload["freshness"], "FROZEN")
        self.assertEqual(len(payload["rules"]), 1)
        self.assertEqual(len(payload["ignition_evidence"]), 3)
        self.assertIn("state_machine", payload)
        self.assertIn("readiness", payload)
        self.assertEqual(payload["state_machine"]["current_state"], "INSUFFICIENT_EVIDENCE")
        self.assertTrue(payload["readiness"]["provenance_admissible"])

    def test_state_machine_partitions_rules(self) -> None:
        with patch(
            "market_platform_foundation.donor_bridge.projections.is_available",
            return_value=True,
        ), patch(
            "market_platform_foundation.donor_bridge.projections.fetch_frozen_candidate_detail",
            return_value={
                **_SAMPLE_DETAIL,
                "rules": [
                    {"rule_id": "R_PASS", "category": "SHORT_PRESSURE_CONFIRMATION", "outcome": "PASS", "reason": "ok"},
                    {"rule_id": "R_FAIL", "category": "SHORT_PRESSURE_CONFIRMATION", "outcome": "FAIL", "reason": "bad"},
                    {"rule_id": "R_UNK", "category": "CATALYST_EVIDENCE", "outcome": "UNKNOWN", "reason": ""},
                ],
            },
        ):
            payload = build_workspace_squeeze_payload("AVTX")

        machine = payload["state_machine"]
        self.assertEqual(len(machine["changed_criteria"]), 1)
        self.assertEqual(len(machine["unchanged_criteria"]), 1)
        self.assertEqual(len(machine["unknown_criteria"]), 1)

    def test_inspector_timeline_tab_with_mock(self) -> None:
        from market_platform_foundation.ui_api.projections import build_inspect_payload
        from market_platform_foundation.ui_api.store import ReplayStore

        store = ReplayStore(collection_root=ROOT.parent)
        store.load()
        with patch(
            "market_platform_foundation.donor_bridge.projections.build_workspace_squeeze_payload",
            return_value={
                "available": True,
                "freshness": "FROZEN",
                "state_machine": {
                    "current_state": "WATCH",
                    "last_transition_label": "frozen",
                    "changed_criteria": [],
                    "unchanged_criteria": [],
                    "transitions": [],
                },
                "readiness": {"freshness_state": "FROZEN", "provenance_admissible": True},
            },
        ):
            payload = build_inspect_payload(store, "inspect:squeeze:timeline:AVTX")
        self.assertEqual(payload["default_tab"], "TIMELINE")
        self.assertIn("TIMELINE", payload["tabs"])
        self.assertIn("PROVENANCE", payload["tabs"])
        from market_platform_foundation.donor_bridge.projections import build_squeeze_attention_items

        items = build_squeeze_attention_items(base_url="http://127.0.0.1:59999")
        self.assertEqual(items, [])

    def test_explain_squeeze_ref_with_mock(self) -> None:
        from market_platform_foundation.ui_api.projections import build_explain_payload
        from market_platform_foundation.ui_api.store import ReplayStore

        store = ReplayStore(collection_root=ROOT.parent)
        store.load()
        with patch(
            "market_platform_foundation.donor_bridge.projections.build_workspace_squeeze_payload",
            return_value={
                "available": True,
                "ignition_state": "INSUFFICIENT_EVIDENCE",
                "outcome_status": "UNKNOWN",
                "evidence_coverage": "15 / 25",
                "disclaimer": "Research only.",
            },
        ):
            payload = build_explain_payload(store, "explain:squeeze:BIYA")
        self.assertEqual(payload["explanation"]["ref"], "explain:squeeze:BIYA")

    def test_available_when_server_up(self) -> None:
        payload = build_workspace_squeeze_payload(FROZEN_DEMO_REFERENCE_SYMBOL, base_url="http://127.0.0.1:8787")
        if not payload["available"]:
            self.skipTest("squeeze FROZEN_DEMO server not running on :8787")
        self.assertEqual(payload["symbol"], FROZEN_DEMO_REFERENCE_SYMBOL)
        self.assertFalse(payload["replay_chart_available"])
        self.assertIsNotNone(payload["phase3a_summary"])

    def test_biya_replay_only_when_server_up(self) -> None:
        payload = build_workspace_squeeze_payload(ADMITTED_REPLAY_INSTRUMENT_ID, base_url="http://127.0.0.1:8787")
        if payload.get("reason", "").startswith("Short squeeze FROZEN_DEMO server not reachable"):
            self.skipTest("squeeze FROZEN_DEMO server not running on :8787")
        self.assertTrue(payload["replay_chart_available"])
        self.assertFalse(payload["available"])
        self.assertIn("not one of the 13 frozen research cases", payload["reason"] or "")

    def test_requires_symbol(self) -> None:
        with self.assertRaises(ValueError):
            build_workspace_squeeze_payload("  ")


if __name__ == "__main__":
    unittest.main()
