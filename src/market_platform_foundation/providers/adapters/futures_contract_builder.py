"""Build canonical FuturesContract records from fixture depth snapshots (F1 wiring)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from ...contracts.futures import (
    FuturesContract,
    FuturesContractSpec,
    FuturesFamily,
    SettlementType,
    futures_contract_to_dict,
)
from ...donor_patterns.futures_lane import quarterly_contract_month


def snapshot_to_futures_contract(
    snapshot: dict[str, Any],
    *,
    symbol: str,
    contract_month: str,
    exchange: str,
    fixture_id: str,
    provider_id: str,
    event_time: str,
) -> FuturesContract | None:
    bids = snapshot.get("bids", [])
    asks = snapshot.get("asks", [])
    if not isinstance(bids, list) or not isinstance(asks, list):
        return None
    best_bid = max(bids, key=lambda row: float(row["price"]))
    best_ask = min(asks, key=lambda row: float(row["price"]))
    mid = (float(best_bid["price"]) + float(best_ask["price"])) / 2
    contract_id = f"{symbol.upper()}{contract_month or quarterly_contract_month()}"
    spec = FuturesContractSpec(
        multiplier=Decimal("50"),
        tick_size=Decimal("0.25"),
        tick_value=Decimal("12.5"),
        point_value=Decimal("50"),
        spec_version="1",
        spec_effective_date="2020-01-01",
    )
    return FuturesContract(
        instrument_family=symbol.upper(),
        contract_id=contract_id,
        underlying_id=symbol.upper(),
        asset_class="futures",
        subclass="equity_index",
        family=FuturesFamily.EQUITY_INDEX,
        exchange=exchange,
        expiration=_contract_month_to_expiration(contract_month),
        settlement_type=SettlementType.CASH,
        settlement_methodology="cash_settlement_index",
        spec=spec,
        price=Decimal(str(round(mid, 4))),
        last_trade_price=Decimal(str(round(mid, 4))),
        volume=int(snapshot.get("volume", 0) or 0),
        open_interest=int(snapshot.get("open_interest", 0) or 0),
        lead_contract=True,
        provider=provider_id,
        event_time=event_time,
        available_time=event_time,
        ingested_time=event_time,
        provenance_ref=f"{fixture_id}:{event_time}",
    )


def _contract_month_to_expiration(contract_month: str) -> str:
    if len(contract_month) == 6:
        year = int(contract_month[:4])
        month = int(contract_month[4:6])
        return f"{year}-{month:02d}-15"
    return contract_month


def contract_to_chain_dict(contract: FuturesContract) -> dict[str, Any]:
    return futures_contract_to_dict(contract)


__all__ = [
    "contract_to_chain_dict",
    "snapshot_to_futures_contract",
]
