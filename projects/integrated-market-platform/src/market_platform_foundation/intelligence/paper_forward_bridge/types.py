"""Prospective Paper forward-testing domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


SCHEMA_VERSION = "intelligence/paper_forward_bridge/1.0.0"


class ForwardTestRunKind(StrEnum):
    """Explicit run classification — forward tests must never masquerade as backtests."""

    FORWARD_TEST = "FORWARD_TEST"
    BACKTEST = "BACKTEST"


class ForwardTestMode(StrEnum):
    """Whether the forward test may submit a governed Paper order."""

    SIGNAL_ONLY = "SIGNAL_ONLY"
    EXECUTION = "EXECUTION"


class ForwardTestState(StrEnum):
    DRAFT = "DRAFT"
    LOCKED = "LOCKED"
    PAPER_SUBMITTED = "PAPER_SUBMITTED"
    PAPER_ACTIVE = "PAPER_ACTIVE"
    OBSERVING = "OBSERVING"
    EVALUABLE = "EVALUABLE"
    EVALUATED = "EVALUATED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    INVALID = "INVALID"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ForwardTestSessionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class EvaluationState(StrEnum):
    PENDING = "PENDING"
    OBSERVING = "OBSERVING"
    EVALUABLE = "EVALUABLE"
    EVALUATED = "EVALUATED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ForwardTestCohortArm(StrEnum):
    BASELINE = "BASELINE"
    AI_ENHANCED = "AI_ENHANCED"


class ForwardTestEvidenceClass(StrEnum):
    UNCLASSIFIED = "UNCLASSIFIED"
    SOFTWARE_FIXTURE_ONLY = "SOFTWARE_FIXTURE_ONLY"
    PAPER_OBSERVED = "PAPER_OBSERVED"
    ACTUAL_FORWARD = "ACTUAL_FORWARD"
    REPLAY = "REPLAY"
    FIXTURE = "FIXTURE"
    SYNTHETIC = "SYNTHETIC"
    SHAKEDOWN = "SHAKEDOWN"


@dataclass(frozen=True, slots=True)
class ForwardTestSession:
    session_id: str
    account_id: str
    mode: str
    strategy_id: str
    strategy_version: str
    universe: tuple[str, ...]
    evaluation_horizon_ns: int
    created_at_ns: int
    status: ForwardTestSessionStatus
    campaign_id: str | None = None
    protocol_id: str | None = None
    activation_version: str | None = None
    manifest_fingerprint: str | None = None
    cohort_arm: ForwardTestCohortArm | None = None
    config_frozen: bool = False
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "account_id": self.account_id,
            "mode": self.mode,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "universe": list(self.universe),
            "evaluation_horizon_ns": self.evaluation_horizon_ns,
            "created_at_ns": self.created_at_ns,
            "status": self.status.value,
            "campaign_id": self.campaign_id,
            "protocol_id": self.protocol_id,
            "activation_version": self.activation_version,
            "manifest_fingerprint": self.manifest_fingerprint,
            "cohort_arm": self.cohort_arm.value if self.cohort_arm else None,
            "config_frozen": self.config_frozen,
            "config": dict(self.config),
        }


@dataclass(frozen=True, slots=True)
class ForwardTestObservation:
    observation_id: str
    observed_at_ns: int
    source_time_ns: int
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "observed_at_ns": self.observed_at_ns,
            "source_time_ns": self.source_time_ns,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True, slots=True)
class SignalOutcomeMetrics:
    entry_reference_price: float | None
    exit_reference_price: float | None
    absolute_return: float | None
    percentage_return: float | None
    directional_correct: bool | None
    quality: str
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_reference_price": self.entry_reference_price,
            "exit_reference_price": self.exit_reference_price,
            "absolute_return": self.absolute_return,
            "percentage_return": self.percentage_return,
            "directional_correct": self.directional_correct,
            "quality": self.quality,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class ExecutionOutcomeMetrics:
    paper_order_id: str | None
    paper_intent_id: str | None
    realized_pnl_minor: int | None
    unrealized_pnl_minor: int | None
    fill_count: int
    quality: str
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "paper_order_id": self.paper_order_id,
            "paper_intent_id": self.paper_intent_id,
            "realized_pnl_minor": self.realized_pnl_minor,
            "unrealized_pnl_minor": self.unrealized_pnl_minor,
            "fill_count": self.fill_count,
            "quality": self.quality,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class ForwardTestDecision:
    forward_test_id: str
    session_id: str | None
    account_id: str
    mode: str
    run_kind: ForwardTestRunKind
    test_mode: ForwardTestMode
    symbol: str
    decision_time_ns: int
    source_time_ns: int
    state: ForwardTestState
    direction: str
    quantity: int | None
    confidence: float | None
    strategy_id: str
    strategy_version: str
    research_artifact_ref: str | None
    evaluation_horizon_ns: int
    decision_payload: dict[str, Any]
    provenance_snapshot: dict[str, Any]
    paper_order_id: str | None = None
    paper_intent_id: str | None = None
    locked_at_ns: int | None = None
    submitted_at_ns: int | None = None
    observations: tuple[ForwardTestObservation, ...] = ()
    signal_outcome: SignalOutcomeMetrics | None = None
    execution_outcome: ExecutionOutcomeMetrics | None = None
    evaluation_state: EvaluationState = EvaluationState.PENDING
    failure_reason: str | None = None
    evidence_class: ForwardTestEvidenceClass = ForwardTestEvidenceClass.UNCLASSIFIED
    cohort_arm: ForwardTestCohortArm | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "forward_test_id": self.forward_test_id,
            "session_id": self.session_id,
            "account_id": self.account_id,
            "mode": self.mode,
            "run_kind": self.run_kind.value,
            "test_mode": self.test_mode.value,
            "symbol": self.symbol,
            "decision_time_ns": self.decision_time_ns,
            "source_time_ns": self.source_time_ns,
            "state": self.state.value,
            "direction": self.direction,
            "quantity": self.quantity,
            "confidence": self.confidence,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "research_artifact_ref": self.research_artifact_ref,
            "evaluation_horizon_ns": self.evaluation_horizon_ns,
            "decision_payload": dict(self.decision_payload),
            "provenance_snapshot": dict(self.provenance_snapshot),
            "paper_order_id": self.paper_order_id,
            "paper_intent_id": self.paper_intent_id,
            "locked_at_ns": self.locked_at_ns,
            "submitted_at_ns": self.submitted_at_ns,
            "observations": [item.to_dict() for item in self.observations],
            "signal_outcome": self.signal_outcome.to_dict() if self.signal_outcome else None,
            "execution_outcome": self.execution_outcome.to_dict() if self.execution_outcome else None,
            "evaluation_state": self.evaluation_state.value,
            "failure_reason": self.failure_reason,
            "evidence_class": self.evidence_class.value,
            "cohort_arm": self.cohort_arm.value if self.cohort_arm else None,
        }
