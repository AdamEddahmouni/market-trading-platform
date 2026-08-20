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
    # Canonical information / catalyst / narrative lane (supersedes isolated sentiment framing)
    MARKET_CONTEXT = "market_context"
    CATALYST = "catalyst"  # legacy publisher id; prefer MARKET_CONTEXT for new evidence
    ATTENTION = "attention"  # legacy publisher id; prefer MARKET_CONTEXT for new evidence
    CRYPTO = "crypto"
    PREDICTION_MARKET = "prediction_market"
    PARTICIPANT_INTELLIGENCE = "participant_intelligence"


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
    LIQUIDITY_WITHDRAWAL = "LIQUIDITY_WITHDRAWAL"
    LIQUIDITY_REPLENISHMENT = "LIQUIDITY_REPLENISHMENT"
    BOOK_FRAGILITY_ELEVATED = "BOOK_FRAGILITY_ELEVATED"
    ABSORPTION_BUY = "ABSORPTION_BUY"
    ABSORPTION_SELL = "ABSORPTION_SELL"
    EXHAUSTION_BUY = "EXHAUSTION_BUY"
    EXHAUSTION_SELL = "EXHAUSTION_SELL"
    MICROSTRUCTURE_CONTINUATION_UP = "MICROSTRUCTURE_CONTINUATION_UP"
    MICROSTRUCTURE_CONTINUATION_DOWN = "MICROSTRUCTURE_CONTINUATION_DOWN"
    MICROSTRUCTURE_REVERSAL_RISK = "MICROSTRUCTURE_REVERSAL_RISK"
    EXECUTION_SLIPPAGE_ELEVATED = "EXECUTION_SLIPPAGE_ELEVATED"
    EXECUTION_FILL_RISK = "EXECUTION_FILL_RISK"
    ADVERSE_SELECTION_RISK_ELEVATED = "ADVERSE_SELECTION_RISK_ELEVATED"
    PERSISTENT_AGGRESSIVE_BUY_FLOW = "PERSISTENT_AGGRESSIVE_BUY_FLOW"
    PERSISTENT_AGGRESSIVE_SELL_FLOW = "PERSISTENT_AGGRESSIVE_SELL_FLOW"
    # Options → cross-lane (SHARED P3)
    GAMMA_AMPLIFICATION_POTENTIAL = "GAMMA_AMPLIFICATION_POTENTIAL"
    CALL_DEMAND_ANOMALY = "CALL_DEMAND_ANOMALY"
    UPSIDE_SKEW_ELEVATED = "UPSIDE_SKEW_ELEVATED"
    IMPLIED_UPSIDE_TAIL_PROBABILITY = "IMPLIED_UPSIDE_TAIL_PROBABILITY"
    OPTION_FLOW_DIRECTION = "OPTION_FLOW_DIRECTION"
    OPTIONS_FLOW_REVERSAL = "OPTIONS_FLOW_REVERSAL"
    ESTIMATED_HEDGING_PRESSURE = "ESTIMATED_HEDGING_PRESSURE"
    OPTIONS_DATA_CONFIDENCE = "OPTIONS_DATA_CONFIDENCE"
    # Options event volatility (O7)
    EVENT_VOL_PREMIUM = "EVENT_VOL_PREMIUM"
    IV_CRUSH_RISK = "IV_CRUSH_RISK"
    POST_EVENT_IV_NORMALIZATION = "POST_EVENT_IV_NORMALIZATION"
    # Options strategy optimizer (O8)
    STRATEGY_OPPORTUNITY_RANKED = "STRATEGY_OPPORTUNITY_RANKED"
    NO_CLEAR_EDGE = "NO_CLEAR_EDGE"
    # SHARED P4 — cross-lane EV fusion
    CROSS_LANE_OPPORTUNITY_FUSED = "CROSS_LANE_OPPORTUNITY_FUSED"
    OPPORTUNITY_NO_ACTIONABLE_EDGE = "OPPORTUNITY_NO_ACTIONABLE_EDGE"
    # Options execution / simulation (O9)
    OPTIONS_EXECUTION_SIMULATED = "OPTIONS_EXECUTION_SIMULATED"
    ASSIGNMENT_RISK = "ASSIGNMENT_RISK"
    # Short squeeze → cross-lane (SHARED P3)
    SQUEEZE_STATE = "SQUEEZE_STATE"
    SQUEEZE_IGNITION_STRENGTH = "SQUEEZE_IGNITION_STRENGTH"
    REMAINING_SQUEEZE_FUEL = "REMAINING_SQUEEZE_FUEL"
    EXHAUSTION_RISK = "EXHAUSTION_RISK"
    # Market Context → cross-lane (SHARED P3)
    SEMANTIC_SENTIMENT_POSITIVE = "SEMANTIC_SENTIMENT_POSITIVE"
    SEMANTIC_SENTIMENT_NEGATIVE = "SEMANTIC_SENTIMENT_NEGATIVE"
    SEMANTIC_SENTIMENT_MIXED = "SEMANTIC_SENTIMENT_MIXED"
    EVENT_SURPRISE_POSITIVE = "EVENT_SURPRISE_POSITIVE"
    EVENT_SURPRISE_NEGATIVE = "EVENT_SURPRISE_NEGATIVE"
    NOVELTY_HIGH = "NOVELTY_HIGH"
    MATERIALITY_HIGH = "MATERIALITY_HIGH"
    CREDIBILITY_HIGH = "CREDIBILITY_HIGH"
    SHORT_THESIS_INVALIDATION = "SHORT_THESIS_INVALIDATION"
    NARRATIVE_SHIFT = "NARRATIVE_SHIFT"
    MACRO_REGIME_CONTEXT = "MACRO_REGIME_CONTEXT"
    REACTION_CONFIRMED = "REACTION_CONFIRMED"
    REACTION_CONTRADICTED = "REACTION_CONTRADICTED"
    INFORMATION_DIFFUSION_ELEVATED = "INFORMATION_DIFFUSION_ELEVATED"
    # Shared context (legacy signal ids retained for fixture compatibility)
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
    FUTURES_TREND_UP = "FUTURES_TREND_UP"
    FUTURES_TREND_DOWN = "FUTURES_TREND_DOWN"
    FUTURES_LONG_LIQUIDATION_RISK = "FUTURES_LONG_LIQUIDATION_RISK"
    FUTURES_SHORT_LIQUIDATION_RISK = "FUTURES_SHORT_LIQUIDATION_RISK"
    FUTURES_MACRO_EVENT_RISK = "FUTURES_MACRO_EVENT_RISK"
    FUTURES_ORDER_FLOW_CONFIRMING = "FUTURES_ORDER_FLOW_CONFIRMING"
    FUTURES_DATA_CONFIDENCE = "FUTURES_DATA_CONFIDENCE"
    # Platform physical distribution (SHARED P2)
    FORECAST_RV_ELEVATED = "FORECAST_RV_ELEVATED"
    UPSIDE_TAIL_PROBABILITY_PHYSICAL = "UPSIDE_TAIL_PROBABILITY_PHYSICAL"
    DOWNSIDE_TAIL_PROBABILITY_PHYSICAL = "DOWNSIDE_TAIL_PROBABILITY_PHYSICAL"
    # Participant Intelligence → cross-lane (PI3+)
    INSIDER_DISCRETIONARY_PURCHASE = "INSIDER_DISCRETIONARY_PURCHASE"
    INSIDER_SALE_NON_DISCRETIONARY = "INSIDER_SALE_NON_DISCRETIONARY"
    ACTIVIST_STAKE_DISCLOSED = "ACTIVIST_STAKE_DISCLOSED"
    INSTITUTIONAL_HOLDING_CHANGE = "INSTITUTIONAL_HOLDING_CHANGE"
    METAORDER_LIKELY_ACTIVE = "METAORDER_LIKELY_ACTIVE"
    METAORDER_LIKELY_COMPLETE = "METAORDER_LIKELY_COMPLETE"
    FORCED_FLOW_PROBABILITY_ELEVATED = "FORCED_FLOW_PROBABILITY_ELEVATED"
    PARTICIPANT_CROWDING_ELEVATED = "PARTICIPANT_CROWDING_ELEVATED"
    PARTICIPANT_DISAGREEMENT_ELEVATED = "PARTICIPANT_DISAGREEMENT_ELEVATED"
    PARTICIPANT_CONSENSUS_ELEVATED = "PARTICIPANT_CONSENSUS_ELEVATED"
    PARTICIPANT_ALIGNMENT_CANDIDATE = "PARTICIPANT_ALIGNMENT_CANDIDATE"
    PARTICIPANT_CONTRARIAN_CANDIDATE = "PARTICIPANT_CONTRARIAN_CANDIDATE"
    PARTICIPANT_COPYABILITY_HIGH = "PARTICIPANT_COPYABILITY_HIGH"
    PARTICIPANT_COPYABILITY_LOW = "PARTICIPANT_COPYABILITY_LOW"
    PARTICIPANT_DATA_CONFIDENCE = "PARTICIPANT_DATA_CONFIDENCE"
    PARTICIPANT_SKILL_ELEVATED = "PARTICIPANT_SKILL_ELEVATED"
    PARTICIPANT_SKILL_BELOW_BASELINE = "PARTICIPANT_SKILL_BELOW_BASELINE"
    PARTICIPANT_CROSS_ASSET_ALIGNED = "PARTICIPANT_CROSS_ASSET_ALIGNED"
    PARTICIPANT_CROSS_ASSET_DIVERGENT = "PARTICIPANT_CROSS_ASSET_DIVERGENT"
    LARGE_DERIVATIVE_FLOW_CONFIRMED = "LARGE_DERIVATIVE_FLOW_CONFIRMED"
    LARGE_DERIVATIVE_FLOW_AMBIGUOUS = "LARGE_DERIVATIVE_FLOW_AMBIGUOUS"


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


