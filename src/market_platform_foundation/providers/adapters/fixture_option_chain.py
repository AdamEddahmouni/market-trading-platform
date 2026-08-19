"""Fixture-first option chain provider (O1 — canonical OptionContract wiring).

PIT semantics: chain provider filters activities on event_time (not envelope available_time).
Activity whale path uses available_time on ingested envelopes — see providers/projections.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...normalization.equity_bars import iso_to_epoch_ns
from ..contracts import ProviderResult, SymbolMapping
from ..envelope import enrich_chain_contract_event
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
NVDA_SIGNED_FLOW_FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "providers"
    / "options"
    / "nvda_signed_flow_slice.json"
)
BIYA_ADJUSTED_OPTIONS_FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "providers"
    / "options"
    / "biya_adjusted_option_slice.json"
)


class FixtureOptionChainProvider:
    """Offline option chain adapter returning canonical OptionContract dicts."""

    provider_id = "options.fixture.chain"
    capability = "option_chain"
    entitlement = "OPTIONS_DEMO_FIXTURE"

    def __init__(self, *, fixture_paths: tuple[Path, ...] | None = None) -> None:
        paths = fixture_paths or (
            DEFAULT_OPTIONS_FIXTURE,
            NVDA_OPTIONS_FIXTURE,
            NVDA_SIGNED_FLOW_FIXTURE,
            BIYA_ADJUSTED_OPTIONS_FIXTURE,
        )
        self._providers = [FixtureOptionsProvider(fixture_path=path) for path in paths]

    def fetch_chain(
        self,
        symbol: str,
        *,
        expiration: str | None = None,
        as_of_time_ns: int | None = None,
    ) -> ProviderResult:
        symbol_upper = symbol.upper()
        for provider in self._providers:
            fixture = provider._fixture
            fixture_symbol = str(fixture.get("symbol", "")).upper()
            if fixture_symbol != symbol_upper:
                continue
            activities = fixture.get("activities", [])
            if not isinstance(activities, list):
                continue
            filtered = [
                row
                for row in activities
                if isinstance(row, dict) and _pit_eligible(row, as_of_time_ns)
            ]
            if expiration:
                filtered = [
                    row
                    for row in filtered
                    if str(row.get("expiry", "")) == expiration
                ]
            contracts = activities_to_chain_dicts(
                filtered,
                symbol=fixture_symbol,
                fixture_id=str(fixture.get("fixture_id", "FIXTURE-OPTIONS")),
                provider_id=self.provider_id,
            )
            if not contracts:
                continue
            events = tuple(
                enrich_chain_contract_event(
                    contract,
                    provider_id=self.provider_id,
                    entitlement=self.entitlement,
                    instrument_id=fixture_symbol,
                    event_time_ns=_activity_event_time_ns(contract),
                    receive_time_ns=_activity_event_time_ns(contract),
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
        return ProviderResult(
            status="unavailable",
            reason_code="OPTION_CHAIN_SYMBOL_NOT_IN_FIXTURE",
            provider_id=self.provider_id,
            capability=self.capability,
        )


def _pit_eligible(activity: dict[str, Any], as_of_time_ns: int | None) -> bool:
    if as_of_time_ns is None:
        return True
    event_time = str(activity.get("event_time", ""))
    if not event_time:
        return False
    return iso_to_epoch_ns(event_time) <= as_of_time_ns


def _activity_event_time_ns(contract: dict[str, Any]) -> int:
    event_time = str(contract.get("event_time", ""))
    if not event_time:
        return 0
    return iso_to_epoch_ns(event_time)


__all__ = [
    "BIYA_ADJUSTED_OPTIONS_FIXTURE",
    "FixtureOptionChainProvider",
    "NVDA_OPTIONS_FIXTURE",
    "NVDA_SIGNED_FLOW_FIXTURE",
]
