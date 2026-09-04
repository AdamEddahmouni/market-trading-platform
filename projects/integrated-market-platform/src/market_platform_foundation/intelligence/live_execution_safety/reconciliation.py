"""Broker reconciliation snapshots for live safety (BUILD 28)."""

from __future__ import annotations

from .identity import derive_reconciliation_snapshot_id
from .types import (
    LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
    AccountEnvironment,
    BrokerReconciliationSnapshotV1,
    ReconciliationHealthState,
)


def build_reconciliation_snapshot(
    *,
    broker: str,
    account_environment: AccountEnvironment,
    as_of_ns: int,
    local_open_intents: tuple[str, ...],
    broker_open_orders: tuple[str, ...],
    local_known_fills: tuple[str, ...] = (),
    broker_fills: tuple[str, ...] = (),
) -> BrokerReconciliationSnapshotV1:
    local_set = set(local_open_intents)
    broker_set = set(broker_open_orders)
    matched = tuple(sorted(local_set & broker_set))
    local_only = tuple(sorted(local_set - broker_set))
    broker_only = tuple(sorted(broker_set - local_set))
    conflicts: list[str] = []
    reason_codes: list[str] = []

    if broker_only:
        reason_codes.append("BROKER_ONLY_ORDER")
    if local_only:
        reason_codes.append("LOCAL_ONLY_ORDER")

    if broker_only or local_only or conflicts:
        health = ReconciliationHealthState.UNHEALTHY
    else:
        health = ReconciliationHealthState.HEALTHY

    snapshot = BrokerReconciliationSnapshotV1(
        snapshot_id="",
        schema_version=LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
        broker=broker,
        account_environment=account_environment,
        as_of_ns=as_of_ns,
        local_open_intents=local_open_intents,
        broker_open_orders=broker_open_orders,
        local_known_fills=local_known_fills,
        broker_fills=broker_fills,
        matched=matched,
        local_only=local_only,
        broker_only=broker_only,
        conflicts=tuple(conflicts),
        health_state=health,
        reason_codes=tuple(reason_codes),
    )
    object.__setattr__(snapshot, "snapshot_id", derive_reconciliation_snapshot_id(snapshot))
    return snapshot


def blocks_new_submission(snapshot: BrokerReconciliationSnapshotV1) -> bool:
    return snapshot.health_state != ReconciliationHealthState.HEALTHY