_CONTEXT_OPTIONS_COUPLED_SIGNALS: tuple[tuple[EvidenceSignal, EvidenceSignal], ...] = (
    (EvidenceSignal.EVENT_SURPRISE_POSITIVE, EvidenceSignal.EVENT_VOL_PREMIUM),
    (EvidenceSignal.EVENT_SURPRISE_NEGATIVE, EvidenceSignal.IV_CRUSH_RISK),
    (EvidenceSignal.SEMANTIC_SENTIMENT_POSITIVE, EvidenceSignal.OPTION_FLOW_DIRECTION),
    (EvidenceSignal.SEMANTIC_SENTIMENT_NEGATIVE, EvidenceSignal.OPTIONS_FLOW_REVERSAL),
    (EvidenceSignal.CATALYST_STRENGTH, EvidenceSignal.EVENT_VOL_PREMIUM),
)


def validate_evidence_dag(evidence_items: list[NormalizedLaneEvidence]) -> list[str]:
    """Detect illegal same-lane MODEL_OUTPUT → CROSS_LANE_MODEL_OUTPUT cycles.

    Also flags MC-D20 same-timestamp Market Context ↔ Options model coupling.

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

    model_outputs = [
        item
        for item in evidence_items
        if item.provenance_class
        in {EvidenceProvenanceClass.MODEL_OUTPUT, EvidenceProvenanceClass.CROSS_LANE_MODEL_OUTPUT}
        and item.observed_at
    ]
    by_timestamp: dict[str, list[NormalizedLaneEvidence]] = {}
    for item in model_outputs:
        by_timestamp.setdefault(item.observed_at or "", []).append(item)

    for observed_at, group in by_timestamp.items():
        if not observed_at:
            continue
        mc_signals = {
            item.signal
            for item in group
            if item.lane in {LaneId.MARKET_CONTEXT, LaneId.CATALYST, LaneId.ATTENTION}
        }
        options_signals = {item.signal for item in group if item.lane == LaneId.OPTIONS}
        if not mc_signals or not options_signals:
            continue
        for mc_signal, options_signal in _CONTEXT_OPTIONS_COUPLED_SIGNALS:
            if mc_signal in mc_signals and options_signal in options_signals:
                violations.append(
                    "MC-D20 same-timestamp Context↔Options coupling at "
                    f"{observed_at}: {mc_signal.value} with {options_signal.value}"
                )
    return violations


def apply_evidence_lag_rules(
    evidence_items: list[NormalizedLaneEvidence],
) -> tuple[list[NormalizedLaneEvidence], list[str]]:
    """Drop lower-priority same-timestamp coupled items to prevent circular reinforcement."""
    violations = validate_evidence_dag(evidence_items)
    if not violations:
        return evidence_items, []

    drop_keys: set[tuple[str, str, str]] = set()
    by_timestamp: dict[str, list[NormalizedLaneEvidence]] = {}
    for item in evidence_items:
        if item.observed_at:
            by_timestamp.setdefault(item.observed_at, []).append(item)

    for observed_at, group in by_timestamp.items():
        mc_signals = {
            item.signal
            for item in group
            if item.lane in {LaneId.MARKET_CONTEXT, LaneId.CATALYST, LaneId.ATTENTION}
        }
        options_signals = {item.signal for item in group if item.lane == LaneId.OPTIONS}
        for mc_signal, options_signal in _CONTEXT_OPTIONS_COUPLED_SIGNALS:
            if mc_signal in mc_signals and options_signal in options_signals:
                for item in group:
                    if item.lane == LaneId.OPTIONS and item.signal == options_signal:
                        if item.provenance_class in {
                            EvidenceProvenanceClass.MODEL_OUTPUT,
                            EvidenceProvenanceClass.CROSS_LANE_MODEL_OUTPUT,
                        }:
                            drop_keys.add(
                                (item.lane.value, item.signal.value, item.source_ref)
                            )

    if not drop_keys:
        return evidence_items, violations

    filtered = [
        item
        for item in evidence_items
        if (item.lane.value, item.signal.value, item.source_ref) not in drop_keys
    ]
    return filtered, violations
