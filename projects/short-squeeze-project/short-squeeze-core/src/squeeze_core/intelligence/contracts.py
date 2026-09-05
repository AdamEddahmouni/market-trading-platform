"""Contracts for causal short-squeeze intelligence outputs.

These types separate observations, derived dimensions, state, and research-only
predictions. No field implies calibrated probability unless ``status`` is
``CALIBRATED``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class SqueezeState(StrEnum):
    BASELINE = "BASELINE"
    VULNERABLE = "VULNERABLE"
    ARMED = "ARMED"
    IGNITION_WATCH = "IGNITION_WATCH"
    LIVE_CONFIRMATION = "LIVE_CONFIRMATION"
    ACTIVE_SQUEEZE = "ACTIVE_SQUEEZE"
    EXHAUSTION = "EXHAUSTION"
    POST_SQUEEZE = "POST_SQUEEZE"
    UNEVALUABLE = "UNEVALUABLE"


class MechanismLabel(StrEnum):
    MARKET_SQUEEZE = "MARKET_SQUEEZE"
    LENDER_SQUEEZE = "LENDER_SQUEEZE"
    GAMMA_AMPLIFIED = "GAMMA_AMPLIFIED"
    ATTENTION_AMPLIFIED = "ATTENTION_AMPLIFIED"
    COMBINED_REFLEXIVE = "COMBINED_REFLEXIVE"
    NON_SQUEEZE_MOMENTUM = "NON_SQUEEZE_MOMENTUM"
    UNKNOWN = "UNKNOWN"


class CausalDimension(StrEnum):
    SHORT_CROWDING = "SHORT_CROWDING"
    SECURITIES_LENDING = "SECURITIES_LENDING"
    SHORT_STRESS = "SHORT_STRESS"
    LIQUIDITY_SUPPLY = "LIQUIDITY_SUPPLY"
    CATALYST = "CATALYST"
    ATTENTION = "ATTENTION"
    ORDER_FLOW = "ORDER_FLOW"
    OPTIONS_AMPLIFICATION = "OPTIONS_AMPLIFICATION"
    REFLEXIVITY = "REFLEXIVITY"
    REMAINING_FUEL = "REMAINING_FUEL"
    EXHAUSTION = "EXHAUSTION"


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    code: str
    label: str
    dimension: CausalDimension
    polarity: str  # SUPPORTS | CONTRADICTS | NEUTRAL
    strength: str  # LOW | MODERATE | HIGH
    source: str
    detail: str
    available: bool = True


@dataclass(frozen=True, slots=True)
class HorizonProbability:
    horizon_days: int
    value: float | None
    status: str  # UNAVAILABLE | RESEARCH_ONLY | CALIBRATED
    note: str


@dataclass(frozen=True, slots=True)
class MagnitudeEstimateSnapshot:
    expected_move_pct: float | None
    upside_tail_pct: float | None
    status: str
    method: str
    model_version: str


@dataclass(frozen=True, slots=True)
class HorizonModelSnapshot:
    """Walk-forward validated model outputs for horizon probability slots."""

    model_version: str
    status: str  # RESEARCH_ONLY | CALIBRATED
    pit_verified: bool = False
    occurrence_probability: float | None = None
    hazard_by_horizon: tuple[tuple[int, float], ...] = ()
    magnitude: MagnitudeEstimateSnapshot | None = None


@dataclass(frozen=True, slots=True)
class SqueezeExplanation:
    summary: str
    nodes: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class SqueezeIntelligenceResult:
    model_version: str
    state: SqueezeState
    previous_state: SqueezeState | None
    state_confidence: str  # LOW | MEDIUM | HIGH
    mechanism_labels: tuple[MechanismLabel, ...]
    vulnerability: float | None
    constraint_pressure: float | None
    short_stress: float | None
    ignition_strength: float | None
    reflexivity_strength: float | None
    remaining_fuel: float | None
    exhaustion_risk: float | None
    market_squeeze_mechanism_score: float | None
    lender_squeeze_mechanism_score: float | None
    horizon_probabilities: tuple[HorizonProbability, ...]
    model_confidence: str
    data_confidence: str
    overall_confidence: str
    quality_flags: tuple[str, ...]
    missing_capabilities: tuple[str, ...]
    supporting_evidence: tuple[EvidenceItem, ...]
    contradicting_evidence: tuple[EvidenceItem, ...]
    explanation: SqueezeExplanation
    research_status: str  # IMPLEMENTED | EXPERIMENTAL | RESEARCH_ONLY
    transition: dict[str, Any] = field(default_factory=dict)
