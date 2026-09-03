import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid5

if TYPE_CHECKING:
    from .models import MetricResult


# Fixed, distinct from contracts.identifiers.OBSERVATION_NAMESPACE so a metric's
# deterministic ID can never collide with, or be mistaken for, a Phase 1 observation ID.
METRIC_NAMESPACE = UUID("9f6a7f9e-2d1b-4a3e-8c2f-6a5e0b7c4d21")


def _identity_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return str(value.value)
    raise TypeError(f"unsupported identity value: {type(value)!r}")


def deterministic_metric_id(identity: dict[str, Any]) -> str:
    encoded = json.dumps(
        identity,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_identity_default,
    )
    return str(uuid5(METRIC_NAMESPACE, encoded))


def metric_identity(result: "MetricResult") -> dict[str, Any]:
    """Every field that affects the computed result. `value` and `diagnostics` are
    deliberately excluded: two runs with identical inputs/policy always share one ID,
    independent of whether the arithmetic outcome changed under an unchanged metric_version.
    """

    return {
        "metric_name": result.metric_name,
        "metric_version": result.metric_version,
        "calculation_policy_version": result.calculation_policy_version,
        "symbol": result.symbol,
        "asset_class": result.asset_class,
        "as_of": result.as_of,
        "source_interval": result.source_interval,
        "session_scope": sorted(item.value for item in result.session_scope),
        "provider_scope": result.provider_scope,
        "provider": result.provider,
        "price_field": result.price_field,
        "window": None
        if result.window is None
        else {
            "window_type": result.window.window_type,
            "requested_count": result.window.requested_count,
            "exclude_current_bar": result.window.exclude_current_bar,
            "minimum_samples": result.window.minimum_samples,
        },
        "input_observation_ids": sorted(result.input_observation_ids),
        "input_bar_boundaries": sorted(
            (
                {
                    "bar_start": boundary.bar_start,
                    "bar_end": boundary.bar_end,
                    "observation_id": boundary.observation_id,
                }
                for boundary in result.input_bar_boundaries
            ),
            key=lambda item: (item["bar_start"], item["bar_end"], item["observation_id"]),
        ),
    }
