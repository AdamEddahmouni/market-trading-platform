"""DTO projections for PLATFORM-PAPER-001 paper observability API."""

from __future__ import annotations

import time
from typing import Any

from ..operational_identity import attach_operational_identity
from ..paper.broker_paper import cancel_broker_paper_order
from ..paper.execution import cancel_interactive_order, preview_interactive_order, submit_interactive_order
from ..paper.contracts import decimal_minor_to_display
from ..paper.ledger import PaperExecutionLedger
from .account_registry import resolve_paper_portfolio_identity
from .lane_provenance import attach_lane_provenance
from .projections import build_as_of_context
from .store import ReplayStore


def _paper_envelope(store: ReplayStore, payload: dict[str, Any]) -> dict[str, Any]:
    from ..execution.simulator import SIMULATOR_VERSION
    from ..market_data.live_config import live_internal_simulation_enabled, live_observational_enabled
    from ..operating_modes import PAPER_EXECUTION_AUTHORITIES, paper_execution_env_enabled

    live = live_observational_enabled() or store.data_mode == "LIVE_OBSERVATIONAL" or store.paper_ledger.data_mode == "LIVE_OBSERVATIONAL"
    data_provider = "MOOMOO" if live else store.paper_ledger.data_provider
    execution_provider = "INTERNAL"
    paper_reachable = paper_execution_env_enabled() and (
        store.paper_ledger.execution_authority in PAPER_EXECUTION_AUTHORITIES or live_internal_simulation_enabled()
    )
    return {
        "as_of_context": build_as_of_context(store),
        "capability_states": [
            {
                "capability_id": "paper.execution",
                "state": "AVAILABLE" if paper_reachable else "GATED",
                "reason": store.paper_ledger.execution_mode,
            }
        ],
        "data_health": {
            "data_mode": store.paper_ledger.data_mode,
            "data_provider": data_provider,
            "detail": "Execution uses forward bars from replay cursor (no look-ahead)",
            "execution_authority": store.paper_ledger.execution_authority,
            "execution_mode": store.paper_ledger.execution_mode,
            "execution_provider": execution_provider,
            "quality_state": "PASS" if store.paper_ledger.data_mode == "FIXTURE_REPLAY" else "UNKNOWN",
            "simulation_model": SIMULATOR_VERSION,
        },
        **payload,
    }


def build_paper_account_payload(store: ReplayStore) -> dict[str, Any]:
    return _paper_envelope(store, {"account": store.paper_ledger.project_account()})


def build_paper_positions_payload(store: ReplayStore) -> dict[str, Any]:
    return _paper_envelope(store, {"positions": store.paper_ledger.project_positions()})


def build_paper_orders_payload(store: ReplayStore) -> dict[str, Any]:
    return _paper_envelope(store, {"orders": store.paper_ledger.project_orders()})


_TERMINAL_ORDER_STATES = frozenset({"FILLED", "CANCELLED", "REJECTED", "EXPIRED", "RISK_REJECTED"})


def _is_terminal_order_state(state: str | None) -> bool:
    if not state:
        return False
    return str(state).upper() in _TERMINAL_ORDER_STATES


