"""Pure direction target adjudication (BUILD 15)."""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts.common import (
    ContractKind,
    ContractReference,
    Direction,
    OutcomeResolutionStatus,
    QualityState,
    QualitySummary,
)
from ..contracts.outcome import OutcomeV1
from ..contracts.prediction_ledger import PredictionLedgerEntryV1
from .identity import derive_outcome_id
from .p6_compat import p6_classify_return, p6_realized_return
from .policy import OutcomeSettlementPolicy
from .types import (
    PriceObservationReceipt,
    SettlementMode,
    SettlementResult,
    SettlementStatus,
    TerminalResolutionReceipt,
    UnlabelableReason,
)


@dataclass(frozen=True, slots=True)
class DirectionOutcomeAdjudicator:
    """Pure adjudicator — no repository or clock access."""

    def adjudicate(
        self,
        *,
        entry: PredictionLedgerEntryV1,
        policy: OutcomeSettlementPolicy,
        anchor: PriceObservationReceipt,
        terminal: TerminalResolutionReceipt,
        settlement_clock_ns: int,
        mode: SettlementMode | str,
        scenario_id: str | None = None,
    ) -> SettlementResult:
        if settlement_clock_ns < entry.availability_cutoff_ns:
            return SettlementResult(
                status=SettlementStatus.NOT_DUE,
                ledger_entry_id=entry.ledger_entry_id,
                forecast_id=entry.forecast_id,
                mode=str(mode),
                scenario_id=scenario_id,
                ledger_entry=entry,
                anchor_receipt=anchor,
                terminal_receipt=terminal,
            )
        label_available_time_ns = entry.availability_cutoff_ns
        if terminal.observation is None:
            return self._unlabelable(
                entry=entry,
                reason=UnlabelableReason.NO_TARGET_OBSERVATION.value,
                settlement_clock_ns=settlement_clock_ns,
                label_available_time_ns=label_available_time_ns,
                anchor=anchor,
                terminal=terminal,
                mode=mode,
                scenario_id=scenario_id,
            )
        realized_return = p6_realized_return(p0=anchor.price, p_target=terminal.observation.price)
        label_class = p6_classify_return(realized_return)
        if label_class == "ZERO_RETURN":
            return self._unlabelable(
                entry=entry,
                reason=UnlabelableReason.ZERO_RETURN.value,
                settlement_clock_ns=settlement_clock_ns,
                label_available_time_ns=label_available_time_ns,
                anchor=anchor,
                terminal=terminal,
                mode=mode,
                scenario_id=scenario_id,
                realized_return=realized_return,
            )
        direction = Direction.LONG if label_class == "UP" else Direction.SHORT
        outcome_id = derive_outcome_id(
            forecast_id=entry.forecast_id,
            ledger_entry_id=entry.ledger_entry_id,
            settlement_policy_identity=entry.settlement_policy_identity,
            mode=mode,
            scenario_id=scenario_id,
        )
        outcome = OutcomeV1(
            outcome_id=outcome_id,
            schema_version="1",
            forecast_id=entry.forecast_id,
            adjudicated_at_ns=settlement_clock_ns,
            resolution_status=OutcomeResolutionStatus.SETTLED,
            quality=QualitySummary(state=QualityState.GOOD),
            start_observation=anchor.to_dict(),
            end_observation={
                **terminal.to_dict(),
                "label_available_time_ns": label_available_time_ns,
            },
            realized_return=realized_return,
            realized_direction=direction,
            lineage_refs=(
                ContractReference(kind=ContractKind.FORECAST.value, id=entry.forecast_id),
                ContractReference(kind=ContractKind.PREDICTION_LEDGER_ENTRY.value, id=entry.ledger_entry_id),
            ),
            metadata={
                "settlement_policy_identity": entry.settlement_policy_identity,
                "mode": str(mode),
                "scenario_id": scenario_id,
                "label_available_time_ns": label_available_time_ns,
                "target_time_ns": entry.target_time_ns,
                "ledger_entry_id": entry.ledger_entry_id,
            },
        )
        return SettlementResult(
            status=SettlementStatus.SETTLED,
            ledger_entry_id=entry.ledger_entry_id,
            forecast_id=entry.forecast_id,
            outcome=outcome,
            outcome_id=outcome.outcome_id,
            label_available_time_ns=label_available_time_ns,
            anchor_receipt=anchor,
            terminal_receipt=terminal,
            realized_return=realized_return,
            mode=str(mode),
            scenario_id=scenario_id,
            ledger_entry=entry,
        )

    def _unlabelable(
        self,
        *,
        entry: PredictionLedgerEntryV1,
        reason: str,
        settlement_clock_ns: int,
        label_available_time_ns: int,
        anchor: PriceObservationReceipt,
        terminal: TerminalResolutionReceipt,
        mode: SettlementMode | str,
        scenario_id: str | None,
        realized_return: float | None = None,
    ) -> SettlementResult:
        outcome_id = derive_outcome_id(
            forecast_id=entry.forecast_id,
            ledger_entry_id=entry.ledger_entry_id,
            settlement_policy_identity=entry.settlement_policy_identity,
            mode=mode,
            scenario_id=scenario_id,
        )
        outcome = OutcomeV1(
            outcome_id=outcome_id,
            schema_version="1",
            forecast_id=entry.forecast_id,
            adjudicated_at_ns=settlement_clock_ns,
            resolution_status=OutcomeResolutionStatus.UNLABELABLE,
            quality=QualitySummary(state=QualityState.DEGRADED),
            start_observation=anchor.to_dict(),
            end_observation={
                **terminal.to_dict(),
                "label_available_time_ns": label_available_time_ns,
            },
            realized_return=realized_return,
            unlabelable_reason=reason,
            lineage_refs=(
                ContractReference(kind=ContractKind.FORECAST.value, id=entry.forecast_id),
                ContractReference(kind=ContractKind.PREDICTION_LEDGER_ENTRY.value, id=entry.ledger_entry_id),
            ),
            metadata={
                "settlement_policy_identity": entry.settlement_policy_identity,
                "mode": str(mode),
                "scenario_id": scenario_id,
                "label_available_time_ns": label_available_time_ns,
                "ledger_entry_id": entry.ledger_entry_id,
            },
        )
        return SettlementResult(
            status=SettlementStatus.UNLABELABLE,
            ledger_entry_id=entry.ledger_entry_id,
            forecast_id=entry.forecast_id,
            outcome=outcome,
            outcome_id=outcome.outcome_id,
            unlabelable_reason=reason,
            label_available_time_ns=label_available_time_ns,
            anchor_receipt=anchor,
            terminal_receipt=terminal,
            realized_return=realized_return,
            mode=str(mode),
            scenario_id=scenario_id,
            ledger_entry=entry,
        )


__all__ = ["DirectionOutcomeAdjudicator"]
