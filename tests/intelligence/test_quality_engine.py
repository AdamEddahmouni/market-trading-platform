"""BUILD 04 — quality finding and validator tests."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.contracts import (  # noqa: E402
    EventV1,
    QualityState,
    QualitySummary,
    SourceReference,
)
from market_platform_foundation.intelligence.quality import (  # noqa: E402
    DecisionAction,
    IntelligenceCapability,
    QualityFindingCode,
    assess_event_quality,
    inspect_quality,
    quality_summary_from_assessment,
)
from market_platform_foundation.intelligence.temporal import (  # noqa: E402
    TemporalIntegrityPolicy,
    inspect_event_temporal_integrity,
)

T0 = 1_000_000_000_000
ONE_SEC = 1_000_000_000
SOURCE_MOOMOO = SourceReference(provider_id="MOOMOO", source_type="quote", source_record_id="q1")
SOURCE_IBKR = SourceReference(provider_id="IBKR", source_type="quote", source_record_id="q2")
QUALITY_GOOD = QualitySummary(state=QualityState.GOOD)


def _quote_event(
    *,
    event_id: str = "evt-quote",
    provider: SourceReference = SOURCE_MOOMOO,
    bid: float = 100.0,
    ask: float = 100.05,
    instrument_id: str = "NVDA",
    available_time_ns: int = T0,
) -> EventV1:
    return EventV1(
        event_id=event_id,
        schema_version="1",
        event_type="QUOTE",
        event_time_ns=available_time_ns,
        available_time_ns=available_time_ns,
        payload={"bid_price": bid, "ask_price": ask, "bid_vol": 100, "ask_vol": 100},
        quality=QUALITY_GOOD,
        source=provider,
        instrument_id=instrument_id,
    )


class QuoteValidationTests(unittest.TestCase):
    def test_valid_quote_no_findings(self) -> None:
        event = _quote_event()
        findings = assess_event_quality(event, decision_time_ns=T0 + ONE_SEC)
        codes = {row.code for row in findings}
        self.assertNotIn(QualityFindingCode.CROSSED_BOOK.value, codes)
        self.assertNotIn(QualityFindingCode.INVALID_QUOTE.value, codes)

    def test_crossed_book_finding(self) -> None:
        event = _quote_event(bid=101.0, ask=100.0)
        findings = assess_event_quality(event, decision_time_ns=T0 + ONE_SEC)
        codes = {row.code for row in findings}
        self.assertIn(QualityFindingCode.CROSSED_BOOK.value, codes)

    def test_invalid_quote_nan(self) -> None:
        event = _quote_event(bid=0.0, ask=0.0)
        findings = assess_event_quality(event, decision_time_ns=T0 + ONE_SEC)
        codes = {row.code for row in findings}
        self.assertIn(QualityFindingCode.INVALID_QUOTE.value, codes)

    def test_locked_book_warning(self) -> None:
        event = _quote_event(bid=100.0, ask=100.0)
        findings = assess_event_quality(event, decision_time_ns=T0 + ONE_SEC)
        codes = {row.code for row in findings}
        self.assertIn(QualityFindingCode.LOCKED_BOOK.value, codes)

    def test_event_input_not_mutated(self) -> None:
        event = _quote_event()
        snapshot = copy.deepcopy(event_v1_to_dict(event))
        assess_event_quality(event, decision_time_ns=T0 + ONE_SEC)
        self.assertEqual(event_v1_to_dict(event), snapshot)


def event_v1_to_dict(event: EventV1):
    from market_platform_foundation.intelligence.contracts import event_v1_to_dict as _fn

    return _fn(event)


class TemporalIntegrationTests(unittest.TestCase):
    def test_future_information_hard_finding(self) -> None:
        event = _quote_event(available_time_ns=T0 + ONE_SEC)
        report = inspect_event_temporal_integrity(event, decision_time_ns=T0)
        findings = assess_event_quality(
            event,
            decision_time_ns=T0,
            temporal_report=report,
        )
        codes = {row.code for row in findings}
        self.assertIn(QualityFindingCode.FUTURE_INFORMATION.value, codes)

    def test_clock_drift_mapping(self) -> None:
        policy = TemporalIntegrityPolicy(max_provider_clock_ahead_ns=1_000)
        event = EventV1(
            event_id="evt-clock",
            schema_version="1",
            event_type="QUOTE",
            event_time_ns=T0,
            available_time_ns=T0,
            payload={"bid_price": 1.0, "ask_price": 1.1, "bid_vol": 1, "ask_vol": 1},
            quality=QUALITY_GOOD,
            source=SOURCE_MOOMOO,
            provider_time_ns=T0 + 5_000_000,
            received_time_ns=T0,
        )
        report = inspect_event_temporal_integrity(event, decision_time_ns=T0, policy=policy)
        findings = assess_event_quality(event, decision_time_ns=T0, temporal_report=report)
        codes = {row.code for row in findings}
        self.assertIn(QualityFindingCode.CLOCK_DRIFT.value, codes)

    def test_stale_information_mapping(self) -> None:
        policy = TemporalIntegrityPolicy(max_age_ns=100, reject_stale_for_usability=True)
        event = _quote_event(available_time_ns=T0)
        report = inspect_event_temporal_integrity(event, decision_time_ns=T0 + 1000, policy=policy)
        findings = assess_event_quality(event, decision_time_ns=T0 + 1000, temporal_report=report)
        codes = {row.code for row in findings}
        self.assertIn(QualityFindingCode.STALE_INFORMATION.value, codes)


class StaleCapabilityTests(unittest.TestCase):
    def test_borrow_stale(self) -> None:
        from market_platform_foundation.intelligence.quality.policy import QualityPolicy

        event = EventV1(
            event_id="evt-borrow",
            schema_version="1",
            event_type="BORROW",
            event_time_ns=T0,
            available_time_ns=T0,
            payload={"rate": 0.02},
            quality=QUALITY_GOOD,
            source=SOURCE_MOOMOO,
            instrument_id="NVDA",
        )
        policy = QualityPolicy(freshness_max_age_ns={"BORROW": 100})
        findings = assess_event_quality(
            event,
            decision_time_ns=T0 + 1000,
            quality_policy=policy,
        )
        codes = {row.code for row in findings}
        self.assertIn(QualityFindingCode.BORROW_STALE.value, codes)

    def test_short_interest_stale(self) -> None:
        from market_platform_foundation.intelligence.quality.policy import QualityPolicy

        event = EventV1(
            event_id="evt-si",
            schema_version="1",
            event_type="SHORT_INTEREST",
            event_time_ns=T0,
            available_time_ns=T0,
            payload={"shares": 1000},
            quality=QUALITY_GOOD,
            source=SOURCE_MOOMOO,
            instrument_id="NVDA",
        )
        policy = QualityPolicy(freshness_max_age_ns={"SHORT_INTEREST": 100})
        findings = assess_event_quality(
            event,
            decision_time_ns=T0 + 1000,
            quality_policy=policy,
        )
        codes = {row.code for row in findings}
        self.assertIn(QualityFindingCode.SHORT_INTEREST_STALE.value, codes)


class QualitySummaryTests(unittest.TestCase):
    def test_crossed_book_maps_invalid(self) -> None:
        event = _quote_event(bid=101.0, ask=100.0)
        assessment = inspect_quality(events=[event], decision_time_ns=T0 + ONE_SEC)
        summary = quality_summary_from_assessment(assessment)
        self.assertEqual(summary.state, QualityState.INVALID)
        self.assertIn(QualityFindingCode.CROSSED_BOOK.value, summary.flags)

    def test_good_quote_maps_good(self) -> None:
        event = _quote_event()
        assessment = inspect_quality(events=[event], decision_time_ns=T0 + ONE_SEC)
        summary = quality_summary_from_assessment(assessment)
        self.assertEqual(summary.state, QualityState.GOOD)


class InstrumentScopeTests(unittest.TestCase):
    def test_bad_aapl_does_not_affect_nvda(self) -> None:
        bad = _quote_event(event_id="bad", instrument_id="AAPL", bid=101.0, ask=100.0)
        good = _quote_event(event_id="good", instrument_id="NVDA")
        assessment = inspect_quality(events=[bad, good], decision_time_ns=T0 + ONE_SEC)
        nvda_findings = [
            row
            for row in assessment.findings
            if row.instrument_id == "NVDA" and row.code == QualityFindingCode.CROSSED_BOOK.value
        ]
        self.assertEqual(nvda_findings, [])


class DeterminismTests(unittest.TestCase):
    def test_identical_inputs_identical_semantics(self) -> None:
        events = [_quote_event(event_id="a"), _quote_event(event_id="b", provider=SOURCE_IBKR)]
        first = inspect_quality(events=events, decision_time_ns=T0 + ONE_SEC)
        second = inspect_quality(events=list(reversed(events)), decision_time_ns=T0 + ONE_SEC)
        self.assertEqual([row.code for row in first.findings], [row.code for row in second.findings])
        self.assertEqual(
            quality_summary_from_assessment(first),
            quality_summary_from_assessment(second),
        )

    def test_finding_order_stable(self) -> None:
        event = _quote_event(bid=101.0, ask=100.0)
        assessment = inspect_quality(events=[event], decision_time_ns=T0 + ONE_SEC)
        codes = [row.code for row in assessment.findings]
        self.assertEqual(codes, sorted(codes, key=lambda code: (code,)))


if __name__ == "__main__":
    unittest.main()
