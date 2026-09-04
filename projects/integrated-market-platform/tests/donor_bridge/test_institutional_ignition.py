"""Tests for institutional ignition evidence on squeeze workspace payloads."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.donor_bridge.institutional_ignition import (  # noqa: E402
    build_institutional_borrow_card,
    build_institutional_depth_card,
    build_institutional_options_card,
    build_supplemental_ignition_evidence,
)
from market_platform_foundation.donor_bridge.projections import (  # noqa: E402
    build_workspace_squeeze_payload,
)
from market_platform_foundation.features.institutional import configure_institutional_ledger, get_institutional_ledger
from market_platform_foundation.providers.whale_ledger import build_combined_fixture_ledger
from market_platform_foundation.ui_api.store import ReplayStore

_SAMPLE_DETAIL = {
    "identity": {"symbol": "AVTX", "mode_label": "FROZEN_RESEARCH"},
    "available": True,
    "freshness": "FROZEN",
    "phase3a": {"summary": "10 PASS / 5 FAIL / 10 UNKNOWN", "counts": {"PASS": 10, "FAIL": 5, "UNKNOWN": 10}},
    "research_detection": {"status": "INSUFFICIENT_EVIDENCE"},
    "outcome": {"status": "UNKNOWN", "reasons": ["No forward outcome in sanitized demo."]},
    "evidence_coverage": {"label": "15 / 25 rules supported"},
    "provenance": {"source_kind": "SANITIZED_AGGREGATE"},
    "rules": [{"rule_id": "R1", "category": "SHORT_PRESSURE_CONFIRMATION", "outcome": "PASS", "reason": "x"}],
}


class InstitutionalIgnitionTests(unittest.TestCase):
    store: ReplayStore

    @classmethod
    def setUpClass(cls) -> None:
        cls.store = ReplayStore(collection_root=ROOT.parent)
        cls.store.load()

    def setUp(self) -> None:
        self._original_ledger = get_institutional_ledger()
        configure_institutional_ledger(build_combined_fixture_ledger())

    def tearDown(self) -> None:
        configure_institutional_ledger(self._original_ledger)

    def test_biya_supplemental_options_card_is_admitted(self) -> None:
        cards = build_supplemental_ignition_evidence(
            "BIYA",
            prediction_cutoff=self.store.prediction_cutoff(),
        )
        self.assertEqual(len(cards), 4)
        borrow = cards[1]
        self.assertEqual(borrow["label"], "Borrow")
        self.assertEqual(borrow["state"], "PARTIAL")
        options = cards[2]
        self.assertEqual(options["label"], "Options")
        self.assertEqual(options["state"], "ADMITTED")
        self.assertIn("admitted activities", options["detail"])
        self.assertEqual(options["explain_ref"], "explain:options:BIYA")
        depth = cards[3]
        self.assertEqual(depth["label"], "Depth")
        self.assertEqual(depth["state"], "UNAVAILABLE")

    def test_nvda_depth_card_is_admitted(self) -> None:
        card = build_institutional_depth_card(
            "NVDA",
            prediction_cutoff=self.store.prediction_cutoff(),
        )
        self.assertEqual(card["state"], "ADMITTED")
        self.assertEqual(card["explain_ref"], "explain:order-book:NVDA")

    def test_biya_borrow_card_is_partial_disclosure(self) -> None:
        card = build_institutional_borrow_card(
            "BIYA",
            prediction_cutoff=self.store.prediction_cutoff(),
        )
        self.assertEqual(card["state"], "PARTIAL")
        self.assertEqual(card["explain_ref"], "explain:disclosure:BIYA")

    def test_avtx_supplemental_options_stays_unavailable(self) -> None:
        cards = build_supplemental_ignition_evidence(
            "AVTX",
            prediction_cutoff=self.store.prediction_cutoff(),
        )
        options = cards[2]
        self.assertEqual(options["state"], "UNAVAILABLE")

    def test_biya_unavailable_squeeze_includes_institutional_cards(self) -> None:
        with patch(
            "market_platform_foundation.donor_bridge.projections.is_available",
            return_value=True,
        ), patch(
            "market_platform_foundation.donor_bridge.projections.fetch_frozen_candidate_detail",
            return_value={"available": False, "error": "BIYA is not one of the 13 frozen research cases."},
        ):
            payload = build_workspace_squeeze_payload(
                "BIYA",
                prediction_cutoff=self.store.prediction_cutoff(),
            )

        self.assertFalse(payload["available"])
        self.assertEqual(len(payload["ignition_evidence"]), 4)
        options = next(card for card in payload["ignition_evidence"] if card["label"] == "Options")
        self.assertEqual(options["state"], "ADMITTED")

    def test_avtx_frozen_squeeze_replaces_options_with_institutional_lookup(self) -> None:
        with patch(
            "market_platform_foundation.donor_bridge.projections.is_available",
            return_value=True,
        ), patch(
            "market_platform_foundation.donor_bridge.projections.fetch_frozen_candidate_detail",
            return_value=_SAMPLE_DETAIL,
        ):
            payload = build_workspace_squeeze_payload(
                "AVTX",
                prediction_cutoff=self.store.prediction_cutoff(),
            )

        options = next(card for card in payload["ignition_evidence"] if card["label"] == "Options")
        self.assertEqual(options["state"], "UNAVAILABLE")
        self.assertIn("No entitled options source", options["detail"])

    def test_options_card_without_replay_context_stays_frozen_unavailable(self) -> None:
        card = build_institutional_options_card("BIYA", prediction_cutoff=None)
        self.assertEqual(card["state"], "UNAVAILABLE")
        self.assertIn("replay context", card["detail"])


if __name__ == "__main__":
    unittest.main()
