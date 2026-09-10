"""Non-executable strategy evaluation contracts — research laboratory only."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


EVALUATION_SCHEMA_VERSION = "intelligence/news_strategy_evaluation/1.0.0"


class EvaluationDecision(StrEnum):
    """Non-execution-oriented strategy evaluation semantics."""

    POSITIVE_DIRECTIONAL_BIAS = "POSITIVE_DIRECTIONAL_BIAS"
    NEGATIVE_DIRECTIONAL_BIAS = "NEGATIVE_DIRECTIONAL_BIAS"
    NEUTRAL = "NEUTRAL"


class PolicyClassification(StrEnum):
    BASELINE_DETERMINISTIC = "BASELINE_DETERMINISTIC"
    BASELINE_NAIVE = "BASELINE_NAIVE"
    AI_ENHANCED = "AI_ENHANCED"


class DirectionalLabel(StrEnum):
    UP = "UP"
    DOWN = "DOWN"
    FLAT = "FLAT"


class OutcomeQuality(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL_HORIZON = "PARTIAL_HORIZON"
    MISSING_START_BAR = "MISSING_START_BAR"
    MISSING_END_BAR = "MISSING_END_BAR"
    INSUFFICIENT_MARKET_DATA = "INSUFFICIENT_MARKET_DATA"
    SESSION_CLOSED = "SESSION_CLOSED"
    EXCLUDED = "EXCLUDED"


class SampleExclusionReason(StrEnum):
    FUTURE_NEWS_NOT_OBSERVABLE = "FUTURE_NEWS_NOT_OBSERVABLE"
    FUTURE_INFERENCE_NOT_OBSERVABLE = "FUTURE_INFERENCE_NOT_OBSERVABLE"
    FUTURE_MARKET_FEATURE = "FUTURE_MARKET_FEATURE"
    DUPLICATE_EVENT_SAMPLE = "DUPLICATE_EVENT_SAMPLE"
    STALE_EVENT_REJECTED = "STALE_EVENT_REJECTED"
    NO_CURATED_EVENTS = "NO_CURATED_EVENTS"
    INFERENCE_FAILED = "INFERENCE_FAILED"
    INCOMPLETE_OUTCOME_DATA = "INCOMPLETE_OUTCOME_DATA"
    CONFIG_INVALID = "CONFIG_INVALID"


@dataclass(frozen=True, slots=True)
class OutcomeHorizon:
    horizon_id: str
    duration_seconds: int
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "horizon_id": self.horizon_id,
            "duration_seconds": self.duration_seconds,
            "description": self.description,
        }


@dataclass(frozen=True, slots=True)
class DeterministicNewsFeatures:
    event_count: int
    catalyst_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    source_trust_tiers: tuple[str, ...]
    youngest_event_age_seconds: int | None
    oldest_event_age_seconds: int | None
    publication_times: tuple[str, ...]
    retrieval_times: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_count": self.event_count,
            "catalyst_ids": list(self.catalyst_ids),
            "source_ids": list(self.source_ids),
            "source_trust_tiers": list(self.source_trust_tiers),
            "youngest_event_age_seconds": self.youngest_event_age_seconds,
            "oldest_event_age_seconds": self.oldest_event_age_seconds,
            "publication_times": list(self.publication_times),
            "retrieval_times": list(self.retrieval_times),
        }


@dataclass(frozen=True, slots=True)
class IntelligenceFeatures:
    inference_record_id: str
    sentiment_label: str | None
    sentiment_score: float | None
    market_impact_level: str | None
    impact_horizon: str | None
    model_confidence: float | None
    confidence_kind: str
    catalyst_interpretation: str = ""
    prompt_id: str = ""
    prompt_version: str = ""
    model_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "inference_record_id": self.inference_record_id,
            "sentiment_label": self.sentiment_label,
            "sentiment_score": self.sentiment_score,
            "market_impact_level": self.market_impact_level,
            "impact_horizon": self.impact_horizon,
            "model_confidence": self.model_confidence,
            "confidence_kind": self.confidence_kind,
            "catalyst_interpretation": self.catalyst_interpretation,
            "prompt_id": self.prompt_id,
            "prompt_version": self.prompt_version,
            "model_id": self.model_id,
        }


@dataclass(frozen=True, slots=True)
class MarketFeatures:
    instrument_id: str
    asset_class: str
    price_at_as_of: float | None
    return_1_bar: float | None
    bar_event_time: str
    market_data_ref: str
    volatility_proxy: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "asset_class": self.asset_class,
            "price_at_as_of": self.price_at_as_of,
            "return_1_bar": self.return_1_bar,
            "bar_event_time": self.bar_event_time,
            "market_data_ref": self.market_data_ref,
            "volatility_proxy": self.volatility_proxy,
        }


@dataclass(frozen=True, slots=True)
class StrategyFeatureSnapshot:
    """Frozen decision-time information — no future data."""

    snapshot_id: str
    as_of: str
    instrument_id: str
    asset_class: str
    news_event_ids: tuple[str, ...]
    deterministic: DeterministicNewsFeatures
    market: MarketFeatures
    intelligence: IntelligenceFeatures | None = None
    overlap_sample_ids: tuple[str, ...] = ()
    overlap_flags: tuple[str, ...] = ()
    snapshot_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "as_of": self.as_of,
            "instrument_id": self.instrument_id,
            "asset_class": self.asset_class,
            "news_event_ids": list(self.news_event_ids),
            "deterministic": self.deterministic.to_dict(),
            "market": self.market.to_dict(),
            "intelligence": self.intelligence.to_dict() if self.intelligence else None,
            "overlap_sample_ids": list(self.overlap_sample_ids),
            "overlap_flags": list(self.overlap_flags),
            "snapshot_hash": self.snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class StrategyEvaluationDecision:
    """Non-executable evaluation decision — never valid as an order object."""

    decision_id: str
    evaluation_run_id: str
    sample_id: str
    policy_id: str
    policy_version: str
    policy_classification: PolicyClassification
    config_hash: str
    as_of: str
    instrument_id: str
    asset_class: str
    decision: EvaluationDecision
    normalized_directional_units: int
    simulation_only: bool
    execution_authority: bool
    news_event_ids: tuple[str, ...]
    inference_record_ids: tuple[str, ...]
    feature_snapshot_id: str
    market_snapshot_ref: str
    overlap_flags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "evaluation_run_id": self.evaluation_run_id,
            "sample_id": self.sample_id,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_classification": self.policy_classification.value,
            "config_hash": self.config_hash,
            "as_of": self.as_of,
            "instrument_id": self.instrument_id,
            "asset_class": self.asset_class,
            "decision": self.decision.value,
            "normalized_directional_units": self.normalized_directional_units,
            "simulation_only": self.simulation_only,
            "execution_authority": self.execution_authority,
            "news_event_ids": list(self.news_event_ids),
            "inference_record_ids": list(self.inference_record_ids),
            "feature_snapshot_id": self.feature_snapshot_id,
            "market_snapshot_ref": self.market_snapshot_ref,
            "overlap_flags": list(self.overlap_flags),
        }


@dataclass(frozen=True, slots=True)
class RealizedOutcome:
    """Subsequent market movement after decision time — not causal attribution."""

    outcome_id: str
    decision_id: str
    sample_id: str
    horizon_id: str
    start_time: str
    end_time: str
    start_price: float | None
    end_price: float | None
    high_price: float | None
    low_price: float | None
    raw_return: float | None
    normalized_directional_return: float | None
    maximum_favorable_excursion: float | None
    maximum_adverse_excursion: float | None
    directional_label: DirectionalLabel | None
    quality: OutcomeQuality
    data_provenance: str
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome_id": self.outcome_id,
            "decision_id": self.decision_id,
            "sample_id": self.sample_id,
            "horizon_id": self.horizon_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "start_price": self.start_price,
            "end_price": self.end_price,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "raw_return": self.raw_return,
            "normalized_directional_return": self.normalized_directional_return,
            "maximum_favorable_excursion": self.maximum_favorable_excursion,
            "maximum_adverse_excursion": self.maximum_adverse_excursion,
            "directional_label": self.directional_label.value if self.directional_label else None,
            "quality": self.quality.value,
            "data_provenance": self.data_provenance,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class EvaluationSampleResult:
    sample_id: str
    as_of: str
    instrument_id: str
    asset_class: str
    excluded: bool
    exclusion_reason: SampleExclusionReason | None
    feature_snapshot: StrategyFeatureSnapshot | None
    baseline_decision: StrategyEvaluationDecision | None
    enhanced_decision: StrategyEvaluationDecision | None
    naive_decision: StrategyEvaluationDecision | None
    baseline_outcomes: tuple[RealizedOutcome, ...] = ()
    enhanced_outcomes: tuple[RealizedOutcome, ...] = ()
    overlap_flags: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "as_of": self.as_of,
            "instrument_id": self.instrument_id,
            "asset_class": self.asset_class,
            "excluded": self.excluded,
            "exclusion_reason": self.exclusion_reason.value if self.exclusion_reason else None,
            "feature_snapshot": self.feature_snapshot.to_dict() if self.feature_snapshot else None,
            "baseline_decision": self.baseline_decision.to_dict() if self.baseline_decision else None,
            "enhanced_decision": self.enhanced_decision.to_dict() if self.enhanced_decision else None,
            "naive_decision": self.naive_decision.to_dict() if self.naive_decision else None,
            "baseline_outcomes": [o.to_dict() for o in self.baseline_outcomes],
            "enhanced_outcomes": [o.to_dict() for o in self.enhanced_outcomes],
            "overlap_flags": list(self.overlap_flags),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class PolicyMetrics:
    policy_id: str
    policy_version: str
    policy_classification: PolicyClassification
    sample_count: int
    evaluated_count: int
    excluded_count: int
    abstention_count: int
    directional_accuracy: float | None
    mean_forward_return: float | None
    median_forward_return: float | None
    positive_outcome_rate: float | None
    mean_mfe: float | None
    mean_mae: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_classification": self.policy_classification.value,
            "sample_count": self.sample_count,
            "evaluated_count": self.evaluated_count,
            "excluded_count": self.excluded_count,
            "abstention_count": self.abstention_count,
            "directional_accuracy": self.directional_accuracy,
            "mean_forward_return": self.mean_forward_return,
            "median_forward_return": self.median_forward_return,
            "positive_outcome_rate": self.positive_outcome_rate,
            "mean_mfe": self.mean_mfe,
            "mean_mae": self.mean_mae,
        }


@dataclass(frozen=True, slots=True)
class CalibrationBucket:
    bucket_id: str
    bucket_label: str
    count: int
    realized_correct: int
    realized_incorrect: int
    empirical_correctness_rate: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "bucket_id": self.bucket_id,
            "bucket_label": self.bucket_label,
            "count": self.count,
            "realized_correct": self.realized_correct,
            "realized_incorrect": self.realized_incorrect,
            "empirical_correctness_rate": self.empirical_correctness_rate,
        }


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    sentiment_buckets: tuple[CalibrationBucket, ...]
    impact_buckets: tuple[CalibrationBucket, ...]
    confidence_buckets: tuple[CalibrationBucket, ...]
    terminology: str = "EMPIRICAL_CONFIDENCE_ANALYSIS"

    def to_dict(self) -> dict[str, Any]:
        return {
            "sentiment_buckets": [b.to_dict() for b in self.sentiment_buckets],
            "impact_buckets": [b.to_dict() for b in self.impact_buckets],
            "confidence_buckets": [b.to_dict() for b in self.confidence_buckets],
            "terminology": self.terminology,
        }


@dataclass(frozen=True, slots=True)
class EvaluationRunRecord:
    run_id: str
    lane_id: str
    instrument_universe: tuple[str, ...]
    eval_start: str
    eval_end: str
    baseline_policy_id: str
    baseline_policy_version: str
    enhanced_policy_id: str
    enhanced_policy_version: str
    outcome_horizons: tuple[OutcomeHorizon, ...]
    config_hash: str
    run_hash: str
    status: str
    warnings: tuple[str, ...] = ()
    news_policy_versions: dict[str, str] = field(default_factory=dict)
    prompt_provenance: tuple[dict[str, str], ...] = ()
    development_partition_end: str = ""
    oos_partition_start: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "lane_id": self.lane_id,
            "instrument_universe": list(self.instrument_universe),
            "eval_start": self.eval_start,
            "eval_end": self.eval_end,
            "baseline_policy_id": self.baseline_policy_id,
            "baseline_policy_version": self.baseline_policy_version,
            "enhanced_policy_id": self.enhanced_policy_id,
            "enhanced_policy_version": self.enhanced_policy_version,
            "outcome_horizons": [h.to_dict() for h in self.outcome_horizons],
            "config_hash": self.config_hash,
            "run_hash": self.run_hash,
            "status": self.status,
            "warnings": list(self.warnings),
            "news_policy_versions": dict(self.news_policy_versions),
            "prompt_provenance": list(self.prompt_provenance),
            "development_partition_end": self.development_partition_end,
            "oos_partition_start": self.oos_partition_start,
            "schema_version": EVALUATION_SCHEMA_VERSION,
        }


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    run: EvaluationRunRecord
    sample_results: tuple[EvaluationSampleResult, ...]
    baseline_metrics: PolicyMetrics
    enhanced_metrics: PolicyMetrics
    ai_incremental_delta: dict[str, float | None]
    calibration: CalibrationReport
    limitations: tuple[str, ...]
    report_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "run": self.run.to_dict(),
            "sample_results": [s.to_dict() for s in self.sample_results],
            "baseline_metrics": self.baseline_metrics.to_dict(),
            "enhanced_metrics": self.enhanced_metrics.to_dict(),
            "ai_incremental_delta": dict(self.ai_incremental_delta),
            "calibration": self.calibration.to_dict(),
            "limitations": list(self.limitations),
            "report_hash": self.report_hash,
        }


@dataclass(frozen=True, slots=True)
class EvaluationShadowRecord:
    """
    Paper-shadow laboratory record — hypothetical evaluation intent only.

    Explicitly excluded: broker account, order ID, submit flag, preview binding.
    """

    shadow_id: str
    evaluation_run_id: str
    decision_id: str
    as_of: str
    instrument_id: str
    decision: EvaluationDecision
    normalized_directional_units: int
    simulation_only: bool
    execution_authority: bool
    feature_snapshot_id: str
    recorded_at: str
    shadow_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "shadow_id": self.shadow_id,
            "evaluation_run_id": self.evaluation_run_id,
            "decision_id": self.decision_id,
            "as_of": self.as_of,
            "instrument_id": self.instrument_id,
            "decision": self.decision.value,
            "normalized_directional_units": self.normalized_directional_units,
            "simulation_only": self.simulation_only,
            "execution_authority": self.execution_authority,
            "feature_snapshot_id": self.feature_snapshot_id,
            "recorded_at": self.recorded_at,
            "shadow_hash": self.shadow_hash,
        }


__all__ = [
    "CalibrationBucket",
    "CalibrationReport",
    "DeterministicNewsFeatures",
    "DirectionalLabel",
    "EVALUATION_SCHEMA_VERSION",
    "EvaluationDecision",
    "EvaluationReport",
    "EvaluationRunRecord",
    "EvaluationSampleResult",
    "EvaluationShadowRecord",
    "IntelligenceFeatures",
    "MarketFeatures",
    "OutcomeHorizon",
    "OutcomeQuality",
    "PolicyClassification",
    "PolicyMetrics",
    "RealizedOutcome",
    "SampleExclusionReason",
    "StrategyEvaluationDecision",
    "StrategyFeatureSnapshot",
]
