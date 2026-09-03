"""Fixture-first fund/ETF cross-asset adapter (synthetic flow proxy semantics)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ...contracts.identity import normalized_event_id
from ...donor_patterns.fund_etf_lane import flow_direction_label
from ...normalization.equity_bars import iso_to_epoch_ns
from ..contracts import ProviderResult, SymbolMapping
from ..envelope import (
    build_fund_etf_envelope,
    build_provider_metadata,
    event_to_fund_etf_event,
)

DEFAULT_FUND_ETF_FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "providers"
    / "fund_etf"
    / "nvda_fund_etf_slice.json"
)


class FixtureFundEtfProvider:
    """Offline fund/ETF cross-asset adapter using bounded NVDA demo slice."""

    provider_id = "fund_etf.fixture.activity"
    capability = "fund_etf_cross_asset"
    entitlement = "FUND_ETF_DEMO_FIXTURE"

    def __init__(self, *, fixture_path: Path | None = None, ingest_run_id: str | None = None) -> None:
        self.fixture_path = fixture_path or DEFAULT_FUND_ETF_FIXTURE
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
            raise ValueError("FUND_ETF_FIXTURE_INVALID")
        return payload

    def fetch_fund_etf_activity(
        self,
        symbol: str,
        *,
        as_of_time_ns: int | None = None,
    ) -> ProviderResult:
        fixture_symbol = str(self._fixture.get("symbol", "")).upper()
        if symbol.upper() != fixture_symbol:
            return ProviderResult(
                status="unavailable",
                reason_code="FUND_ETF_SYMBOL_NOT_IN_FIXTURE",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        events = self.build_envelopes(as_of_time_ns=as_of_time_ns)
        if not events:
            return ProviderResult(
                status="unavailable",
                reason_code="FUND_ETF_NO_ELIGIBLE_EVENTS",
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
        rows = self._fixture.get("events", [])
        if not isinstance(rows, list):
            return []
        envelopes: list[dict[str, Any]] = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            event_time = str(row.get("event_time", ""))
            available_time = str(row.get("available_time", event_time))
            if not event_time or not available_time:
                continue
            available_time_ns = iso_to_epoch_ns(available_time)
            if as_of_time_ns is not None and available_time_ns > as_of_time_ns:
                continue
            event_type = str(row.get("event_type", "etf_flow_proxy"))
            etf_ticker = str(row.get("etf_ticker", ""))
            flow_proxy = float(row.get("flow_proxy_ratio", 0.0))
            source_record_id = f"{available_time}:{event_type}:{etf_ticker}:{index}"
            whale_event = event_to_fund_etf_event(
                event_time=event_time,
                event_type=event_type,
                etf_ticker=etf_ticker,
                flow_direction=str(row.get("flow_direction", "neutral")),
                flow_proxy_ratio=flow_proxy,
                reference_type=str(row.get("reference_type", "creation_unit_proxy")),
                reference_value=float(row.get("reference_value", 0.0)),
                correlation_20d=float(row.get("correlation_20d", 0.0)),
                regime_label=str(row.get("regime_label", "neutral")),
                direction_label=flow_direction_label(flow_proxy),
                source=str(row.get("source", "unknown")),
            )
            normalized_id = normalized_event_id(
                provider_id=self.provider_id,
                venue_id="US_EQUITY",
                publisher_id="FUND_ETF_FIXTURE",
                channel_id=symbol,
                source_instance_id=str(self._fixture.get("fixture_id", "FIXTURE-FUND-ETF")),
                source_record_id=source_record_id,
                source_revision_id="1",
                event_family="FUND_ETF_EVENT",
            )
            provider_metadata = build_provider_metadata(
                provider_id=self.provider_id,
                entitlement=self.entitlement,
                event_time_ns=iso_to_epoch_ns(event_time),
                receive_time_ns=available_time_ns,
                symbol_mapping=mapping,
                raw_source_reference=f"{self.fixture_path.name}:{source_record_id}",
            )
            envelopes.append(
                build_fund_etf_envelope(
                    normalized_event_id=normalized_id,
                    source_record_id=source_record_id,
                    instrument_id=instrument_id,
                    event_time_ns=iso_to_epoch_ns(event_time),
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
    "DEFAULT_FUND_ETF_FIXTURE",
    "FixtureFundEtfProvider",
]
