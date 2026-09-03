"""Tests for live-provider squeeze bridge and scanner explore projections."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.donor_bridge.projections import (  # noqa: E402
    build_explore_squeeze_scanner_payload,
    build_squeeze_scanner_attention_items,
    build_workspace_squeeze_payload,
)
from market_platform_foundation.donor_bridge.squeeze_client import (  # noqa: E402
    fetch_donor_deployment_mode,
)

_CURRENT_ROW = {
    "symbol": "AAA",
    "freshness": "CURRENT",
    "mode_label": "CURRENT",
    "provider_scanner_order": 1,
    "phase3a": {"summary": "5 PASS / 3 FAIL / 17 UNKNOWN"},
    "research_detection": {"status": "INSUFFICIENT_EVIDENCE"},
}

_CURRENT_DETAIL = {
    "identity": {"symbol": "AAA", "mode_label": "CURRENT"},
    "available": True,
    "freshness": "CURRENT",
    "phase3a": {"summary": "5 PASS / 3 FAIL / 17 UNKNOWN"},
    "research_detection": {"status": "INSUFFICIENT_EVIDENCE"},
    "rules": [{"rule_id": "R1", "category": "SHORT_PRESSURE_CONFIRMATION", "outcome": "PASS", "reason": "ok"}],
}


class LiveSqueezeBridgeTests(unittest.TestCase):
    def test_scanner_explore_unavailable_when_server_down(self) -> None:
        payload = build_explore_squeeze_scanner_payload(base_url="http://127.0.0.1:59999")
        self.assertFalse(payload["available"])
        self.assertEqual(payload["data_mode"], "current")
        self.assertEqual(payload["rows"], [])

    def test_scanner_explore_projects_current_rows(self) -> None:
        with patch(
            "market_platform_foundation.donor_bridge.projections.is_available",
            return_value=True,
        ), patch(
            "market_platform_foundation.donor_bridge.projections.fetch_donor_deployment_mode",
            return_value="FROZEN_DEMO",
        ), patch(
            "market_platform_foundation.donor_bridge.projections.fetch_manifest",
            return_value={"api_version": "1.0.0", "schema_version": "batch14.integration.v1"},
        ), patch(
            "market_platform_foundation.donor_bridge.projections.fetch_current_candidates",
            return_value={"rows": [_CURRENT_ROW], "reason": None},
        ):
            payload = build_explore_squeeze_scanner_payload()

        self.assertTrue(payload["available"])
        self.assertEqual(payload["row_count"], 1)
        self.assertEqual(payload["rows"][0]["symbol"], "AAA")
        self.assertEqual(payload["rows"][0]["scanner_rank"], 1)
        self.assertEqual(payload["rows"][0]["explanation_ref"], "explain:squeeze:scanner:AAA")
        self.assertEqual(payload["detection_summary"], [{"label": "INSUFFICIENT_EVIDENCE", "count": 1}])

    def test_scanner_attention_items_when_rows_present(self) -> None:
        with patch(
            "market_platform_foundation.donor_bridge.projections.is_available",
            return_value=True,
        ), patch(
            "market_platform_foundation.donor_bridge.projections.fetch_donor_deployment_mode",
            return_value="FROZEN_DEMO",
        ), patch(
            "market_platform_foundation.donor_bridge.projections.fetch_manifest",
            return_value={"api_version": "1.0.0", "schema_version": "batch14.integration.v1"},
        ), patch(
            "market_platform_foundation.donor_bridge.projections.fetch_current_candidates",
            return_value={"rows": [_CURRENT_ROW], "reason": None},
        ):
            items = build_squeeze_scanner_attention_items()

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["attention_id"], "att-squeeze-scanner-aaa")
        self.assertEqual(items[0]["explanation_ref"], "explain:squeeze:scanner:AAA")
        self.assertEqual(items[0]["priority_rank"], 15)

    def test_scanner_attention_items_empty_when_no_rows(self) -> None:
        with patch(
            "market_platform_foundation.donor_bridge.projections.is_available",
            return_value=True,
        ), patch(
            "market_platform_foundation.donor_bridge.projections.fetch_donor_deployment_mode",
            return_value="FROZEN_DEMO",
        ), patch(
            "market_platform_foundation.donor_bridge.projections.fetch_manifest",
            return_value={"api_version": "1.0.0", "schema_version": "batch14.integration.v1"},
        ), patch(
            "market_platform_foundation.donor_bridge.projections.fetch_current_candidates",
            return_value={"rows": [], "reason": None},
        ):
            items = build_squeeze_scanner_attention_items()

        self.assertEqual(items, [])

    def test_workspace_current_mode_projects_detail(self) -> None:
        with patch(
            "market_platform_foundation.donor_bridge.projections.is_available",
            return_value=True,
        ), patch(
            "market_platform_foundation.donor_bridge.projections.fetch_donor_deployment_mode",
            return_value="LOCAL_FULL",
        ), patch(
            "market_platform_foundation.donor_bridge.projections.fetch_current_candidate_detail",
            return_value=_CURRENT_DETAIL,
        ):
            payload = build_workspace_squeeze_payload("AAA", data_mode="current")

        self.assertTrue(payload["available"])
        self.assertEqual(payload["data_mode"], "current")
        self.assertEqual(payload["donor_deployment_mode"], "LOCAL_FULL")
        self.assertEqual(payload["explanation_ref"], "explain:squeeze:scanner:AAA")
        self.assertIn("EPHEMERAL", payload["outcome_status"] or "")
        self.assertEqual(len(payload["rules"]), 1)

    def test_workspace_current_mode_unavailable_when_symbol_missing(self) -> None:
        with patch(
            "market_platform_foundation.donor_bridge.projections.is_available",
            return_value=True,
        ), patch(
            "market_platform_foundation.donor_bridge.projections.fetch_donor_deployment_mode",
            return_value="LOCAL_FULL",
        ), patch(
            "market_platform_foundation.donor_bridge.projections.fetch_current_candidate_detail",
            return_value={"error": "ZZZZ is not a tracked current candidate.", "available": False},
        ):
            payload = build_workspace_squeeze_payload("ZZZZ", data_mode="current")

        self.assertFalse(payload["available"])
        self.assertIn("ZZZZ", payload["reason"] or "")

    def test_fetch_donor_deployment_mode_reads_envelope_mode(self) -> None:
        with patch(
            "market_platform_foundation.donor_bridge.squeeze_client.fetch_health",
            return_value={"status": "OK", "mode": "CLOUD_PROVIDER_MODE"},
        ):
            self.assertEqual(fetch_donor_deployment_mode(), "CLOUD_PROVIDER_MODE")


if __name__ == "__main__":
    unittest.main()
