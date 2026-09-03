"""Outcome settlement orchestration services (BUILD 15)."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..contracts.forecast import ForecastV1
from ..contracts.prediction_ledger import PredictionLedgerEntryV1
from ..persistence.repository import IntelligenceRepository, RepositoryPutResult
from .adjudicator import DirectionOutcomeAdjudicator
from .errors import OutcomeRegistrationError, OutcomeSettlementError
from .ledger import anchor_receipt_from_entry, build_prediction_ledger_entry
from .policy import OutcomeSettlementPolicy, policy_for_forecast
from .resolver import OutcomeObservationResolver
from .scheduler import OutcomeSettlementScheduler
from .types import SettlementMode, SettlementResult, SettlementStatus


@dataclass
class PredictionLedgerService:
    repository: IntelligenceRepository

    def register_forecast(
        self,
        forecast: ForecastV1,
        *,
        now_ns: int,
        mode: SettlementMode = SettlementMode.ACTUAL_LIVE,
        scenario_id: str | None = None,
        policy: OutcomeSettlementPolicy | None = None,
        reject_late_registration: bool = True,
        persist: bool = True,
    ) -> PredictionLedgerEntryV1 | SettlementResult:
        stored = self.repository.get_forecast(forecast.forecast_id)
        if stored is None:
            raise OutcomeRegistrationError(
                "FORECAST_NOT_FOUND",
                details={"forecast_id": forecast.forecast_id},
            )
        try:
            entry = build_prediction_ledger_entry(
                stored,
                self.repository,
                policy=policy,
                mode=mode,
                scenario_id=scenario_id,
                registered_at_ns=now_ns,
                reject_late_registration=reject_late_registration,
            )
        except OutcomeRegistrationError as exc:
            if exc.code == "LATE_REGISTRATION":
                return SettlementResult(
                    status=SettlementStatus.LATE_REGISTRATION,
                    ledger_entry_id="",
                    forecast_id=forecast.forecast_id,
                    unlabelable_reason=exc.code,
                    mode=str(mode),
                    scenario_id=scenario_id,
                    diagnostics={"details": exc.details},
                )
            if exc.code in {
                SettlementStatus.UNSUPPORTED_TARGET.value,
                "UNSUPPORTED_TARGET",
                "UNSUPPORTED_HORIZON",
            } or str(exc.code).startswith("UNLABELABLE"):
                return SettlementResult(
                    status=SettlementStatus.REGISTRATION_FAILED,
                    ledger_entry_id="",
                    forecast_id=forecast.forecast_id,
                    unlabelable_reason=str(exc.code),
                    mode=str(mode),
                    scenario_id=scenario_id,
                    diagnostics={"details": exc.details},
                )
            raise
        if persist:
            self.repository.put_prediction_ledger_entry(entry)
        return entry


@dataclass
class OutcomeSettlementService:
    repository: IntelligenceRepository
    adjudicator: DirectionOutcomeAdjudicator = field(default_factory=DirectionOutcomeAdjudicator)
    resolver: OutcomeObservationResolver | None = None
    scheduler: OutcomeSettlementScheduler | None = None

    def __post_init__(self) -> None:
        if self.resolver is None:
            self.resolver = OutcomeObservationResolver(self.repository)
        if self.scheduler is None:
            self.scheduler = OutcomeSettlementScheduler(self.repository)

    def inspect_settlement(
        self,
        entry: PredictionLedgerEntryV1,
        *,
        now_ns: int,
    ) -> SettlementStatus:
        if now_ns < entry.availability_cutoff_ns:
            return SettlementStatus.NOT_DUE
        for outcome in self.repository.get_outcomes_by_forecast(entry.forecast_id):
            if outcome.metadata.get("ledger_entry_id") != entry.ledger_entry_id:
                continue
            if outcome.metadata.get("mode") != entry.mode:
                continue
            if entry.scenario_id is not None and outcome.metadata.get("scenario_id") != entry.scenario_id:
                continue
            return SettlementStatus.ALREADY_SETTLED
        return SettlementStatus.DUE

    def settle(
        self,
        entry: PredictionLedgerEntryV1,
        *,
        now_ns: int,
        persist: bool = True,
    ) -> SettlementResult:
        status = self.inspect_settlement(entry, now_ns=now_ns)
        if status == SettlementStatus.ALREADY_SETTLED:
            existing = self._existing_outcome(entry)
            return SettlementResult(
                status=SettlementStatus.ALREADY_SETTLED,
                ledger_entry_id=entry.ledger_entry_id,
                forecast_id=entry.forecast_id,
                outcome=existing,
                outcome_id=existing.outcome_id if existing is not None else None,
                mode=entry.mode,
                scenario_id=entry.scenario_id,
                ledger_entry=entry,
            )
        if now_ns < entry.availability_cutoff_ns:
            return SettlementResult(
                status=SettlementStatus.NOT_DUE,
                ledger_entry_id=entry.ledger_entry_id,
                forecast_id=entry.forecast_id,
                mode=entry.mode,
                scenario_id=entry.scenario_id,
                ledger_entry=entry,
            )
        policy = policy_for_forecast(
            target_kind=entry.target.target_kind,
            horizon_ns=entry.horizon_ns,
        )
        if policy is None or policy.policy_id != entry.settlement_policy_identity:
            raise OutcomeSettlementError(
                "POLICY_MISMATCH",
                details={
                    "expected": entry.settlement_policy_identity,
                    "resolved": policy.policy_id if policy else None,
                },
            )
        anchor = anchor_receipt_from_entry(entry)
        terminal = self.resolver.resolve_terminal(entry, settlement_policy=policy, settlement_clock_ns=now_ns)
        result = self.adjudicator.adjudicate(
            entry=entry,
            policy=policy,
            anchor=anchor,
            terminal=terminal,
            settlement_clock_ns=now_ns,
            mode=entry.mode,
            scenario_id=entry.scenario_id,
        )
        if persist and result.outcome is not None:
            put_result = self.repository.put_outcome(result.outcome)
            if put_result == RepositoryPutResult.ALREADY_PRESENT:
                existing = self.repository.get_outcome(result.outcome.outcome_id)
                return SettlementResult(
                    status=SettlementStatus.ALREADY_SETTLED,
                    ledger_entry_id=entry.ledger_entry_id,
                    forecast_id=entry.forecast_id,
                    outcome=existing,
                    outcome_id=existing.outcome_id if existing is not None else result.outcome_id,
                    label_available_time_ns=result.label_available_time_ns,
                    anchor_receipt=result.anchor_receipt,
                    terminal_receipt=result.terminal_receipt,
                    realized_return=result.realized_return,
                    unlabelable_reason=result.unlabelable_reason,
                    mode=entry.mode,
                    scenario_id=entry.scenario_id,
                    ledger_entry=entry,
                )
        return result

    def settle_due(
        self,
        entries: tuple[PredictionLedgerEntryV1, ...] | list[PredictionLedgerEntryV1],
        *,
        now_ns: int,
        persist: bool = True,
    ) -> tuple[SettlementResult, ...]:
        due = self.scheduler.list_due_entries(entries, now_ns=now_ns)
        return tuple(self.settle(entry, now_ns=now_ns, persist=persist) for entry in due)

    def _existing_outcome(self, entry: PredictionLedgerEntryV1):
        for outcome in self.repository.get_outcomes_by_forecast(entry.forecast_id):
            if outcome.metadata.get("ledger_entry_id") != entry.ledger_entry_id:
                continue
            if outcome.metadata.get("mode") != entry.mode:
                continue
            if entry.scenario_id is not None and outcome.metadata.get("scenario_id") != entry.scenario_id:
                continue
            return outcome
        return None


__all__ = ["OutcomeSettlementService", "PredictionLedgerService"]
