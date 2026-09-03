"""Event detector and capability-aware smart router (BUILD 09)."""

from .detector_engine import EventDetectorEngine
from .errors import DetectionError, DetectionInputError, RoutingConfigurationError
from .identity import (
    DETECTION_IDENTITY_VERSION,
    ROUTING_IDENTITY_VERSION,
    derive_detection_id,
    derive_routing_decision_id,
)
from .models import (
    DetectionEngineResult,
    DetectionFrame,
    DetectorStateSnapshot,
    DetectorSupport,
    DetectorSupportStatus,
    RegimeContext,
)
from .policy import DetectionPolicyV1, RouteTemplate, RoutingPolicyV1
from .router import SmartRouter

__all__ = [
    "DETECTION_IDENTITY_VERSION",
    "ROUTING_IDENTITY_VERSION",
    "DetectionEngineResult",
    "DetectionError",
    "DetectionFrame",
    "DetectionInputError",
    "DetectionPolicyV1",
    "DetectorStateSnapshot",
    "DetectorSupport",
    "DetectorSupportStatus",
    "EventDetectorEngine",
    "RegimeContext",
    "RouteTemplate",
    "RoutingConfigurationError",
    "RoutingPolicyV1",
    "SmartRouter",
    "derive_detection_id",
    "derive_routing_decision_id",
]
