"""Paper/Demo persist+load for Path A PRODUCTION ForecastV1 artifacts.

The hop only *loads* a previously persisted ``ForecastV1``. This module does
not mint a probability from a quote, does not call CONTROL baseline
construction, and does not wrap a research score dict as a production
forecast.

``persist_paper_demo_forecast`` is serialization of an already-constructed
``ForecastV1`` (separate from scan). The fail-closed *producer* is
``path_a_forecast_producer.produce_paper_demo_forecast``: it may call this
serializer only after BUILD 14 fusion emits ``EMITTED_CALIBRATED`` and
identity/PIT/champion/horizon/account/mode plus calibration gates pass.
Load is fail-closed against Opportunity Engine hop policy: identity, PIT,
champion, horizon, account, and mode must match; CONTROL, RESEARCH, and
uncalibrated artifacts return ``None``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from ..canonical import load_json_strict, write_canonical_json
from ..intelligence.contracts.forecast import (
    ForecastV1,
    forecast_v1_from_dict,
    forecast_v1_to_dict,
)
from ..intelligence.contracts.strategy_match import StrategyMatch
from ..intelligence.evaluation.types import forecast_role
from ..intelligence.fusion.types import CONTROL_FORECAST_STAGE, ForecastContributorRole
from ..intelligence.opportunity.engine import forecast_matches_champion
from ..intelligence.opportunity.types import OpportunityPolicyV1
from ..intelligence.promotion.types import ChampionAssignmentV1
from .path_a_scan_caller import _resolve_forecast
from .scanning import ScanRequest


def persist_paper_demo_forecast(
    forecast: ForecastV1,
    *,
    destination: str | Path,
) -> dict[str, Any]:
    """Serialize an already-constructed ForecastV1. Not a producer.

    Does not accept a raw probability, a quote print, or a research score.
    Callers that need a PRODUCTION artifact must already have one.
    """

    if not isinstance(forecast, ForecastV1):
        raise TypeError("FORECAST_V1_REQUIRED")
    dest = Path(destination)
    payload = forecast_v1_to_dict(forecast)
    if dest.suffix.lower() == ".json":
        target = dest
    else:
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / f"{forecast.forecast_id}.json"
    write_canonical_json(target, payload)
    return payload


def load_paper_demo_forecasts(source: str | Path) -> tuple[ForecastV1, ...]:
    """Load previously persisted ForecastV1 rows. Fail closed on missing/corrupt."""

    path = Path(source)
    if not path.exists():
        return ()
    if path.is_dir():
        rows: list[ForecastV1] = []
        for child in sorted(path.glob("*.json")):
            rows.extend(_load_forecast_payload(child))
        return tuple(rows)
    return tuple(_load_forecast_payload(path))


def select_eligible_forecast(
    match: StrategyMatch,
    records: Iterable[ForecastV1 | Mapping[str, Any]],
    *,
    request: ScanRequest,
    champion: ChampionAssignmentV1,
    policy: OpportunityPolicyV1,
) -> ForecastV1 | None:
    """Return a stored ForecastV1 only when OE hop policy and PIT match.

    Absent, corrupt, CONTROL, RESEARCH, uncalibrated, or identity/PIT/
    champion/horizon/account/mode mismatch → ``None`` (``FORECAST_UNAVAILABLE``).
    """

    eligible: list[ForecastV1] = []
    for record in records:
        forecast = _coerce_forecast(record)
        if forecast is None:
            continue
        if not forecast_matches_path_a_hop_policy(forecast, champion=champion, policy=policy):
            continue
        resolved = _resolve_forecast(
            match=match,
            request=request,
            forecast=forecast,
            champion=champion,
        )
        if resolved is None:
            continue
        eligible.append(resolved)
    if not eligible:
        return None
    eligible.sort(key=lambda row: str(row.forecast_id))
    return eligible[0]


def forecast_matches_path_a_hop_policy(
    forecast: ForecastV1,
    *,
    champion: ChampionAssignmentV1,
    policy: OpportunityPolicyV1,
) -> bool:
    role = forecast_role(forecast)
    if role == ForecastContributorRole.CONTROL.value:
        return False
    if role == ForecastContributorRole.RESEARCH.value:
        return False
    if role not in policy.allowed_contributor_roles:
        return False
    stage = str(forecast.metadata.get("forecast_stage") or "")
    if stage == CONTROL_FORECAST_STAGE or stage == "RESEARCH_ONLY":
        return False
    if policy.allowed_forecast_stages and stage not in policy.allowed_forecast_stages:
        return False
    calibration = str(forecast.metadata.get("calibration_status") or "").upper()
    if calibration in {"UNCALIBRATED", "CALIBRATION_UNAVAILABLE", "IDENTITY_CONTROL"}:
        return False
    if forecast.estimate.calibrated_probability is None:
        return False
    if not forecast_matches_champion(forecast, champion):
        return False
    return True


def _coerce_forecast(payload: object) -> ForecastV1 | None:
    if isinstance(payload, ForecastV1):
        return payload
    if not isinstance(payload, Mapping):
        return None
    if "interface_version" in payload and "forecast_id" not in payload:
        return None
    try:
        return forecast_v1_from_dict(dict(payload))
    except (KeyError, TypeError, ValueError):
        return None


def _load_forecast_payload(path: Path) -> tuple[ForecastV1, ...]:
    try:
        payload = load_json_strict(path)
    except (OSError, TypeError, ValueError):
        return ()
    if isinstance(payload, Mapping):
        forecast = _coerce_forecast(payload)
        return (forecast,) if forecast is not None else ()
    if isinstance(payload, list):
        rows = tuple(
            forecast
            for forecast in (_coerce_forecast(row) for row in payload)
            if forecast is not None
        )
        return rows
    return ()


__all__ = [
    "forecast_matches_path_a_hop_policy",
    "load_paper_demo_forecasts",
    "persist_paper_demo_forecast",
    "select_eligible_forecast",
]
