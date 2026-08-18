"""Fixture-first options activity adapter (PORT_ADAPT from options_lane concepts)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ...contracts.identity import normalized_event_id
from ...donor_patterns.options_lane import confirmation_score, liquidity_gate
from ...normalization.equity_bars import iso_to_epoch_ns
from ..contracts import ProviderResult, SymbolMapping
from ..envelope import (
    activity_to_options_event,
    build_options_envelope,
    build_provider_metadata,
)
from ...contracts.options import option_contract_to_dict
from .option_contract_builder import activity_to_option_contract

DEFAULT_OPTIONS_FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "providers"
    / "options"
    / "biya_options_slice.json"
)


class FixtureOptionsProvider:
    """Offline options-activity adapter using bounded BIYA demo slice."""

    provider_id = "options.fixture.activity"
    capability = "options_activity"
    entitlement = "OPTIONS_DEMO_FIXTURE"

    def __init__(self, *, fixture_path: Path | None = None, ingest_run_id: str | None = None) -> None:
        self.fixture_path = fixture_path or DEFAULT_OPTIONS_FIXTURE
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
            raise ValueError("OPTIONS_FIXTURE_INVALID")
        return payload

    def fetch_options_activity(
        self,
        symbol: str,
        *,
        as_of_time_ns: int | None = None,
    ) -> ProviderResult:
        fixture_symbol = str(self._fixture.get("symbol", "")).upper()
        if symbol.upper() != fixture_symbol:
            return ProviderResult(
                status="unavailable",
                reason_code="OPTIONS_SYMBOL_NOT_IN_FIXTURE",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        events = self.build_envelopes(as_of_time_ns=as_of_time_ns)
        if not events:
            return ProviderResult(
                status="unavailable",
                reason_code="OPTIONS_NO_ELIGIBLE_ACTIVITY",
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
        activities = self._fixture.get("activities", [])
        if not isinstance(activities, list):
            return []
        envelopes: list[dict[str, Any]] = []
        for index, activity in enumerate(activities):
            if not isinstance(activity, dict):
                continue
            event_time = str(activity.get("event_time", ""))
            if not event_time:
                continue
            available_time_ns = iso_to_epoch_ns(event_time)
            if as_of_time_ns is not None and available_time_ns > as_of_time_ns:
                continue
            bid = float(activity.get("bid", 0.0))
            ask = float(activity.get("ask", 0.0))
            open_interest = int(activity.get("open_interest", 0))
            liquidity_ok, liquidity_reasons = liquidity_gate(
                bid=bid,
                ask=ask,
                open_interest=open_interest,
            )
            iv_rank = float(activity.get("iv_rank", 0.0))
            volume_ratio = float(activity.get("volume_ratio", 0.0))
            skew_signal = float(activity.get("skew_signal", 0.0))
            score = confirmation_score(
                iv_rank=iv_rank,
                volume_ratio=volume_ratio,
                skew_signal=skew_signal,
            )
            strike = float(activity.get("strike", 0.0))
            expiry = str(activity.get("expiry", ""))
            option_type = str(activity.get("option_type", "call"))
            source_record_id = f"{event_time}:{strike}:{expiry}:{option_type}"
            whale_event = activity_to_options_event(
                event_time=event_time,
                strike=strike,
                expiry=expiry,
                option_type=option_type,
                volume=int(activity.get("volume", 0)),
                open_interest=open_interest,
                volume_oi_ratio=float(activity.get("volume_oi_ratio", 0.0)),
                iv_rank=iv_rank,
                bid=bid,
                ask=ask,
                liquidity_ok=liquidity_ok,
                liquidity_reasons=liquidity_reasons,
                confirmation_score=score,
                direction_label=str(activity.get("direction_label", "ambiguous")),
                volume_ratio=volume_ratio,
                skew_signal=skew_signal,
                source=str(activity.get("source", "unknown")),
            )
            canonical = activity_to_option_contract(
                activity,
                symbol=symbol,
                fixture_id=str(self._fixture.get("fixture_id", "FIXTURE-OPTIONS")),
                provider_id=self.provider_id,
            )
            whale_event["canonical_contract"] = option_contract_to_dict(canonical)
            normalized_id = normalized_event_id(
                provider_id=self.provider_id,
                venue_id="US_EQUITY",
                publisher_id="OPTIONS_FIXTURE",
                channel_id=symbol,
                source_instance_id=str(self._fixture.get("fixture_id", "FIXTURE-OPTIONS")),
                source_record_id=source_record_id,
                source_revision_id="1",
                event_family="OPTIONS_EVENT",
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
                build_options_envelope(
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
    "DEFAULT_OPTIONS_FIXTURE",
    "FixtureOptionsProvider",
]
