"""Order Flow / Market Microstructure intelligence lane.

Owns observable auction mechanics and reusable microstructure evidence.
Domain engines (Short Squeeze, Options, Futures) interpret evidence — they do
not own trade classification, CVD, OFI, or book-pressure primitives.
"""

from .aggressor import classify_trade, provenance_from_quality_label
from .contracts import (
    AggressorSide,
    AggressorSource,
    BookPressureEvidence,
    ClassifiedTrade,
    CVDState,
    L1QuoteState,
    MicrostructureCapabilityTier,
    OrderFlowEvidence,
)
from .cvd import (
    compute_cvd_series,
    compute_cvd_state,
    cvd_acceleration,
    cvd_slope,
)
from .evidence import build_order_flow_evidence, order_flow_evidence_to_dict
from .l1 import compute_l1_state, depth_imbalance_ratio, queue_imbalance
from .quality import OrderFlowQualityFlag

__all__ = [
    "AggressorSide",
    "AggressorSource",
    "BookPressureEvidence",
    "ClassifiedTrade",
    "CVDState",
    "L1QuoteState",
    "MicrostructureCapabilityTier",
    "OrderFlowEvidence",
    "OrderFlowQualityFlag",
    "build_order_flow_evidence",
    "classify_trade",
    "compute_cvd_series",
    "compute_cvd_state",
    "compute_l1_state",
    "cvd_acceleration",
    "cvd_slope",
    "depth_imbalance_ratio",
    "order_flow_evidence_to_dict",
    "provenance_from_quality_label",
    "queue_imbalance",
]
