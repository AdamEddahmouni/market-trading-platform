"""Fixture/JSONL equity quote adapter — no vendor SDK."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...market_data.capture import read_envelopes
from ...market_data.normalization import live_envelope_from_capture, replay_envelope_from_capture
from ..contracts import ProviderResult


class CapturedEquityQuoteProvider:
    """Serves captured observational snapshots. Not an admitted dataset."""

    provider_id = "moomoo.captured.equity_quote"
    capability = "US_EQUITY_SNAPSHOT"

    def __init__(self, *, capture_path: Path, acquisition_mode: str = "historical") -> None:
        self.capture_path = capture_path
        self.acquisition_mode = acquisition_mode

    def fetch_quote(self, symbol: str) -> ProviderResult:
        wanted = symbol.upper()
        events: list[dict[str, Any]] = []
        for record in read_envelopes(self.capture_path):
            instrument = str(record.get("instrument_id") or "").upper()
            provider_symbol = str(record.get("provider_symbol") or "").upper()
            if wanted not in {instrument, provider_symbol, provider_symbol.split(".")[-1]}:
                continue
            if self.acquisition_mode == "live":
                events.append(live_envelope_from_capture(record))
            else:
                events.append(replay_envelope_from_capture(record))
        if not events:
            return ProviderResult(
                status="unavailable",
                reason_code="CAPTURE_NOT_FOUND",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        return ProviderResult(
            status="available",
            events=tuple(events),
            provider_id=self.provider_id,
            capability=self.capability,
        )
