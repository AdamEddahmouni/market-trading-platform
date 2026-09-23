"""Path B: NEWS_EVENT activates from canonical NEWS_ARTICLE; UOA stays inactive."""

from __future__ import annotations

import inspect
import unittest

from market_platform_foundation.intelligence.contracts import (
    ContractKind,
    ContractReference,
    QualityState,
    QualitySummary,
    SemanticEventType,
    SignalV1,
)
from market_platform_foundation.intelligence.routing import (
    DetectionFrame,
    DetectorSupportStatus,
    EventDetectorEngine,
)
from market_platform_foundation.intelligence.routing.detector_engine import INACTIVE_SEMANTIC_TYPES
from tests.intelligence.routing_fixtures import (
    T,
    event,
    quality_decision,
    snapshot,
)


class PathBNewsEventActivationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = EventDetectorEngine()

    def _news_frame(self, event_type: str = "NEWS", *, event_id: str = "news-1", payload: dict | None = None):
        snap = snapshot(event_id, decision_time_ns=T + 1, event_ids=(event_id,))
        body = {"headline": "widget sold"} if payload is None else payload
        return DetectionFrame(
            snapshot=snap,
            events=(event(snap, event_id, event_type, body),),
            quality_decision=quality_decision(decision_time_ns=snap.decision_time_ns),
        )

    def _article_payload(self, *, headline: str = "Company reports earnings beat") -> dict:
        return {
            "headline": headline,
            "summary": "Quarterly results released",
            "source_id": "fixture-wire",
            "instrument_linkages": [
                {
                    "instrument_id": "US:XYZ",
                    "provider_symbol": "XYZ",
                    "asset_class": "EQUITY",
                    "linkage_method": "PROVIDER_SYMBOL",
                    "confidence": "EXPLICIT",
                }
            ],
        }

    def test_support_matrix_news_implemented_uoa_inactive(self) -> None:
        support = {row.semantic_event_type: row for row in self.engine.support_matrix()}
        self.assertEqual(support[SemanticEventType.NEWS_EVENT].status, DetectorSupportStatus.IMPLEMENTED)
        self.assertEqual(
            support[SemanticEventType.UNUSUAL_OPTIONS_ACTIVITY].status,
            DetectorSupportStatus.INACTIVE_INPUT_UNAVAILABLE,
        )
        self.assertEqual(INACTIVE_SEMANTIC_TYPES, {SemanticEventType.UNUSUAL_OPTIONS_ACTIVITY})

    def test_tempting_news_event_input_does_not_emit_news_detection(self) -> None:
        result = self.engine.detect(self._news_frame("NEWS"))
        self.assertEqual(result.detections, ())
        self.assertNotIn("NEWS_EVENT:INACTIVE_INPUT_UNAVAILABLE", result.diagnostics)
        self.assertIn("NEWS_EVENT:NEWS_LANE_NOT_CANONICAL", result.diagnostics)
        self.assertEqual(self.engine.state_snapshot().seen_news_event_count, 0)

    def test_sec_filing_is_not_relabeled_news_event(self) -> None:
        result = self.engine.detect(self._news_frame("8-K"))
        self.assertEqual(result.detections, ())
        self.assertNotIn(SemanticEventType.NEWS_EVENT, {row.semantic_event_type for row in result.detections})
        self.assertIn("NEWS_EVENT:FILING_IS_NOT_NEWS_EVENT", result.diagnostics)
        self.assertNotIn("NEWS_EVENT:NEWS_LANE_NOT_CANONICAL", result.diagnostics)

    def test_option_like_signal_does_not_emit_uoa(self) -> None:
        snap = snapshot("opt-1", decision_time_ns=T + 1)
        option_signal = SignalV1(
            signal_id="opt-vol-1",
            schema_version="1",
            signal_type="option_volume",
            scope=snap.scope,
            as_of_time_ns=snap.decision_time_ns,
            value=1_000_000.0,
            quality=QualitySummary(state=QualityState.GOOD),
            source_snapshot_ref=ContractReference(kind=ContractKind.SNAPSHOT.value, id=snap.snapshot_id),
            calculation_lineage={"calculator_id": "option-volume-calculator", "calculator_version": "1"},
        )
        result = self.engine.detect(
            DetectionFrame(
                snapshot=snap,
                signals=(option_signal,),
                quality_decision=quality_decision(decision_time_ns=snap.decision_time_ns),
            )
        )
        self.assertEqual(result.detections, ())
        self.assertIn("UNUSUAL_OPTIONS_ACTIVITY:INACTIVE_INPUT_UNAVAILABLE", result.diagnostics)
        self.assertIn("UNUSUAL_OPTIONS_ACTIVITY:OPTION_CHAIN_NOT_CANONICAL", result.diagnostics)

    def test_implemented_path_b_detectors_still_emit_with_uoa_honesty(self) -> None:
        first_snap = snapshot("si-1", decision_time_ns=T + 1, event_ids=("si-1",))
        first = event(first_snap, "si-1", "SHORT_INTEREST", {"current_short_position_quantity": 100.0})
        self.engine.detect(
            DetectionFrame(
                snapshot=first_snap,
                events=(first,),
                quality_decision=quality_decision(decision_time_ns=first_snap.decision_time_ns),
            )
        )
        second_snap = snapshot("si-2", decision_time_ns=T + 2, event_ids=("si-2",))
        second = event(second_snap, "si-2", "SHORT_INTEREST", {"current_short_position_quantity": 125.0})
        result = self.engine.detect(
            DetectionFrame(
                snapshot=second_snap,
                events=(second,),
                quality_decision=quality_decision(decision_time_ns=second_snap.decision_time_ns),
            )
        )
        self.assertEqual(len(result.detections), 1)
        self.assertEqual(result.detections[0].semantic_event_type, SemanticEventType.BORROW_CHANGE)
        self.assertNotIn("NEWS_EVENT:INACTIVE_INPUT_UNAVAILABLE", result.diagnostics)
        self.assertIn("UNUSUAL_OPTIONS_ACTIVITY:INACTIVE_INPUT_UNAVAILABLE", result.diagnostics)
        self.assertNotIn(SemanticEventType.NEWS_EVENT, {row.semantic_event_type for row in result.detections})
        self.assertNotIn(
            SemanticEventType.UNUSUAL_OPTIONS_ACTIVITY,
            {row.semantic_event_type for row in result.detections},
        )

    def test_path_a_is_not_replaced(self) -> None:
        source = inspect.getsource(EventDetectorEngine)
        self.assertNotIn("path_a", source)
        self.assertNotIn("PathA", source)
        self.assertIn("INACTIVE_INPUT_UNAVAILABLE", source)


if __name__ == "__main__":
    unittest.main()
