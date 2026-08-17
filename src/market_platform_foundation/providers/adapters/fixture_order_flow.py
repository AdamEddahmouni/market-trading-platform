"""Fixture-first order-flow adapter (PORT_ADAPT from CVD Bubble candle shape)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ...contracts.identity import normalized_event_id
from ...donor_patterns.cvd_formulas import cumulative_delta
from ...normalization.equity_bars import iso_to_epoch_ns
from ..contracts import ProviderResult, SymbolMapping
from ..envelope import (
    bar_to_order_flow_event,
    build_order_flow_envelope,
    build_provider_metadata,
)

DEFAULT_ORDER_FLOW_FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "providers"
    / "order_flow"
    / "nvda_order_flow_slice.json"
)


def _aggressor_provenance(*, quality: str, delta: float) -> str:
    if quality in {"tick", "mixed"}:
        return "known"
    if quality == "neutral" and delta == 0:
        return "unknown"
    return "inferred"


class FixtureOrderFlowProvider:
    """Offline order-flow adapter using bounded NVDA CVD demo slice."""

    provider_id = "cvd.fixture.order_flow"
    capability = "order_flow"
    entitlement = "CVD_DEMO_FIXTURE"

    def __init__(self, *, fixture_path: Path | None = None, ingest_run_id: str | None = None) -> None:
        self.fixture_path = fixture_path or DEFAULT_ORDER_FLOW_FIXTURE
        self.ingest_run_id = ingest_run_id or sha256_bytes(
            canonical_bytes({"fixture_path": str(self.fixture_path), "provider": self.provider_id})
        )
        self._fixture = self._load_fixture()

    def _load_fixture(self) -> dict[str, Any]:
        payload = json.loads(
            self.fixture_path.read_text(encoding="utf-8"),
            object_pairs_hook=_pairs_no_duplicates,
        )
        if not isinstance(payload, dict):
            raise ValueError("ORDER_FLOW_FIXTURE_INVALID")
        return payload

    def fetch_order_flow(
        self,
        symbol: str,
        *,
        as_of_time_ns: int | None = None,
    ) -> ProviderResult:
        fixture_symbol = str(self._fixture.get("symbol", "")).upper()
        if symbol.upper() != fixture_symbol:
            return ProviderResult(
                status="unavailable",
                reason_code="ORDER_FLOW_SYMBOL_NOT_IN_FIXTURE",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        events = self.build_envelopes(as_of_time_ns=as_of_time_ns)
        if not events:
            return ProviderResult(
                status="unavailable",
                reason_code="ORDER_FLOW_NO_ELIGIBLE_BARS",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        return ProviderResult(
            status="available",
            events=tuple(events),
            provider_id=self.provider_id,
            capability=self.capability,
        )

    def build_envelopes(self, *, as_of_time_ns: int | None = None) -> list[dict[str, Any]]:
        symbol = str(self._fixture["symbol"]).upper()
        instrument_id = symbol
        mapping = SymbolMapping(provider_symbol=symbol, instrument_id=instrument_id)
        bars = self._fixture.get("bars", [])
        if not isinstance(bars, list):
            return []
        deltas: list[float] = []
        for bar in bars:
            if isinstance(bar, dict):
                deltas.append(float(bar.get("delta", 0.0)))
        cvd_series = cumulative_delta(deltas)
        envelopes: list[dict[str, Any]] = []
        for index, bar in enumerate(bars):
            if not isinstance(bar, dict):
                continue
            bar_time = str(bar.get("date", ""))
            if not bar_time:
                continue
            available_time_ns = iso_to_epoch_ns(bar_time)
            if as_of_time_ns is not None and available_time_ns > as_of_time_ns:
                continue
            delta = float(bar.get("delta", 0.0))
            quality = str(bar.get("quality", "bvc"))
            source = str(bar.get("source", "unknown"))
            source_record_id = f"{bar_time}:{index}"
            whale_event = bar_to_order_flow_event(
                bar_time=bar_time,
                delta=delta,
                cumulative_delta=cvd_series[index],
                volume=float(bar.get("volume", 0.0)),
                quality=quality,
                source=source,
                aggressor_provenance=_aggressor_provenance(quality=quality, delta=delta),
                source_revision_id="1",
            )
            normalized_id = normalized_event_id(
                provider_id=self.provider_id,
                venue_id="US_EQUITY",
                publisher_id="CVD_FIXTURE",
                channel_id=symbol,
                source_instance_id=str(self._fixture.get("fixture_id", "FIXTURE-ORDER-FLOW")),
                source_record_id=source_record_id,
                source_revision_id="1",
                event_family="ORDER_FLOW_EVENT",
            )
            provider_metadata = build_provider_metadata(
                provider_id=self.provider_id,
                entitlement=self.entitlement,
                event_time_ns=available_time_ns,
                receive_time_ns=available_time_ns,
                symbol_mapping=mapping,
                raw_source_reference=f"{self.fixture_path.name}:{source_record_id}",
            )
            envelopes.append(
                build_order_flow_envelope(
                    normalized_event_id=normalized_id,
                    source_record_id=source_record_id,
                    instrument_id=instrument_id,
                    event_time_ns=available_time_ns,
                    available_time_ns=available_time_ns,
                    ingest_run_id=self.ingest_run_id,
                    provider_metadata=provider_metadata,
                    whale_event=whale_event,
                )
            )
        return _sort_envelopes(envelopes)


def _sort_envelopes(envelopes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        envelopes,
        key=lambda row: (
            int(row["available_time"]),
            str(row["source_record_id"]),
            str(row["source_revision_id"]),
        ),
    )


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


__all__ = [
    "DEFAULT_ORDER_FLOW_FIXTURE",
    "FixtureOrderFlowProvider",
]
