"""Append-only whale disclosure ledger per ADR-WHALE-002."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from .adapters.edgar_disclosure import DEFAULT_FIXTURE, FixtureEdgarDisclosureProvider, build_edgar_provider
from .composition import ProviderComposition, configure_provider_composition

WHALE_ENTITLED_DISCLOSURE = "WHALE_ENTITLED_DISCLOSURE"
WHALE_ENTITLED_ORDER_FLOW = "WHALE_ENTITLED_ORDER_FLOW"
WHALE_ENTITLED_OPTIONS = "WHALE_ENTITLED_OPTIONS"
WHALE_ENTITLED_LARGE_TRANSACTIONS = "WHALE_ENTITLED_LARGE_TRANSACTIONS"
WHALE_ENTITLED_ORDER_BOOK = "WHALE_ENTITLED_ORDER_BOOK"
WHALE_ENTITLED_FUTURES = "WHALE_ENTITLED_FUTURES"
WHALE_ENTITLED_CATALYST = "WHALE_ENTITLED_CATALYST"
WHALE_ENTITLED_FUND_ETF = "WHALE_ENTITLED_FUND_ETF"
ORDER_FLOW_FAMILY = "order_flow"
OPTIONS_FAMILY = "options"
LARGE_TRANSACTIONS_FAMILY = "large_transactions"
ORDER_BOOK_FAMILY = "order_book"
FUTURES_FAMILY = "futures_positioning"
PUBLIC_CATALYST_FAMILY = "public_catalyst"
FUND_ETF_FAMILY = "fund_etf_cross_asset"
LEDGER_LOGICAL_ID = "providers.whale_ledger"


@dataclass
class WhaleLedger:
    """Deterministic in-memory ledger of disclosure envelopes."""

    events: list[dict[str, Any]] = field(default_factory=list)
    ledger_id: str = ""

    def append(self, new_events: list[dict[str, Any]]) -> int:
        seen = {
            (str(row.get("source_record_id")), str(row.get("source_revision_id")))
            for row in self.events
        }
        added = 0
        for event in new_events:
            key = (str(event.get("source_record_id")), str(event.get("source_revision_id")))
            if key in seen:
                continue
            seen.add(key)
            self.events.append(event)
            added += 1
        self.events = _sort_events(self.events)
        self.ledger_id = self.root_hash()
        return added

    def ingest_provider_result(self, result_events: tuple[dict[str, Any], ...]) -> int:
        return self.append(list(result_events))

    def query_events(
        self,
        *,
        family: str,
        instrument_id: str | None = None,
        prediction_cutoff: int,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for event in self.events:
            payload = _event_payload(event)
            if not isinstance(payload, dict):
                continue
            if str(payload.get("family", "")) != family:
                continue
            if instrument_id is not None and str(event.get("instrument_id")) != instrument_id:
                continue
            if int(event.get("available_time", 0)) > prediction_cutoff:
                continue
            rows.append(event)
        return rows

    def query_disclosure_summaries(
        self,
        *,
        instrument_id: str,
        prediction_cutoff: int,
    ) -> list[dict[str, Any]]:
        events = self.query_events(
            family="regulatory_disclosure",
            instrument_id=instrument_id,
            prediction_cutoff=prediction_cutoff,
        )
        summaries: list[dict[str, Any]] = []
        for event in events:
            disclosure = event.get("disclosure_event")
            if not isinstance(disclosure, dict):
                continue
            summaries.append(
                {
                    "accepted_at": disclosure.get("accepted_at"),
                    "accession_number": disclosure.get("accession_number"),
                    "available_time": int(event.get("available_time", 0)),
                    "disclosure_lag_note": disclosure.get("disclosure_lag_note"),
                    "epistemic_class": disclosure.get("epistemic_class"),
                    "event_type": disclosure.get("event_type"),
                    "filer": disclosure.get("filer"),
                    "form_type": disclosure.get("form_type"),
                    "is_amendment": disclosure.get("is_amendment"),
                    "normalized_event_id": event.get("normalized_event_id"),
                    "research_only": disclosure.get("research_only"),
                    "source_url": disclosure.get("source_url"),
                }
            )
        return summaries

    def query_order_flow_summaries(
        self,
        *,
        instrument_id: str,
        prediction_cutoff: int,
    ) -> list[dict[str, Any]]:
        events = self.query_events(
            family=ORDER_FLOW_FAMILY,
            instrument_id=instrument_id,
            prediction_cutoff=prediction_cutoff,
        )
        summaries: list[dict[str, Any]] = []
        for event in events:
            payload = _event_payload(event)
            if not isinstance(payload, dict):
                continue
            summaries.append(
                {
                    "aggressor_provenance": payload.get("aggressor_provenance"),
                    "available_time": int(event.get("available_time", 0)),
                    "bar_time": payload.get("bar_time"),
                    "cumulative_delta": payload.get("cumulative_delta"),
                    "delta": payload.get("delta"),
                    "epistemic_class": payload.get("epistemic_class"),
                    "normalized_event_id": event.get("normalized_event_id"),
                    "quality": payload.get("quality"),
                    "volume": payload.get("volume"),
                }
            )
        return summaries

    def query_options_summaries(
        self,
        *,
        instrument_id: str,
        prediction_cutoff: int,
    ) -> list[dict[str, Any]]:
        events = self.query_events(
            family=OPTIONS_FAMILY,
            instrument_id=instrument_id,
            prediction_cutoff=prediction_cutoff,
        )
        summaries: list[dict[str, Any]] = []
        for event in events:
            payload = _event_payload(event)
            if not isinstance(payload, dict):
                continue
            summaries.append(
                {
                    "ask": payload.get("ask"),
                    "available_time": int(event.get("available_time", 0)),
                    "bid": payload.get("bid"),
                    "confirmation_score": payload.get("confirmation_score"),
                    "direction_label": payload.get("direction_label"),
                    "epistemic_class": payload.get("epistemic_class"),
                    "event_time": payload.get("event_time"),
                    "expiry": payload.get("expiry"),
                    "iv_rank": payload.get("iv_rank"),
                    "liquidity_ok": payload.get("liquidity_ok"),
                    "liquidity_reasons": payload.get("liquidity_reasons"),
                    "normalized_event_id": event.get("normalized_event_id"),
                    "open_interest": payload.get("open_interest"),
                    "option_type": payload.get("option_type"),
                    "strike": payload.get("strike"),
                    "volume": payload.get("volume"),
                    "volume_oi_ratio": payload.get("volume_oi_ratio"),
                }
            )
        return summaries

    def query_large_transaction_summaries(
        self,
        *,
        instrument_id: str,
        prediction_cutoff: int,
    ) -> list[dict[str, Any]]:
        events = self.query_events(
            family=LARGE_TRANSACTIONS_FAMILY,
            instrument_id=instrument_id,
            prediction_cutoff=prediction_cutoff,
        )
        summaries: list[dict[str, Any]] = []
        for event in events:
            payload = _event_payload(event)
            if not isinstance(payload, dict):
                continue
            summaries.append(
                {
                    "aggressor_provenance": payload.get("aggressor_provenance"),
                    "available_time": int(event.get("available_time", 0)),
                    "direction_label": payload.get("direction_label"),
                    "epistemic_class": payload.get("epistemic_class"),
                    "event_time": payload.get("event_time"),
                    "normalized_event_id": event.get("normalized_event_id"),
                    "price": payload.get("price"),
                    "print_size": payload.get("print_size"),
                    "reference_type": payload.get("reference_type"),
                    "reference_value": payload.get("reference_value"),
                    "side": payload.get("side"),
                    "size_ratio": payload.get("size_ratio"),
                    "threshold_gate_ok": payload.get("threshold_gate_ok"),
                    "threshold_reasons": payload.get("threshold_reasons"),
                }
            )
        return summaries

    def query_order_book_summaries(
        self,
        *,
        instrument_id: str,
        prediction_cutoff: int,
    ) -> list[dict[str, Any]]:
        events = self.query_events(
            family=ORDER_BOOK_FAMILY,
            instrument_id=instrument_id,
            prediction_cutoff=prediction_cutoff,
        )
        summaries: list[dict[str, Any]] = []
        for event in events:
            payload = _event_payload(event)
            if not isinstance(payload, dict):
                continue
            summaries.append(
                {
                    "ask_size": payload.get("ask_size"),
                    "available_time": int(event.get("available_time", 0)),
                    "best_ask": payload.get("best_ask"),
                    "best_bid": payload.get("best_bid"),
                    "bid_size": payload.get("bid_size"),
                    "direction_label": payload.get("direction_label"),
                    "epistemic_class": payload.get("epistemic_class"),
                    "event_time": payload.get("event_time"),
                    "imbalance_ratio": payload.get("imbalance_ratio"),
                    "level_count": payload.get("level_count"),
                    "normalized_event_id": event.get("normalized_event_id"),
                    "ofi_value": payload.get("ofi_value"),
                    "snapshot_provenance": payload.get("snapshot_provenance"),
                }
            )
        return summaries

    def query_futures_summaries(
        self,
        *,
        instrument_id: str,
        prediction_cutoff: int,
    ) -> list[dict[str, Any]]:
        events = self.query_events(
            family=FUTURES_FAMILY,
            instrument_id=instrument_id,
            prediction_cutoff=prediction_cutoff,
        )
        summaries: list[dict[str, Any]] = []
        for event in events:
            payload = _event_payload(event)
            if not isinstance(payload, dict):
                continue
            summaries.append(
                {
                    "ask_size": payload.get("ask_size"),
                    "available_time": int(event.get("available_time", 0)),
                    "best_ask": payload.get("best_ask"),
                    "best_bid": payload.get("best_bid"),
                    "bid_size": payload.get("bid_size"),
                    "contract_month": payload.get("contract_month"),
                    "epistemic_class": payload.get("epistemic_class"),
                    "event_time": payload.get("event_time"),
                    "exchange": payload.get("exchange"),
                    "imbalance_ratio": payload.get("imbalance_ratio"),
                    "imbalance_signal": payload.get("imbalance_signal"),
                    "level_count": payload.get("level_count"),
                    "normalized_event_id": event.get("normalized_event_id"),
                    "ofi_value": payload.get("ofi_value"),
                    "rth": payload.get("rth"),
                    "session_state": payload.get("session_state"),
                    "snapshot_provenance": payload.get("snapshot_provenance"),
                }
            )
        return summaries

    def query_catalyst_summaries(
        self,
        *,
        instrument_id: str,
        prediction_cutoff: int,
    ) -> list[dict[str, Any]]:
        events = self.query_events(
            family=PUBLIC_CATALYST_FAMILY,
            instrument_id=instrument_id,
            prediction_cutoff=prediction_cutoff,
        )
        summaries: list[dict[str, Any]] = []
        for event in events:
            payload = _event_payload(event)
            if not isinstance(payload, dict):
                continue
            summaries.append(
                {
                    "available_time": int(event.get("available_time", 0)),
                    "catalyst_type": payload.get("catalyst_type"),
                    "confidence": payload.get("confidence"),
                    "direction_label": payload.get("direction_label"),
                    "epistemic_class": payload.get("epistemic_class"),
                    "event_time": payload.get("event_time"),
                    "gate_ok": payload.get("gate_ok"),
                    "gate_reasons": payload.get("gate_reasons"),
                    "headline": payload.get("headline"),
                    "lean": payload.get("lean"),
                    "normalized_event_id": event.get("normalized_event_id"),
                    "signal_source": payload.get("signal_source"),
                    "source": payload.get("source"),
                }
            )
        return summaries

    def query_fund_etf_summaries(
        self,
        *,
        instrument_id: str,
        prediction_cutoff: int,
    ) -> list[dict[str, Any]]:
        events = self.query_events(
            family=FUND_ETF_FAMILY,
            instrument_id=instrument_id,
            prediction_cutoff=prediction_cutoff,
        )
        summaries: list[dict[str, Any]] = []
        for event in events:
            payload = _event_payload(event)
            if not isinstance(payload, dict):
                continue
            summaries.append(
                {
                    "available_time": int(event.get("available_time", 0)),
                    "correlation_20d": payload.get("correlation_20d"),
                    "direction_label": payload.get("direction_label"),
                    "epistemic_class": payload.get("epistemic_class"),
                    "etf_ticker": payload.get("etf_ticker"),
                    "event_time": payload.get("event_time"),
                    "event_type": payload.get("event_type"),
                    "flow_direction": payload.get("flow_direction"),
                    "flow_proxy_ratio": payload.get("flow_proxy_ratio"),
                    "normalized_event_id": event.get("normalized_event_id"),
                    "reference_type": payload.get("reference_type"),
                    "reference_value": payload.get("reference_value"),
                    "regime_label": payload.get("regime_label"),
                    "source": payload.get("source"),
                }
            )
        return summaries

    def root_hash(self) -> str:
        body = {
            "events": [
                {
                    "available_time": int(row.get("available_time", 0)),
                    "normalized_event_id": str(row.get("normalized_event_id")),
                    "source_record_id": str(row.get("source_record_id")),
                    "source_revision_id": str(row.get("source_revision_id")),
                }
                for row in self.events
            ],
            "logical_id": LEDGER_LOGICAL_ID,
        }
        return sha256_bytes(canonical_bytes(body))

    def write_jsonl(self, path: Path) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(row, sort_keys=True, separators=(",", ":")) for row in self.events]
        payload = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
        path.write_bytes(payload)
        return sha256_bytes(payload)

    @classmethod
    def from_jsonl(cls, path: Path) -> WhaleLedger:
        ledger = cls()
        if not path.is_file():
            return ledger
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line, object_pairs_hook=_pairs_no_duplicates)
            if isinstance(row, dict):
                ledger.events.append(row)
        ledger.events = _sort_events(ledger.events)
        ledger.ledger_id = ledger.root_hash()
        return ledger


def _event_payload(event: dict[str, Any]) -> dict[str, Any] | None:
    disclosure = event.get("disclosure_event")
    if isinstance(disclosure, dict):
        return disclosure
    whale_event = event.get("whale_event")
    if isinstance(whale_event, dict):
        return whale_event
    return None


def _sort_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        events,
        key=lambda row: (
            int(row.get("available_time", 0)),
            str(row.get("source_record_id", "")),
            str(row.get("source_revision_id", "")),
        ),
    )


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def build_ledger_from_edgar_fixture(
    *,
    fixture_path: Path | None = None,
    as_of_time_ns: int | None = None,
) -> WhaleLedger:
    provider = FixtureEdgarDisclosureProvider(fixture_path=fixture_path)
    symbol = str(provider._fixture.get("symbol", "BIYA"))
    result = provider.fetch_disclosures(symbol, as_of_time_ns=as_of_time_ns)
    ledger = WhaleLedger()
    if result.status == "available":
        ledger.ingest_provider_result(result.events)
    return ledger


def build_combined_fixture_ledger(*, as_of_time_ns: int | None = None) -> WhaleLedger:
    from .adapters.fixture_catalyst import (
        DEFAULT_CATALYST_FIXTURE,
        FixtureCatalystProvider,
    )
    from .adapters.fixture_fund_etf import (
        DEFAULT_FUND_ETF_FIXTURE,
        FixtureFundEtfProvider,
    )
    from .adapters.fixture_futures import (
        DEFAULT_FUTURES_FIXTURE,
        FixtureFuturesProvider,
    )
    from .adapters.fixture_large_transactions import (
        DEFAULT_LARGE_TRANSACTIONS_FIXTURE,
        FixtureLargeTransactionsProvider,
    )
    from .adapters.fixture_order_book import (
        DEFAULT_ORDER_BOOK_FIXTURE,
        FixtureOrderBookProvider,
    )
    from .adapters.fixture_options import (
        DEFAULT_OPTIONS_FIXTURE,
        FixtureOptionsProvider,
    )
    from .adapters.fixture_order_flow import (
        DEFAULT_ORDER_FLOW_FIXTURE,
        FixtureOrderFlowProvider,
    )

    ledger = build_ledger_from_edgar_fixture(as_of_time_ns=as_of_time_ns)
    order_flow = FixtureOrderFlowProvider(fixture_path=DEFAULT_ORDER_FLOW_FIXTURE)
    symbol = str(order_flow._fixture.get("symbol", "NVDA"))
    result = order_flow.fetch_order_flow(symbol, as_of_time_ns=as_of_time_ns)
    if result.status == "available":
        ledger.ingest_provider_result(result.events)
    options = FixtureOptionsProvider(fixture_path=DEFAULT_OPTIONS_FIXTURE)
    options_symbol = str(options._fixture.get("symbol", "BIYA"))
    options_result = options.fetch_options_activity(options_symbol, as_of_time_ns=as_of_time_ns)
    if options_result.status == "available":
        ledger.ingest_provider_result(options_result.events)
    large_transactions = FixtureLargeTransactionsProvider(
        fixture_path=DEFAULT_LARGE_TRANSACTIONS_FIXTURE
    )
    lt_symbol = str(large_transactions._fixture.get("symbol", "NVDA"))
    lt_result = large_transactions.fetch_large_transactions(lt_symbol, as_of_time_ns=as_of_time_ns)
    if lt_result.status == "available":
        ledger.ingest_provider_result(lt_result.events)
    order_book = FixtureOrderBookProvider(fixture_path=DEFAULT_ORDER_BOOK_FIXTURE)
    ob_symbol = str(order_book._fixture.get("symbol", "NVDA"))
    ob_result = order_book.fetch_order_book(ob_symbol, as_of_time_ns=as_of_time_ns)
    if ob_result.status == "available":
        ledger.ingest_provider_result(ob_result.events)
    futures = FixtureFuturesProvider(fixture_path=DEFAULT_FUTURES_FIXTURE)
    es_symbol = str(futures._fixture.get("symbol", "ES"))
    futures_result = futures.fetch_futures_depth(es_symbol, as_of_time_ns=as_of_time_ns)
    if futures_result.status == "available":
        ledger.ingest_provider_result(futures_result.events)
    catalyst = FixtureCatalystProvider(fixture_path=DEFAULT_CATALYST_FIXTURE)
    catalyst_symbol = str(catalyst._fixture.get("symbol", "BOXL"))
    catalyst_result = catalyst.fetch_catalyst_activity(catalyst_symbol, as_of_time_ns=as_of_time_ns)
    if catalyst_result.status == "available":
        ledger.ingest_provider_result(catalyst_result.events)
    fund_etf = FixtureFundEtfProvider(fixture_path=DEFAULT_FUND_ETF_FIXTURE)
    fund_symbol = str(fund_etf._fixture.get("symbol", "NVDA"))
    fund_result = fund_etf.fetch_fund_etf_activity(fund_symbol, as_of_time_ns=as_of_time_ns)
    if fund_result.status == "available":
        ledger.ingest_provider_result(fund_result.events)
    return ledger


def load_default_biya_fixture_ledger(*, as_of_time_ns: int | None = None) -> WhaleLedger:
    return build_ledger_from_edgar_fixture(fixture_path=DEFAULT_FIXTURE, as_of_time_ns=as_of_time_ns)


def bootstrap_default_providers(*, as_of_time_ns: int | None = None) -> WhaleLedger:
    provider = build_edgar_provider()
    composition = ProviderComposition(disclosure=provider)
    configure_provider_composition(composition)
    return build_combined_fixture_ledger(as_of_time_ns=as_of_time_ns)


__all__ = [
    "FUND_ETF_FAMILY",
    "FUTURES_FAMILY",
    "LARGE_TRANSACTIONS_FAMILY",
    "LEDGER_LOGICAL_ID",
    "OPTIONS_FAMILY",
    "ORDER_BOOK_FAMILY",
    "ORDER_FLOW_FAMILY",
    "PUBLIC_CATALYST_FAMILY",
    "WHALE_ENTITLED_CATALYST",
    "WHALE_ENTITLED_DISCLOSURE",
    "WHALE_ENTITLED_FUND_ETF",
    "WHALE_ENTITLED_FUTURES",
    "WHALE_ENTITLED_LARGE_TRANSACTIONS",
    "WHALE_ENTITLED_OPTIONS",
    "WHALE_ENTITLED_ORDER_BOOK",
    "WHALE_ENTITLED_ORDER_FLOW",
    "WhaleLedger",
    "bootstrap_default_providers",
    "build_combined_fixture_ledger",
    "build_ledger_from_edgar_fixture",
    "load_default_biya_fixture_ledger",
]
