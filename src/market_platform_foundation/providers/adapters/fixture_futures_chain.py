"""Fixture-first futures chain provider (F1 — canonical FuturesContract wiring)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..contracts import ProviderResult
from .fixture_futures import DEFAULT_FUTURES_FIXTURE, FixtureFuturesProvider
from .futures_contract_builder import contract_to_chain_dict, snapshot_to_futures_contract


class FixtureFuturesChainProvider:
    """Offline futures chain adapter returning canonical FuturesContract dicts."""

    provider_id = "depth.fixture.futures_chain"
    capability = "futures_chain"

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
        snapshots = fixture.get("snapshots", [])
        if not isinstance(snapshots, list) or not snapshots:
            return ProviderResult(
                status="unavailable",
                reason_code="FUTURES_CHAIN_NO_SNAPSHOTS",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        contract_month = str(fixture.get("contract_month", ""))
        exchange = str(fixture.get("exchange", "CME"))
        fixture_id = str(fixture.get("fixture_id", "FIXTURE-L2-ES"))
        contracts: list[dict[str, Any]] = []
        for snapshot in snapshots:
            if not isinstance(snapshot, dict):
                continue
            event_time = str(snapshot.get("event_time", ""))
            if not event_time:
                continue
            contract = snapshot_to_futures_contract(
                snapshot,
                symbol=fixture_symbol,
                contract_month=contract_month,
                exchange=exchange,
                fixture_id=fixture_id,
                provider_id=self.provider_id,
                event_time=event_time,
            )
            if contract is not None:
                contracts.append(contract_to_chain_dict(contract))
        if not contracts:
            return ProviderResult(
                status="unavailable",
                reason_code="FUTURES_CHAIN_NO_CONTRACTS",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        return ProviderResult(
            status="available",
            events=tuple(contracts),
            provider_id=self.provider_id,
            capability=self.capability,
        )


__all__ = ["FixtureFuturesChainProvider"]
