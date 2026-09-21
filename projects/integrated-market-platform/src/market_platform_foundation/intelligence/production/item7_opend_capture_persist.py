"""Item 7 — auto-persist lawful SNAPSHOT_BBO capture appends into governed intelligence store.

After a successful ``item7_opend_capture_writer`` append, materializes the operator
capture JSONL through the existing #212→#213→#214→ledger path (fail-closed). Appends
new events and ledger rows to ``intelligence_records.jsonl`` under ``IMP_STATE_DIR``.
Does not force settlement, mint forecasts, or claim empirical corpus readiness.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from ...clock import monotonic_wall_ns
from ...market_data.moomoo_snapshot_bbo import (
    SNAPSHOT_BBO_CAPABILITY,
    snapshot_bbo_quality_flags,
)
from ...market_data.timestamps import clocks_from_capture
from ...shadow.session import session_bounds_ns
from ..contracts.event import EventV1, event_v1_to_dict
from ..contracts.prediction_ledger import (
    PredictionLedgerEntryV1,
    prediction_ledger_entry_v1_to_dict,
)
from ..outcomes.opend_capture_ledger import CaptureLedgerMaterializationResult
from ..persistence.repository import IntelligenceRepository
from .corpus_persistence import (
    discover_governed_persistence_paths,
    load_governed_intelligence_repository,
    resolve_persistence_root,
)
from .item7_opend_capture_writer import (
    DISPOSITION_APPENDED,
    REFUSAL_IMP_STATE_DIR_MISSING,
    canonical_item7_opend_capture_path,
)
from .item7_natural_settlement import (
    Item7NaturalSettlementResult,
    exercise_item7_natural_settlement,
)
from .item7_p0_anchor import materialize_item7_lawful_capture_ledger

ET = ZoneInfo("America/New_York")
PERSIST_ARTIFACT_KIND = "item7_opend_capture_auto_persist_receipt_v1"
GOVERNED_INTELLIGENCE_JSONL = "intelligence_records.jsonl"

DISPOSITION_PERSISTED = "PERSISTED"
DISPOSITION_SKIPPED = "SKIPPED"
DISPOSITION_REFUSED = "REFUSED"

REFUSAL_NOT_LAWFUL_SNAPSHOT_BBO = "SNAPSHOT_BBO_NOT_LAWFUL_FOR_PERSIST"
REFUSAL_CAPTURE_PATH_MISSING = "CAPTURE_PATH_MISSING"
REFUSAL_PERSISTENCE_ROOT_MISSING = "PERSISTENCE_ROOT_MISSING"

_DEFAULT_CONTRIBUTOR_RELATIVE = (
    "path-a/contributors",
    "path-a/production/contributors",
    "contributors",
)


@dataclass(frozen=True, slots=True)
class Item7CaptureAutoPersistResult:
    disposition: str
    intelligence_jsonl_path: str | None = None
    events_persisted: int = 0
    ledger_registered: int = 0
    refusal_reason: str | None = None
    materialization: dict[str, Any] | None = None
    natural_settlement: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_kind": PERSIST_ARTIFACT_KIND,
            "disposition": self.disposition,
            "events_persisted": self.events_persisted,
            "intelligence_jsonl_path": self.intelligence_jsonl_path,
            "ledger_registered": self.ledger_registered,
            "materialization": self.materialization,
            "natural_settlement": self.natural_settlement,
            "refusal_reason": self.refusal_reason,
        }


def is_lawful_persistable_snapshot_bbo_envelope(envelope: Mapping[str, Any]) -> bool:
    """True only for validated SNAPSHOT_BBO envelopes (never last_price-as-BBO)."""

    if str(envelope.get("capability") or "").upper() != SNAPSHOT_BBO_CAPABILITY:
        return False
    flags = snapshot_bbo_quality_flags(envelope)
    return "BBO_VALID" in flags


def canonical_governed_intelligence_jsonl_path(
    *,
    persistence_root: Path | None = None,
) -> Path | None:
    root = persistence_root or resolve_persistence_root()
    if root is None:
        return None
    return (root / GOVERNED_INTELLIGENCE_JSONL).resolve()


def _event_time_date_iso(event_time_ns: int) -> str:
    stamp = datetime.fromtimestamp(event_time_ns / 1_000_000_000, tz=ET)
    return stamp.date().isoformat()


def derive_materialize_clocks_from_envelope(
    envelope: Mapping[str, Any],
    *,
    as_of_ns: int | None = None,
    session_start_ns: int | None = None,
) -> tuple[int, int]:
    clocks = clocks_from_capture(dict(envelope))
    event_time = clocks.event_time_ns
    available = clocks.available_time_ns
    received = clocks.received_time_ns
    if event_time is None:
        raise ValueError("SNAPSHOT_BBO_MISSING_EVENT_TIME")
    resolved_as_of = as_of_ns
    if resolved_as_of is None:
        resolved_as_of = max(
            value
            for value in (available, received, monotonic_wall_ns())
            if value is not None
        )
    resolved_session_start = session_start_ns
    if resolved_session_start is None:
        open_ns, _close_ns = session_bounds_ns(_event_time_date_iso(event_time))
        resolved_session_start = open_ns
    return int(resolved_as_of), int(resolved_session_start)


def _append_jsonl_record(path: Path, record_type: str, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"record_type": record_type, "payload": payload}, sort_keys=True, separators=(",", ":"))
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")


def _outcome_ids(repository: IntelligenceRepository) -> set[str]:
    stores = getattr(repository, "_stores", None)
    if not isinstance(stores, dict):
        return set()
    bucket = stores.get("outcomes")
    if not isinstance(bucket, dict):
        return set()
    return {str(key) for key in bucket}


def _ledger_ids(repository: IntelligenceRepository) -> set[str]:
    stores = getattr(repository, "_stores", None)
    if not isinstance(stores, dict):
        return set()
    bucket = stores.get("prediction_ledger")
    if not isinstance(bucket, dict):
        return set()
    return {str(key) for key in bucket}


def _event_ids(repository: IntelligenceRepository) -> set[str]:
    stores = getattr(repository, "_stores", None)
    if not isinstance(stores, dict):
        return set()
    bucket = stores.get("events")
    if not isinstance(bucket, dict):
        return set()
    return {str(key) for key in bucket}


def _events_by_id(repository: IntelligenceRepository) -> dict[str, EventV1]:
    stores = getattr(repository, "_stores", None)
    decode = getattr(repository, "_decode", None)
    if not isinstance(stores, dict) or decode is None:
        return {}
    bucket = stores.get("events")
    if not isinstance(bucket, dict):
        return {}
    rows: dict[str, EventV1] = {}
    for body in bucket.values():
        event = decode(EventV1, body)
        if event is not None:
            rows[str(event.event_id)] = event
    return rows


def _ledger_entries_by_id(repository: IntelligenceRepository) -> dict[str, PredictionLedgerEntryV1]:
    stores = getattr(repository, "_stores", None)
    decode = getattr(repository, "_decode", None)
    if not isinstance(stores, dict) or decode is None:
        return {}
    bucket = stores.get("prediction_ledger")
    if not isinstance(bucket, dict):
        return {}
    rows: dict[str, PredictionLedgerEntryV1] = {}
    for body in bucket.values():
        entry = decode(PredictionLedgerEntryV1, body)
        if entry is not None:
            rows[str(entry.ledger_entry_id)] = entry
    return rows


def discover_operator_contributor_paths(persistence_root: Path) -> tuple[Path, ...]:
    paths: list[Path] = []
    for relative in _DEFAULT_CONTRIBUTOR_RELATIVE:
        candidate = (persistence_root / relative).resolve()
        if candidate.is_dir():
            paths.append(candidate)
    discovered = discover_governed_persistence_paths(persistence_root)
    paths.extend(discovered.forecast_dirs)
    unique: dict[str, Path] = {}
    for path in paths:
        unique[str(path)] = path
    return tuple(sorted(unique.values(), key=str))


def append_materialized_records_to_governed_jsonl(
    repository: IntelligenceRepository,
    *,
    intelligence_jsonl_path: Path,
    event_ids_before: set[str],
    ledger_ids_before: set[str],
) -> tuple[int, int]:
    """Append newly materialized events and ledger rows (idempotent on disk)."""

    events_appended = 0
    ledger_appended = 0
    if intelligence_jsonl_path.is_file():
        existing_event_ids: set[str] = set()
        existing_ledger_ids: set[str] = set()
        for line in intelligence_jsonl_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            record_type = str(row.get("record_type") or "")
            payload = row.get("payload")
            if not isinstance(payload, dict):
                continue
            if record_type == "event":
                event_id = str(payload.get("event_id") or "")
                if event_id:
                    existing_event_ids.add(event_id)
            elif record_type == "prediction_ledger_entry":
                ledger_id = str(payload.get("ledger_entry_id") or "")
                if ledger_id:
                    existing_ledger_ids.add(ledger_id)
    else:
        existing_event_ids = set()
        existing_ledger_ids = set()

    for event_id, event in _events_by_id(repository).items():
        if event_id in event_ids_before or event_id in existing_event_ids:
            continue
        _append_jsonl_record(intelligence_jsonl_path, "event", event_v1_to_dict(event))
        events_appended += 1

    for ledger_id, entry in _ledger_entries_by_id(repository).items():
        if ledger_id in ledger_ids_before or ledger_id in existing_ledger_ids:
            continue
        _append_jsonl_record(
            intelligence_jsonl_path,
            "prediction_ledger_entry",
            prediction_ledger_entry_v1_to_dict(entry),
        )
        ledger_appended += 1

    return events_appended, ledger_appended


def persist_lawful_opend_capture_append(
    envelope: Mapping[str, Any],
    *,
    capture_path: Path | None = None,
    as_of_ns: int | None = None,
    session_start_ns: int | None = None,
    contributor_path: Path | None = None,
    forecast_path: Path | None = None,
    bind_expected_account_id: str | None = None,
    bind_expected_mode: str | None = None,
    register_ledger: bool = True,
    persistence_root: Path | None = None,
    natural_settle: bool = True,
) -> Item7CaptureAutoPersistResult:
    """Materialize lawful capture into governed persistence (fail-closed).

    When ``natural_settle`` is True, exercises Item 7 natural settlement after
    materialization. Only ``SETTLED`` outcomes are persisted; due
    ``UNLABELABLE`` is reported on the receipt without sealing the ledger.
    """

    if not is_lawful_persistable_snapshot_bbo_envelope(envelope):
        return Item7CaptureAutoPersistResult(
            disposition=DISPOSITION_REFUSED,
            refusal_reason=REFUSAL_NOT_LAWFUL_SNAPSHOT_BBO,
        )

    if persistence_root is None and not os.environ.get("IMP_STATE_DIR", "").strip():
        return Item7CaptureAutoPersistResult(
            disposition=DISPOSITION_REFUSED,
            refusal_reason=REFUSAL_IMP_STATE_DIR_MISSING,
        )
    root = persistence_root or resolve_persistence_root()
    if root is None or not root.is_dir():
        return Item7CaptureAutoPersistResult(
            disposition=DISPOSITION_REFUSED,
            refusal_reason=REFUSAL_PERSISTENCE_ROOT_MISSING,
        )

    path = capture_path or canonical_item7_opend_capture_path(require_imp_state_dir=True)
    if not path.is_file():
        return Item7CaptureAutoPersistResult(
            disposition=DISPOSITION_REFUSED,
            refusal_reason=REFUSAL_CAPTURE_PATH_MISSING,
            intelligence_jsonl_path=str(
                canonical_governed_intelligence_jsonl_path(persistence_root=root)
            ),
        )

    jsonl_path = canonical_governed_intelligence_jsonl_path(persistence_root=root)
    assert jsonl_path is not None

    repository, _load_report = load_governed_intelligence_repository(persistence_root=root)
    event_ids_before = _event_ids(repository)
    ledger_ids_before = _ledger_ids(repository)
    outcome_ids_before = _outcome_ids(repository)

    resolved_as_of, resolved_session = derive_materialize_clocks_from_envelope(
        envelope,
        as_of_ns=as_of_ns,
        session_start_ns=session_start_ns,
    )

    contributor_paths = discover_operator_contributor_paths(root)
    resolved_contributor = contributor_path
    if resolved_contributor is None and contributor_paths:
        resolved_contributor = contributor_paths[0]

    materialized: CaptureLedgerMaterializationResult = materialize_item7_lawful_capture_ledger(
        (path,),
        repository,
        as_of_ns=resolved_as_of,
        session_start_ns=resolved_session,
        contributor_path=resolved_contributor,
        forecast_path=forecast_path,
        bind_expected_account_id=bind_expected_account_id,
        bind_expected_mode=bind_expected_mode,
        register_ledger=register_ledger,
        use_production_ingress=False,
    )

    events_appended, ledger_appended = append_materialized_records_to_governed_jsonl(
        repository,
        intelligence_jsonl_path=jsonl_path,
        event_ids_before=event_ids_before,
        ledger_ids_before=ledger_ids_before,
    )

    settlement_summary: Item7NaturalSettlementResult | None = None
    if natural_settle:
        settlement_summary = exercise_item7_natural_settlement(
            repository,
            now_ns=resolved_as_of,
            persist_outcomes=True,
            intelligence_jsonl_path=jsonl_path,
            outcome_ids_before=outcome_ids_before,
        )

    return Item7CaptureAutoPersistResult(
        disposition=DISPOSITION_PERSISTED,
        intelligence_jsonl_path=str(jsonl_path),
        events_persisted=events_appended,
        ledger_registered=ledger_appended,
        materialization={
            "events_persisted": materialized.events_persisted,
            "ledger_registered": materialized.ledger_registered,
            "refusal_reasons": dict(materialized.refusal_reasons),
            "funnel": materialized.funnel.to_dict(),
        },
        natural_settlement=(
            settlement_summary.to_dict() if settlement_summary is not None else None
        ),
    )


def maybe_auto_persist_capture_append(
    *,
    append_disposition: str,
    envelope: dict[str, Any] | None,
    dry_run: bool,
    auto_persist: bool,
    capture_path: Path | None = None,
    as_of_ns: int | None = None,
    session_start_ns: int | None = None,
    contributor_path: Path | None = None,
    forecast_path: Path | None = None,
    bind_expected_account_id: str | None = None,
    bind_expected_mode: str | None = None,
    register_ledger: bool = True,
    natural_settle: bool = True,
) -> Item7CaptureAutoPersistResult | None:
    if not auto_persist or dry_run or append_disposition != DISPOSITION_APPENDED:
        return None
    if envelope is None:
        return Item7CaptureAutoPersistResult(
            disposition=DISPOSITION_REFUSED,
            refusal_reason=REFUSAL_NOT_LAWFUL_SNAPSHOT_BBO,
        )
    return persist_lawful_opend_capture_append(
        envelope,
        capture_path=capture_path,
        as_of_ns=as_of_ns,
        session_start_ns=session_start_ns,
        contributor_path=contributor_path,
        forecast_path=forecast_path,
        bind_expected_account_id=bind_expected_account_id,
        bind_expected_mode=bind_expected_mode,
        register_ledger=register_ledger,
        natural_settle=natural_settle,
    )


__all__ = [
    "DISPOSITION_PERSISTED",
    "DISPOSITION_REFUSED",
    "DISPOSITION_SKIPPED",
    "GOVERNED_INTELLIGENCE_JSONL",
    "Item7CaptureAutoPersistResult",
    "PERSIST_ARTIFACT_KIND",
    "REFUSAL_NOT_LAWFUL_SNAPSHOT_BBO",
    "append_materialized_records_to_governed_jsonl",
    "canonical_governed_intelligence_jsonl_path",
    "derive_materialize_clocks_from_envelope",
    "discover_operator_contributor_paths",
    "is_lawful_persistable_snapshot_bbo_envelope",
    "maybe_auto_persist_capture_append",
    "persist_lawful_opend_capture_append",
]
