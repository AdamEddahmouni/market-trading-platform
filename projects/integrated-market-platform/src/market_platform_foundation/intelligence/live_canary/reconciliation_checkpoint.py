"""Durable reconciliation checkpoints across sessions (BUILD 30)."""

from __future__ import annotations

from ..live_execution_safety.types import ReconciliationHealthState
from .identity import derive_checkpoint_id
from .ledger import LiveExecutionLedger
from .types import (
    LIVE_CANARY_SCHEMA_VERSION,
    LiveReconciliationCheckpointV1,
)


class ReconciliationCheckpointResult:
    __slots__ = ("passed", "reason_codes", "checkpoint")

    def __init__(
        self,
        *,
        passed: bool,
        reason_codes: tuple[str, ...],
        checkpoint: LiveReconciliationCheckpointV1,
    ) -> None:
        self.passed = passed
        self.reason_codes = reason_codes
        self.checkpoint = checkpoint


def build_reconciliation_checkpoint(
    *,
    as_of_ns: int,
    broker: str,
    account_ref: str,
    ledger: LiveExecutionLedger,
    broker_open_orders: tuple[str, ...] = (),
    broker_fills: tuple[str, ...] = (),
    broker_positions: tuple[dict[str, object], ...] = (),
    local_positions: tuple[dict[str, object], ...] = (),
    session_ref: str | None = None,
    program_run_ref: str | None = None,
    incident_refs: tuple[str, ...] = (),
) -> LiveReconciliationCheckpointV1:
    local_orders = ledger.get_open_local_orders()
    local_fills = tuple(f.broker_fill_id for f in ledger.fill_receipts)
    matched = tuple(set(local_orders) & set(broker_open_orders))
    local_only = tuple(o for o in local_orders if o not in broker_open_orders)
    broker_only = tuple(o for o in broker_open_orders if o not in local_orders)
    fill_local_only = tuple(f for f in local_fills if f not in broker_fills)
    fill_broker_only = tuple(f for f in broker_fills if f not in local_fills)
    conflicts: list[str] = []
    if local_only:
        conflicts.append("LOCAL_ONLY_ORDERS")
    if broker_only:
        conflicts.append("BROKER_ONLY_ORDERS")
    if broker_fills and (fill_local_only or fill_broker_only):
        conflicts.append("FILL_MISMATCH")
    health = ReconciliationHealthState.HEALTHY.value
    if conflicts:
        health = ReconciliationHealthState.UNHEALTHY.value

    checkpoint = LiveReconciliationCheckpointV1(
        checkpoint_id="",
        schema_version=LIVE_CANARY_SCHEMA_VERSION,
        as_of_ns=as_of_ns,
        broker=broker,
        account_ref=account_ref,
        known_local_orders=local_orders,
        broker_open_orders=broker_open_orders,
        known_local_fills=local_fills,
        broker_fills=broker_fills,
        local_positions=local_positions,
        broker_positions=broker_positions,
        matched=matched,
        local_only=local_only,
        broker_only=broker_only,
        conflicts=tuple(conflicts),
        health=health,
        incident_refs=incident_refs,
        session_ref=session_ref,
        program_run_ref=program_run_ref,
    )
    object.__setattr__(checkpoint, "checkpoint_id", derive_checkpoint_id(checkpoint))
    return checkpoint


def evaluate_checkpoint_clean(checkpoint: LiveReconciliationCheckpointV1) -> ReconciliationCheckpointResult:
    reason_codes: list[str] = []
    if checkpoint.broker_only:
        reason_codes.append("BROKER_ONLY_ORDER")
    if checkpoint.local_only:
        reason_codes.append("LOCAL_ONLY_ORDER")
    if checkpoint.conflicts:
        reason_codes.extend(checkpoint.conflicts)
    if checkpoint.health != ReconciliationHealthState.HEALTHY.value:
        reason_codes.append("RECONCILIATION_UNHEALTHY")
    passed = len(reason_codes) == 0
    return ReconciliationCheckpointResult(
        passed=passed,
        reason_codes=tuple(reason_codes),
        checkpoint=checkpoint,
    )
