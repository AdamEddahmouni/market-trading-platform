"""Fixture-first order-book adapter (PORT_ADAPT from Eric_futuresX ladder concepts)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ...contracts.identity import normalized_event_id
from ...donor_patterns.order_book_lane import (
    best_bid_ask,
    book_pressure_side,
    depth_imbalance,
    direction_from_imbalance,
    snapshot_ofi,
)
from ...normalization.equity_bars import iso_to_epoch_ns
from ..contracts import ProviderResult, SymbolMapping
from ..envelope import (
    build_order_book_envelope,
    build_provider_metadata,
    snapshot_to_order_book_event,
)

DEFAULT_ORDER_BOOK_FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "providers"
    / "order_book"
    / "nvda_depth_slice.json"
)


class FixtureOrderBookProvider:
    """Offline order-book adapter using bounded NVDA depth demo slice."""

    provider_id = "depth.fixture.order_book"
    capability = "order_book"
    entitlement = "L2_DEMO_FIXTURE"

    def __init__(self, *, fixture_path: Path | None = None, ingest_run_id: str | None = None) -> None:
        self.fixture_path = fixture_path or DEFAULT_ORDER_BOOK_FIXTURE
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
            raise ValueError("ORDER_BOOK_FIXTURE_INVALID")
        return payload

    def fetch_order_book(
        self,
        symbol: str,
        *,
        as_of_time_ns: int | None = None,
    ) -> ProviderResult:
        fixture_symbol = str(self._fixture.get("symbol", "")).upper()
        if symbol.upper() != fixture_symbol:
            return ProviderResult(
                status="unavailable",
                reason_code="ORDER_BOOK_SYMBOL_NOT_IN_FIXTURE",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        events = self.build_envelopes(as_of_time_ns=as_of_time_ns)
        if not events:
            return ProviderResult(
                status="unavailable",
                reason_code="ORDER_BOOK_NO_ELIGIBLE_SNAPSHOTS",
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
        snapshots = self._fixture.get("snapshots", [])
        if not isinstance(snapshots, list):
            return []
        level_count = int(self._fixture.get("level_count", 10))
        imbalance_threshold = float(self._fixture.get("imbalance_threshold", 1.2))
        envelopes: list[dict[str, Any]] = []
        prev_snapshot: dict[str, Any] | None = None
        for index, snapshot in enumerate(snapshots):
            if not isinstance(snapshot, dict):
                continue
            event_time = str(snapshot.get("event_time", ""))
            if not event_time:
                continue
            available_time_ns = iso_to_epoch_ns(event_time)
            if as_of_time_ns is not None and available_time_ns > as_of_time_ns:
                continue
            bids = snapshot.get("bids", [])
            asks = snapshot.get("asks", [])
            if not isinstance(bids, list) or not isinstance(asks, list):
                continue
            bbo = best_bid_ask(snapshot)
            if bbo is None:
                continue
            ratio = depth_imbalance(bids, asks, level_count=level_count)
            ofi_value = 0.0 if prev_snapshot is None else snapshot_ofi(prev_snapshot, snapshot)
            pressure = book_pressure_side(ratio, threshold=imbalance_threshold)
            label = direction_from_imbalance(ratio, threshold=imbalance_threshold)
            source_record_id = f"{event_time}:{index}"
            whale_event = snapshot_to_order_book_event(
                event_time=event_time,
                level_count=level_count,
                best_bid=bbo["bid_price"],
                best_ask=bbo["ask_price"],
                bid_size=bbo["bid_size"],
                ask_size=bbo["ask_size"],
                imbalance_ratio=ratio,
                ofi_value=ofi_value,
                direction_label=label,
                snapshot_provenance=str(snapshot.get("source", "fixture_synthetic")),
                book_pressure_side=pressure,
                interpretation_policy="momentum",
            )
            normalized_id = normalized_event_id(
                provider_id=self.provider_id,
                venue_id="US_EQUITY",
                publisher_id="L2_FIXTURE",
                channel_id=symbol,
                source_instance_id=str(self._fixture.get("fixture_id", "FIXTURE-L2")),
                source_record_id=source_record_id,
                source_revision_id="1",
                event_family="ORDER_BOOK_EVENT",
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
                build_order_book_envelope(
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
            prev_snapshot = snapshot
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
    "DEFAULT_ORDER_BOOK_FIXTURE",
    "FixtureOrderBookProvider",
]
