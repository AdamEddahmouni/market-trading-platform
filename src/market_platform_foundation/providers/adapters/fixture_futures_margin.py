"""Fixture-first CME margin history adapter for futures (F8)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...normalization.equity_bars import iso_to_epoch_ns
from ..contracts import ProviderResult

DEFAULT_MARGIN_FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "providers"
    / "futures"
    / "es_margin_history_slice.json"
)


class FixtureFuturesMarginProvider:
    """Offline margin history adapter returning rows for PIT filtering."""

    provider_id = "margin.fixture.futures_margin"
    capability = "futures_margin"
    entitlement = "MARGIN_ES_DEMO_FIXTURE"

    def __init__(self, *, fixture_path: Path | None = None) -> None:
        path = fixture_path or DEFAULT_MARGIN_FIXTURE
        self._fixture = json.loads(path.read_text(encoding="utf-8"))

    def fetch_margin(
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
                reason_code="MARGIN_SYMBOL_NOT_IN_FIXTURE",
                provider_id=self.provider_id,
                capability=self.capability,
            )

        rows = self._fixture.get("margin_history", [])
        if not isinstance(rows, list) or not rows:
            return ProviderResult(
                status="unavailable",
                reason_code="MARGIN_NO_ROWS",
                provider_id=self.provider_id,
                capability=self.capability,
            )

        eligible: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            available_time = str(row.get("available_time") or row.get("observation_time") or "")
            if as_of_time_ns is not None and available_time:
                if iso_to_epoch_ns(available_time) > as_of_time_ns:
                    continue
            eligible.append(dict(row))

        if not eligible:
            return ProviderResult(
                status="unavailable",
                reason_code="MARGIN_NOT_PIT_ELIGIBLE",
                provider_id=self.provider_id,
                capability=self.capability,
            )

        return ProviderResult(
            status="available",
            events=tuple(eligible),
            provider_id=self.provider_id,
            capability=self.capability,
        )
