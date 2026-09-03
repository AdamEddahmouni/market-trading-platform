"""Deterministic outcome settlement scheduler (BUILD 15)."""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts.prediction_ledger import PredictionLedgerEntryV1
from ..persistence.repository import IntelligenceRepository
from .types import SettlementStatus


@dataclass(frozen=True, slots=True)
class OutcomeSettlementScheduler:
    repository: IntelligenceRepository

    def due_time_ns(self, entry: PredictionLedgerEntryV1) -> int:
        return entry.availability_cutoff_ns

    def inspect(self, entry: PredictionLedgerEntryV1, *, now_ns: int) -> SettlementStatus:
        if now_ns < self.due_time_ns(entry):
            return SettlementStatus.NOT_DUE
        existing = self.repository.get_outcomes_by_forecast(entry.forecast_id)
        for outcome in existing:
            if outcome.metadata.get("ledger_entry_id") == entry.ledger_entry_id and outcome.metadata.get("mode") == entry.mode:
                if entry.scenario_id is None or outcome.metadata.get("scenario_id") == entry.scenario_id:
                    return SettlementStatus.ALREADY_SETTLED
        return SettlementStatus.DUE

    def is_due(self, entry: PredictionLedgerEntryV1, *, now_ns: int) -> bool:
        return now_ns >= self.due_time_ns(entry)

    def list_due_entries(
        self,
        entries: tuple[PredictionLedgerEntryV1, ...] | list[PredictionLedgerEntryV1],
        *,
        now_ns: int,
    ) -> tuple[PredictionLedgerEntryV1, ...]:
        return tuple(entry for entry in entries if self.is_due(entry, now_ns=now_ns))


__all__ = ["OutcomeSettlementScheduler"]
