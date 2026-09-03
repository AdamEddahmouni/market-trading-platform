from typing import TYPE_CHECKING, Any

from .identifiers import METRIC_NAMESPACE, deterministic_metric_id

if TYPE_CHECKING:
    from .pressure_models import DaysToCoverComponents, PressureMetricResult

# Reuses Phase 2A's METRIC_NAMESPACE UUID and its generic deterministic_metric_id(identity)
# function directly -- no new namespace, no reimplemented UUID5/JSON-encoding logic.
# pressure_metric_identity()'s and days_to_cover_components_identity()'s key sets are
# structurally distinct from each other and from every prior-phase identity shape (Phase 2A's
# metric_identity(), Phase 2B's baseline_identity()/normalized_metric_identity()), so an
# accidental cross-model collision under the shared namespace remains cryptographically
# negligible -- verified, not merely asserted, by tests/metrics/test_pressure_anchors.py. See
# docs/phase-2c-design.md Section 7.


def deterministic_pressure_metric_id(identity: dict[str, Any]) -> str:
    return deterministic_metric_id(identity)


def deterministic_days_to_cover_components_id(identity: dict[str, Any]) -> str:
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


def pressure_metric_identity(result: "PressureMetricResult") -> dict[str, Any]:
    """Every field that affects the computed result. `value`, `diagnostics`,
    `deterministic_id` are excluded (mirrors metrics/identifiers.py's metric_identity()
    rationale exactly). `starting_source_age`/`ending_source_age` are also excluded: both are
    a pure function of fields already present here (the resolved observation ids, the
    reporting periods, and `as_of`), so including them would be redundant, never
    discriminating."""

    return {
        "metric_name": result.metric_name,
        "metric_version": result.metric_version,
        "calculation_policy_version": result.calculation_policy_version,
        "symbol": result.symbol,
        "asset_class": result.asset_class,
        "as_of": result.as_of,
        "provider_scope": result.provider_scope,
        "provider": result.provider,
        "volume_provider": result.volume_provider,
        "starting_observation_id": result.starting_observation_id,
        "ending_observation_id": result.ending_observation_id,
        "starting_reporting_period": result.starting_reporting_period,
        "ending_reporting_period": result.ending_reporting_period,
        "days_to_cover_components_id": result.days_to_cover_components_id,
        "unit": result.unit,
        "input_observation_ids": sorted(result.input_observation_ids),
        "input_metric_ids": sorted(result.input_metric_ids),
    }


def days_to_cover_components_identity(components: "DaysToCoverComponents") -> dict[str, Any]:
    """Every field that affects the component breakdown, excluding the computed
    `short_interest_value`/`volume_baseline_value` (the "value"-equivalent outcomes),
    `short_interest_source_age` (derived, see pressure_metric_identity()), `diagnostics`, and
    `deterministic_id`."""

    return {
        "component_version": components.component_version,
        "calculation_policy_version": components.calculation_policy_version,
        "symbol": components.symbol,
        "asset_class": components.asset_class,
        "as_of": components.as_of,
        "short_interest_provider": components.short_interest_provider,
        "short_interest_observation_id": components.short_interest_observation_id,
        "short_interest_reporting_period": components.short_interest_reporting_period,
        "short_interest_unit": components.short_interest_unit,
        "volume_provider": components.volume_provider,
        "volume_baseline_metric_id": components.volume_baseline_metric_id,
        "volume_unit": components.volume_unit,
        "volume_interval": components.volume_interval,
        "volume_session_scope": sorted(item.value for item in components.volume_session_scope),
        "volume_window": _window_identity(components.volume_window),
        "input_observation_ids": sorted(components.input_observation_ids),
        "input_metric_ids": sorted(components.input_metric_ids),
    }


__all__ = [
    "METRIC_NAMESPACE",
    "days_to_cover_components_identity",
    "deterministic_days_to_cover_components_id",
    "deterministic_pressure_metric_id",
    "pressure_metric_identity",
]
