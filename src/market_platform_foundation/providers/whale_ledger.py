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
            disclosure = event.get("disclosure_event")
            if not isinstance(disclosure, dict):
                continue
            if str(disclosure.get("family", "")) != family:
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


def load_default_biya_fixture_ledger(*, as_of_time_ns: int | None = None) -> WhaleLedger:
    return build_ledger_from_edgar_fixture(fixture_path=DEFAULT_FIXTURE, as_of_time_ns=as_of_time_ns)


def bootstrap_default_providers(*, as_of_time_ns: int | None = None) -> WhaleLedger:
    provider = build_edgar_provider()
    composition = ProviderComposition(disclosure=provider)
    configure_provider_composition(composition)
    symbol = "BIYA"
    result = provider.fetch_disclosures(symbol, as_of_time_ns=as_of_time_ns)
    ledger = WhaleLedger()
    if result.status == "available":
        ledger.ingest_provider_result(result.events)
    return ledger


__all__ = [
    "LEDGER_LOGICAL_ID",
    "WHALE_ENTITLED_DISCLOSURE",
    "WhaleLedger",
    "bootstrap_default_providers",
    "build_ledger_from_edgar_fixture",
    "load_default_biya_fixture_ledger",
]
