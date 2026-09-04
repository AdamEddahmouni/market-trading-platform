"""Contributor role resolution for BUILD 14."""

from __future__ import annotations

from ..contracts import ForecastV1
from .types import CONTROL_FORECAST_STAGE, ForecastContributorRole


def resolve_contributor_role(forecast: ForecastV1) -> ForecastContributorRole:
    metadata = forecast.metadata
    explicit = metadata.get("contributor_role")
    if explicit is not None:
        return ForecastContributorRole(str(explicit))
    if metadata.get("baseline_model_kind") is not None:
        return ForecastContributorRole.CONTROL
    if metadata.get("forecast_stage") == CONTROL_FORECAST_STAGE:
        return ForecastContributorRole.CONTROL
    if metadata.get("forecast_stage") == "RESEARCH_ONLY":
        return ForecastContributorRole.RESEARCH
    return ForecastContributorRole.CONTROL


def resolve_forecast_family_key(forecast: ForecastV1, explicit: str | None = None) -> str | None:
    if explicit is not None:
        return explicit
    metadata_family = forecast.metadata.get("forecast_family_key")
    if metadata_family is not None:
        return str(metadata_family)
    baseline_kind = forecast.metadata.get("baseline_model_kind")
    if baseline_kind is not None:
        return f"baseline:{baseline_kind}"
    if forecast.component_lineage is not None:
        return f"component:{forecast.component_lineage.model_id}"
    return None


__all__ = ["resolve_contributor_role", "resolve_forecast_family_key"]
