"""Causal short-squeeze state machine evaluator (interpretable baseline v1).

This module implements evidence-gated state assignment. It does **not** emit
calibrated squeeze probabilities — those require labeled datasets and separate
model artifacts (see docs/research/SHORT_SQUEEZE_CAUSAL_RESEARCH_SPEC.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import (
    CausalDimension,
    EvidenceItem,
    HorizonModelSnapshot,
    HorizonProbability,
    MagnitudeEstimateSnapshot,
    MechanismLabel,
    SqueezeExplanation,
    SqueezeIntelligenceResult,
    SqueezeState,
)
from .explanation import build_explanation_graph
from .fuel import (
    FUEL_METHOD,
    detect_cvd_divergence,
    estimate_covering_pressure,
    estimate_exhaustion_risk,
    estimate_reflexivity_strength,
    estimate_remaining_fuel,
)

MODEL_VERSION = "squeeze_causal_baseline.v4"
HORIZON_DAYS = (1, 3, 5, 10, 20)

_STATE_ORDER: dict[SqueezeState, int] = {
    SqueezeState.BASELINE: 0,
    SqueezeState.VULNERABLE: 1,
    SqueezeState.ARMED: 2,
    SqueezeState.IGNITION_WATCH: 3,
    SqueezeState.LIVE_CONFIRMATION: 4,
    SqueezeState.ACTIVE_SQUEEZE: 5,
    SqueezeState.EXHAUSTION: 6,
    SqueezeState.POST_SQUEEZE: 7,
    SqueezeState.UNEVALUABLE: -1,
}


@dataclass(frozen=True, slots=True)
class RuleSnapshot:
    rule_id: str
    category: str
    outcome: str
    reason: str = ""


@dataclass(frozen=True, slots=True)
class AdamSnapshot:
    pressure: float | None
    ignition: float | None
    classification: str
    coverage_label: str | None = None


@dataclass(frozen=True, slots=True)
class CrossLaneSnapshot:
    """Normalized evidence published by other IMP lanes (optional)."""

    order_flow_cvd_slope: float | None = None
    order_flow_aggressive_buy: bool | None = None
    order_flow_aggressive_sell: bool | None = None
    order_flow_available: bool = False
    options_call_demand_anomaly: bool | None = None
    options_gamma_amplification: bool | None = None
    options_hedging_pressure: float | None = None
    options_flow_reversal: bool | None = None
    options_gamma_decay: bool | None = None
    options_available: bool = False
    borrow_normalization_score: float | None = None
    attention_acceleration: float | None = None
    attention_available: bool = False
    catalyst_strength: float | None = None
    catalyst_available: bool = False
    thesis_invalidation_score: float | None = None
    lending_fee_rate: float | None = None
    lending_shares_available: int | None = None
    lending_utilization_rate: float | None = None
    lending_shares_on_loan: int | None = None
    lending_available: bool = False
    borrow_utilization_velocity: float | None = None


@dataclass(frozen=True, slots=True)
class FuelHistorySnapshot:
    """Prior fuel/CVD metrics from PIT-filtered transition stream."""

    previous_remaining_fuel: float | None = None
    previous_cvd_slope: float | None = None
    previous_reflexivity: float | None = None


@dataclass(frozen=True, slots=True)
class QualitySnapshot:
    stale_fields: tuple[str, ...] = ()
    unavailable_capabilities: tuple[str, ...] = ()
    provider_conflicts: bool = False
    frozen_snapshot: bool = False


def _rule_outcome(rules: tuple[RuleSnapshot, ...], rule_id: str) -> str | None:
    for rule in rules:
        if rule.rule_id == rule_id:
            return rule.outcome.upper()
    return None


def _rules_in_category(rules: tuple[RuleSnapshot, ...], category: str) -> list[RuleSnapshot]:
    return [rule for rule in rules if rule.category == category]


def _count_outcomes(rules: tuple[RuleSnapshot, ...], outcome: str) -> int:
    return sum(1 for rule in rules if rule.outcome.upper() == outcome)


def _confidence_from_coverage(
    *,
    data_confidence: str,
    evaluable_dimensions: int,
    required_dimensions: int,
) -> str:
    if data_confidence == "LOW":
        return "LOW"
    ratio = evaluable_dimensions / max(required_dimensions, 1)
    if ratio >= 0.75:
        return "HIGH"
    if ratio >= 0.5:
        return "MEDIUM"
    return "LOW"


def _horizon_probabilities_unavailable() -> tuple[HorizonProbability, ...]:
    return tuple(
        HorizonProbability(
            horizon_days=days,
            value=None,
            status="RESEARCH_ONLY",
            note=(
                "Horizon probability requires calibrated models and walk-forward "
                "validation. Not available in baseline causal evaluator."
            ),
        )
        for days in HORIZON_DAYS
    )


def _horizon_probabilities_from_model(
    horizon_model: HorizonModelSnapshot | None,
) -> tuple[HorizonProbability, ...]:
    if horizon_model is None:
        return _horizon_probabilities_unavailable()
    if horizon_model.status != "CALIBRATED" or not horizon_model.pit_verified:
        return _horizon_probabilities_unavailable()

    hazard_map = {days: value for days, value in horizon_model.hazard_by_horizon}
    probabilities: list[HorizonProbability] = []
    for days in HORIZON_DAYS:
        value = hazard_map.get(days)
        if value is None and horizon_model.occurrence_probability is not None:
            value = horizon_model.occurrence_probability
        probabilities.append(
            HorizonProbability(
                horizon_days=days,
                value=round(float(value), 6) if value is not None else None,
                status="CALIBRATED" if value is not None else "RESEARCH_ONLY",
                note=f"Calibrated via {horizon_model.model_version}",
            )
        )
    return tuple(probabilities)


def evaluate_squeeze_intelligence(
    *,
    rules: tuple[RuleSnapshot, ...],
    adam: AdamSnapshot | None = None,
    cross_lane: CrossLaneSnapshot | None = None,
    quality: QualitySnapshot | None = None,
    previous_state: SqueezeState | None = None,
    fuel_history: FuelHistorySnapshot | None = None,
    horizon_model: HorizonModelSnapshot | None = None,
) -> SqueezeIntelligenceResult:
    """Evaluate causal squeeze state from explicit evidence snapshots."""
    quality = quality or QualitySnapshot()
    cross_lane = cross_lane or CrossLaneSnapshot()
    fuel_history = fuel_history or FuelHistorySnapshot()
    supporting: list[EvidenceItem] = []
    contradicting: list[EvidenceItem] = []
    quality_flags: list[str] = list(quality.stale_fields)
    missing: list[str] = list(quality.unavailable_capabilities)

    if quality.provider_conflicts:
        quality_flags.append("PROVIDER_CONFLICT")
    if quality.frozen_snapshot:
        quality_flags.append("FROZEN_SNAPSHOT_NO_LIVE_TRANSITIONS")

    pressure = adam.pressure if adam else None
    ignition = adam.ignition if adam else None

    si_pass = _rule_outcome(rules, "PUBLISHED_SHORT_INTEREST_AVAILABLE") == "PASS"
    dtc_pass = _rule_outcome(rules, "DAYS_TO_COVER_MINIMUM") == "PASS"
    borrow_fee_pass = _rule_outcome(rules, "BORROW_FEE_MINIMUM") == "PASS"
    borrow_avail_pass = _rule_outcome(rules, "BORROW_AVAILABILITY_MAXIMUM") == "PASS"

    short_pressure_rules = _rules_in_category(rules, "SHORT_PRESSURE_CONFIRMATION")
    catalyst_rules = _rules_in_category(rules, "CATALYST_EVIDENCE")
    catalyst_pass = any(rule.outcome.upper() == "PASS" for rule in catalyst_rules)

    # --- Dimension scores (explicit null when insufficient evidence) ---
    vulnerability: float | None = pressure
    if si_pass:
        supporting.append(
            EvidenceItem(
                code="SI_ELEVATED",
                label="Elevated published short interest",
                dimension=CausalDimension.SHORT_CROWDING,
                polarity="SUPPORTS",
                strength="MODERATE" if (pressure or 0) < 70 else "HIGH",
                source="phase3a:PUBLISHED_SHORT_INTEREST_AVAILABLE",
                detail="Short-interest rule PASS",
            )
        )
    elif _count_outcomes(short_pressure_rules, "UNKNOWN") > 0:
        contradicting.append(
            EvidenceItem(
                code="SI_STALE_OR_UNKNOWN",
                label="Short interest unavailable or stale",
                dimension=CausalDimension.SHORT_CROWDING,
                polarity="CONTRADICTS",
                strength="MODERATE",
                source="phase3a",
                detail="Short-pressure evidence incomplete",
            )
        )
        quality_flags.append("SHORT_INTEREST_STALE")

    constraint_pressure: float | None = None
    if borrow_fee_pass or borrow_avail_pass:
        constraint_pressure = pressure if pressure is not None else 55.0
        supporting.append(
            EvidenceItem(
                code="LENDING_CONSTRAINT",
                label="Securities-lending constraint signal",
                dimension=CausalDimension.SECURITIES_LENDING,
                polarity="SUPPORTS",
                strength="MODERATE",
                source="phase3a:borrow_rules",
                detail="Borrow fee or availability rule PASS",
            )
        )
    elif cross_lane.lending_available:
        score_parts: list[float] = []
        if cross_lane.lending_fee_rate is not None and cross_lane.lending_fee_rate >= 5.0:
            score_parts.append(min(100.0, cross_lane.lending_fee_rate * 3.0))
        if cross_lane.lending_utilization_rate is not None:
            score_parts.append(min(100.0, cross_lane.lending_utilization_rate))
        elif (
            cross_lane.lending_shares_available is not None
            and cross_lane.lending_shares_available < 100_000
        ):
            score_parts.append(60.0)
        if score_parts:
            constraint_pressure = round(sum(score_parts) / len(score_parts), 1)
            supporting.append(
                EvidenceItem(
                    code="LENDING_SNAPSHOT_CONSTRAINT",
                    label="IBKR securities-lending snapshot constraint",
                    dimension=CausalDimension.SECURITIES_LENDING,
                    polarity="SUPPORTS",
                    strength="MODERATE",
                    source="cross_lane:lending",
                    detail="Borrow fee/availability from governed lending snapshot",
                )
            )
        if cross_lane.borrow_utilization_velocity is not None:
            if "borrow_utilization_velocity" in missing:
                missing.remove("borrow_utilization_velocity")
        if cross_lane.lending_utilization_rate is not None:
            if "shares_on_loan_delta" in missing:
                missing.remove("shares_on_loan_delta")
    else:
        missing.append("borrow_utilization_velocity")
        missing.append("shares_on_loan_delta")

    short_stress: float | None = None
    if pressure is not None and ignition is not None:
        short_stress = round((pressure + max(0.0, ignition - 50.0)) / 2.0, 1)

    ignition_strength: float | None = ignition
    if catalyst_pass:
        supporting.append(
            EvidenceItem(
                code="CATALYST_PRESENT",
                label="Catalyst evidence detected",
                dimension=CausalDimension.CATALYST,
                polarity="SUPPORTS",
                strength="MODERATE",
                source="phase3a:CATALYST_EVIDENCE",
                detail="At least one catalyst rule PASS",
            )
        )
    if ignition is not None and ignition >= 50:
        supporting.append(
            EvidenceItem(
                code="PRICE_RVOL_IGNITION",
                label="Price / RVOL ignition signal",
                dimension=CausalDimension.CATALYST,
                polarity="SUPPORTS",
                strength="HIGH" if ignition >= 70 else "MODERATE",
                source="adam:ignition",
                detail=f"Ignition dimension {ignition}",
            )
        )
    if cross_lane.catalyst_available and cross_lane.catalyst_strength is not None:
        base_ignition = ignition_strength if ignition_strength is not None else 0.0
        ignition_strength = round(
            min(100.0, max(base_ignition, cross_lane.catalyst_strength * 0.9)),
            1,
        )
        supporting.append(
            EvidenceItem(
                code="CATALYST_STRENGTH",
                label="Market-context catalyst strength",
                dimension=CausalDimension.CATALYST,
                polarity="SUPPORTS",
                strength="HIGH" if cross_lane.catalyst_strength >= 75.0 else "MODERATE",
                source="cross_lane:market_context",
                detail=f"Gated catalyst strength {cross_lane.catalyst_strength}",
            )
        )
    if (
        cross_lane.thesis_invalidation_score is not None
        and cross_lane.thesis_invalidation_score >= 55.0
    ):
        contradicting.append(
            EvidenceItem(
                code="THESIS_INVALIDATED",
                label="Short thesis invalidation signal",
                dimension=CausalDimension.CATALYST,
                polarity="CONTRADICTS",
                strength="HIGH" if cross_lane.thesis_invalidation_score >= 75.0 else "MODERATE",
                source="cross_lane:market_context",
                detail=f"Thesis invalidation score {cross_lane.thesis_invalidation_score}",
            )
        )

    reflexivity_strength: float | None = None
    remaining_fuel: float | None = None
    exhaustion_risk: float | None = None
    covering_pressure: float | None = None

    if cross_lane.order_flow_available:
        if cross_lane.order_flow_aggressive_buy:
            supporting.append(
                EvidenceItem(
                    code="CVD_AGGRESSIVE_BUY",
                    label="Aggressive buy pressure (order flow)",
                    dimension=CausalDimension.ORDER_FLOW,
                    polarity="SUPPORTS",
                    strength="MODERATE",
                    source="cross_lane:order_flow",
                    detail="Normalized order-flow evidence consumed by squeeze lane",
                )
            )
        if cross_lane.order_flow_cvd_slope is not None and cross_lane.order_flow_cvd_slope < 0:
            contradicting.append(
                EvidenceItem(
                    code="CVD_DIVERGENCE",
                    label="CVD divergence under rising price",
                    dimension=CausalDimension.ORDER_FLOW,
                    polarity="CONTRADICTS",
                    strength="MODERATE",
                    source="cross_lane:order_flow",
                    detail="Negative CVD slope weakens live confirmation",
                )
            )
    else:
        missing.append("order_flow_cvd")

    if cross_lane.options_available and cross_lane.options_gamma_amplification:
        supporting.append(
            EvidenceItem(
                code="GAMMA_AMPLIFICATION",
                label="Options gamma amplification potential",
                dimension=CausalDimension.OPTIONS_AMPLIFICATION,
                polarity="SUPPORTS",
                strength="MODERATE",
                source="cross_lane:options",
                detail="Dealer-hedging amplification asserted only with positioning evidence",
            )
        )
    elif not cross_lane.options_available:
        missing.append("options_dealer_positioning")

    if cross_lane.options_flow_reversal:
        contradicting.append(
            EvidenceItem(
                code="OPTIONS_FLOW_REVERSAL",
                label="Options signed flow reversal toward sell-initiated",
                dimension=CausalDimension.OPTIONS_AMPLIFICATION,
                polarity="CONTRADICTS",
                strength="MODERATE",
                source="cross_lane:options",
                detail="Sell-initiated dominant flow weakens reflexive amplification",
            )
        )
    if cross_lane.options_gamma_decay:
        contradicting.append(
            EvidenceItem(
                code="GAMMA_DECAY",
                label="Dealer gamma amplification decaying",
                dimension=CausalDimension.OPTIONS_AMPLIFICATION,
                polarity="CONTRADICTS",
                strength="MODERATE",
                source="cross_lane:options",
                detail="Negative-gamma hedging pressure declining from prior snapshot",
            )
        )
    if isinstance(cross_lane.borrow_normalization_score, (int, float)) and (
        cross_lane.borrow_normalization_score >= 50.0
    ):
        supporting.append(
            EvidenceItem(
                code="BORROW_NORMALIZATION",
                label="Securities-lending normalization from squeeze peak",
                dimension=CausalDimension.SECURITIES_LENDING,
                polarity="SUPPORTS",
                strength="MODERATE",
                source=f"fuel:{FUEL_METHOD}",
                detail=(
                    f"Borrow normalization score {cross_lane.borrow_normalization_score} "
                    "(utilization/fee decline proxy)"
                ),
            )
        )

    reflexivity_strength = estimate_reflexivity_strength(
        order_flow_available=cross_lane.order_flow_available,
        aggressive_buy=cross_lane.order_flow_aggressive_buy,
        cvd_slope=cross_lane.order_flow_cvd_slope,
        options_gamma_amplification=cross_lane.options_gamma_amplification,
        hedging_pressure=cross_lane.options_hedging_pressure,
    )
    if reflexivity_strength is not None and reflexivity_strength >= 60:
        supporting.append(
            EvidenceItem(
                code="REFLEXIVE_FEEDBACK_LOOP",
                label="Reflexive price-feedback loop evidence",
                dimension=CausalDimension.ORDER_FLOW,
                polarity="SUPPORTS",
                strength="HIGH" if reflexivity_strength >= 75 else "MODERATE",
                source=f"fuel:{FUEL_METHOD}",
                detail=f"Reflexivity strength {reflexivity_strength} from cross-lane proxies",
            )
        )

    covering_pressure = estimate_covering_pressure(
        order_flow_available=cross_lane.order_flow_available,
        cvd_slope=cross_lane.order_flow_cvd_slope,
        aggressive_buy=cross_lane.order_flow_aggressive_buy,
        aggressive_sell=cross_lane.order_flow_aggressive_sell,
    )
    if covering_pressure is not None and covering_pressure >= 30:
        supporting.append(
            EvidenceItem(
                code="COVERING_PRESSURE_PROXY",
                label="Order-flow covering pressure proxy",
                dimension=CausalDimension.ORDER_FLOW,
                polarity="SUPPORTS",
                strength="MODERATE",
                source=f"fuel:{FUEL_METHOD}",
                detail=(
                    f"Covering pressure estimate {covering_pressure} — "
                    "order-flow proxy, not published SI delta"
                ),
            )
        )

    remaining_fuel = estimate_remaining_fuel(
        vulnerability=vulnerability,
        covering_pressure=covering_pressure,
    )
    if (
        remaining_fuel is not None
        and vulnerability is not None
        and remaining_fuel < vulnerability - 5
    ):
        supporting.append(
            EvidenceItem(
                code="FUEL_DEPLETION",
                label="Structural fuel consumption detected",
                dimension=CausalDimension.SHORT_CROWDING,
                polarity="SUPPORTS",
                strength="MODERATE",
                source=f"fuel:{FUEL_METHOD}",
                detail=f"Remaining fuel {remaining_fuel} after covering proxy consumption",
            )
        )

    cvd_divergence = detect_cvd_divergence(
        cvd_slope=cross_lane.order_flow_cvd_slope,
        previous_cvd_slope=fuel_history.previous_cvd_slope,
        aggressive_buy=cross_lane.order_flow_aggressive_buy,
    )
    if cvd_divergence:
        contradicting.append(
            EvidenceItem(
                code="CVD_DIVERGENCE_HISTORY",
                label="CVD slope flipped negative under buy regime",
                dimension=CausalDimension.ORDER_FLOW,
                polarity="CONTRADICTS",
                strength="HIGH",
                source=f"fuel:{FUEL_METHOD}",
                detail="Temporal CVD divergence from prior positive slope",
            )
        )

    exhaustion_risk = estimate_exhaustion_risk(
        covering_pressure=covering_pressure,
        cvd_slope=cross_lane.order_flow_cvd_slope,
        remaining_fuel=remaining_fuel,
        previous_fuel=fuel_history.previous_remaining_fuel,
        aggressive_buy=cross_lane.order_flow_aggressive_buy,
        cvd_divergence=cvd_divergence,
        borrow_normalization=cross_lane.borrow_normalization_score,
        options_flow_reversal=cross_lane.options_flow_reversal,
        options_gamma_decay=cross_lane.options_gamma_decay,
    )

    market_mechanism: float | None = None
    lender_mechanism: float | None = None
    mechanisms: list[MechanismLabel] = []

    if vulnerability is not None and vulnerability >= 50:
        market_mechanism = vulnerability
        if ignition_strength is not None and ignition_strength >= 50:
            market_mechanism = round((vulnerability + ignition_strength) / 2.0, 1)
            mechanisms.append(MechanismLabel.MARKET_SQUEEZE)
    if constraint_pressure is not None and constraint_pressure >= 50:
        lender_mechanism = constraint_pressure
        mechanisms.append(MechanismLabel.LENDER_SQUEEZE)
    if cross_lane.options_gamma_amplification:
        mechanisms.append(MechanismLabel.GAMMA_AMPLIFIED)
    if cross_lane.attention_available and (cross_lane.attention_acceleration or 0) > 0:
        mechanisms.append(MechanismLabel.ATTENTION_AMPLIFIED)
    if not mechanisms:
        mechanisms.append(MechanismLabel.UNKNOWN)

    # --- Fail-closed unevaluable gate ---
    adam_class = (adam.classification if adam else "UNEVALUABLE").upper()
    if adam_class == "CONFLICTED" or quality.provider_conflicts:
        return _unevaluable_result(
            supporting=supporting,
            contradicting=contradicting,
            quality_flags=quality_flags + ["CAPABILITY_CONFLICTED"],
            missing=missing,
            previous_state=previous_state,
            note="Material provider conflicts block causal state assignment.",
        )

    evaluable_dims = sum(
        1 for value in (vulnerability, constraint_pressure, ignition_strength) if value is not None
    )
    if evaluable_dims == 0 and not rules:
        return _unevaluable_result(
            supporting=supporting,
            contradicting=contradicting,
            quality_flags=quality_flags + ["CAPABILITY_UNAVAILABLE"],
            missing=missing,
            previous_state=previous_state,
            note="Insufficient evidence for any causal dimension.",
        )

    data_confidence = "LOW" if quality.stale_fields else "MEDIUM"
    if evaluable_dims >= 2 and not quality.stale_fields:
        data_confidence = "HIGH"

    # --- State assignment (evidence cascade, not single score) ---
    state = SqueezeState.BASELINE
    transition_trigger = "default_baseline"

    if (
        reflexivity_strength is not None
        and reflexivity_strength >= 70
        and ignition_strength is not None
        and ignition_strength >= 70
        and vulnerability is not None
        and vulnerability >= 60
    ):
        state = SqueezeState.ACTIVE_SQUEEZE
        transition_trigger = "reflexive_feedback_with_structural_fuel"
    elif (
        reflexivity_strength is not None
        and reflexivity_strength >= 50
        and ignition_strength is not None
        and ignition_strength >= 55
    ):
        state = SqueezeState.LIVE_CONFIRMATION
        transition_trigger = "live_order_flow_confirmation"
    elif (
        ignition_strength is not None
        and ignition_strength >= 55
        and (vulnerability is None or vulnerability < 45)
        and ignition_strength >= 70
    ):
        state = SqueezeState.IGNITION_WATCH
        transition_trigger = "momentum_without_structural_fuel"
        mechanisms = [MechanismLabel.NON_SQUEEZE_MOMENTUM]
        contradicting.append(
            EvidenceItem(
                code="LOW_STRUCTURAL_FUEL",
                label="Strong ignition without structural vulnerability",
                dimension=CausalDimension.SHORT_CROWDING,
                polarity="CONTRADICTS",
                strength="HIGH",
                source="causal:state_machine",
                detail="May indicate momentum rally rather than short squeeze",
            )
        )
    elif ignition_strength is not None and ignition_strength >= 55 and (
        catalyst_pass or (ignition_strength >= 65)
    ):
        state = SqueezeState.IGNITION_WATCH
        transition_trigger = "ignition_and_catalyst_or_momentum"
    elif (
        vulnerability is not None
        and vulnerability >= 60
        and (constraint_pressure is not None and constraint_pressure >= 55 or dtc_pass)
    ):
        state = SqueezeState.ARMED
        transition_trigger = "structural_vulnerability_worsening"
    elif vulnerability is not None and vulnerability >= 45 and (si_pass or dtc_pass):
        state = SqueezeState.VULNERABLE
        transition_trigger = "latent_short_pressure_structure"

    # Backward transition hints (frozen snapshots cannot prove exhaustion without history)
    if previous_state is not None and _STATE_ORDER.get(state, 0) < _STATE_ORDER.get(previous_state, 0):
        transition_trigger = f"evidence_deterioration:{previous_state.value}->{state.value}"

    if exhaustion_risk is not None and exhaustion_risk >= 70:
        state = SqueezeState.EXHAUSTION
        transition_trigger = "exhaustion_signals"

    horizon_probabilities = _horizon_probabilities_from_model(horizon_model)
    if horizon_model is not None and horizon_model.status == "CALIBRATED" and horizon_model.pit_verified:
        supporting.append(
            EvidenceItem(
                code="CALIBRATED_HORIZON_PROBABILITY",
                label="Walk-forward calibrated horizon probabilities",
                dimension=CausalDimension.REFLEXIVITY,
                polarity="SUPPORTS",
                strength="MODERATE",
                source=f"model:{horizon_model.model_version}",
                detail="Horizon slots populated from adjudicated fixture walk-forward harness",
            )
        )
        if horizon_model.magnitude is not None and horizon_model.magnitude.expected_move_pct is not None:
            supporting.append(
                EvidenceItem(
                    code="MAGNITUDE_ESTIMATE",
                    label="Conditional squeeze magnitude estimate",
                    dimension=CausalDimension.REMAINING_FUEL,
                    polarity="SUPPORTS",
                    strength="MODERATE",
                    source=f"model:{horizon_model.magnitude.model_version}",
                    detail=(
                        f"Expected move {horizon_model.magnitude.expected_move_pct:.2f}% "
                        f"via {horizon_model.magnitude.method}"
                    ),
                )
            )

    overall = _confidence_from_coverage(
        data_confidence=data_confidence,
        evaluable_dimensions=evaluable_dims,
        required_dimensions=3,
    )
    model_confidence = "MEDIUM"  # baseline rules — not walk-forward validated

    summary = _build_summary(state, vulnerability, ignition_strength, overall)
    transition = {
        "trigger": transition_trigger,
        "from_state": previous_state.value if previous_state else None,
        "to_state": state.value,
        "hysteresis_note": (
            "Live deployments should require sustained evidence and cooldown "
            "before backward transitions to reduce state flapping."
        ),
    }
    draft = SqueezeIntelligenceResult(
        model_version=MODEL_VERSION,
        state=state,
        previous_state=previous_state,
        state_confidence=overall,
        mechanism_labels=tuple(mechanisms),
        vulnerability=vulnerability,
        constraint_pressure=constraint_pressure,
        short_stress=short_stress,
        ignition_strength=ignition_strength,
        reflexivity_strength=reflexivity_strength,
        remaining_fuel=remaining_fuel,
        exhaustion_risk=exhaustion_risk,
        market_squeeze_mechanism_score=market_mechanism,
        lender_squeeze_mechanism_score=lender_mechanism,
        horizon_probabilities=horizon_probabilities,
        model_confidence=model_confidence,
        data_confidence=data_confidence,
        overall_confidence=overall,
        quality_flags=tuple(dict.fromkeys(quality_flags)),
        missing_capabilities=tuple(dict.fromkeys(missing)),
        supporting_evidence=tuple(supporting),
        contradicting_evidence=tuple(contradicting),
        explanation=SqueezeExplanation(summary=summary, nodes=()),
        research_status="EXPERIMENTAL",
        transition=transition,
    )
    graph = build_explanation_graph(draft)
    return SqueezeIntelligenceResult(
        model_version=draft.model_version,
        state=draft.state,
        previous_state=draft.previous_state,
        state_confidence=draft.state_confidence,
        mechanism_labels=draft.mechanism_labels,
        vulnerability=draft.vulnerability,
        constraint_pressure=draft.constraint_pressure,
        short_stress=draft.short_stress,
        ignition_strength=draft.ignition_strength,
        reflexivity_strength=draft.reflexivity_strength,
        remaining_fuel=draft.remaining_fuel,
        exhaustion_risk=draft.exhaustion_risk,
        market_squeeze_mechanism_score=draft.market_squeeze_mechanism_score,
        lender_squeeze_mechanism_score=draft.lender_squeeze_mechanism_score,
        horizon_probabilities=draft.horizon_probabilities,
        model_confidence=draft.model_confidence,
        data_confidence=draft.data_confidence,
        overall_confidence=draft.overall_confidence,
        quality_flags=draft.quality_flags,
        missing_capabilities=draft.missing_capabilities,
        supporting_evidence=draft.supporting_evidence,
        contradicting_evidence=draft.contradicting_evidence,
        explanation=SqueezeExplanation(summary=summary, nodes=(graph,)),
        research_status=draft.research_status,
        transition=transition,
    )


def _build_summary(
    state: SqueezeState,
    vulnerability: float | None,
    ignition: float | None,
    confidence: str,
) -> str:
    parts = [f"Causal state {state.value} ({confidence} confidence)."]
    if vulnerability is not None:
        parts.append(f"Structural vulnerability {vulnerability:.0f}/100.")
    if ignition is not None:
        parts.append(f"Ignition strength {ignition:.0f}/100.")
    if state is SqueezeState.BASELINE:
        parts.append("No material squeeze mechanism detected at this snapshot.")
    return " ".join(parts)


def _unevaluable_result(
    *,
    supporting: list[EvidenceItem],
    contradicting: list[EvidenceItem],
    quality_flags: list[str],
    missing: list[str],
    previous_state: SqueezeState | None,
    note: str,
) -> SqueezeIntelligenceResult:
    explanation = SqueezeExplanation(summary=note, nodes=())
    return SqueezeIntelligenceResult(
        model_version=MODEL_VERSION,
        state=SqueezeState.UNEVALUABLE,
        previous_state=previous_state,
        state_confidence="LOW",
        mechanism_labels=(MechanismLabel.UNKNOWN,),
        vulnerability=None,
        constraint_pressure=None,
        short_stress=None,
        ignition_strength=None,
        reflexivity_strength=None,
        remaining_fuel=None,
        exhaustion_risk=None,
        market_squeeze_mechanism_score=None,
        lender_squeeze_mechanism_score=None,
        horizon_probabilities=_horizon_probabilities_unavailable(),
        model_confidence="LOW",
        data_confidence="LOW",
        overall_confidence="LOW",
        quality_flags=tuple(dict.fromkeys(quality_flags)),
        missing_capabilities=tuple(dict.fromkeys(missing)),
        supporting_evidence=tuple(supporting),
        contradicting_evidence=tuple(contradicting),
        explanation=explanation,
        research_status="EXPERIMENTAL",
        transition={"trigger": "fail_closed", "to_state": SqueezeState.UNEVALUABLE.value},
    )


def intelligence_result_to_dict(result: SqueezeIntelligenceResult) -> dict[str, Any]:
    """Serialize for HTTP/API consumers."""
    return {
        "model_version": result.model_version,
        "state": result.state.value,
        "previous_state": result.previous_state.value if result.previous_state else None,
        "state_confidence": result.state_confidence,
        "mechanism_labels": [label.value for label in result.mechanism_labels],
        "vulnerability": result.vulnerability,
        "constraint_pressure": result.constraint_pressure,
        "short_stress": result.short_stress,
        "ignition_strength": result.ignition_strength,
        "reflexivity_strength": result.reflexivity_strength,
        "remaining_fuel": result.remaining_fuel,
        "exhaustion_risk": result.exhaustion_risk,
        "market_squeeze_mechanism_score": result.market_squeeze_mechanism_score,
        "lender_squeeze_mechanism_score": result.lender_squeeze_mechanism_score,
        "horizon_probabilities": [
            {
                "horizon_days": hp.horizon_days,
                "value": hp.value,
                "status": hp.status,
                "note": hp.note,
            }
            for hp in result.horizon_probabilities
        ],
        "model_confidence": result.model_confidence,
        "data_confidence": result.data_confidence,
        "overall_confidence": result.overall_confidence,
        "quality_flags": list(result.quality_flags),
        "missing_capabilities": list(result.missing_capabilities),
        "supporting_evidence": [
            {
                "code": item.code,
                "label": item.label,
                "dimension": item.dimension.value,
                "polarity": item.polarity,
                "strength": item.strength,
                "source": item.source,
                "detail": item.detail,
            }
            for item in result.supporting_evidence
        ],
        "contradicting_evidence": [
            {
                "code": item.code,
                "label": item.label,
                "dimension": item.dimension.value,
                "polarity": item.polarity,
                "strength": item.strength,
                "source": item.source,
                "detail": item.detail,
            }
            for item in result.contradicting_evidence
        ],
        "explanation": {
            "summary": result.explanation.summary,
            "graph": build_explanation_graph(result),
        },
        "research_status": result.research_status,
        "transition": result.transition,
    }
