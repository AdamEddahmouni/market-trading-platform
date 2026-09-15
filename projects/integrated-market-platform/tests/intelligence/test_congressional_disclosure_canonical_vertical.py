"""Golden path: congressional PTR row → ingress router → evidence / candidate context."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.normalization.models import (  # noqa: E402
    IngestionMode,
    NormalizationContext,
)
from market_platform_foundation.intelligence.observation_ingress import (  # noqa: E402
    build_production_observation_ingress_router,
    dispatch_congressional_disclosure_row,
)
from market_platform_foundation.intelligence.observation_ingress.types import IngressDispatchContext  # noqa: E402
from market_platform_foundation.intelligence.opportunity.congressional_disclosure import (  # noqa: E402
    FORBIDDEN_CANDIDATE_DIRECTIONS,
    STRATEGY_FAMILY,
    assert_candidate_not_directional,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository  # noqa: E402

_MT_FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "market_trackers"
    / "congressional_disclosure"
    / "senate_stock_purchase.json"
)
_PTR_FIXTURE = ROOT / "tests" / "fixtures" / "congressional_disclosure" / "ptr_primary_senate_example.json"
_PLATFORM_RECEIVED_NS = 1_725_100_800_000_000_000
ONE_DAY = 86_400_000_000_000

_STATUS_FLAG = "CONGRESSIONAL_DISCLOSURE_RUNTIME_READY"


class CongressionalDisclosureCanonicalVerticalTests(unittest.TestCase):
    def test_CONGRESSIONAL_DISCLOSURE_RUNTIME_READY(self) -> None:
        row = json.loads(_MT_FIXTURE.read_text(encoding="utf-8"))
        primary = json.loads(_PTR_FIXTURE.read_text(encoding="utf-8"))
        norm_ctx = NormalizationContext(
            received_time_ns=_PLATFORM_RECEIVED_NS,
            ingestion_mode=IngestionMode.FIXTURE,
        )
        repo = InMemoryIntelligenceRepository()
        evidence_rows: list[dict[str, str]] = []
        router = build_production_observation_ingress_router(
            repo,
            oe_evidence_sink=evidence_rows,
        )
        dispatch_ctx = IngressDispatchContext(
            dispatch_time_ns=_PLATFORM_RECEIVED_NS + ONE_DAY,
            ingestion_mode=IngestionMode.FIXTURE,
            source_label="test.congressional_ptr_canonical",
        )
        receipt = dispatch_congressional_disclosure_row(
            router,
            row,
            normalization_context=norm_ctx,
            dispatch_context=dispatch_ctx,
            ptr_primary=primary,
        )
        self.assertIsNotNone(receipt)
        assert receipt is not None
        self.assertFalse(receipt.duplicate)
        event = repo.get_event(receipt.event_id)
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(len(evidence_rows), 1)
        oe_row = evidence_rows[0]
        self.assertEqual(oe_row["event_id"], receipt.event_id)
        self.assertTrue(oe_row.get("evidence_id", "").startswith("EVID-"))
        self.assertTrue(oe_row.get("detection_id", "").startswith("DET-"))
        self.assertTrue(oe_row.get("opportunity_candidate_id", "").startswith("OPP-CAND-"))
        self.assertEqual(oe_row.get("strategy_family"), STRATEGY_FAMILY)

        stored_evidence = repo.get_evidence(oe_row["evidence_id"])
        self.assertIsNotNone(stored_evidence)
        assert stored_evidence is not None
        self.assertIsNone(stored_evidence.directional_score)
        self.assertIn("DISCLOSED_SIDE_NOT_EXECUTION_SIDE", stored_evidence.evidence_against)

        candidate_id = oe_row["opportunity_candidate_id"]
        self.assertNotIn(str(FORBIDDEN_CANDIDATE_DIRECTIONS), candidate_id)
        self.assertEqual(_STATUS_FLAG, "CONGRESSIONAL_DISCLOSURE_RUNTIME_READY")

    def test_buy_side_not_mapped_to_long(self) -> None:
        row = json.loads(_MT_FIXTURE.read_text(encoding="utf-8"))
        norm_ctx = NormalizationContext(
            received_time_ns=_PLATFORM_RECEIVED_NS,
            ingestion_mode=IngestionMode.FIXTURE,
        )
        repo = InMemoryIntelligenceRepository()
        evidence_rows: list[dict[str, str]] = []
        router = build_production_observation_ingress_router(repo, oe_evidence_sink=evidence_rows)
        receipt = dispatch_congressional_disclosure_row(
            router,
            row,
            normalization_context=norm_ctx,
            dispatch_context=IngressDispatchContext(
                dispatch_time_ns=_PLATFORM_RECEIVED_NS + ONE_DAY,
                ingestion_mode=IngestionMode.FIXTURE,
            ),
        )
        assert receipt is not None
        oe_row = evidence_rows[0]
        detection = repo.get_detection(oe_row["detection_id"])
        assert detection is not None
        self.assertEqual(row["side"], "buy")
        self.assertNotIn("LONG", detection.reason_codes)
        assert_candidate_not_directional({"direction_or_expression": "REGULATORY_DISCLOSURE_FACT"})


if __name__ == "__main__":
    unittest.main()
