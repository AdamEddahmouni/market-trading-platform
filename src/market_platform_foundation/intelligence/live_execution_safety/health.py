"""Broker execution health assessment (BUILD 28)."""

from __future__ import annotations

from .identity import _sha256_prefix
from .types import (
    LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
    AccountEnvironment,
    BrokerExecutionHealthV1,
    ReconciliationHealthState,
)


def build_broker_execution_health(
    *,
    broker: str,
    account_environment: AccountEnvironment,
    as_of_ns: int,
    adapter_loaded: bool = True,
    connection_available: bool = True,
    environment_identified: bool = True,
    account_resolved: bool = True,
    permissions_observable: bool = False,
    preview_endpoint_available: bool = False,
    order_status_feed_available: bool = False,
    reconciliation_healthy: bool = True,
) -> BrokerExecutionHealthV1:
    if account_environment == AccountEnvironment.UNKNOWN:
        disposition = ReconciliationHealthState.UNKNOWN
        reason_codes = ("BROKER_ENVIRONMENT_UNKNOWN",)
    elif not adapter_loaded or not connection_available:
        disposition = ReconciliationHealthState.UNHEALTHY
        reason_codes = ("BROKER_CONNECTION_UNAVAILABLE",)
    elif not environment_identified:
        disposition = ReconciliationHealthState.UNKNOWN
        reason_codes = ("ENVIRONMENT_NOT_IDENTIFIED",)
    else:
        disposition = ReconciliationHealthState.HEALTHY
        reason_codes = ()

    health_id = _sha256_prefix(
        "BROKHLTH",
        {
            "broker": broker,
            "account_environment": account_environment.value,
            "as_of_ns": as_of_ns,
            "disposition": disposition.value,
        },
    )
    return BrokerExecutionHealthV1(
        health_id=health_id,
        schema_version=LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
        broker=broker,
        account_environment=account_environment,
        adapter_loaded=adapter_loaded,
        connection_available=connection_available,
        environment_identified=environment_identified,
        account_resolved=account_resolved,
        permissions_observable=permissions_observable,
        preview_endpoint_available=preview_endpoint_available,
        order_status_feed_available=order_status_feed_available,
        reconciliation_healthy=reconciliation_healthy,
        disposition=disposition,
        as_of_ns=as_of_ns,
        reason_codes=reason_codes,
    )
