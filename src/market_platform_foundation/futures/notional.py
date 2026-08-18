"""Futures notional exposure and tick economics."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from ..contracts.futures import FuturesContract, FuturesContractSpec


def tick_economics_from_spec(spec: FuturesContractSpec) -> dict[str, str]:
    """Expose tick_size, tick_value, point_value for PnL from contract specs."""
    return {
        "tick_size": str(spec.tick_size),
        "tick_value": str(spec.tick_value),
        "point_value": str(spec.point_value),
    }


def notional_exposure(
    contracts: int | Decimal,
    multiplier: Decimal,
    underlying_price: Decimal,
) -> Decimal:
    """NotionalExposure = Contracts × Multiplier × RelevantUnderlyingPrice."""
    return Decimal(contracts) * multiplier * underlying_price


def effective_leverage(
    notional: Decimal,
    margin: Decimal,
) -> Decimal | None:
    """Effective leverage = notional / margin capital requirement."""
    if margin <= 0:
        return None
    return notional / margin


def pnl_from_price_change(
    contracts: int | Decimal,
    price_change: Decimal,
    spec: FuturesContractSpec,
) -> Decimal:
    """Calculate PnL from actual tick/point economics — not generic percentage returns."""
    ticks = price_change / spec.tick_size
    return Decimal(contracts) * ticks * spec.tick_value


def exposure_summary(
    contract: FuturesContract,
    contracts_held: int | Decimal,
    *,
    margin_type: str = "maintenance",
) -> dict[str, Any]:
    """Return notional, capital, effective_leverage separately — never just contract count."""
    if contract.spec is None or contract.price is None:
        return {
            "contracts": str(contracts_held),
            "notional": None,
            "capital": None,
            "effective_leverage": None,
            "tick_economics": None,
            "quality_note": "CONTRACT_SPEC_OR_PRICE_MISSING",
        }
    notional = notional_exposure(contracts_held, contract.spec.multiplier, contract.price)
    margin = (
        contract.maintenance_margin
        if margin_type == "maintenance"
        else contract.initial_margin
    )
    leverage = effective_leverage(notional, margin) if margin is not None else None
    return {
        "contracts": str(contracts_held),
        "notional": str(notional),
        "capital": str(margin) if margin is not None else None,
        "effective_leverage": str(leverage) if leverage is not None else None,
        "tick_economics": tick_economics_from_spec(contract.spec),
        "margin_type": margin_type,
    }


# Canonical ES contract spec for fixture/research baselines
ES_CONTRACT_SPEC = FuturesContractSpec(
    multiplier=Decimal("50"),
    tick_size=Decimal("0.25"),
    tick_value=Decimal("12.50"),
    point_value=Decimal("50"),
    spec_version="es_cme_v1",
    spec_effective_date="2020-01-01",
)
