"""Golden path: SEC row → ingress router → detector vertical → evidence/candidate."""

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
    dispatch_sec_insider_row,
)
from market_platform_foundation.intelligence.observation_ingress.types import IngressDispatchContext  # noqa: E402
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository  # noqa: E402
from market_platform_foundation.intelligence.routing import (  # noqa: E402
    DetectionFrame,
    EventDetectorEngine,
)
from market_platform_foundation.intelligence.opportunity.sec_insider.constants import (  # noqa: E402
    FORBIDDEN_CANDIDATE_DIRECTIONS,
    STRATEGY_FAMILY,
)
from tests.intelligence.test_sec_insider_opportunity_vertical import (  # noqa: E402
    _EDGAR_FIXTURE,
    _MT_FIXTURE,
    _PLATFORM_RECEIVED_NS,
    ONE_DAY,
    _snapshot,
)

_STATUS_FLAG = "SEC_TO_OPPORTUNITY_EVIDENCE_VERTICAL_READY"


class SecInsiderCanonicalVerticalTests(unittest.TestCase):
    def test_SEC_TO_OPPORTUNITY_EVIDENCE_VERTICAL_READY(self) -> None:
        row = json.loads(_MT_FIXTURE.read_text(encoding="utf-8"))
        edgar = json.loads(_EDGAR_FIXTURE.read_text(encoding="utf-8"))
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
            source_label="test.sec_insider_canonical",
        )
        receipt = dispatch_sec_insider_row(
            router,
            row,
            normalization_context=norm_ctx,
            dispatch_context=dispatch_ctx,
            edgar_primary=edgar,
        )
        self.assertIsNotNone(receipt)
        assert receipt is not None
        self.assertFalse(receipt.duplicate)
        event_id = receipt.event_id
        event = repo.get_event(event_id)
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(len(evidence_rows), 1)
        oe_row = evidence_rows[0]
        self.assertEqual(oe_row["event_id"], event_id)
        self.assertTrue(oe_row.get("evidence_id", "").startswith("EVID-"))
        self.assertTrue(oe_row.get("detection_id", "").startswith("DET-"))
        candidate_id = oe_row.get("opportunity_candidate_id", "")
        self.assertTrue(candidate_id.startswith("OPP-CAND-"))
        self.assertEqual(oe_row.get("strategy_family"), STRATEGY_FAMILY)

        stored_evidence = repo.get_evidence(oe_row["evidence_id"])
        self.assertIsNotNone(stored_evidence)
        assert stored_evidence is not None
        self.assertIsNone(stored_evidence.directional_score)

        engine = EventDetectorEngine()
        snapshot = _snapshot(
            decision_time_ns=event.available_time_ns + ONE_DAY,
            instrument=event.instrument_id or "",
        )
        from market_platform_foundation.intelligence.contracts import ContractKind, ContractReference, SnapshotV1

        snapshot = SnapshotV1(
            snapshot_id=snapshot.snapshot_id,
            schema_version=snapshot.schema_version,
            decision_time_ns=snapshot.decision_time_ns,
            scope=snapshot.scope,
            quality=snapshot.quality,
            source_event_refs=(
                ContractReference(kind=ContractKind.EVENT.value, id=event.event_id),
            ),
        )
        from tests.intelligence.routing_fixtures import quality_decision

        quality = quality_decision(decision_time_ns=snapshot.decision_time_ns)
        detected = engine.detect(
            DetectionFrame(
                snapshot=snapshot,
                signals=(),
                events=(event,),
                quality_decision=quality,
            )
        )
        self.assertEqual(len(detected.detections), 1)
        self.assertEqual(
            detected.detections[0].semantic_event_type.value,
            "SEC_INSIDER_DISCLOSURE",
        )

        # Candidate projection is forecast-gated; not OpportunityV1 mint via assess().
        self.assertNotIn(
            str(FORBIDDEN_CANDIDATE_DIRECTIONS),
            oe_row.get("opportunity_candidate_id", ""),
        )
        self.assertEqual(_STATUS_FLAG, "SEC_TO_OPPORTUNITY_EVIDENCE_VERTICAL_READY")


if __name__ == "__main__":
    unittest.main()
