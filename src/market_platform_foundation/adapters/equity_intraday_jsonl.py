"""Offline adapter for admitted equity intraday JSONL bars."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from ..contracts.identity import normalized_event_id
from ..normalization.equity_bars import iso_to_epoch_ns

COLLECTION_RELATIVE_PATH = (
    "short-squeeze-project/short-squeeze-core/tests/fixtures/validation/"
    "outcome_amendment/biya_market_bars_intraday.jsonl"
)
PINNED_SHA256 = "6895533AA441AE309BD944AE9AD2ACAB81B348CE972DB7E4287BCFF264389E3A"
SOURCE_OBJECT_ID = "ADMITTED-SHORTSQ-BIYA-BARS-001"
NORMALIZATION_VERSION = "phase3.equity-intraday-jsonl/1.0.0"
SCHEMA_VERSION = "1.0.0"
SUPPORTED_CAPABILITIES = frozenset({"BAR_OHLCV_1M", "EQUITY_INTRADAY_SESSION_LABELS"})

PROHIBITED_REGISTRY_IDS = frozenset(
    {
        "live.market_data",
        "live.execution",
        "broker.ibkr",
        "broker.any",
    }
)


@dataclass
class AdapterResult:
    canonical_events: list[dict[str, Any]] = field(default_factory=list)
    quarantined: list[dict[str, Any]] = field(default_factory=list)
    provenance_index: dict[str, str] = field(default_factory=dict)
    idempotent_replays: int = 0
    conflict_count: int = 0
    dangling_count: int = 0
    record_count: int = 0


class EquityIntradayJsonlAdapter:
    """Read-only adapter for the admitted Short Squeeze equity bar fixture."""

    registry_id = "offline.equity_intraday_jsonl"

    def __init__(self, *, ingest_run_id: str) -> None:
        self.ingest_run_id = ingest_run_id
        self._identity_hashes: dict[str, str] = {}

    def verify_source_bytes(self, path: Path) -> list[str]:
        reasons: list[str] = []
        if not path.is_file():
            reasons.append("ADP_SOURCE_MISSING")
            return reasons
        observed = sha256_bytes(path.read_bytes())
        if observed != PINNED_SHA256:
            reasons.append("ADP_SOURCE_HASH_MISMATCH")
        return reasons

    def normalize_record(self, record: dict[str, Any], *, line_number: int) -> dict[str, Any] | None:
        if str(record.get("event_type")) != "BAR":
            return None
        payload = record.get("payload")
        if not isinstance(payload, dict):
            return None
        if str(payload.get("timeframe")) != "1_MINUTE":
            return None
        provenance = record.get("provenance")
        if not isinstance(provenance, dict):
            return None
        provider_metadata = provenance.get("provider_metadata")
        if not isinstance(provider_metadata, dict):
            return None
        source_record_id = str(record.get("source_record_id", ""))
        if not source_record_id:
            return None
        raw_hash = str(record.get("raw_payload_hash", ""))
        bar_end = str(provider_metadata.get("bar_end", ""))
        bar_start = str(provider_metadata.get("bar_start", ""))
        if not bar_end or not bar_start:
            epoch_suffix = source_record_id.rsplit("-", 1)[-1]
            if not epoch_suffix.isdigit():
                return None
            bar_end_ns = int(epoch_suffix) * 1_000_000_000
            bar_start_ns = bar_end_ns - 60_000_000_000
        else:
            bar_start_ns = iso_to_epoch_ns(bar_start)
            bar_end_ns = iso_to_epoch_ns(bar_end)
        publication = str(
            provider_metadata.get("publication_timestamp")
            or record.get("received_timestamp")
            or ""
        )
        received = str(record.get("received_timestamp", ""))
        if not received:
            return None
        symbol = str(record.get("symbol", ""))
        exchange = str(record.get("exchange", ""))
        provider = str(provenance.get("provider", "yahoo-chart"))
        normalized_id = normalized_event_id(
            provider_id=provider,
            venue_id=exchange,
            publisher_id=provider,
            channel_id=symbol,
            source_instance_id=SOURCE_OBJECT_ID,
            source_record_id=source_record_id,
            source_revision_id=str(provider_metadata.get("revision_number") or "1"),
            event_family="BAR_OHLCV_1M",
        )
        raw_reference = f"{SOURCE_OBJECT_ID}:{source_record_id}:{raw_hash}"
        return {
            "available_time": bar_end_ns,
            "bar_payload": {
                "close": str(payload.get("close")),
                "high": str(payload.get("high")),
                "low": str(payload.get("low")),
                "open": str(payload.get("open")),
                "timeframe": "1_MINUTE",
                "volume": int(payload.get("volume", 0)),
            },
            "channel_id": symbol,
            "event_time": bar_start_ns,
            "event_type": "BAR_OHLCV_1M",
            "historical_ingested_time": iso_to_epoch_ns(received),
            "ingest_run_id": self.ingest_run_id,
            "instrument_id": symbol,
            "line_number": line_number,
            "market_session": str(record.get("market_session", "")),
            "normalization_version": NORMALIZATION_VERSION,
            "normalized_event_id": normalized_id,
            "operation": "UPSERT",
            "publisher_id": provider,
            "quality_observation_refs": [],
            "raw_reference": raw_reference,
            "schema_version": SCHEMA_VERSION,
            "source_instance_id": SOURCE_OBJECT_ID,
            "source_publish_time": iso_to_epoch_ns(publication) if publication else None,
            "source_record_id": source_record_id,
            "source_revision_id": str(provider_metadata.get("revision_number") or "1"),
            "source_sequence": None,
            "supersedes_event_id": None,
            "venue_id": exchange,
        }

    def ingest_path(self, path: Path) -> AdapterResult:
        result = AdapterResult()
        reasons = self.verify_source_bytes(path)
        if reasons:
            result.quarantined.append({"reason_codes": reasons, "scope": "source_bytes"})
            return result
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    record = json.loads(stripped)
                except ValueError:
                    result.quarantined.append(
                        {"line_number": line_number, "reason_codes": ["ADP_PARSE_FAILURE"]}
                    )
                    continue
                if not isinstance(record, dict):
                    result.quarantined.append(
                        {"line_number": line_number, "reason_codes": ["ADP_RECORD_NOT_OBJECT"]}
                    )
                    continue
                result.record_count += 1
                canonical = self.normalize_record(record, line_number=line_number)
                if canonical is None:
                    result.quarantined.append(
                        {"line_number": line_number, "reason_codes": ["ADP_UNSUPPORTED_RECORD"]}
                    )
                    continue
                identity = str(canonical["normalized_event_id"])
                record_hash = sha256_bytes(canonical_bytes(canonical))
                prior = self._identity_hashes.get(identity)
                if prior is None:
                    self._identity_hashes[identity] = record_hash
                    result.canonical_events.append(canonical)
                    result.provenance_index[str(canonical["raw_reference"])] = identity
                elif prior == record_hash:
                    result.idempotent_replays += 1
                else:
                    result.conflict_count += 1
                    result.quarantined.append(
                        {
                            "identity": identity,
                            "line_number": line_number,
                            "reason_codes": ["ADP_IDENTITY_CONFLICT"],
                        }
                    )
        result.dangling_count = sum(
            1
            for event in result.canonical_events
            if not event.get("raw_reference") or event["raw_reference"] not in result.provenance_index
        )
        return result

    def ingest_collection(self, collection_root: Path) -> AdapterResult:
        return self.ingest_path(collection_root / COLLECTION_RELATIVE_PATH)


def verify_registry_integrity(registry_ids: list[str]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    for registry_id in registry_ids:
        if registry_id in PROHIBITED_REGISTRY_IDS:
            reasons.append(f"SAFE002_PROHIBITED_REGISTRY_ID_{registry_id.upper()}")
        if registry_id.startswith("live."):
            reasons.append(f"SAFE002_LIVE_REGISTRY_ID_{registry_id.upper()}")
    return ("PASS" if not reasons else "FAIL"), reasons


def verify_dependency_lock(lock_path: Path) -> tuple[str, list[str]]:
    if not lock_path.is_file():
        return "BLOCKED", ["SAFE001_LOCK_MISSING"]
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    third_party = payload.get("third_party")
    if isinstance(third_party, list) and not third_party:
        return "PASS", []
    groups = payload.get("distribution_groups", {})
    if isinstance(groups, dict):
        for group in groups.values():
            if isinstance(group, dict) and group.get("third_party"):
                return "FAIL", ["SAFE001_THIRD_PARTY_DEPENDENCY_PRESENT"]
    if payload.get("third_party_dependency_count") == 0:
        return "PASS", []
    return "FAIL", ["SAFE001_THIRD_PARTY_DEPENDENCY_PRESENT"]
