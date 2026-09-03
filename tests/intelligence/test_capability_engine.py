"""BUILD 04 — capability requirements and decision tests."""

from __future__ import annotations

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
    AvailabilityState,
    CapabilityRequirement,
    ConnectionState,
    DecisionAction,
    IntelligenceCapability,
    ProviderCapabilityObservation,
    ProviderHealthSnapshot,
    QualityCapabilityError,
    QualityFindingCode,
    QualityPolicy,
    RequirementSet,
    SupportState,
    assess_capabilities,
    inspect_quality,
    require_quality_decision,
    select_usable_source,
)
from market_platform_foundation.intelligence.temporal import inspect_event_temporal_integrity  # noqa: E402

T0 = 1_000_000_000_000
ONE_SEC = 1_000_000_000
QUALITY_GOOD = QualitySummary(state=QualityState.GOOD)


def _quote(
    provider_id: str,
    *,
    event_id: str,
    bid: float = 100.0,
    ask: float = 100.05,
    instrument_id: str = "NVDA",
) -> EventV1:
    return EventV1(
        event_id=event_id,
        schema_version="1",
        event_type="QUOTE",
        event_time_ns=T0,
        available_time_ns=T0,
        payload={"bid_price": bid, "ask_price": ask, "bid_vol": 100, "ask_vol": 100},
        quality=QUALITY_GOOD,
        source=SourceReference(provider_id=provider_id, source_type="quote", source_record_id=event_id),
        instrument_id=instrument_id,
    )


class RequirementDecisionTests(unittest.TestCase):
    def test_all_required_healthy_use(self) -> None:
        events = [_quote("MOOMOO", event_id="q1")]
        requirements = RequirementSet.of(
            CapabilityRequirement(capability=IntelligenceCapability.QUOTES, required=True),
        )
        decision = assess_capabilities(events=events, decision_time_ns=T0 + ONE_SEC, requirements=requirements)
        self.assertEqual(decision.action, DecisionAction.USE)

    def test_optional_depth_unavailable_degrade(self) -> None:
        events = [_quote("MOOMOO", event_id="q1")]
        requirements = RequirementSet.of(
            CapabilityRequirement(capability=IntelligenceCapability.QUOTES, required=True),
            CapabilityRequirement(
                capability=IntelligenceCapability.DEPTH,
                required=False,
                failure_action=DecisionAction.DEGRADE,
            ),
        )
        decision = assess_capabilities(events=events, decision_time_ns=T0 + ONE_SEC, requirements=requirements)
        self.assertEqual(decision.action, DecisionAction.DEGRADE)
        self.assertIn(IntelligenceCapability.DEPTH, decision.degraded_requirements)

    def test_required_quotes_unavailable_fail_closed(self) -> None:
        requirements = RequirementSet.of(
            CapabilityRequirement(
                capability=IntelligenceCapability.QUOTES,
                required=True,
                failure_action=DecisionAction.FAIL_CLOSED,
            ),
        )
        decision = assess_capabilities(events=[], decision_time_ns=T0, requirements=requirements)
        self.assertEqual(decision.action, DecisionAction.FAIL_CLOSED)

    def test_unknown_mandatory_abstain(self) -> None:
        health = ProviderHealthSnapshot(
            provider_id="MOOMOO",
            as_of_time_ns=T0,
            connection=ConnectionState.CONNECTED,
            observations=(
                ProviderCapabilityObservation(
                    provider_id="MOOMOO",
                    capability=IntelligenceCapability.QUOTES,
                    support=SupportState.UNKNOWN,
                    availability=AvailabilityState.UNKNOWN,
                ),
            ),
        )
        requirements = RequirementSet.of(
            CapabilityRequirement(capability=IntelligenceCapability.QUOTES, required=True),
        )
        decision = assess_capabilities(
            events=[],
            decision_time_ns=T0,
            requirements=requirements,
            provider_health=(health,),
        )
        self.assertEqual(decision.action, DecisionAction.ABSTAIN)

    def test_crossed_quote_fail_closed_strict_api(self) -> None:
        event = _quote("MOOMOO", event_id="bad", bid=101.0, ask=100.0)
        requirements = RequirementSet.of(
            CapabilityRequirement(capability=IntelligenceCapability.QUOTES, required=True),
        )
        with self.assertRaises(QualityCapabilityError) as ctx:
            require_quality_decision(events=[event], decision_time_ns=T0 + ONE_SEC, requirements=requirements)
        self.assertEqual(ctx.exception.action, DecisionAction.FAIL_CLOSED)


