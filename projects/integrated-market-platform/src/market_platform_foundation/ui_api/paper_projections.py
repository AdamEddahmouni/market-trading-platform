"""DTO projections for PLATFORM-PAPER-001 paper observability API."""

from __future__ import annotations

import time
from typing import Any

from ..operational_identity import attach_operational_identity
from ..paper.broker_paper import (
    apply_broker_status_event,
    cancel_broker_paper_order,
    preview_broker_paper_order,
    submit_broker_paper_order,
)
from ..paper.contracts import build_instrument_ref, build_semantic_intent_digest
from ..paper.eligibility import InstrumentAdmissionError, admit_order_instrument
from ..paper.execution import (
    cancel_interactive_order,
    preview_interactive_order,
    replace_interactive_order,
    submit_interactive_order,
)
from ..paper.ledger import PaperExecutionLedger
from ..paper.margin_resolution import resolve_futures_margin_facts
from ..paper.preview import (
    PreviewError,
    portfolio_state_revision,
    verify_preview_submit,
)
from ..rt01.enums import TraceStage, TraceStatus
from ..rt01.instrumentation.paper import trace_refs
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
    execution_provider = store.paper_ledger.execution_provider
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
    if identity.is_demo_view():
        positions = []
        orders = []
        fills = []
        gross_exposure = 0
        net_exposure = 0
        demo_execution_mode = "NONE"
        demo_execution_authority = "BLOCKED"
        demo_risk = dict(risk)
        demo_risk["open_order_count"] = 0
        demo_data_health = {
            "data_mode": ledger.data_mode,
            "data_provider": "MOOMOO" if ledger.data_mode == "LIVE_OBSERVATIONAL" else ledger.data_provider,
            "detail": _portfolio_mark_detail(store),
            "execution_authority": demo_execution_authority,
            "execution_mode": demo_execution_mode,
            "execution_provider": "INTERNAL",
            "state": _portfolio_mark_quality(store),
        }
        demo_session = {
            "execution_authority": demo_execution_authority,
            "execution_mode": demo_execution_mode,
            "paper_account_id": ledger.paper_account_id,
            "session_id": ledger.session_id,
            "starting_cash_minor": int(ledger.policy.get("initial_cash_minor", 0)),
        }
    else:
        demo_risk = risk
        demo_data_health = {
            "data_mode": ledger.data_mode,
            "data_provider": "MOOMOO" if ledger.data_mode == "LIVE_OBSERVATIONAL" else ledger.data_provider,
            "detail": _portfolio_mark_detail(store),
            "execution_authority": ledger.execution_authority,
            "execution_mode": ledger.execution_mode,
            "execution_provider": "INTERNAL",
            "state": _portfolio_mark_quality(store),
        }
        demo_session = {
            "execution_authority": ledger.execution_authority,
            "execution_mode": ledger.execution_mode,
            "paper_account_id": ledger.paper_account_id,
            "session_id": ledger.session_id,
            "starting_cash_minor": int(ledger.policy.get("initial_cash_minor", 0)),
        }

    envelope = _paper_envelope(
        store,
        {
            "account": account,
            "authority_boundary": "PAPER_OBSERVABILITY",
            "observation_time": observation_time,
            "data_health": demo_data_health,
            "exposure": {
                "gross_shares": gross_exposure,
                "net_shares": net_exposure,
            },
            "fills": fills,
            "orders": orders,
            "pnl": {
                "realized_minor": int(account.get("realized_pnl_minor", 0)),
                "realized_display": account.get("realized_pnl_display"),
                "total_display": account.get("realized_pnl_display"),
                "total_minor": int(account.get("realized_pnl_minor", 0)),
                "unrealized_display": _sum_unrealized_display(positions),
                "unrealized_minor": _sum_unrealized_minor(positions),
            },
            "positions": positions,
            "reconciliation_status": risk.get("reconciliation_status"),
            "risk": demo_risk,
            "session": demo_session,
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
    allocation_decision_id: str | None = None,
) -> dict[str, Any]:
    if allocation_decision_id is not None:
        repository = getattr(store, "strategy_repository", None)
        if repository is None:
            raise ValueError("STRATEGY_REPOSITORY_UNAVAILABLE")
        from .strategy_runtime_projections import build_strategy_decision_trace_payload

        return _paper_envelope(
            store,
            build_strategy_decision_trace_payload(
                repository=repository,
                ledger=store.paper_ledger,
                account_id=store.paper_ledger.paper_account_id,
                mode="PAPER",
                allocation_decision_id=allocation_decision_id,
            ),
        )
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
    from ..rt01.context import current_context
    from ..rt01.instrumentation.paper import start_paper_trace, trace_refs

    if current_context() is not None:
        return _preview_paper_order(store, body)
    trace = start_paper_trace(
        "paper_order_preview",
        correlation_id=str(
            body.get("correlation_id")
            or body.get("client_order_id")
            or "paper-order-preview"
        ),
    )
    failed = False
    try:
        return _preview_paper_order(store, body)
    except Exception as exc:
        trace.finish(
            status=TraceStatus.ERROR,
            error_code=type(exc).__name__,
            terminated=True,
        )
        failed = True
        raise
    finally:
        if not failed:
            trace.finish()


def _margin_facts_revision(margin_facts: Any) -> str:
    if margin_facts is None:
        return ""
    from ..risk.margin_facts import MarginRequirementFacts

    facts = (
        margin_facts
        if isinstance(margin_facts, MarginRequirementFacts)
        else MarginRequirementFacts.from_dict(margin_facts)
    )
    return facts.revision_digest()


def _resolve_order_margin_facts(
    *,
    focus: str,
    instrument: dict[str, Any],
    body: dict[str, Any],
    observation_time_ns: int,
) -> Any:
    return resolve_futures_margin_facts(
        instrument,
        instrument_id=focus,
        observation_time_ns=observation_time_ns,
        explicit=body.get("margin_facts"),
    )


def _preview_binding_context(
    store: ReplayStore,
    *,
    focus: str,
    parsed: dict[str, Any],
    margin_facts_revision: str = "",
) -> dict[str, Any]:
    """Build the server-authoritative preview claims for one order request.

    Binds the exact intent digest, operational account + mode, the current
    portfolio state revision, and the risk-policy revision (G3 §14–16). The
    same helper is used at preview issuance and at submit verification so
    the two always agree on what is bound.
    """
    ledger = store.paper_ledger
    intent_digest = build_semantic_intent_digest(
        {
            "action": "OPEN",
            "instrument_id": focus,
            "side": parsed["side"],
            "desired_quantity": parsed["quantity"],
            "order_type": parsed["order_type"],
            "limit_price_minor": parsed["limit_price_minor"],
            "currency": ledger.policy.get("currency", "USD"),
            "quantity_unit": "SHARES",
        }
    )
    return {
        "account_id": ledger.paper_account_id,
        "intent_digest": intent_digest,
        "instrument_id": focus,
        "limit_price_minor": parsed["limit_price_minor"],
        "mode": "PAPER",
        "observation_time": _paper_observation_time(store, instrument_id=focus),
        "order_type": parsed["order_type"],
        "portfolio_revision": portfolio_state_revision(ledger),
        "quantity": parsed["quantity"],
        "risk_policy_revision": str(ledger.policy.get("risk_policy_identity_hash", "")),
        "margin_facts_revision": margin_facts_revision,
        "side": parsed["side"],
    }


def _require_valid_preview(
    store: ReplayStore,
    body: dict[str, Any],
    *,
    focus: str,
    parsed: dict[str, Any],
    instrument: dict[str, Any],
) -> None:
    """Verify a client submit is bound to a current server preview (G3 §20).

    Fail-closed: a missing/expired/stale/mismatched preview raises ValueError
    with a machine-readable reason code. The final server risk check still
    runs after this; the preview is never an authorization bypass.
    """
    preview_id = str(body.get("preview_id", "")).strip()
    if not preview_id:
        raise ValueError("PREVIEW_REQUIRED: submit requires a current server preview")
    ledger = store.paper_ledger
    observation_time = _paper_observation_time(store, instrument_id=focus)
    margin_facts = _resolve_order_margin_facts(
        focus=focus,
        instrument=instrument,
        body=body,
        observation_time_ns=observation_time,
    )
    claims = _preview_binding_context(
        store,
        focus=focus,
        parsed=parsed,
        margin_facts_revision=_margin_facts_revision(margin_facts),
    )
    try:
        verify_preview_submit(
            store.preview_store,
            preview_id=preview_id,
            account_id=ledger.paper_account_id,
            mode="PAPER",
            intent_digest=claims["intent_digest"],
            instrument_id=focus,
            side=claims["side"],
            quantity=claims["quantity"],
            order_type=claims["order_type"],
            limit_price_minor=claims["limit_price_minor"],
            portfolio_revision=claims["portfolio_revision"],
            risk_policy_revision=claims["risk_policy_revision"],
            margin_facts_revision=claims["margin_facts_revision"],
        )
    except PreviewError as exc:
        raise ValueError(str(exc)) from exc


def _admit_focus_instrument(store: ReplayStore, focus: str) -> dict[str, Any]:
    """Admit the order target at the real preview/submit boundary (BL-0203).

    Returns the admitted instrument ref: the operator symbol stays the ledger
    key (positions/history are symbol-keyed today), while the canonical
    kind/tradability/contract multiplier resolved through XA-01 are carried
    into the order intent so the fail-closed executable guard has real
    teeth at intent build time (G3 Invariant D/E).
    """
    try:
        admitted = admit_order_instrument(focus)
    except InstrumentAdmissionError as exc:
        raise ValueError(str(exc)) from exc
    ref = build_instrument_ref(
        instrument_id=focus,
        symbol=focus,
    )
    for key in ("instrument_kind", "tradability", "contract_multiplier", "currency"):
        if admitted.get(key) is not None:
            ref[key] = admitted[key]
    return ref


def _preview_paper_order(store: ReplayStore, body: dict[str, Any]) -> dict[str, Any]:
    from . import live_projections

    live_projections.apply_live_marks_to_ledger(store)
    maybe_release_execution_gate(store)
    _assert_live_execution_allowed(store, submit=False)
    parsed = _parse_order_body(body, store)
    focus = _require_order_instrument(store, parsed["explicit_instrument"])
    instrument = _admit_focus_instrument(store, focus)
    observation_time = _paper_observation_time(store, instrument_id=focus)
    margin_facts = _resolve_order_margin_facts(
        focus=focus,
        instrument=instrument,
        body=body,
        observation_time_ns=observation_time,
    )
    if store.paper_ledger.execution_mode == "BROKER_PAPER":
        preview = preview_broker_paper_order(
            ledger=store.paper_ledger,
            instrument=instrument,
            side=parsed["side"],
            quantity=parsed["quantity"],
            observation_time=observation_time,
            client_order_id=parsed["client_order_id"],
            idempotency_key=parsed["idempotency_key"],
            order_type=parsed["order_type"],
            limit_price_minor=parsed["limit_price_minor"],
            correlation_id=parsed["correlation_id"],
            decision_source_snapshot=parsed["decision_source_snapshot"],
        )
        envelope = _paper_envelope(store, {"preview": preview})
    else:
        preview = preview_interactive_order(
            ledger=store.paper_ledger,
            bars=_bars_for_paper_execution(store, instrument_id=focus),
            symbol=focus,
            instrument_id=focus,
            side=parsed["side"],
            quantity=parsed["quantity"],
            observation_time=observation_time,
            client_order_id=parsed["client_order_id"],
            idempotency_key=parsed["idempotency_key"],
            order_type=parsed["order_type"],
            limit_price_minor=parsed["limit_price_minor"],
            correlation_id=parsed["correlation_id"],
            decision_source_snapshot=parsed["decision_source_snapshot"],
            instrument=instrument,
            margin_facts=margin_facts,
        )
        envelope = _paper_envelope(store, {"preview": preview})
    claims = _preview_binding_context(
        store,
        focus=focus,
        parsed=parsed,
        margin_facts_revision=_margin_facts_revision(margin_facts),
    )
    record = store.preview_store.issue(
        account_id=claims["account_id"],
        mode=claims["mode"],
        instrument_id=claims["instrument_id"],
        intent_digest=claims["intent_digest"],
        side=claims["side"],
        quantity=claims["quantity"],
        order_type=claims["order_type"],
        risk_policy_revision=claims["risk_policy_revision"],
        portfolio_revision=claims["portfolio_revision"],
        observation_time=claims["observation_time"],
        limit_price_minor=claims["limit_price_minor"],
        margin_facts_revision=claims["margin_facts_revision"],
    )
    envelope["preview"]["preview_id"] = record.preview_id
    envelope["preview"]["preview_binding"] = {
        "account_id": record.account_id,
        "expires_at_ns": record.expires_at_ns,
        "intent_digest": record.intent_digest,
        "issued_at_ns": record.issued_at_ns,
        "mode": record.mode,
        "portfolio_revision": record.portfolio_revision,
        "preview_id": record.preview_id,
        "risk_policy_revision": record.risk_policy_revision,
        "margin_facts_revision": record.margin_facts_revision,
    }
    return envelope


def submit_paper_order(store: ReplayStore, body: dict[str, Any]) -> dict[str, Any]:
    from ..rt01.context import current_context
    from ..rt01.instrumentation.paper import start_paper_trace

    if current_context() is not None:
        return _submit_paper_order(store, body)
    trace = start_paper_trace(
        "paper_order_request",
        correlation_id=str(
            body.get("correlation_id")
            or body.get("client_order_id")
            or "paper-order-request"
        ),
    )
    failed = False
    try:
        return _submit_paper_order(store, body)
    except Exception as exc:
        trace.finish(
            status=TraceStatus.ERROR,
            error_code=type(exc).__name__,
            terminated=True,
        )
        failed = True
        raise
    finally:
        if not failed:
            trace.finish()


def _submit_paper_order(store: ReplayStore, body: dict[str, Any]) -> dict[str, Any]:
    from . import live_projections

    live_projections.apply_live_marks_to_ledger(store)
    maybe_release_execution_gate(store)
    parsed = _parse_order_body(body, store)
    _assert_live_execution_allowed(store, submit=True)
    focus = _require_order_instrument(store, parsed["explicit_instrument"])
    instrument = _admit_focus_instrument(store, focus)
    existing_order_id = store.paper_ledger.lookup_idempotent_order(parsed["idempotency_key"])
    if existing_order_id:
        existing = store.paper_ledger.lookup_order(existing_order_id)
        existing_digest = (existing or {}).get("intent_digest")
        if existing_digest is None:
            recorded = store.paper_ledger.lookup_intent_for_order(existing_order_id)
            existing_digest = build_semantic_intent_digest(recorded) if recorded else None
        submit_digest = _preview_binding_context(store, focus=focus, parsed=parsed)["intent_digest"]
        if existing_digest is not None and existing_digest != submit_digest:
            raise ValueError(
                "IDEMPOTENCY_CONFLICT: same idempotency key submitted with a different order intent"
            )
        if existing is not None:
            return _paper_envelope(
                store,
                {
                    "submission": {
                        "duplicate": True,
                        "idempotency_key": parsed["idempotency_key"],
                        "order": existing,
                        "order_id": existing_order_id,
                    }
                },
            )
    intent_time = _paper_observation_time(store, instrument_id=focus)
    margin_facts = _resolve_order_margin_facts(
        focus=focus,
        instrument=instrument,
        body=body,
        observation_time_ns=intent_time,
    )
    _require_valid_preview(store, body, focus=focus, parsed=parsed, instrument=instrument)
    if store.paper_ledger.execution_mode == "BROKER_PAPER":
        from ..providers.composition import get_provider_composition

        result = submit_broker_paper_order(
            ledger=store.paper_ledger,
            provider=get_provider_composition().paper_execution,
            instrument=instrument,
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
        instrument=instrument,
        margin_facts=margin_facts,
    )
    return _paper_envelope(store, {"submission": result})


def cancel_paper_order(store: ReplayStore, body: dict[str, Any]) -> dict[str, Any]:
    from ..rt01.context import current_context
    from ..rt01.instrumentation.paper import start_paper_trace

    if current_context() is not None:
        return _cancel_paper_order(store, body)
    trace = start_paper_trace(
        "paper_order_cancel",
        correlation_id=str(body.get("correlation_id") or body.get("order_id") or "paper-cancel"),
    )
    failed = False
    try:
        return _cancel_paper_order(store, body)
    except Exception as exc:
        trace.finish(
            status=TraceStatus.ERROR,
            error_code=type(exc).__name__,
            terminated=True,
        )
        failed = True
        raise
    finally:
        if not failed:
            trace.finish()


def _cancel_paper_order(store: ReplayStore, body: dict[str, Any]) -> dict[str, Any]:
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


def replace_paper_order(store: ReplayStore, body: dict[str, Any]) -> dict[str, Any]:
    """Server-authoritative replace of a working Paper order (G3 §41–43, BL-0205).

    The internal simulation path owns replace today; broker paper orders fail
    closed (REPLACE_NOT_CERTIFIED) because provider-level replace/modify is
    not yet certified for any adapter — never fake a replace locally against
    a live broker order (live_execution_safety/certification.py).
    """
    from ..rt01.context import current_context
    from ..rt01.instrumentation.paper import start_paper_trace

    if current_context() is not None:
        return _replace_paper_order(store, body)
    trace = start_paper_trace(
        "paper_order_replace",
        correlation_id=str(body.get("correlation_id") or body.get("order_id") or "paper-replace"),
    )
    failed = False
    try:
        return _replace_paper_order(store, body)
    except Exception as exc:
        trace.finish(
            status=TraceStatus.ERROR,
            error_code=type(exc).__name__,
            terminated=True,
        )
        failed = True
        raise
    finally:
        if not failed:
            trace.finish()


def _replace_paper_order(store: ReplayStore, body: dict[str, Any]) -> dict[str, Any]:
    order_id = str(body.get("order_id", "")).strip()
    if not order_id:
        raise ValueError("PAPER_ORDER_ID_REQUIRED")
    ledger = store.paper_ledger
    if ledger.execution_mode == "BROKER_PAPER":
        raise ValueError("PAPER_ORDER_REPLACE_UNSUPPORTED: provider replace not certified")
    result = replace_interactive_order(
        ledger=ledger,
        order_id=order_id,
        replaced_quantity=int(body["replaced_quantity"]),
        order_type=str(body.get("order_type", "MARKET")),
        limit_price_minor=body.get("limit_price_minor"),
    )
    return _paper_envelope(store, {"replacement": result})


def poll_broker_order(store: ReplayStore, body: dict[str, Any]) -> dict[str, Any]:
    from ..rt01.context import current_context
    from ..rt01.instrumentation.paper import start_paper_trace

    if current_context() is not None:
        return _poll_broker_order(store, body)
    trace = start_paper_trace(
        "broker_order_poll",
        correlation_id=str(body.get("correlation_id") or body.get("order_id") or "broker-poll"),
    )
    failed = False
    try:
        return _poll_broker_order(store, body)
    except Exception as exc:
        trace.finish(
            status=TraceStatus.ERROR,
            error_code=type(exc).__name__,
            terminated=True,
        )
        failed = True
        raise
    finally:
        if not failed:
            trace.finish()


def _poll_broker_order(store: ReplayStore, body: dict[str, Any]) -> dict[str, Any]:
    """Apply one cumulative broker status poll through the Paper runtime."""
    from ..operating_modes import PAPER_EXECUTION_AUTHORITIES

    if store.paper_ledger.execution_mode != "BROKER_PAPER":
        raise ValueError("PAPER_EXECUTION_MODE_INVALID")
    if store.paper_ledger.execution_authority not in PAPER_EXECUTION_AUTHORITIES:
        raise ValueError("PAPER_EXECUTION_NOT_AUTHORIZED")
    order_id = str(body.get("order_id", "")).strip()
    if not order_id:
        raise ValueError("PAPER_ORDER_ID_REQUIRED")
    from ..providers.composition import get_provider_composition

    provider = get_provider_composition().paper_execution
    if not callable(getattr(provider, "fetch_order", None)):
        raise ValueError("PROVIDER_NOT_CONFIGURED")
    result = apply_broker_status_event(
        ledger=store.paper_ledger,
        provider=provider,
        order_id=order_id,
    )
    return _paper_envelope(store, {"poll": result})


def reconcile_broker_paper(store: ReplayStore) -> dict[str, Any]:
    from ..rt01.context import current_context
    from ..rt01.instrumentation.paper import start_paper_trace
    from ..rt01.tracer import get_tracer

    if current_context() is None:
        trace = start_paper_trace(
            "broker_reconciliation",
            correlation_id=f"broker-reconciliation:{store.paper_ledger.session_id}",
        )
        reconciliation_span = trace.child(
            TraceStage.RECONCILIATION,
            "reconcile_broker_paper",
            session_id=store.paper_ledger.session_id,
        )
        failed = False
        try:
            result = _reconcile_broker_paper(store)
            if reconciliation_span is not None:
                reconciliation_span.context.attributes.update(
                    trace_refs(report_id=result["reconciliation"].get("report_id"))
                )
                reconciliation_span.end(
                    output_ref=f"report:{result['reconciliation']['report_id']}"
                )
            return result
        except Exception as exc:
            if reconciliation_span is not None:
                reconciliation_span.end(
                    status=TraceStatus.ERROR,
                    error_class=type(exc).__name__,
                    error_code=type(exc).__name__,
                )
            trace.finish(
                status=TraceStatus.ERROR,
                error_code=type(exc).__name__,
                terminated=True,
            )
            failed = True
            raise
        finally:
            if not failed:
                trace.finish()
    context = current_context()
    span = get_tracer().start_span(
        TraceStage.RECONCILIATION,
        "reconcile_broker_paper",
        parent=context,
        input_ref=f"session:{store.paper_ledger.session_id}",
    )
    try:
        result = _reconcile_broker_paper(store)
    except Exception as exc:
        if span is not None:
            span.end(
                status=TraceStatus.ERROR,
                error_class=type(exc).__name__,
                error_code=type(exc).__name__,
            )
        raise
    if span is not None:
        span.context.attributes.update(
            trace_refs(report_id=result["reconciliation"].get("report_id"))
        )
        span.end(output_ref=f"report:{result['reconciliation']['report_id']}")
    return result


def _reconcile_broker_paper(store: ReplayStore) -> dict[str, Any]:
    """Fetch broker snapshots, build, and record one reconciliation report."""
    from ..platform.reconciliation.engine import (
        BrokerOrderSnapshot,
        build_reconciliation_report,
        record_reconciliation,
    )
    from ..operating_modes import PAPER_EXECUTION_AUTHORITIES
    from ..providers.broker_execution import (
        BrokerAccountSnapshot,
        BrokerOrderStatusEvent,
        BrokerPositionSnapshot,
    )
    from ..providers.composition import get_provider_composition

    provider = get_provider_composition().paper_execution
    if store.paper_ledger.execution_mode != "BROKER_PAPER":
        raise ValueError("PAPER_EXECUTION_MODE_INVALID")
    if store.paper_ledger.execution_authority not in PAPER_EXECUTION_AUTHORITIES:
        raise ValueError("PAPER_EXECUTION_NOT_AUTHORIZED")
    for method_name in ("fetch_order", "fetch_account", "fetch_positions"):
        if not callable(getattr(provider, method_name, None)):
            raise ValueError("PROVIDER_NOT_CONFIGURED")
    order_snapshots = []
    for order in store.paper_ledger.project_orders():
        broker_order_id = str(order.get("broker_order_id") or "")
        if not broker_order_id:
            continue
        result = provider.fetch_order(broker_order_id)
        if str(getattr(result, "status", "")) != "ok":
            raise ValueError("BROKER_RECONCILIATION_UNAVAILABLE")
        event = next(
            (
                item
                for item in (getattr(result, "events", ()) or ())
                if isinstance(item, dict) and isinstance(item.get("payload"), dict)
            ),
            None,
        )
        if event is None:
            raise ValueError("BROKER_RECONCILIATION_STATUS_MISSING")
        status_event = BrokerOrderStatusEvent.from_record(event["payload"])
        order_snapshots.append(
            BrokerOrderSnapshot.from_status_event(
                status_event,
                raw_source_reference=str(event.get("raw_reference") or ""),
            )
        )

    account_result = provider.fetch_account()
    if str(getattr(account_result, "status", "")) != "ok":
        raise ValueError("BROKER_RECONCILIATION_ACCOUNT_UNAVAILABLE")
    account_event = next(iter(getattr(account_result, "events", ()) or ()), None)
    account_snapshot = (
        BrokerAccountSnapshot.from_record(account_event)
        if isinstance(account_event, dict)
        else None
    )

    positions_result = provider.fetch_positions()
    if str(getattr(positions_result, "status", "")) != "ok":
        raise ValueError("BROKER_RECONCILIATION_POSITIONS_UNAVAILABLE")
    positions_event = next(iter(getattr(positions_result, "events", ()) or ()), None)
    position_snapshots = (
        tuple(
            BrokerPositionSnapshot.from_record(row)
            for row in positions_event.get("positions", [])
            if isinstance(row, dict)
        )
        if isinstance(positions_event, dict)
        else ()
    )
    timestamps = [
        snapshot.receive_time_ns
        for snapshot in order_snapshots
        if snapshot.receive_time_ns
    ]
    if account_snapshot is not None and account_snapshot.as_of_ns:
        timestamps.append(account_snapshot.as_of_ns)
    timestamps.extend(snapshot.as_of_ns for snapshot in position_snapshots if snapshot.as_of_ns)
    as_of_ns = max(timestamps, default=store.prediction_cutoff())
    report = build_reconciliation_report(
        store.paper_ledger,
        order_snapshots=order_snapshots,
        position_snapshots=position_snapshots,
        account_snapshot=account_snapshot,
        as_of_ns=as_of_ns,
    )
    record_reconciliation(store.paper_ledger, report)
    return _paper_envelope(store, {"reconciliation": report})


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
    from ..providers.composition import get_provider_composition

    provider = get_provider_composition().paper_execution
    execution_provider = (
        str(getattr(provider, "provider_id", ""))
        if requested_mode == "BROKER_PAPER"
        else "INTERNAL"
    )
    if requested_mode == "BROKER_PAPER" and (
        not execution_provider or execution_provider == "stub.execution.disabled"
    ):
        raise ValueError("PROVIDER_NOT_CONFIGURED")
    store.paper_ledger = PaperExecutionLedger.open_session(
        replay_session_id=store.session_id,
        instrument_id=session_instrument,
        symbol=session_instrument,
        execution_mode=requested_mode if authority in PAPER_EXECUTION_AUTHORITIES else "NONE",
        execution_authority=authority,
        data_mode=store.data_mode,
        data_provider="MOOMOO" if store.data_mode == "LIVE_OBSERVATIONAL" else store.data_provider,
        execution_provider=execution_provider,
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
    return store.bars_for_execution()


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
