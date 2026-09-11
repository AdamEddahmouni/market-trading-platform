"""Structured contracts for curated news intelligence — analysis only."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


INFERENCE_SCHEMA_VERSION = "intelligence/inference/1.0.0"


class IntelligenceTaskType(StrEnum):
    NEWS_SENTIMENT = "NEWS_SENTIMENT"
    NEWS_CATALYST_ANALYSIS = "NEWS_CATALYST_ANALYSIS"
    NEWS_MARKET_IMPACT = "NEWS_MARKET_IMPACT"


class SentimentLabel(StrEnum):
    VERY_BEARISH = "VERY_BEARISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    BULLISH = "BULLISH"
    VERY_BULLISH = "VERY_BULLISH"


class MarketImpactLevel(StrEnum):
    NONE = "NONE"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"


class ImpactHorizon(StrEnum):
    INTRADAY = "INTRADAY"
    SHORT_TERM = "SHORT_TERM"
    MEDIUM_TERM = "MEDIUM_TERM"
    UNKNOWN = "UNKNOWN"


class ConfidenceKind(StrEnum):
    """Model-reported confidence is not empirically calibrated."""

    MODEL_REPORTED_CONFIDENCE = "MODEL_REPORTED_CONFIDENCE"


class ParsingStatus(StrEnum):
    VALID = "VALID"
    MALFORMED = "MALFORMED"
    MISSING_FIELDS = "MISSING_FIELDS"
    INVALID_ENUM = "INVALID_ENUM"
    SCORE_OUT_OF_RANGE = "SCORE_OUT_OF_RANGE"
    UNSUPPORTED_SCHEMA = "UNSUPPORTED_SCHEMA"
    PROVIDER_REFUSAL = "PROVIDER_REFUSAL"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    TIMEOUT = "TIMEOUT"


class InferenceStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class ArticleInputRef:
    event_id: str
    source_id: str
    provider_id: str
    published_time: str
    retrieved_time: str
    headline: str
    summary: str = ""
    instrument_ids: tuple[str, ...] = ()
    asset_classes: tuple[str, ...] = ()
    deterministic_catalyst_ids: tuple[str, ...] = ()
    source_trust_tier: str = ""
    publication_time_quality: str = ""


@dataclass(frozen=True, slots=True)
class IntelligenceInputPacket:
    """Self-contained curated input for model inference — no external retrieval."""

    input_id: str
    task_type: IntelligenceTaskType
    as_of: str
    articles: tuple[ArticleInputRef, ...]
    instrument_ids: tuple[str, ...]
    prompt_id: str
    prompt_version: str
    prompt_hash: str
    output_schema_version: str
    model_policy_id: str
    source_policy_version: str = ""
    catalyst_policy_version: str = ""
    filter_chain_version: str = ""
    candidate_article_count: int = 0
    supplied_article_count: int = 0
    truncated: bool = False
    truncation_reason: str = ""
    input_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_id": self.input_id,
            "task_type": self.task_type.value,
            "as_of": self.as_of,
            "articles": [
                {
                    "event_id": article.event_id,
                    "source_id": article.source_id,
                    "provider_id": article.provider_id,
                    "published_time": article.published_time,
                    "retrieved_time": article.retrieved_time,
                    "headline": article.headline,
                    "summary": article.summary,
                    "instrument_ids": list(article.instrument_ids),
                    "asset_classes": list(article.asset_classes),
                    "deterministic_catalyst_ids": list(article.deterministic_catalyst_ids),
                    "source_trust_tier": article.source_trust_tier,
                    "publication_time_quality": article.publication_time_quality,
                }
                for article in self.articles
            ],
            "instrument_ids": list(self.instrument_ids),
            "prompt_id": self.prompt_id,
            "prompt_version": self.prompt_version,
            "prompt_hash": self.prompt_hash,
            "output_schema_version": self.output_schema_version,
            "model_policy_id": self.model_policy_id,
            "source_policy_version": self.source_policy_version,
            "catalyst_policy_version": self.catalyst_policy_version,
            "filter_chain_version": self.filter_chain_version,
            "candidate_article_count": self.candidate_article_count,
            "supplied_article_count": self.supplied_article_count,
            "truncated": self.truncated,
            "truncation_reason": self.truncation_reason,
            "input_hash": self.input_hash,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class StructuredIntelligenceOutput:
    sentiment_label: SentimentLabel | None = None
    sentiment_score: float | None = None
    catalyst_interpretation: str = ""
    catalyst_strength: str = ""
    market_impact_level: MarketImpactLevel | None = None
    impact_horizon: ImpactHorizon | None = None
    rationale: str = ""
    model_confidence: float | None = None
    confidence_kind: ConfidenceKind = ConfidenceKind.MODEL_REPORTED_CONFIDENCE
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "sentiment_label": self.sentiment_label.value if self.sentiment_label else None,
            "sentiment_score": self.sentiment_score,
            "catalyst_interpretation": self.catalyst_interpretation,
            "catalyst_strength": self.catalyst_strength,
            "market_impact_level": (
                self.market_impact_level.value if self.market_impact_level else None
            ),
            "impact_horizon": self.impact_horizon.value if self.impact_horizon else None,
            "rationale": self.rationale,
            "model_confidence": self.model_confidence,
            "confidence_kind": self.confidence_kind.value,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class IntelligenceResult:
    result_id: str
    input_id: str
    status: InferenceStatus
    task_type: IntelligenceTaskType
    as_of: str
    output: StructuredIntelligenceOutput | None = None
    parsing_status: ParsingStatus = ParsingStatus.VALID
    provider_id: str = ""
    model_id: str = ""
    prompt_id: str = ""
    prompt_version: str = ""
    prompt_hash: str = ""
    input_hash: str = ""
    inference_config_hash: str = ""
    requested_time: str = ""
    completed_time: str = ""
    source_event_ids: tuple[str, ...] = ()
    instrument_ids: tuple[str, ...] = ()
    tokens_input: int | None = None
    tokens_output: int | None = None
    latency_ms: int | None = None
    raw_response_hash: str = ""
    provider_request_id: str = ""
    provider_response_id: str = ""
    schema_version: str = INFERENCE_SCHEMA_VERSION
    read_only: bool = True
    execution_authority: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "input_id": self.input_id,
            "status": self.status.value,
            "task_type": self.task_type.value,
            "as_of": self.as_of,
            "output": self.output.to_dict() if self.output else None,
            "parsing_status": self.parsing_status.value,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "prompt_id": self.prompt_id,
            "prompt_version": self.prompt_version,
            "prompt_hash": self.prompt_hash,
            "input_hash": self.input_hash,
            "inference_config_hash": self.inference_config_hash,
            "requested_time": self.requested_time,
            "completed_time": self.completed_time,
            "source_event_ids": list(self.source_event_ids),
            "instrument_ids": list(self.instrument_ids),
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "latency_ms": self.latency_ms,
            "raw_response_hash": self.raw_response_hash,
            "provider_request_id": self.provider_request_id,
            "provider_response_id": self.provider_response_id,
            "schema_version": self.schema_version,
            "read_only": self.read_only,
            "execution_authority": self.execution_authority,
        }


@dataclass(frozen=True, slots=True)
class InferenceFailure:
    failure_id: str
    input_id: str
    error_code: str
    message: str
    parsing_status: ParsingStatus
    provider_id: str = ""
    model_id: str = ""
    requested_time: str = ""
    completed_time: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_id": self.failure_id,
            "input_id": self.input_id,
            "error_code": self.error_code,
            "message": self.message,
            "parsing_status": self.parsing_status.value,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "requested_time": self.requested_time,
            "completed_time": self.completed_time,
        }


@dataclass(frozen=True, slots=True)
class InferenceRecord:
    """Replay-safe audit record linking input, prompt, provider, and result."""

    record_id: str
    input_packet: IntelligenceInputPacket
    result: IntelligenceResult | None = None
    failure: InferenceFailure | None = None
    cache_hit: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "input_packet": self.input_packet.to_dict(),
            "result": self.result.to_dict() if self.result else None,
            "failure": self.failure.to_dict() if self.failure else None,
            "cache_hit": self.cache_hit,
        }


__all__ = [
    "ArticleInputRef",
    "ConfidenceKind",
    "ImpactHorizon",
    "InferenceFailure",
    "InferenceRecord",
    "InferenceStatus",
    "INFERENCE_SCHEMA_VERSION",
    "IntelligenceInputPacket",
    "IntelligenceResult",
    "IntelligenceTaskType",
    "MarketImpactLevel",
    "ParsingStatus",
    "SentimentLabel",
    "StructuredIntelligenceOutput",
]
