"""BUILD 04 — end-to-end BUILD 01–04 composition tests."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.contracts import event_v1_to_dict  # noqa: E402
from market_platform_foundation.intelligence.normalization import (  # noqa: E402
    IngestionMode,
    NormalizationContext,
    require_normalized_event,
)
from market_platform_foundation.intelligence.quality import (  # noqa: E402
    CapabilityRequirement,
    DecisionAction,
    IntelligenceCapability,
    QualityFindingCode,
    RequirementSet,
    assess_capabilities,
    quality_summary_from_assessment,
)
from market_platform_foundation.intelligence.temporal import inspect_temporal_integrity  # noqa: E402

T0 = 1_000_000_000_000
FIVE_SEC = 5 * 1_000_000_000


def _moomoo_quote_fixture() -> dict:
    return {
        "provider": "moomoo.opend.observational",
        "capability": "QUOTE",
        "provider_symbol": "US.NVDA",
        "sequence": 42,
        "clocks": {
            "event_time_ns": T0,
            "provider_time_ns": T0 + 5_000_000,
            "received_time_ns": T0 + FIVE_SEC,
        },
        "raw_payload": {
            "bid_price": 100.0,
            "ask_price": 100.05,
            "bid_vol": 500,
            "ask_vol": 400,
        },
    }


class EndToEndCompositionTests(unittest.TestCase):
    def test_good_pipeline_use(self) -> None:
        raw = _moomoo_quote_fixture()
        ctx = NormalizationContext(received_time_ns=T0 + FIVE_SEC, ingestion_mode=IngestionMode.LIVE_OBSERVED)
        event = require_normalized_event(raw, context=ctx, source_key="moomoo.capture")
        temporal = inspect_temporal_integrity(event, decision_time_ns=T0 + 6 * 1_000_000_000)
        self.assertTrue(temporal.eligible)
        requirements = RequirementSet.of(
            CapabilityRequirement(capability=IntelligenceCapability.QUOTES, required=True),
        )
        decision = assess_capabilities(
            events=[event],
            decision_time_ns=T0 + 6 * 1_000_000_000,
            requirements=requirements,
            temporal_reports={event.event_id: temporal},
        )
        self.assertEqual(decision.action, DecisionAction.USE)
        summary = quality_summary_from_assessment(decision.assessment)
        self.assertEqual(summary.state.value, "GOOD")

    def test_future_pipeline_not_rescued(self) -> None:
        raw = _moomoo_quote_fixture()
        ctx = NormalizationContext(received_time_ns=T0 + FIVE_SEC, ingestion_mode=IngestionMode.LIVE_OBSERVED)
        event = require_normalized_event(raw, context=ctx, source_key="moomoo.capture")
        temporal = inspect_temporal_integrity(event, decision_time_ns=T0 + 2 * 1_000_000_000)
        self.assertFalse(temporal.eligible)
        requirements = RequirementSet.of(
            CapabilityRequirement(
                capability=IntelligenceCapability.QUOTES,
                required=True,
                allow_degraded=True,
                failure_action=DecisionAction.DEGRADE,
            ),
        )
        decision = assess_capabilities(
            events=[event],
            decision_time_ns=T0 + 2 * 1_000_000_000,
            requirements=requirements,
            temporal_reports={event.event_id: temporal},
        )
        self.assertNotEqual(decision.action, DecisionAction.USE)
        codes = {row.code for row in decision.assessment.findings}
        self.assertIn(QualityFindingCode.FUTURE_INFORMATION.value, codes)

    def test_crossed_quote_pipeline_fail_closed(self) -> None:
        raw = _moomoo_quote_fixture()
        raw["raw_payload"]["bid_price"] = 101.0
        raw["raw_payload"]["ask_price"] = 100.0
        ctx = NormalizationContext(received_time_ns=T0 + FIVE_SEC, ingestion_mode=IngestionMode.LIVE_OBSERVED)
        event = require_normalized_event(raw, context=ctx, source_key="moomoo.capture")
        temporal = inspect_temporal_integrity(event, decision_time_ns=T0 + 6 * 1_000_000_000)
        requirements = RequirementSet.of(
            CapabilityRequirement(capability=IntelligenceCapability.QUOTES, required=True),
        )
        decision = assess_capabilities(
            events=[event],
            decision_time_ns=T0 + 6 * 1_000_000_000,
            requirements=requirements,
            temporal_reports={event.event_id: temporal},
        )
        self.assertEqual(decision.action, DecisionAction.FAIL_CLOSED)
        codes = {row.code for row in decision.assessment.findings}
        self.assertIn(QualityFindingCode.CROSSED_BOOK.value, codes)

    def test_optional_missing_degrade(self) -> None:
        raw = _moomoo_quote_fixture()
        ctx = NormalizationContext(received_time_ns=T0 + FIVE_SEC, ingestion_mode=IngestionMode.LIVE_OBSERVED)
        event = require_normalized_event(raw, context=ctx, source_key="moomoo.capture")
        temporal = inspect_temporal_integrity(event, decision_time_ns=T0 + 6 * 1_000_000_000)
        requirements = RequirementSet.of(
            CapabilityRequirement(capability=IntelligenceCapability.QUOTES, required=True),
            CapabilityRequirement(
                capability=IntelligenceCapability.DEPTH,
                required=False,
                failure_action=DecisionAction.DEGRADE,
            ),
        )
        decision = assess_capabilities(
            events=[event],
            decision_time_ns=T0 + 6 * 1_000_000_000,
            requirements=requirements,
            temporal_reports={event.event_id: temporal},
        )
        self.assertEqual(decision.action, DecisionAction.DEGRADE)

    def test_raw_and_event_immutability(self) -> None:
        raw = _moomoo_quote_fixture()
        raw_snapshot = copy.deepcopy(raw)
        ctx = NormalizationContext(received_time_ns=T0 + FIVE_SEC, ingestion_mode=IngestionMode.LIVE_OBSERVED)
        event = require_normalized_event(raw, context=ctx, source_key="moomoo.capture")
        event_snapshot = event_v1_to_dict(event)
        assess_capabilities(
            events=[event],
            decision_time_ns=T0 + 6 * 1_000_000_000,
            requirements=RequirementSet.of(
                CapabilityRequirement(capability=IntelligenceCapability.QUOTES, required=True),
            ),
        )
        self.assertEqual(raw, raw_snapshot)
        self.assertEqual(event_v1_to_dict(event), event_snapshot)


if __name__ == "__main__":
    unittest.main()
