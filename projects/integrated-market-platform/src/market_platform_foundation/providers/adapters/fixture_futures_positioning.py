"""Fixture-first COT / futures positioning adapter (F4)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...normalization.equity_bars import iso_to_epoch_ns
from ..contracts import ProviderResult

DEFAULT_COT_FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "providers"
    / "futures"
    / "es_cot_positioning_slice.json"
)


class FixtureFuturesPositioningProvider:
    """Offline COT positioning adapter returning report rows for PIT filtering."""

    provider_id = "cot.fixture.futures_positioning"
    capability = "futures_positioning"
    entitlement = "COT_ES_DEMO_FIXTURE"

    def __init__(self, *, fixture_path: Path | None = None) -> None:
        path = fixture_path or DEFAULT_COT_FIXTURE
        self._fixture = json.loads(path.read_text(encoding="utf-8"))

    def fetch_positioning(
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
                reason_code="COT_SYMBOL_NOT_IN_FIXTURE",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        reports = self._fixture.get("reports", [])
        if not isinstance(reports, list) or not reports:
            return ProviderResult(
                status="unavailable",
                reason_code="COT_NO_REPORTS",
                provider_id=self.provider_id,
                capability=self.capability,
            )

        eligible: list[dict[str, Any]] = []
        for report in reports:
            if not isinstance(report, dict):
                continue
            pub_time = str(report.get("publication_time", ""))
            if as_of_time_ns is not None and pub_time:
                if iso_to_epoch_ns(pub_time) > as_of_time_ns:
                    continue
            eligible.append(dict(report))

        if not eligible:
            return ProviderResult(
                status="unavailable",
                reason_code="COT_NOT_PIT_ELIGIBLE",
                provider_id=self.provider_id,
                capability=self.capability,
            )

        return ProviderResult(
            status="available",
            events=tuple(eligible),
            provider_id=self.provider_id,
            capability=self.capability,
        )


__all__ = ["DEFAULT_COT_FIXTURE", "FixtureFuturesPositioningProvider"]
