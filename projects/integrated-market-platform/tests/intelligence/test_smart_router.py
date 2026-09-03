"""BUILD 09 deterministic smart-router tests."""

from __future__ import annotations

import dataclasses
import unittest

from market_platform_foundation.intelligence.contracts import (
    ComponentLineage,
    ContractKind,
    ContractReference,
    DetectionSeverity,
    DetectionV1,
    ExpertDomain,
    QualityState,
    QualitySummary,
    RouteAction,
    RoutingPriority,
    SemanticEventType,
)
from market_platform_foundation.intelligence.quality import DecisionAction, IntelligenceCapability
from market_platform_foundation.intelligence.routing import RoutingPolicyV1, SmartRouter
from tests.intelligence.routing_fixtures import SCOPE, T, quality_decision


def detection(event_type: SemanticEventType, *, severity: DetectionSeverity = DetectionSeverity.MEDIUM) -> DetectionV1:
    return DetectionV1(
        detection_id=f"DET-{event_type.value}",
        schema_version="1",
        semantic_event_type=event_type,
        detected_at_ns=T,
        source_snapshot_ref=ContractReference(kind=ContractKind.SNAPSHOT.value, id="snap-router"),
        detector_lineage=ComponentLineage(component_id="fixture-detector", component_version="1"),
        scope=SCOPE,
        severity=severity,
        reason_codes=("FIXTURE_TRIGGER",),
        quality=QualitySummary(state=QualityState.GOOD),
    )


class SmartRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.router = SmartRouter()

    def test_all_event_types_map_to_primitive_domains(self) -> None:
        expected = {
            SemanticEventType.ORDER_FLOW_REVERSAL: ExpertDomain.MICROSTRUCTURE,
            SemanticEventType.UNUSUAL_OPTIONS_ACTIVITY: ExpertDomain.DERIVATIVES,
            SemanticEventType.BORROW_CHANGE: ExpertDomain.POSITIONING_BORROW,
            SemanticEventType.LIQUIDITY_EVENT: ExpertDomain.MICROSTRUCTURE,
            SemanticEventType.NEWS_EVENT: ExpertDomain.NARRATIVE_SENTIMENT,
            SemanticEventType.REGIME_SHIFT: ExpertDomain.REGIME_CROSS_ASSET,
        }
        for event_type, domain in expected.items():
            template = self.router.policy.template_for(event_type)
            self.assertEqual(template.expert_domain, domain)
        self.assertNotIn("SHORT_SQUEEZE", {domain.value for domain in ExpertDomain})

    def test_order_flow_route_has_deterministic_deadline_ttl_and_identity(self) -> None:
        source = detection(SemanticEventType.ORDER_FLOW_REVERSAL)
        decision = quality_decision(IntelligenceCapability.QUOTES, IntelligenceCapability.TRADES)
        first = self.router.route(source, quality_decision=decision)
        second = self.router.route(source, quality_decision=decision)
        self.assertEqual(first, second)
        self.assertEqual(first.route_action, RouteAction.ROUTE)
        self.assertEqual(first.expert_domain, ExpertDomain.MICROSTRUCTURE)
        self.assertEqual(first.deadline_time_ns, T + 5_000_000_000)
        self.assertEqual(first.expires_at_ns, T + 30_000_000_000)
        self.assertEqual(first.ttl_ns, 30_000_000_000)

    def test_required_capability_missing_suppresses_executable_route(self) -> None:
        result = self.router.route(
            detection(SemanticEventType.ORDER_FLOW_REVERSAL),
            quality_decision=quality_decision(IntelligenceCapability.TRADES),
        )
        self.assertEqual(result.route_action, RouteAction.SUPPRESS)
        self.assertIsNone(result.deadline_time_ns)
        self.assertIn("REQUIRED_CAPABILITY_MISSING", result.reason_codes)

    def test_optional_capability_missing_marks_route_degraded(self) -> None:
        result = self.router.route(
            detection(SemanticEventType.LIQUIDITY_EVENT),
            quality_decision=quality_decision(IntelligenceCapability.QUOTES),
        )
        self.assertEqual(result.route_action, RouteAction.ROUTE)
        self.assertEqual(result.quality.state, QualityState.DEGRADED)
        self.assertIn("OPTIONAL_CAPABILITY_MISSING", result.reason_codes)

    def test_abstain_and_fail_closed_are_not_overridden(self) -> None:
        source = detection(SemanticEventType.LIQUIDITY_EVENT)
        for action in (DecisionAction.ABSTAIN, DecisionAction.FAIL_CLOSED):
            result = self.router.route(source, quality_decision=quality_decision(action=action))
            self.assertEqual(result.route_action, RouteAction.ABSTAIN)

    def test_invalid_detection_quality_cannot_be_routed(self) -> None:
        source = dataclasses.replace(
            detection(SemanticEventType.LIQUIDITY_EVENT),
            quality=QualitySummary(state=QualityState.INVALID, flags=("SOURCE_INVALID",)),
        )
        result = self.router.route(
            source,
            quality_decision=quality_decision(
                IntelligenceCapability.QUOTES,
                IntelligenceCapability.DEPTH,
            ),
        )
        self.assertEqual(result.route_action, RouteAction.ABSTAIN)
        self.assertEqual(result.quality.state, QualityState.INVALID)
        self.assertIn("DETECTION_QUALITY_INVALID", result.reason_codes)

    def test_degraded_policy_can_allow_or_reject_routing(self) -> None:
        source = detection(SemanticEventType.LIQUIDITY_EVENT)
        degraded = quality_decision(
            IntelligenceCapability.QUOTES,
            action=DecisionAction.DEGRADE,
            degraded=(IntelligenceCapability.QUOTES,),
        )
        allowed = self.router.route(source, quality_decision=degraded)
        self.assertEqual(allowed.route_action, RouteAction.ROUTE)
        strict = SmartRouter(policy=dataclasses.replace(self.router.policy, allow_degraded=False, policy_version="2"))
        rejected = strict.route(source, quality_decision=degraded)
        self.assertEqual(rejected.route_action, RouteAction.ABSTAIN)

    def test_severity_promotes_priority_without_learning(self) -> None:
        source = detection(SemanticEventType.NEWS_EVENT, severity=DetectionSeverity.CRITICAL)
        routed = self.router.route(
            source,
            quality_decision=quality_decision(IntelligenceCapability.NEWS),
        )
        self.assertEqual(routed.priority, RoutingPriority.HIGH)

    def test_policy_change_changes_route_identity(self) -> None:
        source = detection(SemanticEventType.LIQUIDITY_EVENT)
        decision = quality_decision(IntelligenceCapability.QUOTES, IntelligenceCapability.DEPTH)
        first = self.router.route(source, quality_decision=decision)
        changed_policy = dataclasses.replace(self.router.policy, policy_version="2")
        second = SmartRouter(policy=changed_policy).route(source, quality_decision=decision)
        self.assertNotEqual(first.routing_decision_id, second.routing_decision_id)

    def test_route_identity_binds_detection_inputs_that_change_output(self) -> None:
        source = detection(SemanticEventType.LIQUIDITY_EVENT)
        decision = quality_decision(IntelligenceCapability.QUOTES, IntelligenceCapability.DEPTH)
        changed = dataclasses.replace(
            source,
            severity=DetectionSeverity.CRITICAL,
            quality=QualitySummary(state=QualityState.DEGRADED, flags=("SOURCE_DEGRADED",)),
        )
        first = self.router.route(source, quality_decision=decision)
        second = self.router.route(changed, quality_decision=decision)
        self.assertNotEqual(first.routing_decision_id, second.routing_decision_id)

    def test_irrelevant_capabilities_do_not_change_or_degrade_route(self) -> None:
        source = detection(SemanticEventType.ORDER_FLOW_REVERSAL)
        relevant = quality_decision(IntelligenceCapability.QUOTES, IntelligenceCapability.TRADES)
        noisy = quality_decision(
            IntelligenceCapability.QUOTES,
            IntelligenceCapability.TRADES,
            IntelligenceCapability.NEWS,
            degraded=(IntelligenceCapability.MACRO,),
        )
        first = self.router.route(source, quality_decision=relevant)
        second = self.router.route(source, quality_decision=noisy)
        self.assertEqual(first, second)
        self.assertEqual(second.quality.state, QualityState.GOOD)
        self.assertNotIn("DEGRADED_INPUT_ALLOWED", second.reason_codes)

    def test_route_all_output_order_is_input_order_independent(self) -> None:
        rows = (
            detection(SemanticEventType.REGIME_SHIFT),
            detection(SemanticEventType.LIQUIDITY_EVENT),
        )
        decision = quality_decision(
            IntelligenceCapability.MACRO,
            IntelligenceCapability.QUOTES,
            IntelligenceCapability.DEPTH,
        )
        left = self.router.route_all(rows, quality_decision=decision)
        right = self.router.route_all(tuple(reversed(rows)), quality_decision=decision)
        self.assertEqual(left, right)

    def test_conflicting_duplicate_detection_id_is_rejected(self) -> None:
        source = detection(SemanticEventType.LIQUIDITY_EVENT)
        conflict = dataclasses.replace(source, severity=DetectionSeverity.CRITICAL)
        with self.assertRaisesRegex(ValueError, "ROUTING_DETECTION_ID_CONFLICT"):
            self.router.route_all(
                (source, conflict),
                quality_decision=quality_decision(
                    IntelligenceCapability.QUOTES,
                    IntelligenceCapability.DEPTH,
                ),
            )

    def test_policy_invariants(self) -> None:
        with self.assertRaisesRegex(ValueError, "ROUTING_DEADLINE_AFTER_TTL"):
            RoutingPolicyV1(deadline_overrides_ns={SemanticEventType.NEWS_EVENT: 100}, ttl_overrides_ns={SemanticEventType.NEWS_EVENT: 50})
        for invalid in (True, 1.5, float("nan")):
            with self.assertRaisesRegex(ValueError, "ROUTING_TIME_OFFSET_INVALID"):
                RoutingPolicyV1(deadline_overrides_ns={SemanticEventType.NEWS_EVENT: invalid})
        with self.assertRaisesRegex(ValueError, "ROUTING_POLICY_IDENTITY_INVALID"):
            RoutingPolicyV1(policy_id="")


if __name__ == "__main__":
    unittest.main()
