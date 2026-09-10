"""News intelligence strategy evaluation laboratory — non-executable research."""

from .config import EvaluationConfig, verify_evaluation_config
from .contracts import (
    EVALUATION_SCHEMA_VERSION,
    EvaluationDecision,
    EvaluationReport,
    EvaluationRunRecord,
    EvaluationShadowRecord,
    StrategyEvaluationDecision,
    StrategyFeatureSnapshot,
)
from .evaluator import NewsStrategyEvaluator
from .policies import PolicyRegistry
from .replay import EvaluationReplayHarness

__all__ = [
    "EVALUATION_SCHEMA_VERSION",
    "EvaluationConfig",
    "EvaluationDecision",
    "EvaluationReplayHarness",
    "EvaluationReport",
    "EvaluationRunRecord",
    "EvaluationShadowRecord",
    "NewsStrategyEvaluator",
    "PolicyRegistry",
    "StrategyEvaluationDecision",
    "StrategyFeatureSnapshot",
    "verify_evaluation_config",
]
