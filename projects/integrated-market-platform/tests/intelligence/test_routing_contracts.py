"""BUILD 09 detection and routing contract tests."""

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
    RoutingDecisionV1,
    RoutingPriority,
    SemanticEventType,
    detection_v1_from_dict,
    detection_v1_to_dict,
    routing_decision_v1_from_dict,
    routing_decision_v1_to_dict,
)
from tests.intelligence.routing_fixtures import SCOPE, T


def sample_detection() -> DetectionV1:
    return DetectionV1(
        detection_id="DET-abc",
        schema_version="1",
        semantic_event_type=SemanticEventType.ORDER_FLOW_REVERSAL,
        detected_at_ns=T,
        source_snapshot_ref=ContractReference(kind=ContractKind.SNAPSHOT.value, id="snap-1"),
        source_signal_refs=(
            ContractReference(kind=ContractKind.SIGNAL.value, id="sig-old"),
            ContractReference(kind=ContractKind.SIGNAL.value, id="sig-new"),
        ),
        detector_lineage=ComponentLineage(component_id="order-flow-reversal", component_version="1"),
        scope=SCOPE,
        severity=DetectionSeverity.HIGH,
        reason_codes=("NSS_NEGATIVE_TO_POSITIVE",),
        quality=QualitySummary(state=QualityState.GOOD),
        identity_context={"policy_id": "detector-policy-v1"},
    )


def sample_route() -> RoutingDecisionV1:
    return RoutingDecisionV1(
        routing_decision_id="ROUTE-abc",
        schema_version="1",
        detection_ref=ContractReference(kind=ContractKind.DETECTION.value, id="DET-abc"),
        decision_time_ns=T,
        expert_domain=ExpertDomain.MICROSTRUCTURE,
        route_action=RouteAction.ROUTE,
        priority=RoutingPriority.HIGH,
        reason_codes=("ORDER_FLOW_REVERSAL_DETECTED", "REQUIRED_CAPABILITIES_AVAILABLE"),
        required_capabilities=("QUOTES", "TRADES"),
        optional_capabilities=("DEPTH",),
        deadline_time_ns=T + 5_000_000_000,
        expires_at_ns=T + 30_000_000_000,
        ttl_ns=30_000_000_000,
        quality=QualitySummary(state=QualityState.GOOD),
        router_lineage=ComponentLineage(component_id="smart-router", component_version="1"),
    )


class DetectionContractTests(unittest.TestCase):
    def test_round_trip_and_immutability(self) -> None:
        record = sample_detection()
        self.assertEqual(detection_v1_from_dict(detection_v1_to_dict(record)), record)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            record.detection_id = "changed"  # type: ignore[misc]

    def test_unknown_fields_are_rejected(self) -> None:
        payload = detection_v1_to_dict(sample_detection())
        payload["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "UNKNOWN_FIELDS"):
            detection_v1_from_dict(payload)

    def test_reason_code_parser_rejects_scalar_strings(self) -> None:
        payload = detection_v1_to_dict(sample_detection())
        payload["reason_codes"] = "ABC"
        with self.assertRaisesRegex(ValueError, "DETECTION_REASON_CODES_INVALID"):
            detection_v1_from_dict(payload)

    def test_snapshot_and_signal_reference_kinds_are_enforced(self) -> None:
        with self.assertRaisesRegex(ValueError, "DETECTION_SNAPSHOT_REF_KIND_INVALID"):
            dataclasses.replace(
                sample_detection(),
                source_snapshot_ref=ContractReference(kind="event", id="snap-1"),
            )

    def test_detector_lineage_identity_is_required(self) -> None:
        with self.assertRaisesRegex(ValueError, "DETECTION_LINEAGE_IDENTITY_REQUIRED"):
            dataclasses.replace(sample_detection(), detector_lineage=ComponentLineage())


class RoutingContractTests(unittest.TestCase):
    def test_round_trip_and_deadline_invariants(self) -> None:
        record = sample_route()
        self.assertEqual(routing_decision_v1_from_dict(routing_decision_v1_to_dict(record)), record)
        with self.assertRaisesRegex(ValueError, "ROUTE_DEADLINE_AFTER_EXPIRATION"):
            dataclasses.replace(record, deadline_time_ns=record.expires_at_ns + 1)

    def test_ttl_must_match_expiration(self) -> None:
        with self.assertRaisesRegex(ValueError, "ROUTE_TTL_MISMATCH"):
            dataclasses.replace(sample_route(), ttl_ns=1)

    def test_ttl_is_an_integer_and_router_lineage_is_required(self) -> None:
        with self.assertRaisesRegex(ValueError, "TTL_NS_NOT_INTEGER"):
            dataclasses.replace(sample_route(), ttl_ns=30_000_000_000.0)
        with self.assertRaisesRegex(ValueError, "ROUTER_LINEAGE_IDENTITY_REQUIRED"):
            dataclasses.replace(sample_route(), router_lineage=ComponentLineage())

    def test_suppressed_route_has_no_executable_timestamps(self) -> None:
        suppressed = dataclasses.replace(
            sample_route(),
            route_action=RouteAction.SUPPRESS,
            deadline_time_ns=None,
            expires_at_ns=None,
            ttl_ns=None,
        )
        self.assertEqual(suppressed.route_action, RouteAction.SUPPRESS)

    def test_route_capabilities_are_canonicalized(self) -> None:
        route = dataclasses.replace(
            sample_route(),
            required_capabilities=("TRADES", "QUOTES", "TRADES"),
        )
        self.assertEqual(route.required_capabilities, ("QUOTES", "TRADES"))

    def test_route_string_arrays_reject_scalar_strings(self) -> None:
        for field_name in ("reason_codes", "required_capabilities", "optional_capabilities"):
            payload = routing_decision_v1_to_dict(sample_route())
            payload[field_name] = "ABC"
            with self.assertRaisesRegex(ValueError, "ROUTING_STRING_LIST_INVALID"):
                routing_decision_v1_from_dict(payload)


if __name__ == "__main__":
    unittest.main()
