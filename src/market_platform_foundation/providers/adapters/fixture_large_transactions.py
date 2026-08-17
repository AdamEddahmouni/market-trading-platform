"""Fixture-first large-transaction adapter (PORT_ADAPT from large_print_lane concepts)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ...contracts.identity import normalized_event_id
from ...donor_patterns.large_print_lane import direction_label, size_ratio, threshold_gate
from ...normalization.equity_bars import iso_to_epoch_ns
from ..contracts import ProviderResult, SymbolMapping
from ..envelope import (
    build_large_transaction_envelope,
    build_provider_metadata,
    print_to_large_transaction_event,
)

DEFAULT_LARGE_TRANSACTIONS_FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "providers"
    / "large_transactions"
    / "nvda_large_prints_slice.json"
)


class FixtureLargeTransactionsProvider:
    """Offline large-print adapter using bounded NVDA demo slice."""

    provider_id = "large_prints.fixture.activity"
    capability = "large_transactions"
    entitlement = "LARGE_PRINTS_DEMO_FIXTURE"

    def __init__(self, *, fixture_path: Path | None = None, ingest_run_id: str | None = None) -> None:
        self.fixture_path = fixture_path or DEFAULT_LARGE_TRANSACTIONS_FIXTURE
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
            raise ValueError("LARGE_TRANSACTIONS_FIXTURE_INVALID")
        return payload

    def fetch_large_transactions(
        self,
        symbol: str,
        *,
        as_of_time_ns: int | None = None,
    ) -> ProviderResult:
        fixture_symbol = str(self._fixture.get("symbol", "")).upper()
        if symbol.upper() != fixture_symbol:
            return ProviderResult(
                status="unavailable",
                reason_code="LARGE_TRANSACTIONS_SYMBOL_NOT_IN_FIXTURE",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        events = self.build_envelopes(as_of_time_ns=as_of_time_ns)
        if not events:
            return ProviderResult(
                status="unavailable",
                reason_code="LARGE_TRANSACTIONS_NO_ELIGIBLE_PRINTS",
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
        prints = self._fixture.get("prints", [])
        if not isinstance(prints, list):
            return []
        min_ratio = float(self._fixture.get("min_size_ratio", 0.5))
        envelopes: list[dict[str, Any]] = []
        for print_row in prints:
            if not isinstance(print_row, dict):
                continue
            event_time = str(print_row.get("event_time", ""))
            if not event_time:
                continue
            available_time_ns = iso_to_epoch_ns(event_time)
            if as_of_time_ns is not None and available_time_ns > as_of_time_ns:
                continue
            print_size = float(print_row.get("print_size", 0.0))
            reference_value = float(print_row.get("reference_value", 0.0))
            ratio = size_ratio(print_size, reference_value)
            gate_ok, gate_reasons = threshold_gate(ratio, min_ratio=min_ratio)
            side = str(print_row.get("side", "unknown"))
            label = direction_label(side, ratio, gate_ok=gate_ok)
            price = float(print_row.get("price", 0.0))
            source_record_id = f"{event_time}:{print_size}:{price}:{side}"
            whale_event = print_to_large_transaction_event(
                event_time=event_time,
                print_size=print_size,
                price=price,
                side=side,
                reference_type=str(print_row.get("reference_type", "rolling_volume")),
                reference_value=reference_value,
                size_ratio_value=ratio,
                threshold_ok=gate_ok,
                threshold_reasons=gate_reasons,
                direction_label=label,
                aggressor_provenance=str(print_row.get("aggressor_provenance", "unknown")),
                source=str(print_row.get("source", "unknown")),
            )
            normalized_id = normalized_event_id(
                provider_id=self.provider_id,
                venue_id="US_EQUITY",
                publisher_id="LARGE_PRINTS_FIXTURE",
                channel_id=symbol,
                source_instance_id=str(self._fixture.get("fixture_id", "FIXTURE-LARGE-PRINTS")),
                source_record_id=source_record_id,
                source_revision_id="1",
                event_family="LARGE_TRANSACTION_EVENT",
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
                build_large_transaction_envelope(
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
    "DEFAULT_LARGE_TRANSACTIONS_FIXTURE",
    "FixtureLargeTransactionsProvider",
]
