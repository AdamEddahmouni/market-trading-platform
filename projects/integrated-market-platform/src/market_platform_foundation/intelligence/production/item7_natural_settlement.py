"""Item 7 — natural outcome settlement after lawful capture materialization.

Exercises BUILD 15 ``OutcomeSettlementService`` when ``now_ns`` has reached
ledger maturity and terminal observations exist in the repository. Never forces
settlement before ``availability_cutoff_ns``, synthesizes terminal prices, or
rewrites clocks. Does not claim governed corpus readiness or empirical status.

Hot-path persist gate: only ``SETTLED`` outcomes may be written via
``put_outcome`` / governed JSONL. ``UNLABELABLE`` is counted on the receipt
(``due_unlabelable``) but left non-persisted so a later in-window terminal can
still settle the pending ledger.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..contracts.common import OutcomeResolutionStatus
from ..contracts.outcome import OutcomeV1, outcome_v1_to_dict
from ..contracts.prediction_ledger import PredictionLedgerEntryV1
from ..outcomes.service import OutcomeSettlementService
from ..outcomes.types import SettlementResult, SettlementStatus
from ..persistence.repository import IntelligenceRepository, RepositoryPutResult

ARTIFACT_KIND = "item7_natural_settlement_receipt_v1"


@dataclass(frozen=True, slots=True)
class Item7NaturalSettlementResult:
    now_ns: int
    not_due: int = 0
    due_unlabelable: int = 0
    settled: int = 0
    already_settled: int = 0
    outcomes_appended: int = 0
    refusal_reasons: dict[str, int] = field(default_factory=dict)

    @property
    def attempted(self) -> int:
        return self.not_due + self.due_unlabelable + self.settled + self.already_settled

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_kind": ARTIFACT_KIND,
            "already_settled": self.already_settled,
            "attempted": self.attempted,
            "due_unlabelable": self.due_unlabelable,
            "not_due": self.not_due,
            "now_ns": self.now_ns,
            "outcomes_appended": self.outcomes_appended,
            "refusal_reasons": dict(self.refusal_reasons),
            "settled": self.settled,
        }


def _ledger_entries_in_repository(
    repository: IntelligenceRepository,
) -> tuple[PredictionLedgerEntryV1, ...]:
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


def _outcome_ids(repository: IntelligenceRepository) -> set[str]:
    stores = getattr(repository, "_stores", None)
    if not isinstance(stores, dict):
        return set()
    bucket = stores.get("outcomes")
    if not isinstance(bucket, dict):
        return set()
    return {str(key) for key in bucket}


def _outcomes_by_id(repository: IntelligenceRepository) -> dict[str, OutcomeV1]:
    stores = getattr(repository, "_stores", None)
    decode = getattr(repository, "_decode", None)
    if not isinstance(stores, dict) or decode is None:
        return {}
    bucket = stores.get("outcomes")
    if not isinstance(bucket, dict):
        return {}
    rows: dict[str, OutcomeV1] = {}
    for body in bucket.values():
        outcome = decode(OutcomeV1, body)
        if outcome is not None:
            rows[str(outcome.outcome_id)] = outcome
    return rows


def append_settled_outcomes_to_governed_jsonl(
    repository: IntelligenceRepository,
    *,
    intelligence_jsonl_path: Path,
    outcome_ids_before: set[str],
) -> int:
    """Append newly settled (SETTLED-only) outcomes (idempotent on disk)."""

    if intelligence_jsonl_path.is_file():
        existing_outcome_ids: set[str] = set()
        for line in intelligence_jsonl_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            if str(row.get("record_type") or "") != "outcome":
                continue
            payload = row.get("payload")
            if isinstance(payload, dict):
                outcome_id = str(payload.get("outcome_id") or "")
                if outcome_id:
                    existing_outcome_ids.add(outcome_id)
    else:
        existing_outcome_ids = set()

    appended = 0
    intelligence_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    for outcome_id, outcome in _outcomes_by_id(repository).items():
        if outcome.resolution_status != OutcomeResolutionStatus.SETTLED:
            continue
        if outcome_id in outcome_ids_before or outcome_id in existing_outcome_ids:
            continue
        line = json.dumps(
            {"record_type": "outcome", "payload": outcome_v1_to_dict(outcome)},
            sort_keys=True,
            separators=(",", ":"),
        )
        with intelligence_jsonl_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
        appended += 1
    return appended


def _note_result(
    summary: Item7NaturalSettlementResult,
    result: SettlementResult,
) -> Item7NaturalSettlementResult:
    reasons = dict(summary.refusal_reasons)
    if result.status == SettlementStatus.NOT_DUE:
        return Item7NaturalSettlementResult(
            now_ns=summary.now_ns,
            not_due=summary.not_due + 1,
            due_unlabelable=summary.due_unlabelable,
            settled=summary.settled,
            already_settled=summary.already_settled,
            outcomes_appended=summary.outcomes_appended,
            refusal_reasons=reasons,
        )
    if result.status == SettlementStatus.ALREADY_SETTLED:
        return Item7NaturalSettlementResult(
            now_ns=summary.now_ns,
            not_due=summary.not_due,
            due_unlabelable=summary.due_unlabelable,
            settled=summary.settled,
            already_settled=summary.already_settled + 1,
            outcomes_appended=summary.outcomes_appended,
            refusal_reasons=reasons,
        )
    if result.status == SettlementStatus.SETTLED:
        return Item7NaturalSettlementResult(
            now_ns=summary.now_ns,
            not_due=summary.not_due,
            due_unlabelable=summary.due_unlabelable,
            settled=summary.settled + 1,
            already_settled=summary.already_settled,
            outcomes_appended=summary.outcomes_appended,
            refusal_reasons=reasons,
        )
    reason = str(result.unlabelable_reason or result.status.value)
    reasons[reason] = reasons.get(reason, 0) + 1
    return Item7NaturalSettlementResult(
        now_ns=summary.now_ns,
        not_due=summary.not_due,
        due_unlabelable=summary.due_unlabelable + 1,
        settled=summary.settled,
        already_settled=summary.already_settled,
        outcomes_appended=summary.outcomes_appended,
        refusal_reasons=reasons,
    )


def _persist_settled_only(
    repository: IntelligenceRepository,
    result: SettlementResult,
) -> SettlementResult:
    """Persist only SETTLED outcomes; never seal UNLABELABLE on this path."""

    if result.status != SettlementStatus.SETTLED or result.outcome is None:
        return result
    put_result = repository.put_outcome(result.outcome)
    if put_result != RepositoryPutResult.ALREADY_PRESENT:
        return result
    existing = repository.get_outcome(result.outcome.outcome_id)
    return SettlementResult(
        status=SettlementStatus.ALREADY_SETTLED,
        ledger_entry_id=result.ledger_entry_id,
        forecast_id=result.forecast_id,
        outcome=existing,
        outcome_id=existing.outcome_id if existing is not None else result.outcome_id,
        label_available_time_ns=result.label_available_time_ns,
        anchor_receipt=result.anchor_receipt,
        terminal_receipt=result.terminal_receipt,
        realized_return=result.realized_return,
        unlabelable_reason=result.unlabelable_reason,
        mode=result.mode,
        scenario_id=result.scenario_id,
        ledger_entry=result.ledger_entry,
    )


def exercise_item7_natural_settlement(
    repository: IntelligenceRepository,
    *,
    now_ns: int,
    ledger_entry_ids: set[str] | None = None,
    persist_outcomes: bool = True,
    intelligence_jsonl_path: Path | None = None,
    outcome_ids_before: set[str] | None = None,
) -> Item7NaturalSettlementResult:
    """Settle mature ledger rows through policy when observations exist (fail-closed).

    When ``persist_outcomes`` is True, only ``SETTLED`` rows are written. Due
    ``UNLABELABLE`` results are counted on the receipt but do not call
    ``put_outcome`` and are not appended to governed JSONL.
    """

    service = OutcomeSettlementService(repository)
    entries = _ledger_entries_in_repository(repository)
    if ledger_entry_ids is not None:
        allowed = {str(value) for value in ledger_entry_ids}
        entries = tuple(row for row in entries if row.ledger_entry_id in allowed)

    summary = Item7NaturalSettlementResult(now_ns=int(now_ns))
    before = outcome_ids_before if outcome_ids_before is not None else _outcome_ids(repository)

    for entry in entries:
        # Always evaluate without repository persist first so UNLABELABLE cannot
        # seal the ledger; then persist SETTLED only when requested.
        result = service.settle(entry, now_ns=int(now_ns), persist=False)
        if persist_outcomes:
            result = _persist_settled_only(repository, result)
        summary = _note_result(summary, result)

    appended = 0
    if intelligence_jsonl_path is not None and persist_outcomes:
        appended = append_settled_outcomes_to_governed_jsonl(
            repository,
            intelligence_jsonl_path=intelligence_jsonl_path,
            outcome_ids_before=before,
        )
    if appended:
        summary = Item7NaturalSettlementResult(
            now_ns=summary.now_ns,
            not_due=summary.not_due,
            due_unlabelable=summary.due_unlabelable,
            settled=summary.settled,
            already_settled=summary.already_settled,
            outcomes_appended=appended,
            refusal_reasons=summary.refusal_reasons,
        )
    return summary


__all__ = [
    "ARTIFACT_KIND",
    "Item7NaturalSettlementResult",
    "append_settled_outcomes_to_governed_jsonl",
    "exercise_item7_natural_settlement",
]
