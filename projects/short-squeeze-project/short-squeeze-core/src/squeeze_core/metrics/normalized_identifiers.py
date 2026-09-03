from typing import TYPE_CHECKING, Any

from .identifiers import METRIC_NAMESPACE, deterministic_metric_id

if TYPE_CHECKING:
    from .normalized_models import BaselineStatistics, NormalizedMetricResult

# Reuses Phase 2A's METRIC_NAMESPACE UUID (metrics/identifiers.py) rather than minting a new one:
# a BaselineStatistics identity dict and a NormalizedMetricResult identity dict have structurally
# distinct key sets from each other and from a Phase 2A MetricResult identity dict, so an
# accidental collision across the three shapes is cryptographically negligible -- verified, not
# merely asserted, by tests/metrics/test_normalized_identifiers.py. See docs/phase-2b-design.md
# Section 7.


def deterministic_baseline_id(identity: dict[str, Any]) -> str:
    return deterministic_metric_id(identity)


def deterministic_normalized_metric_id(identity: dict[str, Any]) -> str:
    return deterministic_metric_id(identity)


def _window_identity(window: Any) -> dict[str, Any] | None:
    if window is None:
        return None
    return {
        "window_type": window.window_type,
        "requested_count": window.requested_count,
        "exclude_current_bar": window.exclude_current_bar,
        "minimum_samples": window.minimum_samples,
    }


def _boundaries_identity(boundaries: Any) -> list[dict[str, Any]]:
    return sorted(
        (
            {
                "bar_start": boundary.bar_start,
                "bar_end": boundary.bar_end,
                "observation_id": boundary.observation_id,
            }
            for boundary in boundaries
        ),
        key=lambda item: (item["bar_start"], item["bar_end"], item["observation_id"]),
    )


def baseline_identity(stats: "BaselineStatistics") -> dict[str, Any]:
    """Every field that affects the baseline's numeric output. `mean`, `variance`,
    `standard_deviation`, and `diagnostics` are deliberately excluded -- identical inputs and
    policy always produce the identical ID, independent of the computed outcome (mirrors Phase
    2A's metric_identity() rationale exactly)."""

    return {
        "baseline_kind": stats.baseline_kind,
        "baseline_version": stats.baseline_version,
        "calculation_policy_version": stats.calculation_policy_version,
        "standard_deviation_policy": stats.standard_deviation_policy,
        "symbol": stats.symbol,
        "asset_class": stats.asset_class,
        "as_of": stats.as_of,
        "source_interval": stats.source_interval,
        "session_scope": sorted(item.value for item in stats.session_scope),
        "provider_scope": stats.provider_scope,
        "provider": stats.provider,
        "price_field": stats.price_field,
        "window": _window_identity(stats.window),
        "input_observation_ids": sorted(stats.input_observation_ids),
        "input_metric_ids": sorted(stats.input_metric_ids),
        "input_bar_boundaries": _boundaries_identity(stats.input_bar_boundaries),
    }


def normalized_metric_identity(result: "NormalizedMetricResult") -> dict[str, Any]:
    """Every field that affects the computed result. `value`, `diagnostics`, and
    `deterministic_id` are deliberately excluded, same rationale as baseline_identity()."""

    return {
        "metric_name": result.metric_name,
        "metric_version": result.metric_version,
        "calculation_policy_version": result.calculation_policy_version,
        "standard_deviation_policy": result.standard_deviation_policy,
        "symbol": result.symbol,
        "asset_class": result.asset_class,
        "as_of": result.as_of,
        "source_interval": result.source_interval,
        "session_scope": sorted(item.value for item in result.session_scope),
        "provider_scope": result.provider_scope,
        "provider": result.provider,
        "price_field": result.price_field,
        "window": _window_identity(result.window),
        "target_boundary": None
        if result.target_boundary is None
        else {
            "bar_start": result.target_boundary.bar_start,
            "bar_end": result.target_boundary.bar_end,
            "observation_id": result.target_boundary.observation_id,
        },
        "baseline_metric_id": result.baseline_metric_id,
        "input_observation_ids": sorted(result.input_observation_ids),
        "input_bar_boundaries": _boundaries_identity(result.input_bar_boundaries),
        "input_metric_ids": sorted(result.input_metric_ids),
    }


__all__ = [
    "METRIC_NAMESPACE",
    "baseline_identity",
    "deterministic_baseline_id",
    "deterministic_normalized_metric_id",
    "normalized_metric_identity",
]
