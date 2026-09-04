"""SHARED P4 opportunity fusion contracts — probability × payoff × costs × liquidity."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

OPPORTUNITY_VERSION = "shared_opportunity_v1"
FUSION_METHOD = "CROSS_LANE_FUSION_V1"

OpportunityOutcome = Literal["RANKED", "NO_ACTIONABLE_EDGE", "UNAVAILABLE"]
OpportunityStatus = Literal["RANKED", "NO_ACTIONABLE_EDGE", "UNAVAILABLE"]


class OpportunityQualityFlag(StrEnum):
    STRATEGY_INPUTS_INCOMPLETE = "OPPORTUNITY_STRATEGY_INPUTS_INCOMPLETE"
    PAYOFF_UNAVAILABLE = "OPPORTUNITY_PAYOFF_UNAVAILABLE"
    LIQUIDITY_BLOCKED = "OPPORTUNITY_LIQUIDITY_BLOCKED"
    PHYSICAL_P_UNAVAILABLE = "OPPORTUNITY_PHYSICAL_P_UNAVAILABLE"
    FUSION_INPUTS_INCOMPLETE = "OPPORTUNITY_FUSION_INPUTS_INCOMPLETE"


SQUEEZE_ALIGNED_TEMPLATES = frozenset(
    {
        "long_call_atm",
        "bull_call_spread",
        "long_otm_call",
    }
)

FUTURES_REGIME_TEMPLATES = frozenset(
    {
        "calendar_spread",
        "outright_trend_long",
        "outright_trend_short",
    }
)


@dataclass(frozen=True, slots=True)
class ProbabilityInput:
    """Cross-lane probability components — occurrence vs scenario win-rate kept separate."""

    available: bool
    squeeze_occurrence_probability: float | None = None
    squeeze_hazard_probability: float | None = None
    scenario_win_probability: float | None = None
    physical_upside_tail_probability: float | None = None
    physical_downside_tail_probability: float | None = None
    squeeze_state: str | None = None
    source_ref: str = "cross_lane:probability"
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class PayoffInput:
    """Options strategy payoff decomposition — gross expected P&L under physical P."""

    available: bool
    expected_pnl: float | None = None
    net_expected_pnl: float | None = None
    template: str | None = None
    edge_alignment: str | None = None
    max_loss: float | None = None
    max_gain: float | None = None
    source_ref: str = "options:strategy"
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class CostInput:
    """Explicit cost decomposition — friction and entry outlay."""

    available: bool
    friction_cost: float | None = None
    entry_cost: float | None = None
    execution_fill_cost: float | None = None
    source_ref: str = "options:payoff"
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class FuturesInput:
    """Futures outright/curve regime modifiers for SHARED P4 fusion."""

    available: bool
    carry_percentile: float | None = None
    rv_spread_zscore: float | None = None
    trend_regime: str | None = None
    leverage_stress_regime: str | None = None
    macro_event_risk: bool = False
    curve_regime: str | None = None
    source_ref: str = "futures:workspace"
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class LiquidityInput:
    """Liquidity gates and order-flow confidence for execution conditioning."""

    available: bool
    gates_passed: bool = False
    cvd_confidence: float | None = None
    book_imbalance_supports_trade: bool = False
    book_imbalance_opposes_trade: bool = False
    depth_withdrawal: float | None = None
    depth_replenishment: float | None = None
    fragility_score: float | None = None
    resiliency_score: float | None = None
    book_fragility_elevated: bool = False
    absorption_score: float | None = None
    exhaustion_score: float | None = None
    continuation_probability: float | None = None
    reversal_probability: float | None = None
    microstructure_direction_bias: str | None = None
    fill_probability: float | None = None
    expected_slippage_spread_fraction: float | None = None
    adverse_selection_risk: float | None = None
    liquidity_quality: str | None = None
    source_ref: str = "cross_lane:liquidity"
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class FusedOpportunity:
    """Decomposed fusion output — no opaque universal score."""

    fused_net_ev: float
    occurrence_weight: float
    liquidity_factor: float
    gross_ev_before_weights: float
    template: str | None
    squeeze_aligned: bool


def probability_input_to_dict(item: ProbabilityInput) -> dict[str, Any]:
    return {
        "available": item.available,
        "squeeze_occurrence_probability": item.squeeze_occurrence_probability,
        "squeeze_hazard_probability": item.squeeze_hazard_probability,
        "scenario_win_probability": item.scenario_win_probability,
        "physical_upside_tail_probability": item.physical_upside_tail_probability,
        "physical_downside_tail_probability": item.physical_downside_tail_probability,
        "squeeze_state": item.squeeze_state,
        "source_ref": item.source_ref,
        "quality_flags": list(item.quality_flags),
        "reason": item.reason,
    }


def payoff_input_to_dict(item: PayoffInput) -> dict[str, Any]:
    return {
        "available": item.available,
        "expected_pnl": item.expected_pnl,
        "net_expected_pnl": item.net_expected_pnl,
        "template": item.template,
        "edge_alignment": item.edge_alignment,
        "max_loss": item.max_loss,
        "max_gain": item.max_gain,
        "source_ref": item.source_ref,
        "quality_flags": list(item.quality_flags),
        "reason": item.reason,
    }


def cost_input_to_dict(item: CostInput) -> dict[str, Any]:
    return {
        "available": item.available,
        "friction_cost": item.friction_cost,
        "entry_cost": item.entry_cost,
        "execution_fill_cost": item.execution_fill_cost,
        "source_ref": item.source_ref,
        "quality_flags": list(item.quality_flags),
        "reason": item.reason,
    }


def futures_input_to_dict(item: FuturesInput) -> dict[str, Any]:
    return {
        "available": item.available,
        "carry_percentile": item.carry_percentile,
        "rv_spread_zscore": item.rv_spread_zscore,
        "trend_regime": item.trend_regime,
        "leverage_stress_regime": item.leverage_stress_regime,
        "macro_event_risk": item.macro_event_risk,
        "curve_regime": item.curve_regime,
        "source_ref": item.source_ref,
        "quality_flags": list(item.quality_flags),
        "reason": item.reason,
    }


def liquidity_input_to_dict(item: LiquidityInput) -> dict[str, Any]:
    return {
        "available": item.available,
        "gates_passed": item.gates_passed,
        "cvd_confidence": item.cvd_confidence,
        "book_imbalance_supports_trade": item.book_imbalance_supports_trade,
        "book_imbalance_opposes_trade": item.book_imbalance_opposes_trade,
        "depth_withdrawal": item.depth_withdrawal,
        "depth_replenishment": item.depth_replenishment,
        "fragility_score": item.fragility_score,
        "resiliency_score": item.resiliency_score,
        "book_fragility_elevated": item.book_fragility_elevated,
        "absorption_score": item.absorption_score,
        "exhaustion_score": item.exhaustion_score,
        "continuation_probability": item.continuation_probability,
        "reversal_probability": item.reversal_probability,
        "microstructure_direction_bias": item.microstructure_direction_bias,
        "fill_probability": item.fill_probability,
        "expected_slippage_spread_fraction": item.expected_slippage_spread_fraction,
        "adverse_selection_risk": item.adverse_selection_risk,
        "liquidity_quality": item.liquidity_quality,
        "source_ref": item.source_ref,
        "quality_flags": list(item.quality_flags),
        "reason": item.reason,
    }


def fused_opportunity_to_dict(item: FusedOpportunity) -> dict[str, Any]:
    return {
        "fused_net_ev": round(item.fused_net_ev, 6),
        "occurrence_weight": round(item.occurrence_weight, 6),
        "liquidity_factor": round(item.liquidity_factor, 6),
        "gross_ev_before_weights": round(item.gross_ev_before_weights, 6),
        "template": item.template,
        "squeeze_aligned": item.squeeze_aligned,
    }


__all__ = [
    "CostInput",
    "FUTURES_REGIME_TEMPLATES",
    "FUSION_METHOD",
    "FusedOpportunity",
    "FuturesInput",
    "LiquidityInput",
    "OPPORTUNITY_VERSION",
    "OpportunityOutcome",
    "OpportunityQualityFlag",
    "OpportunityStatus",
    "PayoffInput",
    "ProbabilityInput",
    "SQUEEZE_ALIGNED_TEMPLATES",
    "cost_input_to_dict",
    "fused_opportunity_to_dict",
    "futures_input_to_dict",
    "liquidity_input_to_dict",
    "payoff_input_to_dict",
    "probability_input_to_dict",
]
