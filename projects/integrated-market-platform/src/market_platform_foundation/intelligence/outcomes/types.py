"""Settlement runtime types (BUILD 15)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..contracts.outcome import OutcomeV1
from ..contracts.prediction_ledger import PredictionLedgerEntryV1


class SettlementMode(StrEnum):
    ACTUAL_LIVE = "ACTUAL_LIVE"
    COUNTERFACTUAL = "COUNTERFACTUAL"


class SettlementStatus(StrEnum):
    NOT_DUE = "NOT_DUE"
    DUE = "DUE"
    SETTLED = "SETTLED"
    ALREADY_SETTLED = "ALREADY_SETTLED"
    UNLABELABLE = "UNLABELABLE"
    REGISTRATION_FAILED = "REGISTRATION_FAILED"
    UNSUPPORTED_TARGET = "UNSUPPORTED_TARGET"
    LATE_REGISTRATION = "LATE_REGISTRATION"
    FAILED = "FAILED"


class UnlabelableReason(StrEnum):
    NO_VALID_ANCHOR = "UNLABELABLE_NO_REFERENCE_PRICE"
    NO_TARGET_OBSERVATION = "UNLABELABLE_NO_HORIZON_TRADE"
    INVALID_TARGET_OBSERVATION = "TARGET_DATA_INVALID"
    TARGET_DATA_CONFLICT = "TARGET_DATA_CONFLICT"
    ZERO_RETURN = "ZERO_RETURN"
    ANCHOR_TEMPORALLY_INVALID = "ANCHOR_TEMPORALLY_INVALID"
    UNSUPPORTED_TARGET = "UNSUPPORTED_TARGET"
    UNSUPPORTED_HORIZON = "UNSUPPORTED_HORIZON"
    SOURCE_POLICY_MISMATCH = "SOURCE_POLICY_MISMATCH"


@dataclass(frozen=True, slots=True)
class PriceObservationReceipt:
    event_id: str
    price: float
    event_time_ns: int
    available_time_ns: int
    observation_kind: str
    provider_id: str | None = None
    source_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "event_id": self.event_id,
            "price": self.price,
            "event_time_ns": self.event_time_ns,
            "available_time_ns": self.available_time_ns,
            "observation_kind": self.observation_kind,
        }
        if self.provider_id is not None:
            body["provider_id"] = self.provider_id
        if self.source_type is not None:
            body["source_type"] = self.source_type
        return body


@dataclass(frozen=True, slots=True)
class TerminalResolutionReceipt:
    observation: PriceObservationReceipt | None
    target_time_ns: int
    target_window_start_ns: int
    target_window_end_ns: int
    availability_cutoff_ns: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_time_ns": self.target_time_ns,
            "target_window_start_ns": self.target_window_start_ns,
            "target_window_end_ns": self.target_window_end_ns,
            "availability_cutoff_ns": self.availability_cutoff_ns,
            "observation": self.observation.to_dict() if self.observation is not None else None,
        }


@dataclass(frozen=True, slots=True)
class SettlementResult:
    status: SettlementStatus
    ledger_entry_id: str
    forecast_id: str
    outcome: OutcomeV1 | None = None
    outcome_id: str | None = None
    unlabelable_reason: str | None = None
    label_available_time_ns: int | None = None
    anchor_receipt: PriceObservationReceipt | None = None
    terminal_receipt: TerminalResolutionReceipt | None = None
    realized_return: float | None = None
    mode: str | None = None
    scenario_id: str | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)
    ledger_entry: PredictionLedgerEntryV1 | None = None


__all__ = [
    "PriceObservationReceipt",
    "SettlementMode",
    "SettlementResult",
    "SettlementStatus",
    "TerminalResolutionReceipt",
    "UnlabelableReason",
]
