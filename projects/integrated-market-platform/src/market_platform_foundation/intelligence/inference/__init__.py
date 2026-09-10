"""Canonical news intelligence inference boundary — analysis only, zero execution authority."""

from .analyzer import NewsIntelligenceAnalyzer
from .config import IntelligenceInferenceConfig, verify_inference_config
from .contracts import (
    ConfidenceKind,
    ImpactHorizon,
    InferenceFailure,
    InferenceRecord,
    InferenceStatus,
    IntelligenceInputPacket,
    IntelligenceResult,
    IntelligenceTaskType,
    MarketImpactLevel,
    ParsingStatus,
    SentimentLabel,
)
from .errors import InferenceErrorCode
from .prompts import PromptRegistry
from .provider import FixtureInferenceProvider, InferenceProvider
from .records import InMemoryInferenceRecordRepository
from .replay import IntelligenceReplayHarness

__all__ = [
    "ConfidenceKind",
    "FixtureInferenceProvider",
    "ImpactHorizon",
    "InferenceErrorCode",
    "InferenceFailure",
    "InferenceProvider",
    "InferenceRecord",
    "InferenceStatus",
    "InMemoryInferenceRecordRepository",
    "IntelligenceInferenceConfig",
    "IntelligenceInputPacket",
    "IntelligenceReplayHarness",
    "IntelligenceResult",
    "IntelligenceTaskType",
    "MarketImpactLevel",
    "NewsIntelligenceAnalyzer",
    "ParsingStatus",
    "PromptRegistry",
    "SentimentLabel",
    "verify_inference_config",
]
