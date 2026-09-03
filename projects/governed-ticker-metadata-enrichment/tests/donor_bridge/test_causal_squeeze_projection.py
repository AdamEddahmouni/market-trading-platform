"""Tests for IMP squeeze bridge causal intelligence projection."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.donor_bridge.projections import build_workspace_squeeze_payload  # noqa: E402


class WorkspaceCausalProjectionTests(unittest.TestCase):
    def test_projects_causal_intelligence_from_donor_detail(self) -> None:
        detail = {
            "identity": {"symbol": "AVTX", "mode_label": "FROZEN_RESEARCH"},
            "available": True,
            "freshness": "FROZEN",
            "phase3a": {"summary": "10 PASS / 5 FAIL / 10 UNKNOWN"},
            "research_detection": {"status": "INSUFFICIENT_EVIDENCE", "ignition_state": "VULNERABLE"},
            "outcome": {"status": "UNKNOWN", "reasons": []},
            "evidence_coverage": {"label": "15 / 25"},
            "provenance": {"source_kind": "SANITIZED_AGGREGATE"},
            "rules": [],
            "causal_intelligence": {
                "model_version": "squeeze_causal_baseline.v1",
                "state": "VULNERABLE",
                "overall_confidence": "MEDIUM",
                "explanation": {"summary": "Structural vulnerability present."},
            },
        }
        with patch(
            "market_platform_foundation.donor_bridge.projections.is_available",
            return_value=True,
        ), patch(
            "market_platform_foundation.donor_bridge.projections.fetch_frozen_candidate_detail",
            return_value=detail,
        ):
            payload = build_workspace_squeeze_payload("AVTX")

        self.assertEqual(payload["ignition_state"], "VULNERABLE")
        self.assertIsNotNone(payload.get("causal_intelligence"))
        self.assertEqual(payload["state_machine"]["current_state"], "VULNERABLE")
        self.assertEqual(payload["state_machine"]["causal_model_version"], "squeeze_causal_baseline.v1")

    def test_ignition_state_ignores_research_detection_without_causal(self) -> None:
        detail = {
            "identity": {"symbol": "AVTX", "mode_label": "FROZEN_RESEARCH"},
            "available": True,
            "freshness": "FROZEN",
            "phase3a": {"status": "PASS"},
            "research_detection": {
                "status": "INSUFFICIENT_EVIDENCE",
                "ignition_state": "VULNERABLE",
            },
            "outcome": {"status": "UNKNOWN", "reasons": []},
            "evidence_coverage": {"label": "15 / 25"},
            "provenance": {"source_kind": "SANITIZED_AGGREGATE"},
            "rules": [],
        }
        with patch(
            "market_platform_foundation.donor_bridge.projections.is_available",
            return_value=True,
        ), patch(
            "market_platform_foundation.donor_bridge.projections.fetch_frozen_candidate_detail",
            return_value=detail,
        ):
            payload = build_workspace_squeeze_payload("AVTX")

        self.assertEqual(payload["ignition_state"], "UNKNOWN")
        self.assertIn("CAUSAL_INTELLIGENCE_UNAVAILABLE", payload["ignition_state_quality_flags"])
        self.assertEqual(payload["state_machine"]["current_state"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
