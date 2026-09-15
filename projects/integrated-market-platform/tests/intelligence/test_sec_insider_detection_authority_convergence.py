"""SEC DetectionV1 authority: ingress vs BUILD 09 replay share one identity."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from market_platform_foundation.intelligence.contracts import (
    ContractKind,
    ContractReference,
    SnapshotV1,
)
from market_platform_foundation.intelligence.normalization.models import (
    IngestionMode,
    NormalizationContext,
)
from market_platform_foundation.intelligence.observation_ingress import (
    build_production_observation_ingress_router,
    detector_stub_consumer,
    dispatch_sec_insider_row,
)
from market_platform_foundation.intelligence.observation_ingress.types import IngressDispatchContext
from market_platform_foundation.intelligence.persistence import (
    InMemoryIntelligenceRepository,
    RepositoryPutResult,
)
from market_platform_foundation.intelligence.routing import DetectionFrame, EventDetectorEngine
from market_platform_foundation.intelligence.opportunity.sec_insider.replay_persist import (
    persist_sec_insider_from_detection_frame,
)
from tests.intelligence.routing_fixtures import quality_decision
from tests.intelligence.test_sec_insider_opportunity_vertical import (
    ONE_DAY,
    _PLATFORM_RECEIVED_NS,
    _lane_b_event_from_row,
    _snapshot,
)

_MT_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "market_trackers"
    / "sec_insider"
    / "form4_open_market_purchase.json"
)
_EDGAR_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "sec_edgar"
    / "insider_form4_nvda_submission.json"
)


def _dispatch_ctx() -> IngressDispatchContext:
    return IngressDispatchContext(
        dispatch_time_ns=_PLATFORM_RECEIVED_NS + ONE_DAY * 2,
        ingestion_mode=IngestionMode.FIXTURE,
        source_label="test.sec_detection_authority",
    )


def _ingress_router(repo: InMemoryIntelligenceRepository):
    return build_production_observation_ingress_router(repo)


def _dispatch_row(router, repo: InMemoryIntelligenceRepository):
    row = json.loads(_MT_FIXTURE.read_text(encoding="utf-8"))
    edgar = json.loads(_EDGAR_FIXTURE.read_text(encoding="utf-8"))
    norm_ctx = NormalizationContext(
        received_time_ns=_PLATFORM_RECEIVED_NS,
        ingestion_mode=IngestionMode.FIXTURE,
    )
    receipt = dispatch_sec_insider_row(
        router,
        row,
        normalization_context=norm_ctx,
        dispatch_context=_dispatch_ctx(),
        edgar_primary=edgar,
    )
    assert receipt is not None
    event = repo.get_event(receipt.event_id)
    assert event is not None
    return receipt, event


def _replay_frame(event, *, snapshot_id: str = "SNAP-REPLAY-FRAME") -> DetectionFrame:
    base = _snapshot(
        decision_time_ns=event.available_time_ns + ONE_DAY,
        instrument=event.instrument_id or "",
    )
    snapshot = SnapshotV1(
        snapshot_id=snapshot_id,
        schema_version=base.schema_version,
        decision_time_ns=base.decision_time_ns,
        scope=base.scope,
        quality=base.quality,
        source_event_refs=(ContractReference(kind=ContractKind.EVENT.value, id=event.event_id),),
    )
    quality = quality_decision(decision_time_ns=snapshot.decision_time_ns)
    return DetectionFrame(
        snapshot=snapshot,
        signals=(),
        events=(event,),
        quality_decision=quality,
    )


def _repo_counts(repo: InMemoryIntelligenceRepository) -> tuple[int, int, int]:
    with repo._lock:  # noqa: SLF001 — test-only inventory
        detections = len(repo._stores["detections"])
        evidence = len(repo._stores["evidence"])
        snapshots = len(repo._stores["snapshots"])
    return detections, evidence, snapshots


class SecInsiderDetectionAuthorityConvergenceTests(unittest.TestCase):
    def test_duplicate_ingress_dispatch(self) -> None:
        repo = InMemoryIntelligenceRepository()
        router = _ingress_router(repo)
        receipt1, _ = _dispatch_row(router, repo)
        receipt2, _ = _dispatch_row(router, repo)
        self.assertFalse(receipt1.duplicate)
        self.assertTrue(receipt2.duplicate)
        self.assertEqual(_repo_counts(repo), (1, 1, 1))

    def test_ingress_then_replay_same_detection(self) -> None:
        repo = InMemoryIntelligenceRepository()
        router = _ingress_router(repo)
        _, event = _dispatch_row(router, repo)
        ingress_detection_id = next(iter(repo._stores["detections"]))  # noqa: SLF001

        engine = EventDetectorEngine()
        frame = _replay_frame(event)
        detection, puts = persist_sec_insider_from_detection_frame(repo, engine, frame)
        self.assertIsNotNone(detection)
        assert detection is not None
        self.assertEqual(detection.detection_id, ingress_detection_id)
        self.assertIsNotNone(puts)
        assert puts is not None
        self.assertEqual(puts[0], RepositoryPutResult.ALREADY_PRESENT)
        self.assertEqual(puts[1], RepositoryPutResult.ALREADY_PRESENT)
        self.assertEqual(_repo_counts(repo), (1, 1, 1))

    def test_replay_then_ingress_same_detection(self) -> None:
        repo = InMemoryIntelligenceRepository()
        event = _lane_b_event_from_row()
        repo.put_event(event)
        engine = EventDetectorEngine()
        frame = _replay_frame(event)
        detection, puts = persist_sec_insider_from_detection_frame(repo, engine, frame)
        self.assertIsNotNone(detection)
        assert detection is not None
        self.assertIsNotNone(puts)
        self.assertEqual(_repo_counts(repo), (1, 1, 1))

        seen: set[str] = set()
        consumer = detector_stub_consumer(seen, repository=repo)
        consumer.consume(event, context=_dispatch_ctx())
        self.assertEqual(_repo_counts(repo), (1, 1, 1))
        self.assertEqual(len(seen), 1)

    def test_different_filing_events_two_detections(self) -> None:
        repo = InMemoryIntelligenceRepository()
        router = _ingress_router(repo)
        _dispatch_row(router, repo)
        row2 = json.loads(_MT_FIXTURE.read_text(encoding="utf-8"))
        row2 = dict(row2)
        row2["id"] = row2["accessionNumber"] + ":nd:99"
        row2["shares"] = 50
        edgar = json.loads(_EDGAR_FIXTURE.read_text(encoding="utf-8"))
        norm_ctx = NormalizationContext(
            received_time_ns=_PLATFORM_RECEIVED_NS,
            ingestion_mode=IngestionMode.FIXTURE,
        )
        receipt = dispatch_sec_insider_row(
            router,
            row2,
            normalization_context=norm_ctx,
            dispatch_context=_dispatch_ctx(),
            edgar_primary=edgar,
        )
        self.assertIsNotNone(receipt)
        self.assertFalse(receipt.duplicate)
        self.assertEqual(_repo_counts(repo), (2, 2, 2))

    def test_same_accession_distinct_row_ids_two_detections(self) -> None:
        repo = InMemoryIntelligenceRepository()
        router = _ingress_router(repo)
        row_a = json.loads(_MT_FIXTURE.read_text(encoding="utf-8"))
        row_b = dict(row_a)
        row_b["id"] = f"{row_a['accessionNumber']}:nd:1"
        row_a["id"] = f"{row_a['accessionNumber']}:nd:0"
        edgar = json.loads(_EDGAR_FIXTURE.read_text(encoding="utf-8"))
        norm_ctx = NormalizationContext(
            received_time_ns=_PLATFORM_RECEIVED_NS,
            ingestion_mode=IngestionMode.FIXTURE,
        )
        dispatch_sec_insider_row(
            router,
            row_a,
            normalization_context=norm_ctx,
            dispatch_context=_dispatch_ctx(),
            edgar_primary=edgar,
        )
        dispatch_sec_insider_row(
            router,
            row_b,
            normalization_context=norm_ctx,
            dispatch_context=_dispatch_ctx(),
            edgar_primary=edgar,
        )
        self.assertEqual(_repo_counts(repo), (2, 2, 2))

    def test_engine_and_vertical_detection_ids_match(self) -> None:
        event = _lane_b_event_from_row()
        engine = EventDetectorEngine()
        frame = _replay_frame(event, snapshot_id="SNAP-BUILD09-REPLAY")
        engine_result = engine.detect(frame)
        self.assertEqual(len(engine_result.detections), 1)
        from market_platform_foundation.intelligence.opportunity.sec_insider import run_sec_insider_vertical

        vertical = run_sec_insider_vertical(event=event, snapshot=frame.snapshot)
        assert vertical.detection is not None
        self.assertEqual(engine_result.detections[0].detection_id, vertical.detection.detection_id)
        self.assertEqual(
            engine_result.detections[0].detection_id,
            vertical.evidence.metadata.get("detection_id"),
        )


if __name__ == "__main__":
    unittest.main()
