"""Versioned strategy policy registry — deterministic mapping only."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contracts import (
    EvaluationDecision,
    PolicyClassification,
    StrategyFeatureSnapshot,
)
from .errors import EvaluationError, EvaluationErrorCode
from .hashing import evaluation_config_hash


@dataclass(frozen=True, slots=True)
class StrategyPolicyDefinition:
    policy_id: str
    version: str
    description: str
    classification: PolicyClassification
    required_features: frozenset[str]
    configuration: dict[str, Any]
    comparable_baseline_for: str = ""

    def config_hash(self) -> str:
        return evaluation_config_hash(
            {
                "policy_id": self.policy_id,
                "version": self.version,
                "configuration": self.configuration,
            }
        )


def _baseline_decision(snapshot: StrategyFeatureSnapshot, config: dict[str, Any]) -> EvaluationDecision:
    min_catalysts = int(config.get("min_catalyst_count", 1))
    max_age = int(config.get("max_event_age_seconds", 7200))
    bullish_catalysts = frozenset(config.get("bullish_catalyst_ids", ("cpi", "payroll", "rate_decision")))
    bearish_catalysts = frozenset(config.get("bearish_catalyst_ids", ("inventory",)))

    if snapshot.deterministic.event_count < min_catalysts:
        return EvaluationDecision.NEUTRAL

    age = snapshot.deterministic.youngest_event_age_seconds
    if age is not None and age > max_age:
        return EvaluationDecision.NEUTRAL

    catalysts = set(snapshot.deterministic.catalyst_ids)
    if catalysts & bullish_catalysts:
        return EvaluationDecision.POSITIVE_DIRECTIONAL_BIAS
    if catalysts & bearish_catalysts:
        return EvaluationDecision.NEGATIVE_DIRECTIONAL_BIAS
    return EvaluationDecision.NEUTRAL


def _enhanced_decision(snapshot: StrategyFeatureSnapshot, config: dict[str, Any]) -> EvaluationDecision:
    baseline = _baseline_decision(snapshot, config.get("baseline_config", {}))
    if snapshot.intelligence is None:
        return baseline

    min_confidence = float(config.get("min_model_confidence", 0.0))
    confidence = snapshot.intelligence.model_confidence
    if confidence is not None and confidence < min_confidence:
        return baseline

    sentiment = (snapshot.intelligence.sentiment_label or "").upper()
    impact = (snapshot.intelligence.market_impact_level or "").upper()

    if sentiment in {"VERY_BULLISH", "BULLISH"} and impact in {"MODERATE", "HIGH"}:
        if baseline == EvaluationDecision.NEGATIVE_DIRECTIONAL_BIAS:
            return EvaluationDecision.NEUTRAL
        return EvaluationDecision.POSITIVE_DIRECTIONAL_BIAS
    if sentiment in {"VERY_BEARISH", "BEARISH"} and impact in {"MODERATE", "HIGH"}:
        if baseline == EvaluationDecision.POSITIVE_DIRECTIONAL_BIAS:
            return EvaluationDecision.NEUTRAL
        return EvaluationDecision.NEGATIVE_DIRECTIONAL_BIAS
    if sentiment == "NEUTRAL" or impact in {"NONE", "LOW"}:
        return EvaluationDecision.NEUTRAL
    return baseline


def _naive_decision(_snapshot: StrategyFeatureSnapshot, _config: dict[str, Any]) -> EvaluationDecision:
    return EvaluationDecision.NEUTRAL


_POLICY_HANDLERS = {
    "news_deterministic_baseline": _baseline_decision,
    "news_ai_enhanced": _enhanced_decision,
    "news_naive_reference": _naive_decision,
}


DEFAULT_POLICIES: tuple[StrategyPolicyDefinition, ...] = (
    StrategyPolicyDefinition(
        policy_id="news_deterministic_baseline",
        version="1.0.0",
        description="Deterministic catalyst/recency/source policy without AI features.",
        classification=PolicyClassification.BASELINE_DETERMINISTIC,
        required_features=frozenset({"deterministic_news", "market"}),
        configuration={
            "min_catalyst_count": 1,
            "max_event_age_seconds": 7200,
            "bullish_catalyst_ids": ["cpi", "payroll", "rate_decision", "earnings", "guidance"],
            "bearish_catalyst_ids": ["inventory", "bankruptcy", "investigation"],
        },
    ),
    StrategyPolicyDefinition(
        policy_id="news_ai_enhanced",
        version="1.0.0",
        description="Same deterministic core plus governed intelligence sentiment/impact features.",
        classification=PolicyClassification.AI_ENHANCED,
        required_features=frozenset({"deterministic_news", "market", "intelligence"}),
        configuration={
            "min_model_confidence": 0.5,
            "baseline_config": {
                "min_catalyst_count": 1,
                "max_event_age_seconds": 7200,
                "bullish_catalyst_ids": ["cpi", "payroll", "rate_decision", "earnings", "guidance"],
                "bearish_catalyst_ids": ["inventory", "bankruptcy", "investigation"],
            },
        },
        comparable_baseline_for="news_deterministic_baseline",
    ),
    StrategyPolicyDefinition(
        policy_id="news_naive_reference",
        version="1.0.0",
        description="Always abstain — contextual no-action reference.",
        classification=PolicyClassification.BASELINE_NAIVE,
        required_features=frozenset(),
        configuration={},
    ),
)


class PolicyRegistry:
    VERSION = "intelligence/news_strategy_evaluation/policies/1.0.0"

    def __init__(self, policies: tuple[StrategyPolicyDefinition, ...] | None = None) -> None:
        self._policies = policies or DEFAULT_POLICIES
        self._index = {(p.policy_id, p.version): p for p in self._policies}

    def get(self, policy_id: str, version: str) -> StrategyPolicyDefinition:
        key = (policy_id, version)
        if key not in self._index:
            raise EvaluationError(EvaluationErrorCode.POLICY_UNKNOWN, f"unknown policy {policy_id}@{version}")
        return self._index[key]

    def evaluate(
        self,
        policy: StrategyPolicyDefinition,
        snapshot: StrategyFeatureSnapshot,
    ) -> EvaluationDecision:
        handler = _POLICY_HANDLERS.get(policy.policy_id)
        if handler is None:
            raise EvaluationError(EvaluationErrorCode.POLICY_UNKNOWN, policy.policy_id)
        if policy.classification == PolicyClassification.AI_ENHANCED and snapshot.intelligence is None:
            if "intelligence" in policy.required_features:
                baseline_policy = self.get(
                    policy.comparable_baseline_for or "news_deterministic_baseline",
                    policy.version,
                )
                return _baseline_decision(snapshot, baseline_policy.configuration)
        return handler(snapshot, policy.configuration)


def decision_to_units(decision: EvaluationDecision) -> int:
    if decision == EvaluationDecision.POSITIVE_DIRECTIONAL_BIAS:
        return 1
    if decision == EvaluationDecision.NEGATIVE_DIRECTIONAL_BIAS:
        return -1
    return 0


__all__ = [
    "DEFAULT_POLICIES",
    "PolicyRegistry",
    "StrategyPolicyDefinition",
    "decision_to_units",
]
