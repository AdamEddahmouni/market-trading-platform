"""Snapshot squeeze-state evaluator for the Main Screener (S8).

Adapted from the donor ``squeeze_core.intelligence.evaluator``
(``squeeze_causal_baseline.v4``, projects/short-squeeze-project). The donor's
state cascade, evidence codes, fail-closed UNEVALUABLE gate, and multi-class
requirements are kept. Two things are deliberately not carried over:

* The donor gates states on ADAM ``pressure``/``ignition`` 0-100 composites
  (unvalidated weights, PRIME/SUBPRIME output). Here every gate is the
  donor's own per-input Phase 3A rule (``phase_3a_transparent_candidate_policy.v1``)
  or IMP's canonical ``SHORT_SQUEEZE_DISCOVERY`` threshold, evaluated on a
  named source. No composite score is produced.
* Hysteresis and fuel history need a persisted previous state and prior
  observations. The Screener holds neither, so the result is a single-snapshot
  assessment: no transition is claimed, and states that the donor math can only
  reach with dealer positioning or temporal history (ACTIVE_SQUEEZE,
  EXHAUSTION, POST_SQUEEZE) are reported as unreachable with the reason.

Nothing here is a probability, a ranking, or a trade signal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

MODEL_ID = "imp_squeeze_snapshot.v1"
DONOR_MODEL = "squeeze_causal_baseline.v4"
DONOR_POLICY = "phase_3a_transparent_candidate_policy.v1"


class SqueezeState(StrEnum):
    """The donor lifecycle (``squeeze_core.intelligence.contracts.SqueezeState``)."""

    BASELINE = "BASELINE"
    VULNERABLE = "VULNERABLE"
    ARMED = "ARMED"
    IGNITION_WATCH = "IGNITION_WATCH"
    LIVE_CONFIRMATION = "LIVE_CONFIRMATION"
    ACTIVE_SQUEEZE = "ACTIVE_SQUEEZE"
    EXHAUSTION = "EXHAUSTION"
    POST_SQUEEZE = "POST_SQUEEZE"
    UNEVALUABLE = "UNEVALUABLE"


LIFECYCLE: tuple[SqueezeState, ...] = (
    SqueezeState.BASELINE, SqueezeState.VULNERABLE, SqueezeState.ARMED, SqueezeState.IGNITION_WATCH,
    SqueezeState.LIVE_CONFIRMATION, SqueezeState.ACTIVE_SQUEEZE, SqueezeState.EXHAUSTION, SqueezeState.POST_SQUEEZE,
)


class EvidenceClass(StrEnum):
    SHORT_CROWDING = "SHORT_CROWDING"
    SECURITIES_LENDING = "SECURITIES_LENDING"
    IGNITION = "IGNITION"
    CATALYST = "CATALYST"
    ORDER_FLOW = "ORDER_FLOW"
    OPTIONS_AMPLIFICATION = "OPTIONS_AMPLIFICATION"
    REGULATORY_CONTEXT = "REGULATORY_CONTEXT"


@dataclass(frozen=True, slots=True)
class Threshold:
    value: float
    operator: str  # gt | gte | lte
    source: str    # where the number comes from


# Donor Phase 3A rule thresholds (all marked provisional by the donor) and the
# IMP canonical discovery threshold for crowding. None of these is calibrated.
THRESHOLDS: dict[str, Threshold] = {
    # IMP discovery/screens.py SHORT_SQUEEZE_DISCOVERY: short float > 20 %.
    "SHORT_FLOAT_ELEVATED": Threshold(20.0, "gt", "IMP SHORT_SQUEEZE_DISCOVERY"),
    "DAYS_TO_COVER_MINIMUM": Threshold(2.0, "gte", f"{DONOR_POLICY}:DAYS_TO_COVER_MINIMUM"),
    "SHORT_INTEREST_PERCENTAGE_CHANGE_MINIMUM": Threshold(10.0, "gte", f"{DONOR_POLICY}:SHORT_INTEREST_PERCENTAGE_CHANGE_MINIMUM"),
    "BORROW_FEE_MINIMUM": Threshold(10.0, "gte", f"{DONOR_POLICY}:BORROW_FEE_MINIMUM"),
    "BORROW_AVAILABILITY_MAXIMUM": Threshold(100_000, "lte", f"{DONOR_POLICY}:BORROW_AVAILABILITY_MAXIMUM"),
    "PERCENTAGE_CHANGE_MINIMUM": Threshold(10.0, "gte", f"{DONOR_POLICY}:PERCENTAGE_CHANGE_MINIMUM"),
    "RELATIVE_VOLUME_MINIMUM": Threshold(5.0, "gte", f"{DONOR_POLICY}:RELATIVE_VOLUME_MINIMUM"),
    # IMP SHORT_SQUEEZE_DISCOVERY: float < 50M, RVOL > 1.5 (discovery context only).
    "LOW_FLOAT": Threshold(50_000_000, "lte", "IMP SHORT_SQUEEZE_DISCOVERY"),
    "VOLUME_PARTICIPATION": Threshold(1.5, "gt", "IMP SHORT_SQUEEZE_DISCOVERY"),
}
#: IMP cross-lane order-flow rule (donor_bridge.cross_lane_adapter): one side
#: dominates when its classified volume exceeds the other by 25 %.
AGGRESSOR_DOMINANCE = 1.25
#: Below this share of aggressor-classified volume, buy/sell dominance is not asserted.
MIN_CLASSIFIED_VOLUME_PCT = 50.0

UNREACHABLE: dict[SqueezeState, str] = {
    SqueezeState.ACTIVE_SQUEEZE: (
        "The donor requires reflexivity ≥ 70, which needs dealer gamma/hedging positioning on top of "
        "order flow. No current source supplies dealer positioning."
    ),
    SqueezeState.EXHAUSTION: (
        "The donor requires exhaustion risk ≥ 70, which needs prior fuel and CVD history. "
        "The Screener evaluates one snapshot and keeps no state history."
    ),
    SqueezeState.POST_SQUEEZE: "The donor evaluator never assigns this state from a snapshot.",
}


@dataclass(frozen=True, slots=True)
class OrderFlowInput:
    """Read from the S4 order-flow/CVD projections; never a new subscription."""

    state: str                   # S4 panel state (CURRENT, SESSION_CLOSED, …)
    buy_volume: float
    sell_volume: float
    classified_volume_pct: float | None
    recent_delta: float | None   # net signed volume over the last S4 window (CVD slope proxy)
    trade_count: int


@dataclass(frozen=True, slots=True)
class SqueezeInputs:
    short_float_pct: float | None = None          # Finviz snapshot
    short_ratio_days: float | None = None         # Finviz snapshot (Finviz days-to-cover)
    float_shares: float | None = None             # Finviz snapshot
    official_short_interest_available: bool = False
    official_short_interest_change_pct: float | None = None  # FINRA publication
    official_days_to_cover: float | None = None              # FINRA publication
    borrow_fee_pct: float | None = None
    borrow_available_shares: float | None = None
    change_pct: float | None = None               # Finviz snapshot
    rel_volume: float | None = None               # Finviz snapshot
    catalyst_present: bool | None = None          # None = news source unavailable
    order_flow: OrderFlowInput | None = None
    dealer_positioning_available: bool = False
    threshold_list_member: bool | None = None     # context only
    provider_conflict: bool = False
    stale_inputs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Evidence:
    code: str
    label: str
    evidence_class: EvidenceClass
    polarity: str  # SUPPORTS | CONTRADICTS | CONTEXT
    strength: str  # LOW | MODERATE | HIGH
    source: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "label": self.label, "class": self.evidence_class.value, "polarity": self.polarity,
                "strength": self.strength, "source": self.source, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class RuleOutcome:
    rule_id: str
    evidence_class: EvidenceClass
    outcome: str  # PASS | FAIL | UNKNOWN
    observed: float | None
    threshold: Threshold
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {"rule_id": self.rule_id, "class": self.evidence_class.value, "outcome": self.outcome,
                "observed": self.observed, "threshold": self.threshold.value, "operator": self.threshold.operator,
                "threshold_source": self.threshold.source, "source": self.source}


@dataclass(frozen=True, slots=True)
class SqueezeAssessment:
    state: SqueezeState
    trigger: str
    rules: tuple[RuleOutcome, ...]
    supporting: tuple[Evidence, ...]
    contradicting: tuple[Evidence, ...]
    context: tuple[Evidence, ...]
    missing: tuple[str, ...]
    mechanism_labels: tuple[str, ...]
    quality_flags: tuple[str, ...]
    classes_supporting: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": MODEL_ID, "adapted_from": DONOR_MODEL, "rule_policy": DONOR_POLICY,
            "state": self.state.value, "state_basis": "SNAPSHOT_ASSESSMENT", "trigger": self.trigger,
            "transition": None, "hysteresis": "NOT_APPLIED_NO_STATE_HISTORY",
            "lifecycle": [{"state": item.value, "current": item is self.state,
                           "reachable": item not in UNREACHABLE, "unreachable_reason": UNREACHABLE.get(item)}
                          for item in LIFECYCLE],
            "rules": [rule.to_dict() for rule in self.rules],
            "supporting": [item.to_dict() for item in self.supporting],
            "contradicting": [item.to_dict() for item in self.contradicting],
            "context": [item.to_dict() for item in self.context],
            "missing": list(self.missing), "mechanism_labels": list(self.mechanism_labels),
            "quality_flags": list(self.quality_flags), "classes_supporting": list(self.classes_supporting),
            "probability": None, "score": None,
        }


def _check(value: float | None, threshold: Threshold) -> str:
    if value is None:
        return "UNKNOWN"
    if threshold.operator == "gt":
        return "PASS" if value > threshold.value else "FAIL"
    if threshold.operator == "gte":
        return "PASS" if value >= threshold.value else "FAIL"
    return "PASS" if value <= threshold.value else "FAIL"


def order_flow_view(flow: OrderFlowInput | None) -> dict[str, Any]:
    """Aggressor dominance and CVD direction, or why they cannot be asserted."""

    if flow is None:
        return {"usable": False, "reason": "ORDER_FLOW_NOT_SUBSCRIBED"}
    if flow.state != "CURRENT":
        return {"usable": False, "reason": f"ORDER_FLOW_{flow.state}"}
    if flow.trade_count == 0:
        return {"usable": False, "reason": "ORDER_FLOW_AWAITING_DATA"}
    if flow.classified_volume_pct is None or flow.classified_volume_pct < MIN_CLASSIFIED_VOLUME_PCT:
        return {"usable": False, "reason": "ORDER_FLOW_AGGRESSOR_COVERAGE_LOW"}
    buy, sell = flow.buy_volume, flow.sell_volume
    return {
        "usable": True, "reason": None,
        "aggressive_buy": buy > sell * AGGRESSOR_DOMINANCE and buy > 0,
        "aggressive_sell": sell > buy * AGGRESSOR_DOMINANCE and sell > 0,
        "cvd_rising": flow.recent_delta is not None and flow.recent_delta > 0,
        "cvd_falling": flow.recent_delta is not None and flow.recent_delta < 0,
    }


def evaluate_snapshot(inputs: SqueezeInputs) -> SqueezeAssessment:
    """Evidence-gated state from one snapshot. Missing inputs stay missing."""

    supporting: list[Evidence] = []
    contradicting: list[Evidence] = []
    context: list[Evidence] = []
    missing: list[str] = []
    flags: list[str] = list(inputs.stale_inputs)

    # DTC: the FINRA publication when present, else Finviz's own short ratio.
    # The two are never merged; the rule records which one it read.
    dtc_value, dtc_source = ((inputs.official_days_to_cover, "FINRA") if inputs.official_days_to_cover is not None
                             else (inputs.short_ratio_days, "FINVIZ_SHORT_RATIO"))
    rules = (
        RuleOutcome("SHORT_FLOAT_ELEVATED", EvidenceClass.SHORT_CROWDING,
                    _check(inputs.short_float_pct, THRESHOLDS["SHORT_FLOAT_ELEVATED"]), inputs.short_float_pct,
                    THRESHOLDS["SHORT_FLOAT_ELEVATED"], "FINVIZ_ELITE"),
        RuleOutcome("DAYS_TO_COVER_MINIMUM", EvidenceClass.SHORT_CROWDING,
                    _check(dtc_value, THRESHOLDS["DAYS_TO_COVER_MINIMUM"]), dtc_value,
                    THRESHOLDS["DAYS_TO_COVER_MINIMUM"], dtc_source),
        RuleOutcome("SHORT_INTEREST_PERCENTAGE_CHANGE_MINIMUM", EvidenceClass.SHORT_CROWDING,
                    _check(inputs.official_short_interest_change_pct, THRESHOLDS["SHORT_INTEREST_PERCENTAGE_CHANGE_MINIMUM"]),
                    inputs.official_short_interest_change_pct, THRESHOLDS["SHORT_INTEREST_PERCENTAGE_CHANGE_MINIMUM"], "FINRA"),
        RuleOutcome("BORROW_FEE_MINIMUM", EvidenceClass.SECURITIES_LENDING,
                    _check(inputs.borrow_fee_pct, THRESHOLDS["BORROW_FEE_MINIMUM"]), inputs.borrow_fee_pct,
                    THRESHOLDS["BORROW_FEE_MINIMUM"], "LENDING"),
        RuleOutcome("BORROW_AVAILABILITY_MAXIMUM", EvidenceClass.SECURITIES_LENDING,
                    _check(inputs.borrow_available_shares, THRESHOLDS["BORROW_AVAILABILITY_MAXIMUM"]),
                    inputs.borrow_available_shares, THRESHOLDS["BORROW_AVAILABILITY_MAXIMUM"], "LENDING"),
        RuleOutcome("PERCENTAGE_CHANGE_MINIMUM", EvidenceClass.IGNITION,
                    _check(inputs.change_pct, THRESHOLDS["PERCENTAGE_CHANGE_MINIMUM"]), inputs.change_pct,
                    THRESHOLDS["PERCENTAGE_CHANGE_MINIMUM"], "FINVIZ_ELITE"),
        RuleOutcome("RELATIVE_VOLUME_MINIMUM", EvidenceClass.IGNITION,
                    _check(inputs.rel_volume, THRESHOLDS["RELATIVE_VOLUME_MINIMUM"]), inputs.rel_volume,
                    THRESHOLDS["RELATIVE_VOLUME_MINIMUM"], "FINVIZ_ELITE"),
    )
    outcome = {rule.rule_id: rule.outcome for rule in rules}

    # --- Structural pressure (donor SHORT_CROWDING + SECURITIES_LENDING) ---
    crowding = outcome["SHORT_FLOAT_ELEVATED"] == "PASS"
    dtc_pass = outcome["DAYS_TO_COVER_MINIMUM"] == "PASS"
    lending_pass = "PASS" in (outcome["BORROW_FEE_MINIMUM"], outcome["BORROW_AVAILABILITY_MAXIMUM"])
    # Donor ADAM pressure_critical: short interest plus one corroborating structural input.
    pressure_evaluable = inputs.short_float_pct is not None and any(
        value is not None for value in (dtc_value, inputs.borrow_fee_pct, inputs.borrow_available_shares, inputs.float_shares))
    if crowding:
        supporting.append(Evidence("SI_ELEVATED", "Elevated short interest (% of float)", EvidenceClass.SHORT_CROWDING,
                                   "SUPPORTS", "MODERATE", "FINVIZ_ELITE",
                                   f"Short float {inputs.short_float_pct:.2f}% > {THRESHOLDS['SHORT_FLOAT_ELEVATED'].value:g}%"))
    elif outcome["SHORT_FLOAT_ELEVATED"] == "UNKNOWN":
        missing.append("SHORT_FLOAT")
        flags.append("SHORT_INTEREST_UNKNOWN")
    if dtc_pass:
        supporting.append(Evidence("DAYS_TO_COVER", "Days to cover at or above 2", EvidenceClass.SHORT_CROWDING,
                                   "SUPPORTS", "MODERATE", dtc_source, f"{dtc_value:.2f} days ({dtc_source})"))
    if outcome["SHORT_INTEREST_PERCENTAGE_CHANGE_MINIMUM"] == "PASS":
        supporting.append(Evidence("SI_RISING", "Published short interest rising", EvidenceClass.SHORT_CROWDING,
                                   "SUPPORTS", "MODERATE", "FINRA",
                                   f"{inputs.official_short_interest_change_pct:+.1f}% vs prior settlement"))
    elif inputs.official_short_interest_change_pct is not None and inputs.official_short_interest_change_pct <= -10.0:
        contradicting.append(Evidence("SI_FALLING", "Published short interest falling", EvidenceClass.SHORT_CROWDING,
                                      "CONTRADICTS", "MODERATE", "FINRA",
                                      f"{inputs.official_short_interest_change_pct:+.1f}% vs prior settlement: less short fuel"))
    if not inputs.official_short_interest_available:
        missing.append("OFFICIAL_SHORT_INTEREST")
    if lending_pass:
        supporting.append(Evidence("LENDING_CONSTRAINT", "Securities-lending constraint", EvidenceClass.SECURITIES_LENDING,
                                   "SUPPORTS", "MODERATE", "LENDING", "Borrow fee or availability rule PASS"))
    if inputs.borrow_fee_pct is None and inputs.borrow_available_shares is None:
        # Donor: missing lending never becomes negative evidence.
        missing.append("BORROW")
    if inputs.float_shares is not None and _check(inputs.float_shares, THRESHOLDS["LOW_FLOAT"]) == "PASS":
        context.append(Evidence("LOW_FLOAT", "Small float", EvidenceClass.SHORT_CROWDING, "CONTEXT", "LOW", "FINVIZ_ELITE",
                                "Float at or below 50M shares; supply context, not squeeze evidence by itself"))
    if inputs.threshold_list_member:
        context.append(Evidence("THRESHOLD_LIST", "On a Reg SHO threshold list", EvidenceClass.REGULATORY_CONTEXT,
                                "CONTEXT", "LOW", "REG_SHO",
                                "Persistent settlement fails at a clearing agency; not short interest and not a forced-cover countdown"))

    # --- Ignition (donor MOMENTUM_DISCOVERY rules + CATALYST_EVIDENCE) ---
    ignition_evaluable = inputs.change_pct is not None and inputs.rel_volume is not None
    ignition = outcome["PERCENTAGE_CHANGE_MINIMUM"] == "PASS" and outcome["RELATIVE_VOLUME_MINIMUM"] == "PASS"
    if not ignition_evaluable:
        missing.append("IGNITION_INPUTS")
    if ignition:
        supporting.append(Evidence("PRICE_RVOL_IGNITION", "Price and relative-volume ignition", EvidenceClass.IGNITION,
                                   "SUPPORTS", "HIGH" if inputs.change_pct >= 20 else "MODERATE", "FINVIZ_ELITE",
                                   f"Change {inputs.change_pct:+.2f}% and RVOL {inputs.rel_volume:.2f}×"))
    if inputs.catalyst_present:
        supporting.append(Evidence("CATALYST_PRESENT", "Current headline present", EvidenceClass.CATALYST, "SUPPORTS",
                                   "LOW", "FINVIZ_NEWS", "A headline for this symbol in the current move window; not a cause"))
    elif inputs.catalyst_present is None:
        missing.append("CATALYST")
    if crowding and inputs.rel_volume is not None and _check(inputs.rel_volume, THRESHOLDS["VOLUME_PARTICIPATION"]) == "FAIL":
        contradicting.append(Evidence("NO_VOLUME_PARTICIPATION", "Short pressure without volume participation",
                                      EvidenceClass.IGNITION, "CONTRADICTS", "MODERATE", "FINVIZ_ELITE",
                                      f"RVOL {inputs.rel_volume:.2f}× is not above 1.5×: structure without demand"))

    # --- Live confirmation (donor ORDER_FLOW; reflexivity proxy) ---
    flow = order_flow_view(inputs.order_flow)
    if not flow["usable"]:
        missing.append("ORDER_FLOW")
        flags.append(flow["reason"])
    else:
        if flow["aggressive_buy"]:
            supporting.append(Evidence("CVD_AGGRESSIVE_BUY", "Buy-aggressor volume dominates", EvidenceClass.ORDER_FLOW,
                                       "SUPPORTS", "MODERATE", "MOOMOO_TRADES",
                                       f"Buy {inputs.order_flow.buy_volume:,.0f} vs sell {inputs.order_flow.sell_volume:,.0f} classified shares"))
        if flow["aggressive_sell"]:
            contradicting.append(Evidence("CVD_AGGRESSIVE_SELL", "Sell-aggressor volume dominates", EvidenceClass.ORDER_FLOW,
                                          "CONTRADICTS", "MODERATE", "MOOMOO_TRADES",
                                          "Selling pressure weakens a covering interpretation"))
        if flow["cvd_falling"] and (ignition or (inputs.change_pct or 0) > 0):
            contradicting.append(Evidence("CVD_DIVERGENCE", "CVD falling while price is up", EvidenceClass.ORDER_FLOW,
                                          "CONTRADICTS", "MODERATE", "MOOMOO_TRADES",
                                          "Negative recent delta weakens live confirmation"))
        if flow["aggressive_buy"] and flow["cvd_falling"]:
            # Donor exhaustion input (aggressive buy + negative CVD slope). It adds
            # 45 risk points in the donor; 70 is needed for EXHAUSTION, and the
            # remaining inputs need history, so this stays evidence, not a state.
            contradicting.append(Evidence("EXHAUSTION_SIGNAL", "Buying aggression with falling CVD", EvidenceClass.ORDER_FLOW,
                                          "CONTRADICTS", "MODERATE", "MOOMOO_TRADES",
                                          "Single-snapshot exhaustion input; exhaustion itself needs history"))
    if not inputs.dealer_positioning_available:
        missing.append("DEALER_POSITIONING")

    # --- Fail-closed gate (donor _unevaluable_result) ---
    if inputs.provider_conflict:
        return _result(SqueezeState.UNEVALUABLE, "provider_conflict", rules, supporting, contradicting, context, missing,
                       ("UNKNOWN",), flags + ["CAPABILITY_CONFLICTED"])
    if not pressure_evaluable and not ignition_evaluable:
        return _result(SqueezeState.UNEVALUABLE, "insufficient_evidence", rules, supporting, contradicting, context,
                       missing, ("UNKNOWN",), flags + ["CAPABILITY_UNAVAILABLE"])

    # --- State cascade (donor order; each state needs more than one evidence class) ---
    vulnerable = pressure_evaluable and crowding
    mechanisms: list[str] = []
    live_buy = bool(flow["usable"] and flow["aggressive_buy"])
    state, trigger = SqueezeState.BASELINE, "default_baseline"
    if ignition and live_buy:
        state, trigger = SqueezeState.LIVE_CONFIRMATION, "live_order_flow_confirmation"
    elif ignition:
        state, trigger = SqueezeState.IGNITION_WATCH, "price_and_volume_ignition"
    elif vulnerable and (dtc_pass or lending_pass):
        state, trigger = SqueezeState.ARMED, "structural_pressure_with_constraint"
    elif vulnerable:
        state, trigger = SqueezeState.VULNERABLE, "latent_short_pressure_structure"
    if state in (SqueezeState.IGNITION_WATCH, SqueezeState.LIVE_CONFIRMATION):
        if vulnerable:
            mechanisms.append("MARKET_SQUEEZE")
        else:
            # Donor LOW_STRUCTURAL_FUEL: strong ignition without structural fuel.
            mechanisms.append("NON_SQUEEZE_MOMENTUM")
            contradicting.append(Evidence("LOW_STRUCTURAL_FUEL", "Ignition without structural short pressure",
                                          EvidenceClass.SHORT_CROWDING, "CONTRADICTS", "HIGH", "SQUEEZE_EVALUATOR",
                                          "May be a momentum move rather than a short squeeze"))
    if lending_pass:
        mechanisms.append("LENDER_SQUEEZE")
    return _result(state, trigger, rules, supporting, contradicting, context, missing,
                   tuple(mechanisms) or ("UNKNOWN",), flags)


def _result(state: SqueezeState, trigger: str, rules: tuple[RuleOutcome, ...], supporting: list[Evidence],
            contradicting: list[Evidence], context: list[Evidence], missing: list[str], mechanisms: tuple[str, ...],
            flags: list[str]) -> SqueezeAssessment:
    return SqueezeAssessment(
        state=state, trigger=trigger, rules=rules, supporting=tuple(supporting), contradicting=tuple(contradicting),
        context=tuple(context), missing=tuple(dict.fromkeys(missing)), mechanism_labels=mechanisms,
        quality_flags=tuple(dict.fromkeys(flags)),
        classes_supporting=tuple(dict.fromkeys(item.evidence_class.value for item in supporting)),
    )


__all__ = ["AGGRESSOR_DOMINANCE", "DONOR_MODEL", "EvidenceClass", "LIFECYCLE", "MODEL_ID", "OrderFlowInput",
           "SqueezeAssessment", "SqueezeInputs", "SqueezeState", "THRESHOLDS", "UNREACHABLE", "evaluate_snapshot",
           "order_flow_view"]
