"""DTO projections for PLATFORM-P4-001 §5.1 broker paper observability API.

Read-only views over the composition's ``paper_execution`` slot and the
event-sourced IMP paper ledger. The broker-side view and the IMP ledger view
are carried in **separate** response sections and are never conflated
(PLATFORM-P4-001 §5.1): the broker section reports what the adapter observes
(broker statuses verbatim, ADR-PROV-001 provenance timestamps), while the IMP
section reports the ledger projection (IMP ``ORDER_LIFECYCLE_STATES``).

Fail-closed degradation (P4-SAFE-001): when the broker paper adapter is
unconfigured or disconnected the broker section is a structured error payload
carrying the repo sentinel codes (``EXECUTION_NOT_ENABLED``,
``PROVIDER_NOT_CONFIGURED``, ``TRADIER_TOKEN_NOT_CONFIGURED``,
``TRADIER_PRODUCTION_ENDPOINT_BLOCKED``, ``BROKER_TRANSPORT_NOT_IMPLEMENTED``,
``EXECUTION_ADAPTER_NOT_IMPLEMENTED``) — never a crash. Only adapter-local
fetch surfaces already exposed by the provider are used; no new provider calls
are invented here. All outputs are deterministic: no wall clock, no random ids
(envelope ``ingest_run_id``/``normalized_event_id`` are deliberately excluded).
"""

from __future__ import annotations

import os
from typing import Any

from ..platform.reconciliation.engine import RECONCILIATION_VERSION
from ..providers.adapters.tradier_paper import (
    TRADIER_SANDBOX_ENDPOINT,
    TradierPaperExecutionProvider,
)
from ..providers.composition import get_provider_composition
from ..providers.contracts import EXECUTION_DISABLED
from .store import ReplayStore

AUTHORITY_BOUNDARY = "BROKER_PAPER_OBSERVABILITY"

# Sentinel for a composition slot without adapter-local fetch methods
# (DisabledPaperExecutionProvider vocabulary).
EXECUTION_ADAPTER_NOT_IMPLEMENTED = "EXECUTION_ADAPTER_NOT_IMPLEMENTED"


def _broker_provider() -> Any:
    return get_provider_composition().paper_execution


def _header(store: ReplayStore, provider: Any) -> dict[str, Any]:
    ledger = store.paper_ledger
    return {
        "authority_boundary": AUTHORITY_BOUNDARY,
        "capability": getattr(provider, "capability", None),
        "data_mode": ledger.data_mode,
        "execution_authority": ledger.execution_authority,
        "execution_mode": ledger.execution_mode,
        "execution_provider": ledger.execution_provider,
        "provider_id": getattr(provider, "provider_id", None),
    }


def _unavailable(reason_code: str) -> dict[str, Any]:
    return {"available": False, "reason_code": str(reason_code)}


def _first_event(result: Any) -> dict[str, Any] | None:
    events = getattr(result, "events", ()) or ()
    for event in events:
        if isinstance(event, dict):
            return event
    return None


def _fetch_via(provider: Any, method_name: str, **kwargs: Any) -> tuple[Any | None, dict[str, Any] | None]:
    """Call one adapter-local fetch method, degrading fail-closed.

    Returns ``(result, None)`` on an ok result and ``(None, unavailable)``
    when the method is missing, gated off, or transport-unavailable.
    """
    fetch = getattr(provider, method_name, None)
    if not callable(fetch):
        return None, _unavailable(EXECUTION_ADAPTER_NOT_IMPLEMENTED)
    result = fetch(**kwargs)
    if str(getattr(result, "status", "")) != "ok":
        reason = str(getattr(result, "reason_code", "") or EXECUTION_DISABLED)
        return None, _unavailable(reason)
    return result, None


# -- GET /paper/broker/orders --------------------------------------------------


