"""Futures curve / basis engine (F3 foundation)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from ..contracts.futures import (
    FuturesCurveSnapshot,
    futures_curve_to_dict,
)
from ..providers.contracts import ProviderResult


def build_curve_snapshot_from_chain(
    chain_result: ProviderResult,
    *,
    observation_time: str = "",
) -> FuturesCurveSnapshot | None:
    """Build FuturesCurveSnapshot from F1 chain provider result."""
    if chain_result.status != "available" or not chain_result.events:
        return None
    contracts = [row for row in chain_result.events if isinstance(row, dict)]
    if len(contracts) < 2:
        return None
    family = str(contracts[0].get("instrument_family", ""))
    contract_ids: list[str] = []
    expirations: list[str] = []
    prices: list[Decimal] = []
    volumes: list[int] = []
    open_interests: list[int] = []
    for row in contracts:
        contract_id = str(row.get("contract_id", ""))
        expiration = str(row.get("expiration", ""))
        price_raw = row.get("price") or row.get("close") or row.get("settlement_price")
        if not contract_id or not expiration or price_raw is None:
            continue
        contract_ids.append(contract_id)
        expirations.append(expiration)
        prices.append(Decimal(str(price_raw)))
        vol = row.get("volume")
        volumes.append(int(vol) if isinstance(vol, int) else 0)
        oi = row.get("open_interest")
        open_interests.append(int(oi) if isinstance(oi, int) else 0)
    if len(contract_ids) < 2:
        return None
    lead_id = ""
    roll_state = None
    for row in contracts:
        if row.get("lead_contract"):
            lead_id = str(row.get("contract_id", ""))
            raw_roll = row.get("roll_state")
            if raw_roll:
                from ..contracts.futures import RollState

                try:
                    roll_state = RollState(str(raw_roll))
                except ValueError:
                    roll_state = None
            break
    event_time = observation_time or str(contracts[0].get("event_time", ""))
    return FuturesCurveSnapshot(
        instrument_family=family,
        observation_time=event_time,
        available_time=event_time,
        contract_ids=tuple(contract_ids),
        expirations=tuple(expirations),
        prices=tuple(prices),
        volumes=tuple(volumes),
        open_interests=tuple(open_interests),
        lead_contract_id=lead_id,
        roll_state=roll_state,
        provenance_ref="futures:curve_engine_v1",
    )


def curve_regime(snapshot: FuturesCurveSnapshot) -> str:
    """Return contango, backwardation, or flat from front vs back prices."""
    if len(snapshot.prices) < 2:
        return "flat"
    front = snapshot.prices[0]
    back = snapshot.prices[-1]
    if back > front:
        return "contango"
    if back < front:
        return "backwardation"
    return "flat"


def basis_observation_from_curve(
    snapshot: FuturesCurveSnapshot,
    *,
    spot_reference: Decimal | None = None,
) -> dict[str, Any]:
    """Build basis observation — delegates to basis engine."""
    from .basis import basis_observation_from_curve as _basis_from_curve

    return _basis_from_curve(snapshot, spot_reference=spot_reference)


def curve_snapshot_payload(chain_result: ProviderResult) -> dict[str, Any]:
    snapshot = build_curve_snapshot_from_chain(chain_result)
    if snapshot is None:
        return {"available": False, "reason": "CURVE_SNAPSHOT_UNAVAILABLE"}
    payload = futures_curve_to_dict(snapshot)
    payload["available"] = True
    payload["regime"] = curve_regime(snapshot)
    return payload


__all__ = [
    "basis_observation_from_curve",
    "build_curve_snapshot_from_chain",
    "curve_regime",
    "curve_snapshot_payload",
]
