"""SOFTWARE_CONTROLLED / FIXTURE_REPLAY: NEWS_ARTICLE → NEWS_EVENT DetectionV1."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts import (
    EventV1,
    QualityState,
    QualitySummary,
    SemanticEventType,
    SourceReference,
)
from market_platform_foundation.intelligence.opportunity.news_event import (
    NewsEventFailureCode,
    run_news_event_vertical,
    validate_news_event_inputs,
)
from market_platform_foundation.intelligence.routing import DetectionFrame, EventDetectorEngine
from tests.intelligence.routing_fixtures import T, quality_decision, snapshot

# Evidence class for this suite — software fixture replay only, not empirical.
EVIDENCE_CLASS = "SOFTWARE_CONTROLLED"


def _article_event(
    *,
    event_id: str,
    decision_time_ns: int,
    headline: str = "Company reports earnings beat",
    instrument_id: str | None = "US:XYZ",
    event_time_ns: int | None = None,
    available_time_ns: int | None = None,
    asset_class: str = "EQUITY",
    quality: QualityState = QualityState.GOOD,
) -> EventV1:
    linkages = []
    if instrument_id:
        linkages.append(
            {
                "instrument_id": instrument_id,
                "provider_symbol": instrument_id.split(":")[-1],
                "asset_class": asset_class,
                "linkage_method": "PROVIDER_SYMBOL",
                "confidence": "EXPLICIT",
            }
        )
    published = event_time_ns if event_time_ns is not None else decision_time_ns - 60_000_000_000
    available = available_time_ns if available_time_ns is not None else decision_time_ns
    return EventV1(
        event_id=event_id,
        schema_version="1",
        event_type="NEWS_ARTICLE",
        event_time_ns=published,
        available_time_ns=available,
        payload={
            "headline": headline,
            "summary": "Fixture article body",
            "source_id": "fixture-wire",
            "provider_id": "fixture",
            "instrument_linkages": linkages,
        },
        quality=QualitySummary(state=quality),
        source=SourceReference(
            provider_id="fixture",
            source_type="NEWS",
            source_record_id=event_id,
        ),
        instrument_id=instrument_id,
    )


class NewsArticleToNewsEventConvergenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = EventDetectorEngine()

    def _frame(self, event: EventV1, *, decision_time_ns: int):
        snap = snapshot(event.event_id, decision_time_ns=decision_time_ns, event_ids=(event.event_id,))
        return DetectionFrame(
            snapshot=snap,
            events=(event,),
            quality_decision=quality_decision(decision_time_ns=decision_time_ns),
        )

    def test_valid_news_article_emits_news_event_detection(self) -> None:
        decision = T + 1
        article = _article_event(event_id="art-1", decision_time_ns=decision)
        result = self.engine.detect(self._frame(article, decision_time_ns=decision))
        self.assertEqual(len(result.detections), 1)
        detection = result.detections[0]
        self.assertEqual(detection.semantic_event_type, SemanticEventType.NEWS_EVENT)
        self.assertEqual(detection.metadata.get("evidence_class"), EVIDENCE_CLASS)
        self.assertIn("earnings", detection.metadata.get("matched_catalyst_ids", []))
        self.assertEqual(self.engine.state_snapshot().seen_news_event_count, 1)
        self.assertNotIn("NEWS_EVENT:INACTIVE_INPUT_UNAVAILABLE", result.diagnostics)
        self.assertNotIn("NEWS_EVENT:NEWS_LANE_NOT_CANONICAL", result.diagnostics)

    def test_vertical_pipeline_matches_engine(self) -> None:
        decision = T + 1
        article = _article_event(event_id="art-vert", decision_time_ns=decision)
        snap = snapshot(article.event_id, decision_time_ns=decision, event_ids=(article.event_id,))
        vertical = run_news_event_vertical(event=article, snapshot=snap)
        self.assertTrue(vertical.ok)
        assert vertical.detection is not None
        engine_result = self.engine.detect(
            DetectionFrame(
                snapshot=snap,
                events=(article,),
                quality_decision=quality_decision(decision_time_ns=decision),
            )
        )
        self.assertEqual(engine_result.detections[0].detection_id, vertical.detection.detection_id)

    def test_missing_symbol_rejects(self) -> None:
        decision = T + 1
        article = _article_event(event_id="art-nosym", decision_time_ns=decision, instrument_id=None)
        result = self.engine.detect(self._frame(article, decision_time_ns=decision))
        self.assertEqual(result.detections, ())
        self.assertIn(f"NEWS_EVENT:{NewsEventFailureCode.MISSING_SYMBOL.value}", result.diagnostics)

    def test_stale_pit_invalid_rejects(self) -> None:
        decision = T + 1
        # Publication older than default 72h recency window relative to decision time.
        stale_pub = decision - (80 * 3600 * 1_000_000_000)
        article = _article_event(
            event_id="art-stale",
            decision_time_ns=decision,
            event_time_ns=stale_pub,
            available_time_ns=stale_pub + 1_000_000_000,
        )
        result = self.engine.detect(self._frame(article, decision_time_ns=decision))
        self.assertEqual(result.detections, ())
        self.assertIn(f"NEWS_EVENT:{NewsEventFailureCode.STALE_PIT_INVALID.value}", result.diagnostics)

    def test_unsupported_instrument_rejects(self) -> None:
        decision = T + 1
        article = _article_event(
            event_id="art-fx",
            decision_time_ns=decision,
            instrument_id="FX:EURUSD",
            asset_class="FX",
        )
        # Snapshot scope is US:XYZ from fixtures — FX instrument is unsupported.
        result = self.engine.detect(self._frame(article, decision_time_ns=decision))
        self.assertEqual(result.detections, ())
        self.assertIn(f"NEWS_EVENT:{NewsEventFailureCode.UNSUPPORTED_INSTRUMENT.value}", result.diagnostics)

    def test_duplicate_article_deterministic_dedupe(self) -> None:
        decision = T + 1
        article = _article_event(event_id="art-dup", decision_time_ns=decision)
        first = self.engine.detect(self._frame(article, decision_time_ns=decision))
        self.assertEqual(len(first.detections), 1)
        second = self.engine.detect(
            DetectionFrame(
                snapshot=snapshot("art-dup-2", decision_time_ns=decision + 1, event_ids=("art-dup",)),
                events=(article,),
                quality_decision=quality_decision(decision_time_ns=decision + 1),
            )
        )
        self.assertEqual(second.detections, ())
        self.assertIn("NEWS_EVENT:DUPLICATE_ARTICLE", second.diagnostics)
        self.assertEqual(self.engine.state_snapshot().seen_news_event_count, 1)

    def test_nonmatching_catalyst_emits_no_detection(self) -> None:
        decision = T + 1
        article = _article_event(
            event_id="art-nocat",
            decision_time_ns=decision,
            headline="Local weather remains mild overnight",
        )
        result = self.engine.detect(self._frame(article, decision_time_ns=decision))
        self.assertEqual(result.detections, ())
        self.assertIn(f"NEWS_EVENT:{NewsEventFailureCode.NO_CATALYST_MATCH.value}", result.diagnostics)

    def test_validation_unit_missing_symbol_unknown(self) -> None:
        decision = T + 1
        article = _article_event(event_id="art-v", decision_time_ns=decision, instrument_id=None)
        snap = snapshot("art-v", decision_time_ns=decision, event_ids=("art-v",))
        validated = validate_news_event_inputs(event=article, snapshot=snap)
        self.assertFalse(validated.ok)
        self.assertEqual(validated.reason_codes, (NewsEventFailureCode.MISSING_SYMBOL.value,))


if __name__ == "__main__":
    unittest.main()
