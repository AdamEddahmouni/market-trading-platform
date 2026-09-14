"""PIT-preserving OpenD prospective capture JSONL → BUILD 15 observation + ledger bridge.

Consumes only already-recorded ``market_data.provider_envelope`` JSONL artifacts.
Does not synthesize forecasts, probabilities, labels, or settlements.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

from ...canonical import canonical_bytes, sha256_bytes
from ...market_data.capture import CAPTURE_SCHEMA_VERSION
from ...market_data.timestamps import TimestampSet, clocks_from_capture
from ..contracts.event import EventV1
from ..contracts.prediction_ledger import PredictionLedgerEntryV1
from ..normalization.models import IngestionMode, NormalizationContext
from ..normalization.providers.moomoo import normalize_moomoo_capture
from ..persistence.repository import IntelligenceRepository, RepositoryPutResult
from ..production.identity import PATH_A_HORIZON_NS
from .observations import is_valid_settlement_observation
from .service import OutcomeSettlementService, PredictionLedgerService
from .types import SettlementMode, SettlementResult, SettlementStatus

_OPEND_CAPABILITY_ALIASES: dict[str, str] = {
    "US_EQUITY_L1": "QUOTE",
    "US_EQUITY_SNAPSHOT": "QUOTE",
    "US_EQUITY_TICKS": "TICKER",
    "US_EQUITY_DEPTH": "ORDER_BOOK",
}

_REQUIRED_CLOCK_FIELDS = (
    "event_time_ns",
    "available_time_ns",
    "received_time_ns",
)


@dataclass(frozen=True, slots=True)
class CaptureProvenance:
    capture_path: str
    line_index: int
    schema_version: str
    provider: str
    provider_symbol: str
    capability: str
    sequence: int | None
    clocks: dict[str, int | None]
    lifecycle: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "capture_path": self.capture_path,
            "capability": self.capability,
            "clocks": dict(self.clocks),
            "lifecycle": self.lifecycle,
            "line_index": self.line_index,
            "provider": self.provider,
            "provider_symbol": self.provider_symbol,
            "schema_version": self.schema_version,
            "sequence": self.sequence,
        }


@dataclass(frozen=True, slots=True)
class CaptureLedgerCandidate:
    """Governed grid-point binding between a capture envelope and BUILD 15 registration."""

    candidate_id: str
    event_id: str
    instrument_id: str
    decision_time_ns: int
    horizon_ns: int
    provenance: CaptureProvenance
    ledger_entry_id: str | None = None
    forecast_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "candidate_id": self.candidate_id,
            "decision_time_ns": self.decision_time_ns,
            "event_id": self.event_id,
            "horizon_ns": self.horizon_ns,
            "instrument_id": self.instrument_id,
            "provenance": self.provenance.to_dict(),
        }
        if self.forecast_id is not None:
            body["forecast_id"] = self.forecast_id
        if self.ledger_entry_id is not None:
            body["ledger_entry_id"] = self.ledger_entry_id
        return body


@dataclass(frozen=True, slots=True)
class CaptureFunnelCounts:
    raw_envelopes: int = 0
    tape_eligible: int = 0
    grid_points: int = 0
    materialized_ledger: int = 0
    pending_settlement: int = 0
    settled: int = 0
    specialist_eligible: int = 0
    calibration_eligible: int = 0
    refused: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "calibration_eligible": self.calibration_eligible,
            "grid_points": self.grid_points,
            "materialized_ledger": self.materialized_ledger,
            "pending_settlement": self.pending_settlement,
            "raw_envelopes": self.raw_envelopes,
            "refused": self.refused,
            "settled": self.settled,
            "specialist_eligible": self.specialist_eligible,
            "tape_eligible": self.tape_eligible,
        }


@dataclass
class CaptureLedgerMaterializationResult:
    candidates: list[CaptureLedgerCandidate] = field(default_factory=list)
    events_persisted: int = 0
    events_idempotent: int = 0
    ledger_registered: int = 0
    ledger_idempotent: int = 0
    refusal_reasons: dict[str, int] = field(default_factory=dict)
    funnel: CaptureFunnelCounts = field(default_factory=CaptureFunnelCounts)

    def note_refusal(self, reason: str) -> None:
        self.refusal_reasons[reason] = self.refusal_reasons.get(reason, 0) + 1
        self.funnel = CaptureFunnelCounts(
            raw_envelopes=self.funnel.raw_envelopes,
            tape_eligible=self.funnel.tape_eligible,
            grid_points=self.funnel.grid_points,
            materialized_ledger=self.funnel.materialized_ledger,
            pending_settlement=self.funnel.pending_settlement,
            settled=self.funnel.settled,
            specialist_eligible=self.funnel.specialist_eligible,
            calibration_eligible=self.funnel.calibration_eligible,
            refused=self.funnel.refused + 1,
        )


def canonicalize_opend_capture_envelope(record: dict[str, Any]) -> dict[str, Any]:
    """Map OpenD JSONL capability names onto the moomoo.capture normalizer vocabulary."""
    body = dict(record)
    capability = str(body.get("capability") or "").upper()
    alias = _OPEND_CAPABILITY_ALIASES.get(capability)
    if alias is not None:
        body["capability"] = alias
    return body


def _clocks_dict(clocks: TimestampSet) -> dict[str, int | None]:
    return clocks.to_dict()


def _validate_capture_schema(record: dict[str, Any]) -> str | None:
    version = str(record.get("schema_version") or "")
    if version and version != CAPTURE_SCHEMA_VERSION:
        return "SCHEMA_VERSION_MISMATCH"
    capability = str(record.get("capability") or "")
    if not capability:
        return "MISSING_CAPABILITY"
    provider_symbol = str(record.get("provider_symbol") or record.get("instrument_id") or "")
    if not provider_symbol:
        return "MISSING_SYMBOL"
    clocks = clocks_from_capture(record)
    for field_name in _REQUIRED_CLOCK_FIELDS:
        if getattr(clocks, field_name) is None:
            return f"MISSING_CLOCK_{field_name}"
    event_time = clocks.event_time_ns
    available = clocks.available_time_ns
    received = clocks.received_time_ns
    assert event_time is not None and available is not None and received is not None
    if event_time > available:
        return "TEMPORALLY_IMPOSSIBLE_EVENT_AFTER_AVAILABLE"
    if available > received:
        return "TEMPORALLY_IMPOSSIBLE_AVAILABLE_AFTER_RECEIVED"
    return None


def pit_refusal_reason(
    record: dict[str, Any],
    *,
    as_of_ns: int,
    session_start_ns: int,
) -> str | None:
    schema_reason = _validate_capture_schema(record)
    if schema_reason is not None:
        return schema_reason
    clocks = clocks_from_capture(record)
    available = clocks.available_time_ns
    event_time = clocks.event_time_ns
    assert available is not None and event_time is not None
    if available > as_of_ns:
        return "NON_PIT_AVAILABLE_AFTER_AS_OF"
    if event_time < session_start_ns:
        return "PROSPECTIVE_BACKFILL_BEFORE_SESSION_START"
    return None


def is_tape_eligible_event(event: EventV1, *, as_of_ns: int) -> bool:
    if event.available_time_ns > as_of_ns:
        return False
    if event.event_time_ns > event.available_time_ns:
        return False
    return is_valid_settlement_observation(event)


def is_grid_point_candidate(
    record: dict[str, Any],
    event: EventV1,
    *,
    as_of_ns: int,
    session_start_ns: int,
) -> bool:
    if pit_refusal_reason(record, as_of_ns=as_of_ns, session_start_ns=session_start_ns) is not None:
        return False
    if not is_tape_eligible_event(event, as_of_ns=as_of_ns):
        return False
    canonical = canonicalize_opend_capture_envelope(record)
    capability = str(canonical.get("capability") or "").upper()
    if capability != "QUOTE":
        return False
    return True


def derive_capture_ledger_candidate_id(
    *,
    capture_path: str,
    line_index: int,
    event_id: str,
    decision_time_ns: int,
) -> str:
    payload = canonical_bytes({
        "capture_path": capture_path,
        "decision_time_ns": decision_time_ns,
        "event_id": event_id,
        "line_index": line_index,
        "version": "opend-capture-ledger-candidate/v1",
    })
    return f"OCLC-{sha256_bytes(payload)[:32].upper()}"


def build_capture_provenance(
    record: dict[str, Any],
    *,
    capture_path: Path,
    line_index: int,
) -> CaptureProvenance:
    clocks = clocks_from_capture(record)
    return CaptureProvenance(
        capture_path=str(capture_path),
        line_index=line_index,
        schema_version=str(record.get("schema_version") or CAPTURE_SCHEMA_VERSION),
        provider=str(record.get("provider") or ""),
        provider_symbol=str(record.get("provider_symbol") or record.get("instrument_id") or ""),
        capability=str(record.get("capability") or ""),
        sequence=int(record["sequence"]) if record.get("sequence") is not None else None,
        clocks=_clocks_dict(clocks),
        lifecycle=str(record.get("lifecycle") or "CAPTURED"),
    )


def normalize_capture_record(
    record: dict[str, Any],
    *,
    capture_path: Path,
    line_index: int,
) -> EventV1 | None:
    canonical = canonicalize_opend_capture_envelope(record)
    clocks = clocks_from_capture(canonical)
    received = clocks.received_time_ns or clocks.available_time_ns or 0
    context = NormalizationContext(
        received_time_ns=received,
        ingestion_mode=IngestionMode.REPLAY,
        raw_payload_ref=f"{capture_path}:{line_index}",
    )
    result = normalize_moomoo_capture(canonical, context=context)
    return result.event


def iter_jsonl_envelopes(path: Path) -> Iterator[tuple[int, dict[str, Any] | None, str | None]]:
    if not path.is_file():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line_index, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                yield line_index, None, "MALFORMED_JSON"
                continue
            if not isinstance(payload, dict):
                yield line_index, None, "ENVELOPE_NOT_OBJECT"
                continue
            yield line_index, payload, None


def scan_capture_funnel(
    path: Path,
    *,
    as_of_ns: int,
    session_start_ns: int,
) -> CaptureFunnelCounts:
    raw = tape = grid = refused = 0
    for line_index, record, parse_error in iter_jsonl_envelopes(path):
        if parse_error is not None or record is None:
            refused += 1
            continue
        raw += 1
        reason = pit_refusal_reason(record, as_of_ns=as_of_ns, session_start_ns=session_start_ns)
        if reason is not None:
            refused += 1
            continue
        event = normalize_capture_record(record, capture_path=path, line_index=line_index)
        if event is None:
            refused += 1
            continue
        if is_tape_eligible_event(event, as_of_ns=as_of_ns):
            tape += 1
        if is_grid_point_candidate(record, event, as_of_ns=as_of_ns, session_start_ns=session_start_ns):
            grid += 1
    return CaptureFunnelCounts(
        raw_envelopes=raw,
        tape_eligible=tape,
        grid_points=grid,
        refused=refused,
    )


def _ledger_entries_in_repository(repository: IntelligenceRepository) -> tuple[PredictionLedgerEntryV1, ...]:
    stores = getattr(repository, "_stores", None)
    if not isinstance(stores, dict):
        return ()
    bucket = stores.get("prediction_ledger")
    if not isinstance(bucket, dict):
        return ()
    decode = getattr(repository, "_decode", None)
    if decode is None:
        return ()
    rows: list[PredictionLedgerEntryV1] = []
    for body in bucket.values():
        entry = decode(PredictionLedgerEntryV1, body)
        if entry is not None:
            rows.append(entry)
    return tuple(sorted(rows, key=lambda row: row.ledger_entry_id))


def enrich_funnel_from_repository(
    funnel: CaptureFunnelCounts,
    repository: IntelligenceRepository,
    *,
    as_of_ns: int,
) -> CaptureFunnelCounts:
    entries = _ledger_entries_in_repository(repository)
    materialized = len(entries)
    pending = 0
    settled = 0
    settlement = OutcomeSettlementService(repository)
    for entry in entries:
        status = settlement.inspect_settlement(entry, now_ns=as_of_ns)
        if status == SettlementStatus.ALREADY_SETTLED:
            settled += 1
        elif status in {SettlementStatus.NOT_DUE, SettlementStatus.DUE}:
            pending += 1
    return CaptureFunnelCounts(
        raw_envelopes=funnel.raw_envelopes,
        tape_eligible=funnel.tape_eligible,
        grid_points=funnel.grid_points,
        materialized_ledger=materialized,
        pending_settlement=pending,
        settled=settled,
        specialist_eligible=0,
        calibration_eligible=0,
        refused=funnel.refused,
    )


def materialize_opend_capture_jsonl(
    path: Path,
    repository: IntelligenceRepository,
    *,
    as_of_ns: int,
    session_start_ns: int,
    forecast_bindings: dict[str, str] | None = None,
    register_ledger: bool = True,
) -> CaptureLedgerMaterializationResult:
    """Ingest capture envelopes as events and optionally register BUILD 15 ledger rows.

    ``forecast_bindings`` maps ``candidate_id`` → existing ``forecast_id`` (forecast
    must already be present in ``repository``). No forecast synthesis occurs here.
    """
    result = CaptureLedgerMaterializationResult()
    bindings = forecast_bindings or {}
    ledger_service = PredictionLedgerService(repository)

    for line_index, record, parse_error in iter_jsonl_envelopes(path):
        if parse_error is not None or record is None:
            result.note_refusal(parse_error or "MALFORMED")
            continue
        result.funnel = CaptureFunnelCounts(
            raw_envelopes=result.funnel.raw_envelopes + 1,
            tape_eligible=result.funnel.tape_eligible,
            grid_points=result.funnel.grid_points,
            materialized_ledger=result.funnel.materialized_ledger,
            pending_settlement=result.funnel.pending_settlement,
            settled=result.funnel.settled,
            specialist_eligible=result.funnel.specialist_eligible,
            calibration_eligible=result.funnel.calibration_eligible,
            refused=result.funnel.refused,
        )
        reason = pit_refusal_reason(record, as_of_ns=as_of_ns, session_start_ns=session_start_ns)
        if reason is not None:
            result.note_refusal(reason)
            continue
        event = normalize_capture_record(record, capture_path=path, line_index=line_index)
        if event is None:
            result.note_refusal("NORMALIZATION_FAILED")
            continue
        put_result = repository.put_event(event)
        if put_result == RepositoryPutResult.INSERTED:
            result.events_persisted += 1
        elif put_result == RepositoryPutResult.ALREADY_PRESENT:
            result.events_idempotent += 1
        else:
            result.note_refusal("EVENT_PERSIST_CONFLICT")
            continue

        if is_tape_eligible_event(event, as_of_ns=as_of_ns):
            result.funnel = CaptureFunnelCounts(
                raw_envelopes=result.funnel.raw_envelopes,
                tape_eligible=result.funnel.tape_eligible + 1,
                grid_points=result.funnel.grid_points,
                materialized_ledger=result.funnel.materialized_ledger,
                pending_settlement=result.funnel.pending_settlement,
                settled=result.funnel.settled,
                specialist_eligible=result.funnel.specialist_eligible,
                calibration_eligible=result.funnel.calibration_eligible,
                refused=result.funnel.refused,
            )

        if not is_grid_point_candidate(
            record,
            event,
            as_of_ns=as_of_ns,
            session_start_ns=session_start_ns,
        ):
            continue

        provenance = build_capture_provenance(record, capture_path=path, line_index=line_index)
        candidate_id = derive_capture_ledger_candidate_id(
            capture_path=str(path),
            line_index=line_index,
            event_id=event.event_id,
            decision_time_ns=event.event_time_ns,
        )
        candidate = CaptureLedgerCandidate(
            candidate_id=candidate_id,
            event_id=event.event_id,
            instrument_id=str(event.instrument_id or ""),
            decision_time_ns=event.event_time_ns,
            horizon_ns=PATH_A_HORIZON_NS,
            provenance=provenance,
        )
        result.funnel = CaptureFunnelCounts(
            raw_envelopes=result.funnel.raw_envelopes,
            tape_eligible=result.funnel.tape_eligible,
            grid_points=result.funnel.grid_points + 1,
            materialized_ledger=result.funnel.materialized_ledger,
            pending_settlement=result.funnel.pending_settlement,
            settled=result.funnel.settled,
            specialist_eligible=result.funnel.specialist_eligible,
            calibration_eligible=result.funnel.calibration_eligible,
            refused=result.funnel.refused,
        )

        forecast_id = bindings.get(candidate_id)
        if forecast_id is None:
            result.candidates.append(candidate)
            continue

        if not register_ledger:
            result.candidates.append(
                CaptureLedgerCandidate(
                    candidate_id=candidate.candidate_id,
                    event_id=candidate.event_id,
                    instrument_id=candidate.instrument_id,
                    decision_time_ns=candidate.decision_time_ns,
                    horizon_ns=candidate.horizon_ns,
                    provenance=candidate.provenance,
                    forecast_id=forecast_id,
                )
            )
            continue

        forecast = repository.get_forecast(forecast_id)
        if forecast is None:
            result.note_refusal("FORECAST_NOT_FOUND")
            result.candidates.append(candidate)
            continue
        registered_at_ns = min(as_of_ns, event.available_time_ns)
        register_result = ledger_service.register_forecast(
            forecast,
            now_ns=registered_at_ns,
            mode=SettlementMode.ACTUAL_LIVE,
        )
        if isinstance(register_result, SettlementResult):
            result.note_refusal(str(register_result.status.value))
            result.candidates.append(candidate)
            continue
        entry = register_result
        result.ledger_registered += 1
        result.candidates.append(
            CaptureLedgerCandidate(
                candidate_id=candidate.candidate_id,
                event_id=candidate.event_id,
                instrument_id=candidate.instrument_id,
                decision_time_ns=candidate.decision_time_ns,
                horizon_ns=candidate.horizon_ns,
                provenance=candidate.provenance,
                forecast_id=forecast_id,
                ledger_entry_id=entry.ledger_entry_id,
            )
        )

    result.funnel = enrich_funnel_from_repository(result.funnel, repository, as_of_ns=as_of_ns)
    return result


def materialize_capture_paths(
    paths: Iterable[Path],
    repository: IntelligenceRepository,
    *,
    as_of_ns: int,
    session_start_ns: int,
    forecast_bindings: dict[str, str] | None = None,
) -> CaptureLedgerMaterializationResult:
    aggregate = CaptureLedgerMaterializationResult()
    for path in paths:
        partial = materialize_opend_capture_jsonl(
            path,
            repository,
            as_of_ns=as_of_ns,
            session_start_ns=session_start_ns,
            forecast_bindings=forecast_bindings,
        )
        aggregate.candidates.extend(partial.candidates)
        aggregate.events_persisted += partial.events_persisted
        aggregate.events_idempotent += partial.events_idempotent
        aggregate.ledger_registered += partial.ledger_registered
        for reason, count in partial.refusal_reasons.items():
            aggregate.refusal_reasons[reason] = aggregate.refusal_reasons.get(reason, 0) + count
        aggregate.funnel = CaptureFunnelCounts(
            raw_envelopes=aggregate.funnel.raw_envelopes + partial.funnel.raw_envelopes,
            tape_eligible=aggregate.funnel.tape_eligible + partial.funnel.tape_eligible,
            grid_points=aggregate.funnel.grid_points + partial.funnel.grid_points,
            materialized_ledger=partial.funnel.materialized_ledger,
            pending_settlement=partial.funnel.pending_settlement,
            settled=partial.funnel.settled,
            specialist_eligible=partial.funnel.specialist_eligible,
            calibration_eligible=partial.funnel.calibration_eligible,
            refused=aggregate.funnel.refused + partial.funnel.refused,
        )
    return aggregate


__all__ = [
    "CaptureFunnelCounts",
    "CaptureLedgerCandidate",
    "CaptureLedgerMaterializationResult",
    "CaptureProvenance",
    "build_capture_provenance",
    "canonicalize_opend_capture_envelope",
    "derive_capture_ledger_candidate_id",
    "enrich_funnel_from_repository",
    "is_grid_point_candidate",
    "is_tape_eligible_event",
    "iter_jsonl_envelopes",
    "materialize_capture_paths",
    "materialize_opend_capture_jsonl",
    "normalize_capture_record",
    "pit_refusal_reason",
    "scan_capture_funnel",
]
