"""Fixture-first macro calendar adapter for futures (F7)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...normalization.equity_bars import iso_to_epoch_ns
from ..contracts import ProviderResult

DEFAULT_MACRO_FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "providers"
    / "futures"
    / "es_macro_events_slice.json"
)


class FixtureFuturesMacroEventsProvider:
    """Offline macro calendar adapter returning event rows for PIT filtering."""

    provider_id = "macro.fixture.futures_macro"
    capability = "futures_macro_events"
    entitlement = "MACRO_ES_DEMO_FIXTURE"

    def __init__(self, *, fixture_path: Path | None = None) -> None:
        path = fixture_path or DEFAULT_MACRO_FIXTURE
        self._fixture = json.loads(path.read_text(encoding="utf-8"))

    def fetch_macro_events(
        self,
        symbol: str,
        *,
        as_of_time_ns: int | None = None,
    ) -> ProviderResult:
        symbol_upper = symbol.upper()
        fixture_symbol = str(self._fixture.get("symbol", "")).upper()
        if fixture_symbol != symbol_upper:
            return ProviderResult(
                status="unavailable",
                reason_code="MACRO_SYMBOL_NOT_IN_FIXTURE",
                provider_id=self.provider_id,
                capability=self.capability,
            )

        events = self._fixture.get("events", [])
        if not isinstance(events, list) or not events:
            return ProviderResult(
                status="unavailable",
                reason_code="MACRO_NO_EVENTS",
                provider_id=self.provider_id,
                capability=self.capability,
            )

        eligible: list[dict[str, Any]] = []
        for event in events:
            if not isinstance(event, dict):
                continue
            release_time = str(event.get("release_time") or "")
            if as_of_time_ns is not None and release_time:
                if iso_to_epoch_ns(release_time) > as_of_time_ns:
                    continue
            eligible.append(dict(event))

        if not eligible:
            return ProviderResult(
                status="unavailable",
                reason_code="MACRO_NOT_PIT_ELIGIBLE",
                provider_id=self.provider_id,
                capability=self.capability,
            )

        return ProviderResult(
            status="available",
            events=tuple(eligible),
            provider_id=self.provider_id,
            capability=self.capability,
        )