class ProviderHealthTests(unittest.TestCase):
    def test_provider_disconnect(self) -> None:
        health = ProviderHealthSnapshot(
            provider_id="MOOMOO",
            as_of_time_ns=T0,
            connection=ConnectionState.DISCONNECTED,
            observations=(
                ProviderCapabilityObservation(
                    provider_id="MOOMOO",
                    capability=IntelligenceCapability.QUOTES,
                    support=SupportState.SUPPORTED,
                    availability=AvailabilityState.UNAVAILABLE,
                ),
            ),
        )
        assessment = inspect_quality(events=[], decision_time_ns=T0, provider_health=(health,))
        codes = {row.code for row in assessment.findings}
        self.assertIn(QualityFindingCode.PROVIDER_DISCONNECTED.value, codes)

    def test_not_entitled(self) -> None:
        health = ProviderHealthSnapshot(
            provider_id="MOOMOO",
            as_of_time_ns=T0,
            connection=ConnectionState.CONNECTED,
            observations=(
                ProviderCapabilityObservation(
                    provider_id="MOOMOO",
                    capability=IntelligenceCapability.DEPTH,
                    support=SupportState.SUPPORTED,
                    availability=AvailabilityState.UNAVAILABLE,
                    entitled=False,
                ),
            ),
        )
        assessment = inspect_quality(events=[], decision_time_ns=T0, provider_health=(health,))
        codes = {row.code for row in assessment.findings}
        self.assertIn(QualityFindingCode.NOT_ENTITLED.value, codes)
        row = next(row for row in assessment.capability_assessments if row.capability == IntelligenceCapability.DEPTH)
        self.assertEqual(row.dimensions.support, SupportState.SUPPORTED)
        self.assertEqual(row.dimensions.availability, AvailabilityState.UNAVAILABLE)

    def test_unsupported_capability(self) -> None:
        health = ProviderHealthSnapshot(
            provider_id="MOOMOO",
            as_of_time_ns=T0,
            connection=ConnectionState.CONNECTED,
            observations=(
                ProviderCapabilityObservation(
                    provider_id="MOOMOO",
                    capability=IntelligenceCapability.OPTIONS_CHAIN,
                    support=SupportState.UNSUPPORTED,
                    availability=AvailabilityState.UNAVAILABLE,
                ),
            ),
        )
        assessment = inspect_quality(events=[], decision_time_ns=T0, provider_health=(health,))
        codes = {row.code for row in assessment.findings}
        self.assertIn(QualityFindingCode.CAPABILITY_UNAVAILABLE.value, codes)
        self.assertNotIn(QualityFindingCode.PROVIDER_DISCONNECTED.value, codes)

    def test_provider_isolation(self) -> None:
        bad = _quote("MOOMOO", event_id="bad", bid=101.0, ask=100.0)
        good = _quote("IBKR", event_id="good")
        assessment = inspect_quality(events=[bad, good], decision_time_ns=T0 + ONE_SEC)
        ibkr = [row for row in assessment.capability_assessments if row.provider_id == "IBKR"]
        self.assertTrue(ibkr)
        self.assertEqual(ibkr[0].quality_state, QualityState.GOOD)


