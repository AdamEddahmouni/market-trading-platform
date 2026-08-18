"""Build canonical FuturesContract records from fixture depth snapshots (F1 wiring)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from ...contracts.futures import (
    FuturesContract,
    FuturesContractSpec,
    FuturesFamily,
    RollState,
    SettlementType,
    futures_contract_to_dict,
)
from ...contracts.futures_quality import FuturesQualityFlag
from ...futures.notional import ES_CONTRACT_SPEC
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
    lead_contract: bool = False,
    roll_state: RollState | None = None,
    volume: int | None = None,
    open_interest: int | None = None,
) -> FuturesContract | None:
    bids = snapshot.get("bids", [])
    asks = snapshot.get("asks", [])
    if not isinstance(bids, list) or not isinstance(asks, list):
        return None
    best_bid = max(bids, key=lambda row: float(row["price"]))
    best_ask = min(asks, key=lambda row: float(row["price"]))
    bid_price = float(best_bid["price"])
    ask_price = float(best_ask["price"])
    mid = (bid_price + ask_price) / 2
    contract_id = f"{symbol.upper()}{contract_month or quarterly_contract_month()}"
    spec = FuturesContractSpec(
        multiplier=ES_CONTRACT_SPEC.multiplier,
        tick_size=ES_CONTRACT_SPEC.tick_size,
        tick_value=ES_CONTRACT_SPEC.tick_value,
        point_value=ES_CONTRACT_SPEC.point_value,
        spec_version=ES_CONTRACT_SPEC.spec_version,
        spec_effective_date=ES_CONTRACT_SPEC.spec_effective_date,
    )
    quality_flags: tuple[str, ...] = ()
    if bid_price <= 0 or ask_price <= 0:
        quality_flags = (FuturesQualityFlag.CONTRACT_SPEC_UNKNOWN.value,)
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
        volume=int(volume if volume is not None else snapshot.get("volume", 0) or 0),
        open_interest=int(open_interest if open_interest is not None else snapshot.get("open_interest", 0) or 0),
        lead_contract=lead_contract,
        roll_state=roll_state,
        provider=provider_id,
        event_time=event_time,
        available_time=event_time,
        ingested_time=event_time,
        quality_flags=quality_flags,
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
