"""SS P2/P6 lending adapter — fixture + IBKR borrow fail-closed."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from ..contracts.squeeze_structural import (
    PublicationState,
    SecuritiesLendingSnapshot,
    lending_snapshot_to_dict,
)

DEFAULT_LENDING_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "squeeze"
    / "lending_normalization_slice.json"
)

_PRIOR_LENDING_SNAPSHOTS: dict[str, dict[str, Any]] = {}


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _field_value(detail: dict[str, Any], name: str) -> Any | None:
    fields = detail.get("fields")
    if not isinstance(fields, dict):
        return None
    cell = fields.get(name)
    if not isinstance(cell, dict):
        return None
    if cell.get("status") != "KNOWN":
        return None
    return cell.get("value")


def build_lending_snapshot_from_ibkr(
    *,
    symbol: str,
    fee_rate: float | None,
    shares_available: int | None,
    utilization_rate: float | None = None,
    shares_on_loan: int | None = None,
    observation_time: str,
    available_time: str,
    provider: str = "IBKR",
    provenance_ref: str = "",
    prior_snapshot: SecuritiesLendingSnapshot | None = None,
) -> SecuritiesLendingSnapshot | None:
    """Map IBKR borrow observations into governed SecuritiesLendingSnapshot."""
    if fee_rate is None and shares_available is None and utilization_rate is None:
        return None

    fee_decimal = Decimal(str(fee_rate)) if fee_rate is not None else None
    return SecuritiesLendingSnapshot(
        symbol=symbol.upper(),
        utilization_rate=Decimal(str(utilization_rate)) if utilization_rate is not None else None,
        shares_on_loan=shares_on_loan,
        shares_available=shares_available,
        fee_rate=fee_decimal,
        observation_time=observation_time,
        available_time=available_time,
        publication_state=PublicationState.PUBLISHED,
        provider=provider,
        provenance_ref=provenance_ref or f"ibkr:borrow:{symbol.upper()}",
        quality_flags=(),
    )


def _borrow_utilization_velocity(
    current: SecuritiesLendingSnapshot,
    prior: SecuritiesLendingSnapshot | None,
) -> float | None:
    if prior is None:
        return None
    if current.utilization_rate is not None and prior.utilization_rate is not None:
        return float(current.utilization_rate - prior.utilization_rate)
    if current.fee_rate is not None and prior.fee_rate is not None:
        return float(current.fee_rate - prior.fee_rate)
    return None


def build_lending_snapshot_from_donor_detail(
    detail: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Extract IBKR borrow fields from donor row/detail into lending snapshot dict."""
    if not detail or not isinstance(detail, dict):
        return None

    symbol = str(detail.get("symbol", "")).upper()
    if not symbol:
        identity = detail.get("identity")
        if isinstance(identity, dict):
            symbol = str(identity.get("symbol", "")).upper()
    if not symbol:
        return None

    fee_rate = _optional_float(_field_value(detail, "borrow_fee"))
    shares_available = _optional_int(_field_value(detail, "borrow_availability"))
    lending_row = detail.get("securities_lending_snapshot")
    if isinstance(lending_row, dict):
        fee_rate = fee_rate if fee_rate is not None else _optional_float(lending_row.get("fee_rate"))
        shares_available = (
            shares_available
            if shares_available is not None
            else _optional_int(lending_row.get("shares_available"))
        )
        utilization_rate = _optional_float(lending_row.get("utilization_rate"))
        shares_on_loan = _optional_int(lending_row.get("shares_on_loan"))
        observation_time = str(lending_row.get("observation_time", ""))
        available_time = str(lending_row.get("available_time", observation_time))
    else:
        utilization_rate = None
        shares_on_loan = None
        observation_time = str(detail.get("snapshot_at", ""))
        available_time = observation_time

    if fee_rate is None and shares_available is None:
        return None

    prior_dict = _PRIOR_LENDING_SNAPSHOTS.get(symbol)
    prior_snapshot = None
    if isinstance(prior_dict, dict):
        prior_snapshot = build_lending_snapshot_from_ibkr(
            symbol=symbol,
            fee_rate=_optional_float(prior_dict.get("fee_rate")),
            shares_available=_optional_int(prior_dict.get("shares_available")),
            utilization_rate=_optional_float(prior_dict.get("utilization_rate")),
            shares_on_loan=_optional_int(prior_dict.get("shares_on_loan")),
            observation_time=str(prior_dict.get("observation_time", "")),
            available_time=str(prior_dict.get("available_time", "")),
        )

    snapshot = build_lending_snapshot_from_ibkr(
        symbol=symbol,
        fee_rate=fee_rate,
        shares_available=shares_available,
        utilization_rate=utilization_rate,
        shares_on_loan=shares_on_loan,
        observation_time=observation_time or available_time,
        available_time=available_time or observation_time,
    )
    if snapshot is None:
        return None

    velocity = _borrow_utilization_velocity(snapshot, prior_snapshot)
    payload = lending_snapshot_to_dict(snapshot)
    if velocity is not None:
        payload["borrow_utilization_velocity"] = velocity
    _PRIOR_LENDING_SNAPSHOTS[symbol] = payload
    return payload


def build_lending_cross_lane_snapshot(
    detail: dict[str, Any] | None,
) -> dict[str, Any]:
    """Map donor/IBKR lending snapshot into cross_lane evaluator fields."""
    lending = build_lending_snapshot_from_donor_detail(detail)
    if not lending:
        return {}

    fee_rate = _optional_float(lending.get("fee_rate"))
    shares_available = _optional_int(lending.get("shares_available"))
    utilization_rate = _optional_float(lending.get("utilization_rate"))
    shares_on_loan = _optional_int(lending.get("shares_on_loan"))
    velocity = _optional_float(lending.get("borrow_utilization_velocity"))

    return {
        "lending_available": True,
        "lending_fee_rate": fee_rate,
        "lending_shares_available": shares_available,
        "lending_utilization_rate": utilization_rate,
        "lending_shares_on_loan": shares_on_loan,
        "borrow_utilization_velocity": velocity,
    }


def build_lending_cross_lane_fields(
    fixture_path: Path | None = None,
) -> dict[str, Any]:
    """Map PIT lending fixture to borrow_normalization_score for donor cross_lane."""
    path = fixture_path or DEFAULT_LENDING_FIXTURE
    if not path.is_file():
        return {}

    payload = json.loads(path.read_text(encoding="utf-8"))
    current = payload.get("current")
    prior = payload.get("prior")
    if not isinstance(current, dict) or not isinstance(prior, dict):
        return {}

    try:
        from squeeze_core.intelligence.fuel import estimate_borrow_normalization
    except ImportError:
        return {}

    score = estimate_borrow_normalization(
        current_utilization=_optional_float(current.get("utilization_rate")),
        prior_utilization=_optional_float(prior.get("utilization_rate")),
        current_fee=_optional_float(current.get("fee_rate")),
        prior_fee=_optional_float(prior.get("fee_rate")),
    )
    if score is None:
        return {}
    return {"borrow_normalization_score": score}


def reset_lending_snapshot_cache() -> None:
    """Clear prior lending snapshots — test helper."""
    _PRIOR_LENDING_SNAPSHOTS.clear()


__all__ = [
    "DEFAULT_LENDING_FIXTURE",
    "build_lending_cross_lane_fields",
    "build_lending_cross_lane_snapshot",
    "build_lending_snapshot_from_donor_detail",
    "build_lending_snapshot_from_ibkr",
    "reset_lending_snapshot_cache",
]
