"""Fixture-first public catalyst adapter (PORT_ADAPT from catalyst_lane concepts)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ...contracts.identity import normalized_event_id
from ...donor_patterns.catalyst_lane import (
    confidence_score,
    gate_catalyst,
    lean_direction,
    lean_to_direction_label,
)
from ...normalization.equity_bars import iso_to_epoch_ns
from ..contracts import ProviderResult, SymbolMapping
from ..envelope import (
    build_catalyst_envelope,
    build_provider_metadata,
    catalyst_to_event,
)

DEFAULT_CATALYST_FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "providers"
    / "catalyst"
    / "boxl_catalyst_slice.json"
)


class FixtureCatalystProvider:
    """Offline public-catalyst adapter using bounded BOXL demo slice."""

    provider_id = "catalyst.fixture.activity"
    capability = "public_catalyst"
    entitlement = "CATALYST_DEMO_FIXTURE"

    def __init__(self, *, fixture_path: Path | None = None, ingest_run_id: str | None = None) -> None:
        self.fixture_path = fixture_path or DEFAULT_CATALYST_FIXTURE
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
            raise ValueError("CATALYST_FIXTURE_INVALID")
        return payload

    def fetch_catalyst_activity(
        self,
        symbol: str,
        *,
        as_of_time_ns: int | None = None,
    ) -> ProviderResult:
        fixture_symbol = str(self._fixture.get("symbol", "")).upper()
        if symbol.upper() != fixture_symbol:
            return ProviderResult(
                status="unavailable",
                reason_code="CATALYST_SYMBOL_NOT_IN_FIXTURE",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        events = self.build_envelopes(as_of_time_ns=as_of_time_ns)
        if not events:
            return ProviderResult(
                status="unavailable",
                reason_code="CATALYST_NO_ELIGIBLE_EVENTS",
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
        catalysts = self._fixture.get("catalysts", [])
        if not isinstance(catalysts, list):
            return []
        min_confidence = float(self._fixture.get("min_confidence", 0.5))
        envelopes: list[dict[str, Any]] = []
        for index, row in enumerate(catalysts):
            if not isinstance(row, dict):
                continue
            event_time = str(row.get("event_time", ""))
            if not event_time:
                continue
            available_time_ns = iso_to_epoch_ns(event_time)
            if as_of_time_ns is not None and available_time_ns > as_of_time_ns:
                continue
            confidence = confidence_score(
                news_score=float(row.get("news_score", 0.0)),
                social_score=float(row.get("social_score", 0.0)),
                volume_score=float(row.get("volume_score", 0.0)),
            )
            lean = lean_direction(signed_score=float(row.get("signed_score", 0.0)))
            liquidity_ok = bool(row.get("liquidity_ok", True))
            gate_ok, gate_reasons = gate_catalyst(
                confidence=confidence,
                min_confidence=min_confidence,
                lean=lean,
                liquidity_ok=liquidity_ok,
            )
            catalyst_type = str(row.get("catalyst_type", "unknown"))
            source_record_id = f"{event_time}:{catalyst_type}:{index}"
            whale_event = catalyst_to_event(
                event_time=event_time,
                catalyst_type=catalyst_type,
                headline=str(row.get("headline", "")),
                source=str(row.get("source", "unknown")),
                confidence=confidence,
                lean=lean,
                direction_label=lean_to_direction_label(lean),
                gate_ok=gate_ok,
                gate_reasons=gate_reasons,
                signal_source=str(row.get("signal_source", "news_momentum")),
            )
            normalized_id = normalized_event_id(
                provider_id=self.provider_id,
                venue_id="US_EQUITY",
                publisher_id="CATALYST_FIXTURE",
                channel_id=symbol,
                source_instance_id=str(self._fixture.get("fixture_id", "FIXTURE-CATALYST")),
                source_record_id=source_record_id,
                source_revision_id="1",
                event_family="CATALYST_EVENT",
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
                build_catalyst_envelope(
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
    "DEFAULT_CATALYST_FIXTURE",
    "FixtureCatalystProvider",
]
