"""Normalized cross-lane evidence contracts.

Lanes publish evidence; domain engines (Short Squeeze, Options, Futures) consume
interpretations without owning upstream calculations.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class LaneId(StrEnum):
    SHORT_SQUEEZE = "short_squeeze"
    OPTIONS = "options"
    FUTURES = "futures"
    ORDER_FLOW = "order_flow"
    CATALYST = "catalyst"
    ATTENTION = "attention"
    CRYPTO = "crypto"
    PREDICTION_MARKET = "prediction_market"


class EvidenceProvenanceClass(StrEnum):
    """Prevents same-timestamp circular model leakage across lanes."""

    RAW = "RAW"
    DERIVED = "DERIVED"
    MODEL_OUTPUT = "MODEL_OUTPUT"
    CROSS_LANE_MODEL_OUTPUT = "CROSS_LANE_MODEL_OUTPUT"


class EvidenceSignal(StrEnum):
    # Order flow
    AGGRESSIVE_BUY_PRESSURE = "AGGRESSIVE_BUY_PRESSURE"
    AGGRESSIVE_SELL_PRESSURE = "AGGRESSIVE_SELL_PRESSURE"
    CVD_POSITIVE_SLOPE = "CVD_POSITIVE_SLOPE"
    CVD_NEGATIVE_SLOPE = "CVD_NEGATIVE_SLOPE"
    BOOK_IMBALANCE_BID = "BOOK_IMBALANCE_BID"
    BOOK_IMBALANCE_ASK = "BOOK_IMBALANCE_ASK"
    # Options → cross-lane (SHARED P3)
    GAMMA_AMPLIFICATION_POTENTIAL = "GAMMA_AMPLIFICATION_POTENTIAL"
    CALL_DEMAND_ANOMALY = "CALL_DEMAND_ANOMALY"
    UPSIDE_SKEW_ELEVATED = "UPSIDE_SKEW_ELEVATED"
    IMPLIED_UPSIDE_TAIL_PROBABILITY = "IMPLIED_UPSIDE_TAIL_PROBABILITY"
    OPTION_FLOW_DIRECTION = "OPTION_FLOW_DIRECTION"
    ESTIMATED_HEDGING_PRESSURE = "ESTIMATED_HEDGING_PRESSURE"
    OPTIONS_DATA_CONFIDENCE = "OPTIONS_DATA_CONFIDENCE"
    # Short squeeze → cross-lane (SHARED P3)
    SQUEEZE_STATE = "SQUEEZE_STATE"
    SQUEEZE_IGNITION_STRENGTH = "SQUEEZE_IGNITION_STRENGTH"
    REMAINING_SQUEEZE_FUEL = "REMAINING_SQUEEZE_FUEL"
    EXHAUSTION_RISK = "EXHAUSTION_RISK"
    # Shared context
    CATALYST_STRENGTH = "CATALYST_STRENGTH"
    ATTENTION_ACCELERATION = "ATTENTION_ACCELERATION"
    LIQUIDATION_PRESSURE = "LIQUIDATION_PRESSURE"
    # Futures → cross-lane (SHARED P3)
    FUTURES_CURVE_CONTANGO = "FUTURES_CURVE_CONTANGO"
    FUTURES_CURVE_BACKWARDATION = "FUTURES_CURVE_BACKWARDATION"
    FUTURES_CARRY_POSITIVE = "FUTURES_CARRY_POSITIVE"
    FUTURES_CARRY_NEGATIVE = "FUTURES_CARRY_NEGATIVE"
    FUTURES_POSITIONING_CROWDED_LONG = "FUTURES_POSITIONING_CROWDED_LONG"
    FUTURES_POSITIONING_CROWDED_SHORT = "FUTURES_POSITIONING_CROWDED_SHORT"
    FUTURES_LONG_LIQUIDATION_RISK = "FUTURES_LONG_LIQUIDATION_RISK"
    FUTURES_SHORT_LIQUIDATION_RISK = "FUTURES_SHORT_LIQUIDATION_RISK"
    FUTURES_MACRO_EVENT_RISK = "FUTURES_MACRO_EVENT_RISK"
    FUTURES_ORDER_FLOW_CONFIRMING = "FUTURES_ORDER_FLOW_CONFIRMING"
    FUTURES_DATA_CONFIDENCE = "FUTURES_DATA_CONFIDENCE"
    # Platform physical distribution (SHARED P2)
    FORECAST_RV_ELEVATED = "FORECAST_RV_ELEVATED"
    UPSIDE_TAIL_PROBABILITY_PHYSICAL = "UPSIDE_TAIL_PROBABILITY_PHYSICAL"
    DOWNSIDE_TAIL_PROBABILITY_PHYSICAL = "DOWNSIDE_TAIL_PROBABILITY_PHYSICAL"


@dataclass(frozen=True, slots=True)
class NormalizedLaneEvidence:
    lane: LaneId
    signal: EvidenceSignal
    strength: str  # LOW | MODERATE | HIGH
    available: bool
    source_ref: str
    detail: str
    observed_at: str | None = None
    quality_flags: tuple[str, ...] = ()
    provenance_class: EvidenceProvenanceClass = EvidenceProvenanceClass.DERIVED


def lane_evidence_to_dict(item: NormalizedLaneEvidence) -> dict[str, Any]:
    return {
        "lane": item.lane.value,
        "signal": item.signal.value,
        "strength": item.strength,
        "available": item.available,
        "source_ref": item.source_ref,
        "detail": item.detail,
        "observed_at": item.observed_at,
        "quality_flags": list(item.quality_flags),
        "provenance_class": item.provenance_class.value,
    }


def validate_evidence_dag(evidence_items: list[NormalizedLaneEvidence]) -> list[str]:
    """Detect illegal same-lane MODEL_OUTPUT → CROSS_LANE_MODEL_OUTPUT cycles.

    Returns human-readable violation messages. Empty list means no violations detected
  at the evidence-metadata level (full model DAG validation is lane-specific).
    """
    violations: list[str] = []
    cross_lane_outputs = {
        item.signal
        for item in evidence_items
        if item.provenance_class == EvidenceProvenanceClass.CROSS_LANE_MODEL_OUTPUT
    }
    for item in evidence_items:
        if (
            item.provenance_class == EvidenceProvenanceClass.MODEL_OUTPUT
            and item.signal in cross_lane_outputs
            and item.lane
            in {LaneId.OPTIONS, LaneId.SHORT_SQUEEZE, LaneId.FUTURES}
        ):
            violations.append(
                f"potential circular dependency: {item.lane.value} MODEL_OUTPUT "
                f"feeds signal also present as CROSS_LANE_MODEL_OUTPUT ({item.signal.value})"
            )
    return violations
