"""Automatic settlement worker for EVIDENCE-01B."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from ...contracts.prediction_ledger import PredictionLedgerEntryV1
from ...outcomes.service import OutcomeSettlementService
from ...outcomes.types import SettlementMode, SettlementStatus
from ...persistence.repository import IntelligenceRepository
from ..evidence01a.observations import persist_outcome
from ..evidence01a.store import CampaignStore
from .types import MAX_SETTLEMENT_RETRIES, SettlementWorkerState


@dataclass
class SettlementRetryState:
    ledger_entry_id: str
    retry_count: int = 0
    last_attempt_ns: int = 0
    last_disposition: str | None = None


@dataclass
class SettlementBatchResult:
    settled: int = 0
    skipped_immature: int = 0
    already_settled: int = 0
    transient_failures: int = 0
    permanent_failures: int = 0
    backlog: int = 0
    states: dict[str, int] = field(default_factory=dict)


def _classify_settlement_state(
    entry: PredictionLedgerEntryV1,
    *,
    now_ns: int,
    status: SettlementStatus | None,
) -> SettlementWorkerState:
    if entry.target_time_ns > now_ns:
        return SettlementWorkerState.AWAITING_MATURITY
    if status == SettlementStatus.ALREADY_SETTLED:
        return SettlementWorkerState.SETTLED
    if status == SettlementStatus.NOT_DUE:
        return SettlementWorkerState.AWAITING_MATURITY
    if status == SettlementStatus.DUE:
        return SettlementWorkerState.MATURE_UNSETTLED
    return SettlementWorkerState.MATURE_UNSETTLED


@dataclass
class SettlementWorker:
    repository: IntelligenceRepository
    store: CampaignStore | None = None
    _retry_state: dict[str, SettlementRetryState] = field(default_factory=dict)

    def run_settlement_batch(self, *, now_ns: int | None = None) -> SettlementBatchResult:
        cutoff = now_ns if now_ns is not None else time.time_ns()
        service = OutcomeSettlementService(self.repository)
        result = SettlementBatchResult()
        states: dict[str, int] = {}

        for entry in self.repository.query_prediction_ledger_entries(
            decision_start_ns=0,
            decision_end_ns=cutoff,
        ):
            inspect = service.inspect_settlement(entry, now_ns=cutoff)
            state = _classify_settlement_state(entry, now_ns=cutoff, status=inspect)
            states[state.value] = states.get(state.value, 0) + 1

            if state == SettlementWorkerState.AWAITING_MATURITY:
                result.skipped_immature += 1
                continue

            if state == SettlementWorkerState.SETTLED:
                result.already_settled += 1
                continue

            retry = self._retry_state.get(entry.ledger_entry_id)
            if retry and retry.retry_count >= MAX_SETTLEMENT_RETRIES:
                result.permanent_failures += 1
                states[SettlementWorkerState.UNLABELABLE.value] = (
                    states.get(SettlementWorkerState.UNLABELABLE.value, 0) + 1
                )
                continue

            try:
                settle_result = service.settle(entry, now_ns=cutoff)
                if settle_result.outcome is not None:
                    if self.store is not None:
                        persist_outcome(self.store, settle_result.outcome)
                    result.settled += 1
                    self._retry_state.pop(entry.ledger_entry_id, None)
                elif settle_result.status == SettlementStatus.ALREADY_SETTLED:
                    result.already_settled += 1
                else:
                    result.transient_failures += 1
                    self._record_retry(entry.ledger_entry_id, cutoff, str(settle_result.status))
            except Exception:
                result.transient_failures += 1
                self._record_retry(entry.ledger_entry_id, cutoff, "EXCEPTION")

        result.states = states
        result.backlog = states.get(SettlementWorkerState.MATURE_UNSETTLED.value, 0)
        return result

    def _record_retry(self, ledger_entry_id: str, now_ns: int, disposition: str) -> None:
        existing = self._retry_state.get(ledger_entry_id)
        if existing:
            self._retry_state[ledger_entry_id] = SettlementRetryState(
                ledger_entry_id=ledger_entry_id,
                retry_count=existing.retry_count + 1,
                last_attempt_ns=now_ns,
                last_disposition=disposition,
            )
        else:
            self._retry_state[ledger_entry_id] = SettlementRetryState(
                ledger_entry_id=ledger_entry_id,
                retry_count=1,
                last_attempt_ns=now_ns,
                last_disposition=disposition,
            )

    def settlement_backlog(self, *, now_ns: int | None = None) -> int:
        cutoff = now_ns if now_ns is not None else time.time_ns()
        service = OutcomeSettlementService(self.repository)
        count = 0
        for entry in self.repository.query_prediction_ledger_entries(
            decision_start_ns=0,
            decision_end_ns=cutoff,
        ):
            inspect = service.inspect_settlement(entry, now_ns=cutoff)
            if inspect == SettlementStatus.DUE:
                count += 1
        return count
