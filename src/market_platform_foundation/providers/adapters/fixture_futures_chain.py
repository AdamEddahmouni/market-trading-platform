"""Fixture-first futures chain provider (F1 — canonical FuturesContract wiring)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from ...contracts.futures import (
    FuturesContract,
    FuturesContractSpec,
    FuturesFamily,
    RollState,
    SettlementType,
    futures_contract_to_dict,
)
from ...futures.roll import contract_liquidity_from_dict, select_lead_contract
from ...normalization.equity_bars import iso_to_epoch_ns
from ..envelope import enrich_chain_contract_event
from ..contracts import ProviderResult
from .fixture_futures import DEFAULT_FUTURES_FIXTURE, FixtureFuturesProvider
from .futures_contract_builder import contract_to_chain_dict, snapshot_to_futures_contract


class FixtureFuturesChainProvider:
    """Offline futures chain adapter returning canonical FuturesContract dicts."""

    provider_id = "depth.fixture.futures_chain"
    capability = "futures_chain"
    entitlement = "L2_ES_DEMO_FIXTURE"

    def __init__(self, *, fixture_path: Path | None = None) -> None:
        self._provider = FixtureFuturesProvider(fixture_path=fixture_path or DEFAULT_FUTURES_FIXTURE)

    def fetch_chain(self, symbol: str, *, as_of_time_ns: int | None = None) -> ProviderResult:
        symbol_upper = symbol.upper()
        fixture = self._provider._fixture
        fixture_symbol = str(fixture.get("symbol", "")).upper()
        if fixture_symbol != symbol_upper:
            return ProviderResult(
                status="unavailable",
                reason_code="FUTURES_CHAIN_SYMBOL_NOT_IN_FIXTURE",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        contract_catalog = fixture.get("contracts", [])
        snapshots = fixture.get("snapshots", [])
        if not isinstance(snapshots, list) or not snapshots:
            return ProviderResult(
                status="unavailable",
                reason_code="FUTURES_CHAIN_NO_SNAPSHOTS",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        if as_of_time_ns is not None:
            snapshots = [
                row
                for row in snapshots
                if isinstance(row, dict)
                and row.get("event_time")
                and iso_to_epoch_ns(str(row["event_time"])) <= as_of_time_ns
            ]
            if not snapshots:
                return ProviderResult(
                    status="unavailable",
                    reason_code="FUTURES_CHAIN_NO_PIT_ELIGIBLE",
                    provider_id=self.provider_id,
                    capability=self.capability,
                )
        exchange = str(fixture.get("exchange", "CME"))
        fixture_id = str(fixture.get("fixture_id", "FIXTURE-L2-ES"))
        lead_selection = None
        if isinstance(contract_catalog, list) and contract_catalog:
            liquidity_rows = [
                contract_liquidity_from_dict(row)
                for row in contract_catalog
                if isinstance(row, dict)
            ]
            liquidity_rows = [row for row in liquidity_rows if row is not None]
            if liquidity_rows:
                lead_selection = select_lead_contract(liquidity_rows)

        if isinstance(contract_catalog, list) and len(contract_catalog) >= 2:
            contracts = self._build_from_catalog(
                fixture_symbol,
                contract_catalog,
                snapshots[0],
                exchange=exchange,
                fixture_id=fixture_id,
                lead_selection=lead_selection,
            )
        else:
            contracts = self._build_from_snapshots(
                fixture,
                fixture_symbol,
                snapshots,
                exchange=exchange,
                fixture_id=fixture_id,
                lead_selection=lead_selection,
            )

        if not contracts:
            return ProviderResult(
                status="unavailable",
                reason_code="FUTURES_CHAIN_NO_CONTRACTS",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        events = tuple(
            enrich_chain_contract_event(
                contract,
                provider_id=self.provider_id,
                entitlement=self.entitlement,
                instrument_id=fixture_symbol,
                event_time_ns=iso_to_epoch_ns(str(contract.get("event_time", ""))) if contract.get("event_time") else 0,
                receive_time_ns=iso_to_epoch_ns(str(contract.get("event_time", ""))) if contract.get("event_time") else 0,
                raw_source_reference=str(contract.get("provenance_ref", "")),
                quality_flags=tuple(contract.get("quality_flags", [])),
            )
            for contract in contracts
        )
        return ProviderResult(
            status="available",
            events=events,
            provider_id=self.provider_id,
            capability=self.capability,
        )

    def _build_from_catalog(
        self,
        fixture_symbol: str,
        catalog: list[dict[str, Any]],
        reference_snapshot: dict[str, Any],
        *,
        exchange: str,
        fixture_id: str,
        lead_selection: Any,
    ) -> list[dict[str, Any]]:
        event_time = str(reference_snapshot.get("event_time", ""))
        contracts: list[dict[str, Any]] = []
        for row in catalog:
            if not isinstance(row, dict):
                continue
            contract_id = str(row.get("contract_id", ""))
            if not contract_id:
                continue
            contract_month = contract_id.replace(fixture_symbol, "")
            is_lead = bool(lead_selection and contract_id == lead_selection.lead_contract_id)
            roll_state = lead_selection.roll_state if is_lead and lead_selection else None
            price = row.get("price")
            if price is not None:
                contract = self._contract_from_catalog_row(
                    row,
                    symbol=fixture_symbol,
                    contract_month=contract_month,
                    exchange=exchange,
                    fixture_id=fixture_id,
                    provider_id=self.provider_id,
                    event_time=event_time,
                    lead_contract=is_lead,
                    roll_state=roll_state,
                )
            else:
                contract = snapshot_to_futures_contract(
                    reference_snapshot,
                    symbol=fixture_symbol,
                    contract_month=contract_month,
                    exchange=exchange,
                    fixture_id=fixture_id,
                    provider_id=self.provider_id,
                    event_time=event_time,
                    lead_contract=is_lead,
                    roll_state=roll_state,
                    volume=int(row.get("volume", 0) or 0),
                    open_interest=int(row.get("open_interest", 0) or 0),
                )
            if contract is not None:
                contracts.append(contract_to_chain_dict(contract))
        return contracts

    def _contract_from_catalog_row(
        self,
        row: dict[str, Any],
        *,
        symbol: str,
        contract_month: str,
        exchange: str,
        fixture_id: str,
        provider_id: str,
        event_time: str,
        lead_contract: bool,
        roll_state: RollState | None,
    ) -> FuturesContract | None:
        price = row.get("price")
        if price is None:
            return None
        contract_id = str(row.get("contract_id", f"{symbol}{contract_month}"))
        expiration = str(row.get("expiration", ""))
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
            expiration=expiration,
            settlement_type=SettlementType.CASH,
            settlement_methodology="cash_settlement_index",
            spec=spec,
            price=Decimal(str(price)),
            last_trade_price=Decimal(str(price)),
            volume=int(row.get("volume", 0) or 0),
            open_interest=int(row.get("open_interest", 0) or 0),
            lead_contract=lead_contract,
            roll_state=roll_state,
            provider=provider_id,
            event_time=event_time,
            available_time=event_time,
            ingested_time=event_time,
            provenance_ref=f"{fixture_id}:{contract_id}",
        )

    def _build_from_snapshots(
        self,
        fixture: dict[str, Any],
        fixture_symbol: str,
        snapshots: list[dict[str, Any]],
        *,
        exchange: str,
        fixture_id: str,
        lead_selection: Any,
    ) -> list[dict[str, Any]]:
        contracts: list[dict[str, Any]] = []
        for snapshot in snapshots:
            if not isinstance(snapshot, dict):
                continue
            event_time = str(snapshot.get("event_time", ""))
            if not event_time:
                continue
            contract_month = str(snapshot.get("contract_month", fixture.get("contract_month", "")))
            if lead_selection and contract_month:
                contract_id = f"{fixture_symbol}{contract_month}"
                is_lead = contract_id == lead_selection.lead_contract_id
                roll_state = lead_selection.roll_state if is_lead else None
            else:
                is_lead = contract_month == str(fixture.get("contract_month", ""))
                roll_state = None
            contract = snapshot_to_futures_contract(
                snapshot,
                symbol=fixture_symbol,
                contract_month=contract_month,
                exchange=exchange,
                fixture_id=fixture_id,
                provider_id=self.provider_id,
                event_time=event_time,
                lead_contract=is_lead,
                roll_state=roll_state,
                volume=int(snapshot.get("volume", 0) or 0),
                open_interest=int(snapshot.get("open_interest", 0) or 0),
            )
            if contract is not None:
                contracts.append(contract_to_chain_dict(contract))
        return contracts


__all__ = ["FixtureFuturesChainProvider"]
