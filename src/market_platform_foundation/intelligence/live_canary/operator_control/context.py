"""Mutable operator control plane runtime context (BUILD 31).

Holds references to canonical BUILD 29/30 state. Snapshots and timelines are
derived; this context does not redefine trading authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..kill_switch_store import KillSwitchStore
from ..ledger import LiveExecutionLedger
from ..program_accounting import ProgramAccounting
from ..types import (
    CanaryAuthorizationPreviewV1,
    LiveCanaryPolicyV1,
    LiveCanaryProgramPolicyV1,
    LiveCanaryProgramRunV1,
    LiveExecutionIncidentV1,
    LiveOrderConfirmationV1,
    LiveReconciliationCheckpointV1,
    ProgramGovernanceState,
)
from ...live_execution_safety.types import BrokerOrderIntentV1, LiveExecutionAuthorizationV1
from .types import OperatorActionReceiptV1


@dataclass
class PendingOrderReview:
    confirmation_preview: LiveOrderConfirmationV1
    order_intent: BrokerOrderIntentV1
    risk_decision_ref: str
    requested_quantity: int
    approved_quantity: int
    opportunity_ref: str | None = None
    trade_proposal_ref: str | None = None
    forecast_ref: str | None = None
    preview_snapshot_ref: str | None = None


@dataclass
class OperatorControlContext:
    """Interactive operator session over canonical live-canary state."""

    program_policy: LiveCanaryProgramPolicyV1
    canary_policy: LiveCanaryPolicyV1
    program_run: LiveCanaryProgramRunV1 | None = None
    governance_state: ProgramGovernanceState = ProgramGovernanceState.PROGRAM_PREPARED
    session_ref: str | None = None
    session_state: str | None = None
    kill_switch: KillSwitchStore = field(default_factory=KillSwitchStore)
    ledger: LiveExecutionLedger = field(default_factory=LiveExecutionLedger)
    accounting: ProgramAccounting = field(default_factory=ProgramAccounting)
    incidents: list[LiveExecutionIncidentV1] = field(default_factory=list)
    authorization: LiveExecutionAuthorizationV1 | None = None
    authorization_preview: CanaryAuthorizationPreviewV1 | None = None
    pending_order_reviews: dict[str, PendingOrderReview] = field(default_factory=dict)
    confirmed_orders: dict[str, LiveOrderConfirmationV1] = field(default_factory=dict)
    checkpoints: list[LiveReconciliationCheckpointV1] = field(default_factory=list)
    action_receipts: list[OperatorActionReceiptV1] = field(default_factory=list)
    idempotency_keys: dict[str, OperatorActionReceiptV1] = field(default_factory=dict)
    snapshot_versions: dict[str, str] = field(default_factory=dict)
    frozen_snapshots: dict[str, object] = field(default_factory=dict)
    broker_health: str = "UNKNOWN"
    reconciliation_health: str = "UNKNOWN"
    resume_approvals: list[Any] = field(default_factory=list)
    restart_generation: int = 0
    drill_mode: bool = False

    def latest_checkpoint(self) -> LiveReconciliationCheckpointV1 | None:
        return self.checkpoints[-1] if self.checkpoints else None

    def open_incidents(self) -> tuple[LiveExecutionIncidentV1, ...]:
        return tuple(i for i in self.incidents if i.state.value == "OPEN")

    def critical_open_incidents(self) -> tuple[LiveExecutionIncidentV1, ...]:
        return tuple(
            i
            for i in self.incidents
            if i.state.value == "OPEN" and i.severity.value == "CRITICAL"
        )
