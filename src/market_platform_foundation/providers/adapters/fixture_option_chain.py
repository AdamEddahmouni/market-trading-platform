"""Fixture-first option chain provider (O1 — canonical OptionContract wiring)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..contracts import ProviderResult
from .fixture_options import DEFAULT_OPTIONS_FIXTURE, FixtureOptionsProvider
from .option_contract_builder import activities_to_chain_dicts

NVDA_OPTIONS_FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "providers"
    / "options"
    / "nvda_options_slice.json"
)


class FixtureOptionChainProvider:
    """Offline option chain adapter returning canonical OptionContract dicts."""

    provider_id = "options.fixture.chain"
    capability = "option_chain"

    def __init__(self, *, fixture_paths: tuple[Path, ...] | None = None) -> None:
        paths = fixture_paths or (DEFAULT_OPTIONS_FIXTURE, NVDA_OPTIONS_FIXTURE)
        self._providers = [FixtureOptionsProvider(fixture_path=path) for path in paths]

    def fetch_chain(self, symbol: str, *, expiration: str | None = None) -> ProviderResult:
        symbol_upper = symbol.upper()
        for provider in self._providers:
            fixture = provider._fixture
            fixture_symbol = str(fixture.get("symbol", "")).upper()
            if fixture_symbol != symbol_upper:
                continue
            activities = fixture.get("activities", [])
            if not isinstance(activities, list):
                continue
            filtered = activities
            if expiration:
                filtered = [
                    row
                    for row in activities
                    if isinstance(row, dict) and str(row.get("expiry", "")) == expiration
                ]
            contracts = activities_to_chain_dicts(
                filtered,
                symbol=fixture_symbol,
                fixture_id=str(fixture.get("fixture_id", "FIXTURE-OPTIONS")),
                provider_id=self.provider_id,
            )
            if not contracts:
                continue
            return ProviderResult(
                status="available",
                events=tuple(contracts),
                provider_id=self.provider_id,
                capability=self.capability,
            )
        return ProviderResult(
            status="unavailable",
            reason_code="OPTION_CHAIN_SYMBOL_NOT_IN_FIXTURE",
            provider_id=self.provider_id,
            capability=self.capability,
        )


__all__ = ["FixtureOptionChainProvider", "NVDA_OPTIONS_FIXTURE"]