def _sort_orders_desc(orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(order: dict[str, Any]) -> tuple[int, str]:
        seq = order.get("submitted_sequence")
        seq_val = int(seq) if isinstance(seq, (int, float)) else -1
        return (seq_val, str(order.get("order_id", "")))

    return sorted(orders, key=sort_key, reverse=True)


def build_paper_order_history_page(
    store: ReplayStore,
    *,
    cursor: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    page_size = min(max(int(limit or 25), 1), 100)
    all_orders = _sort_orders_desc(store.paper_ledger.project_orders())
    terminal_orders = [order for order in all_orders if _is_terminal_order_state(str(order.get("state", "")))]
    start = 0
    if cursor:
        for idx, order in enumerate(terminal_orders):
            if str(order.get("order_id", "")) == cursor:
                start = idx + 1
                break
    page = terminal_orders[start : start + page_size]
    next_cursor = (
        str(page[-1].get("order_id", ""))
        if len(page) == page_size and start + page_size < len(terminal_orders)
        else None
    )
    order_ids = {str(order.get("order_id", "")) for order in page}
    page_fills = [
        fill
        for fill in store.paper_ledger.project_fills()
        if str(fill.get("order_id", "")) in order_ids
    ]
    return _paper_envelope(
        store,
        {
            "fills": page_fills,
            "next_cursor": next_cursor,
            "orders": page,
            "page_size": page_size,
            "total_count": len(terminal_orders),
        },
    )


def build_paper_fills_payload(store: ReplayStore) -> dict[str, Any]:
    return _paper_envelope(store, {"fills": store.paper_ledger.project_fills()})


def build_paper_risk_payload(store: ReplayStore) -> dict[str, Any]:
    return _paper_envelope(store, {"risk": store.paper_ledger.project_risk()})


def build_paper_portfolio_payload(store: ReplayStore, *, view_mode: str | None = None) -> dict[str, Any]:
    from . import live_projections

    live_projections.apply_live_marks_to_ledger(store)
    ledger = store.paper_ledger
    identity = resolve_paper_portfolio_identity(store, view_mode=view_mode)
    account = ledger.project_account()
    positions = ledger.project_positions()
    orders = ledger.project_orders()
    fills = ledger.project_fills()
    risk = ledger.project_risk()
    gross_exposure = sum(abs(int(row.get("quantity", 0))) for row in positions)
    net_exposure = sum(int(row.get("quantity", 0)) for row in positions)
    observation_time = _paper_observation_time(store)
    envelope = _paper_envelope(
        store,
        {
            "account": account,
            "authority_boundary": "PAPER_OBSERVABILITY",
            "observation_time": observation_time,
            "data_health": {
                "data_mode": ledger.data_mode,
                "data_provider": "MOOMOO" if ledger.data_mode == "LIVE_OBSERVATIONAL" else ledger.data_provider,
                "detail": _portfolio_mark_detail(store),
                "execution_authority": ledger.execution_authority,
                "execution_mode": ledger.execution_mode,
                "execution_provider": "INTERNAL",
                "state": _portfolio_mark_quality(store),
            },
            "exposure": {
                "gross_notional_display": account.get("gross_exposure_display"),
                "gross_notional_minor": account.get("gross_exposure_minor"),
                "gross_shares": gross_exposure,
                "net_shares": net_exposure,
                "valuation_quality": account.get("valuation_quality"),
            },
            "fills": fills,
            "orders": orders,
            "pnl": {
                "realized_minor": int(account.get("realized_pnl_minor", 0)),
                "realized_display": account.get("realized_pnl_display"),
                "total_display": (
                    decimal_minor_to_display(
                        int(account.get("realized_pnl_minor", 0)) + int(account["unrealized_pnl_minor"])
                    )
                    if account.get("unrealized_pnl_minor") is not None
                    else None
                ),
                "total_minor": (
                    int(account.get("realized_pnl_minor", 0)) + int(account["unrealized_pnl_minor"])
                    if account.get("unrealized_pnl_minor") is not None
                    else None
                ),
                "unrealized_display": account.get("unrealized_pnl_display"),
                "unrealized_minor": account.get("unrealized_pnl_minor"),
                "valuation_quality": account.get("valuation_quality"),
                "valuation_reasons": account.get("valuation_reasons", []),
            },
            "positions": positions,
            "reconciliation_status": risk.get("reconciliation_status"),
            "risk": risk,
            "session": {
                "execution_authority": ledger.execution_authority,
                "execution_mode": ledger.execution_mode,
                "paper_account_id": ledger.paper_account_id,
                "session_id": ledger.session_id,
                "starting_cash_minor": int(ledger.policy.get("initial_cash_minor", 0)),
            },
            **_active_instrument_fields(store),
        },
    )
    envelope = attach_operational_identity(envelope, identity)
    return attach_lane_provenance(envelope, lane_id="paper-portfolio", retrieved_at_ns=time.time_ns())


def build_paper_trace_payload(
    store: ReplayStore,
    *,
    intent_id: str | None = None,
    order_id: str | None = None,
    fill_id: str | None = None,
) -> dict[str, Any]:
    trace = store.paper_ledger.project_execution_trace(
        intent_id=intent_id,
        order_id=order_id,
        fill_id=fill_id,
    )
    return _paper_envelope(
        store,
        {
            "authority_boundary": "PAPER_EXECUTION_OBSERVABILITY",
            "trace": trace,
        },
    )


def _parse_order_body(body: dict[str, Any], store: ReplayStore) -> dict[str, Any]:
    from ..paper.decision_source import (
        parse_decision_source_snapshot,
        validate_snapshot_against_correlation,
    )

    side = str(body.get("side", "")).upper()
    quantity = int(body.get("quantity", 0))
    if quantity <= 0:
        raise ValueError("ORDER_QUANTITY_INVALID")
    if side not in {"BUY", "SELL"}:
        raise ValueError("ORDER_SIDE_INVALID")
    order_type = str(body.get("order_type", "MARKET")).upper()
    if order_type not in {"MARKET", "LIMIT"}:
        raise ValueError("ORDER_TYPE_INVALID")
    limit_price_minor = body.get("limit_price_minor")
    if order_type == "LIMIT" and limit_price_minor is None:
        raise ValueError("ORDER_LIMIT_PRICE_REQUIRED")
    client_order_id = str(body.get("client_order_id", "")).strip() or _default_client_order_id(store)
    idempotency_key = str(body.get("idempotency_key", "")).strip() or client_order_id
    correlation_id = str(body.get("correlation_id", "")).strip() or client_order_id
    explicit = body.get("instrument_id") or body.get("symbol")
    raw_snapshot = body.get("decision_source_snapshot")
    decision_source_snapshot = None
    if raw_snapshot is not None:
        decision_source_snapshot = parse_decision_source_snapshot(raw_snapshot)
        decision_source_snapshot = validate_snapshot_against_correlation(
            snapshot=decision_source_snapshot,
            correlation_id=correlation_id,
        )
    return {
        "client_order_id": client_order_id,
        "correlation_id": correlation_id,
        "decision_source_snapshot": decision_source_snapshot,
        "explicit_instrument": explicit,
        "idempotency_key": idempotency_key,
        "limit_price_minor": int(limit_price_minor) if limit_price_minor is not None else None,
        "order_type": order_type,
        "quantity": quantity,
        "side": side,
    }


def _assert_live_execution_allowed(store: ReplayStore, *, submit: bool = False) -> None:
    from ..market_data.internal_simulation_gate import evaluate_internal_simulation_gates
    from ..market_data.live_config import (
        live_internal_simulation_enabled,
        live_observational_enabled,
        moomoo_live_enabled,
    )
    from ..market_data.live_runtime import get_live_runtime
    from ..market_data.provider_lifecycle import ProviderConnectionState

    if store.data_mode != "LIVE_OBSERVATIONAL":
        return
    if not (live_observational_enabled() and moomoo_live_enabled()):
        return
    if not live_internal_simulation_enabled():
        raise ValueError("LIVE_INTERNAL_SIMULATION_DISABLED")
    runtime = get_live_runtime(create=False)
    if runtime is None:
        raise ValueError("LIVE_RUNTIME_UNAVAILABLE")
    if runtime.lifecycle.connection_state in {
        ProviderConnectionState.DISCONNECTED,
        ProviderConnectionState.RECONNECTING,
        ProviderConnectionState.ERROR,
        ProviderConnectionState.DISABLED,
    }:
        raise ValueError("LIVE_FEED_UNHEALTHY")
    restored = bool(getattr(store, "execution_deferred", False))
    if not submit and not restored:
        return
    # Explicit over inherited: no deployment-level PIT adversarial verification
    # exists at runtime, so pass None (gate records ATTESTED, never a fake
    # PASS). Flip to True only when a verified PIT result backs this deployment.
    gate = evaluate_internal_simulation_gates(
        runtime=runtime,
        probe_stale=runtime.capability_registry.is_stale,
        pit_tests_pass=None,
    )
    if gate.status != "AUTHORIZED":
        if restored:
            raise ValueError("RESTORED_SESSION_AWAITING_FRESH_LIVE_HEALTH")
        raise ValueError("LIVE_INTERNAL_SIMULATION_DEFERRED")


def maybe_release_execution_gate(store: ReplayStore) -> None:
    if not getattr(store, "execution_deferred", False):
        return
    from ..market_data.live_config import live_internal_simulation_enabled
    from ..operating_modes import paper_execution_env_enabled

    if not paper_execution_env_enabled():
        store.paper_ledger.execution_authority = "BLOCKED"
        store.execution_authority = "BLOCKED"
        return
    try:
        _assert_live_execution_allowed(store, submit=True)
    except ValueError:
        store.paper_ledger.execution_authority = "BLOCKED"
        store.execution_authority = "BLOCKED"
        return
    if store.paper_ledger.execution_mode != "INTERNAL_SIMULATION":
        return
    authority = "PAPER_ONLY" if live_internal_simulation_enabled() else "AUTHORIZED"
    store.paper_ledger.execution_authority = authority
    store.execution_mode = "INTERNAL_SIMULATION"
    store.execution_authority = authority
    store.execution_deferred = False


def preview_paper_order(store: ReplayStore, body: dict[str, Any]) -> dict[str, Any]:
    from . import live_projections

    live_projections.apply_live_marks_to_ledger(store)
    maybe_release_execution_gate(store)
    _assert_live_execution_allowed(store, submit=False)
    parsed = _parse_order_body(body, store)
    focus = _require_order_instrument(store, parsed["explicit_instrument"])
    preview = preview_interactive_order(
        ledger=store.paper_ledger,
        bars=_bars_for_paper_execution(store, instrument_id=focus),
        symbol=focus,
        instrument_id=focus,
        side=parsed["side"],
        quantity=parsed["quantity"],
        observation_time=_paper_observation_time(store, instrument_id=focus),
        client_order_id=parsed["client_order_id"],
        idempotency_key=parsed["idempotency_key"],
        order_type=parsed["order_type"],
        limit_price_minor=parsed["limit_price_minor"],
        correlation_id=parsed["correlation_id"],
        decision_source_snapshot=parsed["decision_source_snapshot"],
    )
    return _paper_envelope(store, {"preview": preview})


def submit_paper_order(store: ReplayStore, body: dict[str, Any]) -> dict[str, Any]:
    from . import live_projections

    live_projections.apply_live_marks_to_ledger(store)
    maybe_release_execution_gate(store)
    parsed = _parse_order_body(body, store)
    existing_order_id = store.paper_ledger.lookup_idempotent_order(parsed["idempotency_key"])
    if existing_order_id:
        for order in store.paper_ledger.project_orders():
            if order.get("order_id") == existing_order_id:
                return _paper_envelope(
                    store,
                    {
                        "submission": {
                            "duplicate": True,
                            "idempotency_key": parsed["idempotency_key"],
                            "order": order,
                            "order_id": existing_order_id,
                        }
                    },
                )
    _assert_live_execution_allowed(store, submit=True)
    focus = _require_order_instrument(store, parsed["explicit_instrument"])
    intent_time = _paper_observation_time(store, instrument_id=focus)
    bars = _bars_for_paper_execution(store, instrument_id=focus)
    if parsed["order_type"] == "MARKET":
        bars = _wait_for_post_intent_bars(
            store,
            instrument_id=focus,
            created_time_ns=intent_time,
            bars=bars,
        )
    result = submit_interactive_order(
        ledger=store.paper_ledger,
        bars=bars,
        symbol=focus,
        instrument_id=focus,
        side=parsed["side"],
        quantity=parsed["quantity"],
        observation_time=intent_time,
        client_order_id=parsed["client_order_id"],
        idempotency_key=parsed["idempotency_key"],
        order_type=parsed["order_type"],
        limit_price_minor=parsed["limit_price_minor"],
        correlation_id=parsed["correlation_id"],
        decision_source_snapshot=parsed["decision_source_snapshot"],
    )
    return _paper_envelope(store, {"submission": result})


def cancel_paper_order(store: ReplayStore, body: dict[str, Any]) -> dict[str, Any]:
    order_id = str(body.get("order_id", "")).strip()
    if not order_id:
        raise ValueError("PAPER_ORDER_ID_REQUIRED")
    ledger = store.paper_ledger
    if ledger.execution_mode == "BROKER_PAPER":
        # Broker paper orders must be cancelled through the composed broker
        # adapter; appending a local-only CANCEL event would desynchronize the
        # ledger from a broker order that keeps working. Fail closed when no
        # adapter is composed (the disabled stub exposes no cancel_order).
        from ..providers.composition import get_provider_composition

        provider = get_provider_composition().paper_execution
        if not callable(getattr(provider, "cancel_order", None)):
            raise ValueError("PROVIDER_NOT_CONFIGURED")
        result = cancel_broker_paper_order(ledger=ledger, provider=provider, order_id=order_id)
    else:
        result = cancel_interactive_order(ledger=ledger, order_id=order_id)
    return _paper_envelope(store, {"cancellation": result})


def open_paper_session(store: ReplayStore, body: dict[str, Any]) -> dict[str, Any]:
    from ..local_state.startup import persist_ledger, persist_ledger_batch
    from ..operating_modes import resolve_execution_authority

    requested_mode = str(body.get("execution_mode", "INTERNAL_SIMULATION")).upper()
    if requested_mode not in {"NONE", "INTERNAL_SIMULATION", "BROKER_PAPER", "LIVE"}:
        raise ValueError("PAPER_SESSION_MODE_INVALID")
    if requested_mode == "LIVE":
        # No live execution capability is composed anywhere in the platform;
        # opening a session labeled LIVE/AUTHORIZED would be a false attestation.
        raise ValueError("OPERATING_MODE_UNSUPPORTED: LIVE execution is not implemented")
    closed = any(event["event_type"] == "PaperSessionClosed" for event in store.paper_ledger.events)
    if store.paper_ledger.events and not closed:
        store.paper_ledger.close_session()
        persist_ledger(store.paper_ledger)
    authority = resolve_execution_authority(requested_mode=requested_mode)
    from ..market_data.live_config import live_internal_simulation_enabled
    from ..operating_modes import PAPER_EXECUTION_AUTHORITIES

    if live_internal_simulation_enabled() and authority in PAPER_EXECUTION_AUTHORITIES:
        authority = "PAPER_ONLY"
    preferred = body.get("preferred_instrument")
    if preferred:
        from .operator_instrument import persist_session_preferred_instrument

        persist_session_preferred_instrument(str(preferred))
    from .operator_instrument import resolve_active_operator_instrument

    focus, _source = resolve_active_operator_instrument(store, explicit=preferred)
    session_instrument = focus or ("UNKNOWN" if store.data_mode == "LIVE_OBSERVATIONAL" else store.instrument_id)
    store.paper_ledger = PaperExecutionLedger.open_session(
        replay_session_id=store.session_id,
        instrument_id=session_instrument,
        symbol=session_instrument,
        execution_mode=requested_mode if authority in PAPER_EXECUTION_AUTHORITIES else "NONE",
        execution_authority=authority,
        data_mode=store.data_mode,
        data_provider="MOOMOO" if store.data_mode == "LIVE_OBSERVATIONAL" else store.data_provider,
        execution_provider="INTERNAL",
    )
    store.paper_ledger.persist_sink = persist_ledger_batch
    persist_ledger(store.paper_ledger)
    store.execution_deferred = False
    if authority in PAPER_EXECUTION_AUTHORITIES and requested_mode == "INTERNAL_SIMULATION":
        store.execution_mode = "INTERNAL_SIMULATION"
        store.execution_authority = authority
    return _paper_envelope(
        store,
        {
            "session": {
                "created_at_sequence": len(store.paper_ledger.events) - 1,
                "data_mode": store.paper_ledger.data_mode,
                "data_provider": store.paper_ledger.data_provider,
                "execution_authority": store.paper_ledger.execution_authority,
                "execution_mode": store.paper_ledger.execution_mode,
                "execution_provider": store.paper_ledger.execution_provider,
                "paper_account_id": store.paper_ledger.paper_account_id,
                "session_id": store.paper_ledger.session_id,
                "starting_cash_minor": int(store.paper_ledger.policy["initial_cash_minor"]),
            }
        },
    )


def close_paper_session(store: ReplayStore) -> dict[str, Any]:
    from ..local_state.startup import persist_ledger

    event = store.paper_ledger.close_session()
    persist_ledger(store.paper_ledger)
    store.paper_ledger.execution_authority = "BLOCKED"
    store.paper_ledger.execution_mode = "NONE"
    store.execution_mode = "NONE"
    store.execution_authority = "BLOCKED"
    return _paper_envelope(
        store,
        {
            "session": {
                "closed_event_id": event.get("event_id"),
                "execution_authority": store.paper_ledger.execution_authority,
                "execution_mode": store.paper_ledger.execution_mode,
                "session_id": store.paper_ledger.session_id,
            }
        },
    )


def list_paper_sessions(store: ReplayStore) -> dict[str, Any]:
    from ..local_state.startup import open_local_state

    repo = open_local_state()
    sessions = [] if repo is None else repo.list_sessions()
    return _paper_envelope(store, {"sessions": sessions, "active_session_id": store.paper_ledger.session_id})


def _default_client_order_id(store: ReplayStore) -> str:
    from ..canonical import canonical_bytes, sha256_bytes

    body = {
        "cutoff": store.prediction_cutoff(),
        "instrument_id": store.instrument_id,
        "sequence": len(store.paper_ledger.events),
    }
    return sha256_bytes(canonical_bytes(body))[:16]


def _sum_unrealized_minor(positions: list[dict[str, Any]]) -> int:
    return sum(int(row.get("unrealized_pnl_minor", 0)) for row in positions)


def _sum_unrealized_display(positions: list[dict[str, Any]]) -> str | None:
    if not positions:
        return None
    total = _sum_unrealized_minor(positions)
    from ..paper.contracts import decimal_minor_to_display

    return decimal_minor_to_display(total)


def _active_instrument_fields(store: ReplayStore) -> dict[str, Any]:
    from .operator_instrument import resolve_active_operator_instrument

    instrument, source = resolve_active_operator_instrument(store)
    return {
        "active_instrument": instrument,
        "active_instrument_source": source,
    }


def _require_order_instrument(store: ReplayStore, explicit: Any) -> str:
    from .operator_instrument import resolve_active_operator_instrument

    instrument, _source = resolve_active_operator_instrument(store, explicit=explicit)
    if not instrument:
        raise ValueError("OPERATOR_INSTRUMENT_REQUIRED")
    return instrument


def _live_focus_instrument_id(store: ReplayStore) -> str | None:
    from .operator_instrument import resolve_active_operator_instrument

    instrument, _source = resolve_active_operator_instrument(store)
    return instrument


def _paper_observation_time(store: ReplayStore, *, instrument_id: str | None = None) -> int:
    from ..market_data.live_config import live_observational_enabled, moomoo_live_enabled
    from ..market_data.live_runtime import get_live_runtime
    from ..clock import monotonic_wall_ns

    del instrument_id
    if live_observational_enabled() and moomoo_live_enabled() and get_live_runtime(create=False) is not None:
        return monotonic_wall_ns()
    return store.prediction_cutoff()


def _bars_for_paper_execution(store: ReplayStore, *, instrument_id: str | None = None) -> list[dict[str, Any]]:
    from ..market_data.live_config import live_observational_enabled, moomoo_live_enabled
    from ..market_data.live_runtime import get_live_runtime
    from ..clock import monotonic_wall_ns

    focus = instrument_id or _live_focus_instrument_id(store)
    if live_observational_enabled() and moomoo_live_enabled() and focus:
        runtime = get_live_runtime(create=False)
        if runtime is not None:
            live_bars = runtime.execution_buffer.bars_for_execution(
                observation_time_ns=monotonic_wall_ns(),
                price_scale=int(store.paper_ledger.policy["price_scale"]),
                instrument_id=focus,
            )
            return live_bars
    replay_bars = store.bars_for_execution()
    if not focus:
        return replay_bars
    matching = [
        bar
        for bar in replay_bars
        if str(bar.get("instrument_id", "")).upper() == str(focus).upper()
    ]
    if matching:
        return matching
    if any(str(bar.get("instrument_id", "")).strip() for bar in replay_bars):
        raise ValueError("PAPER_INSTRUMENT_DATA_UNAVAILABLE")
    primary = str(getattr(store, "instrument_id", "")).upper()
    if primary and primary == str(focus).upper():
        return replay_bars
    raise ValueError("PAPER_INSTRUMENT_DATA_UNAVAILABLE")


def _wait_for_post_intent_bars(
    store: ReplayStore,
    *,
    instrument_id: str,
    created_time_ns: int,
    bars: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    import time

    from ..market_data.live_config import live_execution_wait_ms, live_observational_enabled, moomoo_live_enabled
    from ..market_data.live_runtime import get_live_runtime
    from ..clock import monotonic_wall_ns

    if any(int(bar.get("available_time", 0)) > created_time_ns for bar in bars):
        return bars
    if not (live_observational_enabled() and moomoo_live_enabled()):
        return bars
    runtime = get_live_runtime(create=False)
    if runtime is None:
        return bars
    # Deadline uses monotonic elapsed time: a wall clock that freezes or jumps
    # must never stall or truncate the wait (the shared clock for observation times).
    deadline = time.monotonic() + live_execution_wait_ms() / 1000.0
    price_scale = int(store.paper_ledger.policy["price_scale"])
    while time.monotonic() < deadline:
        time.sleep(0.05)
        latest = runtime.execution_buffer.bars_for_execution(
            observation_time_ns=monotonic_wall_ns(),
            price_scale=price_scale,
            instrument_id=instrument_id,
        )
        if any(int(bar.get("available_time", 0)) > created_time_ns for bar in latest):
            return latest
    return runtime.execution_buffer.bars_for_execution(
        observation_time_ns=monotonic_wall_ns(),
        price_scale=price_scale,
        instrument_id=instrument_id,
    )


def _portfolio_mark_detail(store: ReplayStore) -> str:
    ledger = store.paper_ledger
    if ledger._live_mark_provider:
        return (
            f"Fill evidence separate from mark · mark provider {ledger._live_mark_provider} "
            f"quality {ledger._live_mark_quality or 'UNKNOWN'}"
        )
    if ledger.data_mode == "FIXTURE_REPLAY":
        return "Marks derived from internal fixture fills when present"
    return "Mark source unavailable"


def _portfolio_mark_quality(store: ReplayStore) -> str:
    ledger = store.paper_ledger
    if ledger._live_mark_quality:
        return ledger._live_mark_quality
    return "PASS" if ledger.data_mode == "FIXTURE_REPLAY" else "UNKNOWN"
