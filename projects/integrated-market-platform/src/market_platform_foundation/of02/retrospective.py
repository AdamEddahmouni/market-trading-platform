"""Idempotent retrospective indexing through OF-01 commands only."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from market_platform_foundation.of01.canonical import sha256_upper
from market_platform_foundation.of01.errors import OF01Error, OF01ErrorCode
from market_platform_foundation.of01.records import (
    ActionCategory,
    ConsequenceProfile,
    OutcomeValidity,
    ProvenanceQualifier,
    TerminalResult,
)

from .contracts import AttemptSpec, AttributionRequest, AttributionResult, AttributionStatus, DomainIdentity
from .gateway import LedgerWriter
from .identity import derive_retrospective
from .lifecycle import attribute


@dataclass(frozen=True, slots=True)
class IndexCandidate:
    source_type: str
    source_identity: str
    path: str | None
    content_hash: str | None
    classification: str
    provenance_qualifier: str
    expected_records: tuple[str, ...]
    known_missing: tuple[str, ...]
    event_time_ns: int | None
    potential_conflict: bool = False


@dataclass
class IndexBatchResult:
    discovered: int = 0
    eligible: int = 0
    indexed: int = 0
    already_indexed: int = 0
    legacy_partial: int = 0
    skipped: int = 0
    conflicted: int = 0
    failed: int = 0
    candidates: list[IndexCandidate] = field(default_factory=list)
    results: list[AttributionResult] = field(default_factory=list)
    dry_run: bool = False


def hash_file_bytes(path: Path) -> str:
    return sha256_upper(path.read_bytes())


def classify_source(path: Path, *, source_type: str = "generic_json") -> IndexCandidate:
    source_identity = path.as_posix()
    if not path.exists():
        return IndexCandidate(
            source_type=source_type,
            source_identity=source_identity,
            path=str(path),
            content_hash=None,
            classification="missing",
            provenance_qualifier=ProvenanceQualifier.LEGACY_PARTIAL.value,
            expected_records=(),
            known_missing=("source_bytes",),
            event_time_ns=None,
        )
    raw = path.read_bytes()
    content_hash = sha256_upper(raw)
    known_missing: list[str] = []
    event_time_ns = None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return IndexCandidate(
            source_type=source_type,
            source_identity=source_identity,
            path=str(path),
            content_hash=content_hash,
            classification="legacy_partial",
            provenance_qualifier=ProvenanceQualifier.LEGACY_PARTIAL.value,
            expected_records=("RUN",),
            known_missing=("json_payload", "event_time"),
            event_time_ns=None,
        )
    if not isinstance(payload, dict):
        known_missing.extend(["object_payload", "event_time"])
        qualifier = ProvenanceQualifier.LEGACY_PARTIAL
        classification = "legacy_partial"
    else:
        if "schema_version" not in payload:
            known_missing.append("schema_version")
        if "status" not in payload and "started_at" not in payload:
            known_missing.append("status_or_started_at")
        started = payload.get("started_at")
        if isinstance(started, int):
            event_time_ns = started
        elif not started:
            known_missing.append("event_time")
        if known_missing:
            qualifier = ProvenanceQualifier.LEGACY_PARTIAL
            classification = "legacy_partial"
        else:
            qualifier = ProvenanceQualifier.RETROSPECTIVE_INDEX
            classification = "retrospective_index"
    return IndexCandidate(
        source_type=source_type,
        source_identity=source_identity,
        path=str(path),
        content_hash=content_hash,
        classification=classification,
        provenance_qualifier=qualifier.value if classification != "missing" else ProvenanceQualifier.LEGACY_PARTIAL.value,
        expected_records=("RUN", "ATTEMPT", "OUTCOME", "DISPOSITION"),
        known_missing=tuple(known_missing),
        event_time_ns=event_time_ns,
    )


def discover(paths: list[Path], *, source_type: str = "generic_json") -> list[IndexCandidate]:
    return [classify_source(path, source_type=source_type) for path in paths]


def _request_for(candidate: IndexCandidate) -> AttributionRequest:
    qualifier = ProvenanceQualifier(candidate.provenance_qualifier)
    return AttributionRequest(
        adapter_id="retrospective",
        operation_class="RETROSPECTIVE_INDEX",
        objective=f"index {candidate.source_type}",
        consequence_profile=ConsequenceProfile.C2_GOVERNED,
        provenance_qualifier=qualifier,
        domain_identities=(
            DomainIdentity(system="retrospective", id_type=candidate.source_type, value=candidate.source_identity),
        ),
        attempts=(
            AttemptSpec(
                sequence=1,
                terminal_result=TerminalResult.COMPLETED,
                reason_code="ATTEMPT_COMPLETED",
            ),
        ),
        outcome_type="RETROSPECTIVE_REFERENCE",
        validity=OutcomeValidity.NOT_EVALUATED,
        disposition_action=ActionCategory.NO_ACTION,
        disposition_domain_code="INDEXED",
        known_missing=candidate.known_missing,
        event_time_ns=candidate.event_time_ns,
        outcome_limitations="indexing time is OF recorded_at; event_time does not backdate the ledger",
        extra={"content_hash": candidate.content_hash, "source_type": candidate.source_type},
    )


def index_sources(
    paths: list[Path],
    *,
    writer: LedgerWriter | None,
    dry_run: bool = False,
    source_type: str = "generic_json",
    enabled: bool = True,
) -> IndexBatchResult:
    batch = IndexBatchResult(dry_run=dry_run)
    candidates = discover(paths, source_type=source_type)
    batch.discovered = len(candidates)
    batch.candidates = candidates
    if not enabled:
        batch.skipped = len(candidates)
        return batch
    for candidate in candidates:
        if candidate.classification == "missing":
            batch.skipped += 1
            continue
        batch.eligible += 1
        if candidate.classification == "legacy_partial":
            batch.legacy_partial += 1
        if dry_run:
            continue
        if writer is None:
            batch.failed += 1
            continue
        identities = derive_retrospective(
            source_type=candidate.source_type,
            source_identity=candidate.source_identity,
            content_hash=candidate.content_hash or "NOHASH",
            attempt_count=1,
            capture_artifact=False,
            qualifier=candidate.provenance_qualifier,
        )
        existing = writer.resolve_command(identities.register_run_command_id)
        request = _request_for(candidate)
        try:
            result = attribute(request, writer=writer, identities=identities, enabled=True)
        except OF01Error as exc:
            if exc.code == OF01ErrorCode.COMMAND_ID_CONFLICT:
                batch.conflicted += 1
                continue
            batch.failed += 1
            continue
        if result.status == AttributionStatus.CONFLICTED:
            batch.conflicted += 1
        elif result.status in {AttributionStatus.EXISTING} or existing is not None:
            batch.already_indexed += 1
        elif result.status == AttributionStatus.COMMITTED:
            batch.indexed += 1
        else:
            batch.failed += 1
        batch.results.append(result)
    return batch
