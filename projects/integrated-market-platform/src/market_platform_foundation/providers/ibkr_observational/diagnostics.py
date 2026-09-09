"""IBKR observational diagnostics + capability readiness (G6).

Readiness is per capability, never inferred from TCP/TWS connectivity alone:

- READY — connected, entitled, fresh data flowing.
- DEGRADED — connected with partial capability (e.g. L1 good, L2 not
  entitled).
- UNAVAILABLE — disconnected.
- FAILED — contract resolution or subscription failure.

Capability separation: CONTRACT_RESOLUTION / L1 / L2.
"""

from __future__ import annotations

from typing import Any

from ...order_flow.order_book.freshness import FreshnessPolicy, evaluate_book_freshness
from ...order_flow.order_book.projection import project_book_snapshot
from .contracts import (
    AdapterDiagnostics,
    CapabilityKind,
    EntitlementState,
    IbkrConnectionState,
    PacingReport,
)


class CapabilityReadiness:
    CONTRACT_RESOLUTION = "CONTRACT_RESOLUTION"
    L1 = "L1"
    L2 = "L2"
    TRADES = "TRADES"


class ReadinessState:
    READY = "READY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"


def compute_readiness(
    *,
    connection_state: IbkrConnectionState,
    subscriptions: dict[str, dict[str, Any]],
    entitlement: EntitlementState,
    book_freshness: dict[str, str] | None = None,
) -> dict[str, str]:
    """Aggregate capability readiness from adapter facts (pure)."""
    l1_active = any(
        row.get("capability") == CapabilityKind.L1.value
        and row.get("state") in {"ACTIVE", "SUBSCRIBING"}
        for row in subscriptions.values()
    )
    l2_active = any(
        row.get("capability") == CapabilityKind.L2.value
        and row.get("state") in {"ACTIVE", "SUBSCRIBING"}
        for row in subscriptions.values()
    )
    trades_active = any(
        row.get("capability") == CapabilityKind.TRADES.value
        and row.get("state") in {"ACTIVE", "SUBSCRIBING"}
        for row in subscriptions.values()
    )
    l2_entitled = entitlement not in {
        EntitlementState.NOT_ENTITLED.value,
        EntitlementState.UNKNOWN.value,
    }

    connected = connection_state in {
        IbkrConnectionState.CONNECTED.value,
        IbkrConnectionState.DEGRADED.value,
    }
    disconnected = connection_state in {
        IbkrConnectionState.DISCONNECTED.value,
        IbkrConnectionState.FAILED.value,
    }

    def contract_resolution() -> str:
        if disconnected:
            return ReadinessState.UNAVAILABLE
        if not connected:
            return ReadinessState.DEGRADED
        return ReadinessState.READY

    def l1() -> str:
        if disconnected:
            return ReadinessState.UNAVAILABLE
        if not connected:
            return ReadinessState.DEGRADED
        return ReadinessState.READY if l1_active else ReadinessState.DEGRADED

    def l2() -> str:
        if disconnected:
            return ReadinessState.UNAVAILABLE
        if not connected:
            return ReadinessState.DEGRADED
        if not l2_active:
            return ReadinessState.DEGRADED
        if not l2_entitled:
            return ReadinessState.FAILED
        freshness = (book_freshness or {}).get(CapabilityReadiness.L2)
        if freshness in {"STALE", "INVALID", "UNAVAILABLE"}:
            return ReadinessState.DEGRADED
        return ReadinessState.READY

    def trades() -> str:
        if disconnected:
            return ReadinessState.UNAVAILABLE
        if not connected:
            return ReadinessState.DEGRADED
        if not trades_active:
            return ReadinessState.DEGRADED
        if entitlement is EntitlementState.NOT_ENTITLED:
            return ReadinessState.FAILED
        return ReadinessState.READY

    return {
        CapabilityReadiness.CONTRACT_RESOLUTION: contract_resolution(),
        CapabilityReadiness.L1: l1(),
        CapabilityReadiness.L2: l2(),
        CapabilityReadiness.TRADES: trades(),
    }


def book_facts(
    *,
    store: Any,
    instrument_id: str,
    as_of_time_ns: int | None = None,
) -> dict[str, Any]:
    """Compact canonical book diagnostics (engine-derived truth)."""
    engine = store.book_engine_for(instrument_id)
    if engine is None:
        return {
            "book_state": "UNAVAILABLE",
            "book_state_valid": False,
            "freshness": "UNAVAILABLE",
            "sequence_state": "NO_SEQUENCE",
        }
    canonical = project_book_snapshot(engine, include_rows=False)
    freshness = "UNAVAILABLE"
    if engine.last_received_time_ns is not None and as_of_time_ns is not None:
        freshness = evaluate_book_freshness(
            engine,
            as_of_time_ns=as_of_time_ns,
            policy=FreshnessPolicy(),
        ).status.value
    return {
        "book_state": canonical.get("book_status", "UNKNOWN"),
        "book_state_valid": canonical.get("book_state_valid", False),
        "freshness": freshness,
        "generation": canonical.get("generation", engine.generation),
        "sequence_state": canonical.get("sequence_state", engine.sequence_state.value),
        "level_counts": canonical.get("level_counts"),
        "subscription_id": engine.subscription_id,
    }


def build_diagnostics(
    *,
    provider: str,
    connection_state: IbkrConnectionState,
    connection_generation: int,
    reconnect_count: int,
    reset_count: int,
    l1_count: int,
    l2_count: int,
    trades_count: int = 0,
    subscriptions: dict[str, dict[str, Any]],
    pacing: PacingReport,
    entitlement: EntitlementState,
    last_error: dict[str, Any] | None,
    last_received_ns: int | None,
) -> AdapterDiagnostics:
    return AdapterDiagnostics(
        provider=provider,
        connection_state=connection_state,
        connection_generation=connection_generation,
        reconnect_count=reconnect_count,
        reset_count=reset_count,
        l1_subscription_count=l1_count,
        l2_subscription_count=l2_count,
        trades_subscription_count=trades_count,
        subscriptions=subscriptions,
        pacing=pacing.as_dict(),
        entitlement_state=entitlement,
        last_error=last_error,
        last_received_ns=last_received_ns,
    )


__all__ = [
    "CapabilityReadiness",
    "ReadinessState",
    "book_facts",
    "build_diagnostics",
    "compute_readiness",
]