"""Causal short-squeeze intelligence — states, evidence, and explainable outputs."""

from .contracts import (
    CausalDimension,
    EvidenceItem,
    HorizonProbability,
    MechanismLabel,
    SqueezeExplanation,
    SqueezeIntelligenceResult,
    SqueezeState,
)
from .evaluator import evaluate_squeeze_intelligence
from .explanation import build_explanation_graph

__all__ = [
    "CausalDimension",
    "EvidenceItem",
    "HorizonProbability",
    "MechanismLabel",
    "SqueezeExplanation",
    "SqueezeIntelligenceResult",
    "SqueezeState",
    "build_explanation_graph",
    "evaluate_squeeze_intelligence",
]