def build_broker_orders_payload(store: ReplayStore) -> dict[str, Any]:
    """Broker-side order observations alongside the IMP ledger order view."""
    provider = _broker_provider()
    imp_orders = store.paper_ledger.project_orders()
    broker_records: list[dict[str, Any]] = []
    unavailable: dict[str, Any] | None = None
    for order in imp_orders:
        broker_order_id = str(order.get("broker_order_id") or "")
        # Orders not yet bound to a broker id exist only in the IMP view.
        if not broker_order_id:
            continue
        result, failure = _fetch_via(provider, "fetch_order", broker_order_id=broker_order_id)
        if failure is not None:
            # All orders share one gate/transport state; the first failure
            # represents the broker connection for every record.
            unavailable = failure
            break
        event = _first_event(result)
        payload = event.get("payload") if isinstance(event, dict) else None
        if not isinstance(payload, dict):
            unavailable = _unavailable("PROVIDER_NOT_CONFIGURED")
            break
        metadata = event.get("provider_metadata") if isinstance(event, dict) else None
        provenance: dict[str, Any] = {
            "event_time_ns": payload.get("event_time_ns"),
            "raw_source_reference": event.get("raw_reference") if isinstance(event, dict) else None,
            "receive_time_ns": payload.get("receive_time_ns"),
        }
        if isinstance(metadata, dict):
            symbol_mapping = metadata.get("symbol_mapping")
            provenance["symbol_mapping"] = symbol_mapping if isinstance(symbol_mapping, dict) else None
        fills = [
            {
                "broker_fill_id": fill.get("broker_fill_id"),
                "event_time_ns": fill.get("event_time_ns"),
                "price_minor": fill.get("price_minor"),
                "quantity": fill.get("quantity"),
                "receive_time_ns": fill.get("receive_time_ns"),
            }
            for fill in payload.get("fills", [])
            if isinstance(fill, dict)
        ]
        broker_records.append(
            {
                # IMP linkage only; the broker lifecycle fields below stay verbatim.
                "broker_order_id": payload.get("broker_order_id"),
                "avg_fill_price_minor": payload.get("avg_fill_price_minor"),
                "filled_quantity": payload.get("filled_quantity"),
                "fills": fills,
                "imp_order_id": str(order.get("order_id", "")),
                "provenance": provenance,
                "status": payload.get("status"),
                "broker_status_raw": payload.get("broker_status_raw"),
            }
        )
    if unavailable is None:
        broker_view: dict[str, Any] = {"available": True, "orders": broker_records}
    else:
        broker_view = unavailable
    return {
        **_header(store, provider),
        "broker_view": broker_view,
        "imp_ledger_view": {"orders": imp_orders},
    }


# -- GET /paper/broker/account -------------------------------------------------


def build_broker_account_payload(store: ReplayStore) -> dict[str, Any]:
    """Broker-side cash observation alongside the IMP ledger account view."""
    provider = _broker_provider()
    result, failure = _fetch_via(provider, "fetch_account")
    if failure is not None:
        broker_view: dict[str, Any] = failure
    else:
        event = _first_event(result)
        record = event if isinstance(event, dict) else {}
        broker_view = {
            "account": {
                "as_of_ns": record.get("as_of_ns"),
                "buying_power_minor": record.get("buying_power_minor"),
                "cash_minor": record.get("cash_minor"),
                "capability": record.get("capability"),
                "provider_id": record.get("provider_id"),
            },
            "available": True,
        }
    return {
        **_header(store, provider),
        "broker_view": broker_view,
        "imp_ledger_view": {"account": store.paper_ledger.project_account()},
    }


# -- GET /paper/broker/positions -----------------------------------------------


_POSITION_KEYS = (
    "as_of_ns",
    "avg_price_minor",
    "broker_position_id",
    "instrument_id",
    "quantity",
)


def build_broker_positions_payload(store: ReplayStore) -> dict[str, Any]:
    """Broker-side position snapshot alongside the IMP ledger position view."""
    provider = _broker_provider()
    result, failure = _fetch_via(provider, "fetch_positions")
    if failure is not None:
        broker_view: dict[str, Any] = failure
    else:
        event = _first_event(result)
        record = event if isinstance(event, dict) else {}
        raw_positions = record.get("positions")
        positions = [
            {key: row.get(key) for key in _POSITION_KEYS}
            for row in (raw_positions or [])
            if isinstance(row, dict)
        ]
        broker_view = {
            "available": True,
            "as_of_ns": record.get("as_of_ns"),
            "capability": record.get("capability"),
            "positions": positions,
            "provider_id": record.get("provider_id"),
        }
    return {
        **_header(store, provider),
        "broker_view": broker_view,
        "imp_ledger_view": {"positions": store.paper_ledger.project_positions()},
    }


# -- GET /paper/broker/reconciliation ------------------------------------------


