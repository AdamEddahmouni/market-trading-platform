"""Governed evaluation configuration and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contracts import OutcomeHorizon
from .errors import EvaluationError, EvaluationErrorCode
from .hashing import evaluation_config_hash
from .policies import PolicyRegistry


DEFAULT_HORIZONS: tuple[OutcomeHorizon, ...] = (
    OutcomeHorizon("5m", 300, "Five-minute forward window"),
    OutcomeHorizon("15m", 900, "Fifteen-minute forward window"),
    OutcomeHorizon("30m", 1800, "Thirty-minute forward window"),
    OutcomeHorizon("60m", 3600, "Sixty-minute forward window"),
)


@dataclass(frozen=True, slots=True)
class EvaluationConfig:
    lane_id: str = "FUTURES_EQUITY_INDEX"
    baseline_policy_id: str = "news_deterministic_baseline"
    baseline_policy_version: str = "1.0.0"
    enhanced_policy_id: str = "news_ai_enhanced"
    enhanced_policy_version: str = "1.0.0"
    naive_policy_id: str = "news_naive_reference"
    naive_policy_version: str = "1.0.0"
    outcome_horizons: tuple[OutcomeHorizon, ...] = DEFAULT_HORIZONS
    directional_flat_threshold_bps: float = 5.0
    development_partition_end: str = ""
    oos_partition_start: str = ""
    require_inference_for_enhanced: bool = True
    allow_overlapping_windows: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "lane_id": self.lane_id,
            "baseline_policy_id": self.baseline_policy_id,
            "baseline_policy_version": self.baseline_policy_version,
            "enhanced_policy_id": self.enhanced_policy_id,
            "enhanced_policy_version": self.enhanced_policy_version,
            "naive_policy_id": self.naive_policy_id,
            "naive_policy_version": self.naive_policy_version,
            "outcome_horizons": [h.to_dict() for h in self.outcome_horizons],
            "directional_flat_threshold_bps": self.directional_flat_threshold_bps,
            "development_partition_end": self.development_partition_end,
            "oos_partition_start": self.oos_partition_start,
            "require_inference_for_enhanced": self.require_inference_for_enhanced,
            "allow_overlapping_windows": self.allow_overlapping_windows,
            "metadata": dict(self.metadata),
        }

    def config_hash(self) -> str:
        return evaluation_config_hash(self.to_dict())


def verify_evaluation_config(
    config: EvaluationConfig,
    *,
    instrument_ids: tuple[str, ...],
    policy_registry: PolicyRegistry | None = None,
) -> list[str]:
    """Fail-fast validation — returns warnings; raises on hard failures."""
    warnings: list[str] = []
    registry = policy_registry or PolicyRegistry()

    if not instrument_ids:
        raise EvaluationError(EvaluationErrorCode.CONFIG_INVALID, "instrument universe empty")

    if not config.outcome_horizons:
        raise EvaluationError(EvaluationErrorCode.CONFIG_INVALID, "outcome horizons required")

    for horizon in config.outcome_horizons:
        if horizon.duration_seconds <= 0:
            raise EvaluationError(
                EvaluationErrorCode.CONFIG_INVALID,
                f"invalid horizon duration: {horizon.horizon_id}",
            )

    baseline = registry.get(config.baseline_policy_id, config.baseline_policy_version)
    enhanced = registry.get(config.enhanced_policy_id, config.enhanced_policy_version)
    if enhanced.comparable_baseline_for and enhanced.comparable_baseline_for != baseline.policy_id:
        raise EvaluationError(
            EvaluationErrorCode.POLICY_MISMATCH,
            "enhanced policy must declare comparable baseline",
        )

    if config.oos_partition_start and config.development_partition_end:
        if config.oos_partition_start < config.development_partition_end:
            warnings.append("OOS partition overlaps development partition boundary semantics")

    if config.directional_flat_threshold_bps < 0:
        raise EvaluationError(EvaluationErrorCode.CONFIG_INVALID, "flat threshold must be non-negative")

    return warnings


__all__ = ["DEFAULT_HORIZONS", "EvaluationConfig", "verify_evaluation_config"]