class ProviderConflictTests(unittest.TestCase):
    def test_provider_conflict_detected(self) -> None:
        events = [
            _quote("MOOMOO", event_id="m1", bid=100.0, ask=100.1),
            _quote("IBKR", event_id="i1", bid=110.0, ask=110.1),
        ]
        policy = QualityPolicy(price_conflict_tolerance_bps=1.0)
        assessment = inspect_quality(events=events, decision_time_ns=T0 + ONE_SEC, policy=policy)
        codes = {row.code for row in assessment.findings}
        self.assertIn(QualityFindingCode.PROVIDER_CONFLICT.value, codes)

    def test_provider_agreement_within_tolerance(self) -> None:
        events = [
            _quote("MOOMOO", event_id="m1", bid=100.0, ask=100.1),
            _quote("IBKR", event_id="i1", bid=100.01, ask=100.11),
        ]
        assessment = inspect_quality(events=events, decision_time_ns=T0 + ONE_SEC)
        codes = {row.code for row in assessment.findings}
        self.assertNotIn(QualityFindingCode.PROVIDER_CONFLICT.value, codes)

    def test_conflict_policy_affects_decision(self) -> None:
        events = [
            _quote("MOOMOO", event_id="m1", bid=100.0, ask=100.1),
            _quote("IBKR", event_id="i1", bid=110.0, ask=110.1),
        ]
        requirements = RequirementSet.of(
            CapabilityRequirement(capability=IntelligenceCapability.QUOTES, required=True, allow_degraded=True),
        )
        permissive = assess_capabilities(
            events=events,
            decision_time_ns=T0 + ONE_SEC,
            requirements=requirements,
            policy=QualityPolicy(require_provider_agreement=False, price_conflict_tolerance_bps=1.0),
        )
        strict = assess_capabilities(
            events=events,
            decision_time_ns=T0 + ONE_SEC,
            requirements=requirements,
            policy=QualityPolicy(require_provider_agreement=True, price_conflict_tolerance_bps=1.0),
        )
        self.assertEqual(permissive.action, DecisionAction.DEGRADE)
        self.assertIn(strict.action, {DecisionAction.ABSTAIN, DecisionAction.DEGRADE, DecisionAction.FAIL_CLOSED})


class FutureInformationDecisionTests(unittest.TestCase):
    def test_future_information_never_use(self) -> None:
        event = _quote("MOOMOO", event_id="future")
        event = EventV1(
            event_id=event.event_id,
            schema_version=event.schema_version,
            event_type=event.event_type,
            event_time_ns=event.event_time_ns,
            available_time_ns=T0 + ONE_SEC,
            payload=event.payload,
            quality=event.quality,
            source=event.source,
            instrument_id=event.instrument_id,
        )
        report = inspect_event_temporal_integrity(event, decision_time_ns=T0)
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
            decision_time_ns=T0,
            requirements=requirements,
            temporal_reports={event.event_id: report},
        )
        self.assertNotEqual(decision.action, DecisionAction.USE)
        self.assertNotEqual(decision.action, DecisionAction.DEGRADE)


class SourceSelectionTests(unittest.TestCase):
    def test_fallback_to_secondary(self) -> None:
        events = [_quote("IBKR", event_id="good")]
        health = ProviderHealthSnapshot(
            provider_id="MOOMOO",
            as_of_time_ns=T0,
            connection=ConnectionState.DISCONNECTED,
            observations=(
                ProviderCapabilityObservation(
                    provider_id="MOOMOO",
                    capability=IntelligenceCapability.QUOTES,
                    support=SupportState.SUPPORTED,
                    availability=AvailabilityState.UNAVAILABLE,
                ),
            ),
        )
        assessment = inspect_quality(events=events, decision_time_ns=T0 + ONE_SEC, provider_health=(health,))
        result = select_usable_source(
            IntelligenceCapability.QUOTES,
            provider_assessments=assessment.capability_assessments,
        )
        self.assertEqual(result.selected_provider_id, "IBKR")

    def test_no_eligible_source(self) -> None:
        health = ProviderHealthSnapshot(
            provider_id="MOOMOO",
            as_of_time_ns=T0,
            connection=ConnectionState.DISCONNECTED,
            observations=(
                ProviderCapabilityObservation(
                    provider_id="MOOMOO",
                    capability=IntelligenceCapability.QUOTES,
                    support=SupportState.SUPPORTED,
                    availability=AvailabilityState.UNAVAILABLE,
                ),
            ),
        )
        assessment = inspect_quality(events=[], decision_time_ns=T0, provider_health=(health,))
        result = select_usable_source(
            IntelligenceCapability.QUOTES,
            provider_assessments=assessment.capability_assessments,
        )
        self.assertIsNone(result.selected_provider_id)
        self.assertEqual(result.action, DecisionAction.ABSTAIN)


class PolicyImmutabilityTests(unittest.TestCase):
    def test_policy_with_overrides_new_instance(self) -> None:
        base = QualityPolicy()
        changed = base.with_overrides(price_conflict_tolerance_bps=25.0)
        self.assertEqual(base.price_conflict_tolerance_bps, 10.0)
        self.assertEqual(changed.price_conflict_tolerance_bps, 25.0)


if __name__ == "__main__":
    unittest.main()