def build_broker_reconciliation_payload(store: ReplayStore) -> dict[str, Any]:
    """Read-only reconciliation status derived from recorded ledger events.

    Never runs the reconciliation engine (read-only observability); it only
    projects already-recorded ``ReconciliationRecorded`` /
    ``ReconciliationCorrectionRecorded`` events.
    """
    provider = _broker_provider()
    ledger = store.paper_ledger
    risk = ledger.project_risk()
    corrections_by_report: dict[str, list[dict[str, Any]]] = {}
    history: list[dict[str, Any]] = []
    for event in ledger.events:
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        event_type = event.get("event_type")
        report_id = str(payload.get("report_id", ""))
        if event_type == "ReconciliationRecorded":
            history.append(
                {
                    "as_of_ns": payload.get("as_of_ns"),
                    "corrections": [],
                    "mismatch_fields": list(payload.get("mismatch_fields", [])),
                    "overall_status": payload.get("overall_status"),
                    "report_id": report_id,
                }
            )
        elif event_type == "ReconciliationCorrectionRecorded" and report_id:
            corrections_by_report.setdefault(report_id, []).append(
                {
                    "field": payload.get("field"),
                    "resolution": payload.get("resolution"),
                }
            )
    for report in history:
        report["corrections"] = corrections_by_report.get(str(report["report_id"]), [])
    return {
        **_header(store, provider),
        "engine_version": RECONCILIATION_VERSION,
        "history": history,
        "last_report": risk.get("last_reconciliation"),
        "reconciliation_status": risk.get("reconciliation_status"),
    }


# -- GET /paper/broker/health ---------------------------------------------------


def _tradier_gate_state(env: dict[str, str]) -> tuple[dict[str, bool], str | None, str]:
    """Mirror the adapter's gate precedence so codes match real fetch results."""
    endpoint = env.get("IMP_TRADIER_ENDPOINT") or TRADIER_SANDBOX_ENDPOINT
    gates = {
        "IMP_BROKER_PAPER_EXECUTION": env.get("IMP_BROKER_PAPER_EXECUTION") == "1",
        "IMP_TRADIER_PAPER": env.get("IMP_TRADIER_PAPER") == "1",
        "IMP_TRADIER_TOKEN": bool(env.get("IMP_TRADIER_TOKEN")),
        "IMP_TRADIER_ENDPOINT_SANDBOX": endpoint == TRADIER_SANDBOX_ENDPOINT,
    }
    if env.get("IMP_TRADIER_PAPER") != "1":
        return gates, EXECUTION_DISABLED, endpoint
    if env.get("IMP_BROKER_PAPER_EXECUTION") != "1":
        return gates, EXECUTION_DISABLED, endpoint
    if not env.get("IMP_TRADIER_TOKEN", ""):
        return gates, "TRADIER_TOKEN_NOT_CONFIGURED", endpoint
    if endpoint != TRADIER_SANDBOX_ENDPOINT:
        return gates, "TRADIER_PRODUCTION_ENDPOINT_BLOCKED", endpoint
    return gates, None, endpoint


def build_broker_health_payload(store: ReplayStore) -> dict[str, Any]:
    """Configuration-only provider health; no broker request is dispatched."""
    provider = _broker_provider()
    is_tradier = isinstance(provider, TradierPaperExecutionProvider)
    env = dict(getattr(provider, "_env", None) or os.environ)
    if is_tradier:
        gates, reason_code, endpoint = _tradier_gate_state(env)
        state = "CONFIGURED" if reason_code is None else "NOT_CONFIGURED"
    else:
        gates = None
        reason_code = EXECUTION_ADAPTER_NOT_IMPLEMENTED
        state = "UNAVAILABLE"
        endpoint = None
    payload = {
        **_header(store, provider),
        "adapter": type(provider).__name__,
        "configuration_gates": gates,
        "connection": {"reason_code": reason_code, "state": state},
        "ledger_binding": {
            "data_mode": store.paper_ledger.data_mode,
            "execution_mode": store.paper_ledger.execution_mode,
            "execution_provider": store.paper_ledger.execution_provider,
            "session_id": store.paper_ledger.session_id,
        },
        "sandbox_endpoint": endpoint,
        "supports": {
            "cancel_order": callable(getattr(provider, "cancel_order", None)),
            "fetch_account": callable(getattr(provider, "fetch_account", None)),
            "fetch_order": callable(getattr(provider, "fetch_order", None)),
            "fetch_positions": callable(getattr(provider, "fetch_positions", None)),
        },
    }
    return payload


__all__ = [
    "AUTHORITY_BOUNDARY",
    "build_broker_account_payload",
    "build_broker_health_payload",
    "build_broker_orders_payload",
    "build_broker_positions_payload",
    "build_broker_reconciliation_payload",
]
