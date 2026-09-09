"""G14 — Options/Futures product surface projections (canonical runtime + Paper state)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from ..cross_lane.multi_asset_runtime import (
    RuntimeProjectionRequest,
    build_api_projection,
    project_runtime_domain,
)
from ..paper.margin_resolution import resolve_futures_margin_facts
from ..portfolio.paper_adapter import paper_snapshot_to_canonical
from ..risk.margin_facts import MARGIN_MISSING, MARGIN_STALE
from ..xa01.enums import InstrumentKind
from ..xa01.errors import Xa01Error
from ..xa01.registry import get_registry
from .instrument_route_codec import decode_instrument_route_param
from .instrument_selector import ensure_g14_selector_catalog, resolve_instrument_route_ref
from .store import ReplayStore


def _resolve_descriptor(route_ref: str):
    ensure_g14_selector_catalog()
    store = get_registry()
    try:
        canonical_id = resolve_instrument_route_ref(route_ref)
    except ValueError as exc:
        raise ValueError("UI_INSTRUMENT_NOT_FOUND") from exc
    try:
        return store.get(canonical_id).descriptor
    except Xa01Error as exc:
        raise ValueError("UI_INSTRUMENT_NOT_FOUND") from exc


def _portfolio_position_for_instrument(store: ReplayStore, instrument_id: str) -> dict[str, Any] | None:
    ledger = store.paper_ledger
    if not ledger._uses_canonical_authority():
        for row in ledger.project_positions():
            if str(row.get("instrument_id", "")).upper() == instrument_id.upper():
                return row
        return None
    snapshot = paper_snapshot_to_canonical(ledger)
    for position in snapshot.positions:
        if position.instrument_id.upper() == instrument_id.upper():
            return {
                "instrument_id": position.instrument_id,
                "instrument_kind": position.instrument_kind,
                "quantity": str(position.quantity),
                "quantity_unit": position.quantity_unit.value,
                "average_cost": str(position.average_cost),
                "market_value": str(position.valuation.market_value)
                if position.valuation
                else None,
                "unrealized_pnl": str(position.valuation.unrealized_pnl)
                if position.valuation
                else None,
                "source": "CanonicalPortfolio",
            }
    return None


def _orders_for_instrument(store: ReplayStore, instrument_id: str) -> list[dict[str, Any]]:
    rows = []
    for order in store.paper_ledger.project_orders():
        focus = str(order.get("instrument_id") or order.get("symbol") or "").upper()
        if focus == instrument_id.upper():
            rows.append(order)
    return rows


def _margin_status(
    *,
    instrument: dict[str, Any],
    instrument_id: str,
    observation_time_ns: int,
) -> dict[str, Any]:
    kind = str(instrument.get("instrument_kind", "")).upper()
    if kind != InstrumentKind.FUTURE_CONTRACT.value:
        return {"state": "NOT_APPLICABLE", "reason": None}
    facts = resolve_futures_margin_facts(
        instrument,
        instrument_id=instrument_id,
        observation_time_ns=observation_time_ns,
    )
    if facts is None:
        return {"state": MARGIN_MISSING, "reason": "NO_AUTHORITATIVE_MARGIN_FACTS"}
    return {
        "state": "AVAILABLE",
        "reason": None,
        "initial_margin_per_contract": str(facts.initial_margin_per_contract),
        "maintenance_margin_per_contract": str(facts.maintenance_margin_per_contract),
        "currency": facts.currency,
        "provider": facts.provider,
        "provenance": facts.provenance,
        "fixture_semantics": facts.provider.startswith("margin.fixture"),
    }


def _runtime_projection(descriptor, *, provider: str = "fixture") -> dict[str, Any]:
    request = RuntimeProjectionRequest(descriptor=descriptor, provider=provider)
    projection = project_runtime_domain(request)
    return build_api_projection(projection)


def _product_envelope(
    store: ReplayStore,
    *,
    instrument_id: str,
    mode: str,
    account_id: str,
    domain: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if hasattr(store, "data_mode"):
        from .projections import build_as_of_context

        as_of_context = build_as_of_context(store)
    else:
        as_of_context = {
            "mode": mode,
            "as_of_time": "1970-01-01T00:00:00.000000000Z",
            "timezone": "UTC",
            "execution_authority": getattr(getattr(store, "paper_ledger", None), "execution_authority", "PAPER_ONLY"),
            "execution_mode": getattr(getattr(store, "paper_ledger", None), "execution_mode", "INTERNAL_SIMULATION"),
            "data_mode": "FIXTURE_REPLAY",
        }

    return {
        "schema_version": "g14.product.v1",
        "domain": domain,
        "instrument_id": instrument_id,
        "mode": mode,
        "account_id": account_id,
        "as_of_context": as_of_context,
        **payload,
    }


def build_options_product_payload(
    store: ReplayStore,
    route_instrument: str,
    *,
    mode: str = "PAPER",
    account_id: str | None = None,
) -> dict[str, Any]:
    route_ref = decode_instrument_route_param(route_instrument)
    descriptor = _resolve_descriptor(route_ref)
    instrument_id = descriptor.identity.canonical_id
    kind = descriptor.identity.instrument_kind
    if kind == InstrumentKind.TRADABLE_SECURITY:
        runtime = _runtime_projection(descriptor)
        return _product_envelope(
            store,
            instrument_id=instrument_id,
            mode=mode,
            account_id=account_id or store.paper_ledger.paper_account_id,
            domain="options_underlying",
            payload={
                "status": runtime["status"],
                "reason": "OPTION_UNDERLYING_CONTEXT",
                "execution_available": False,
                "runtime": runtime,
                "chain_status": "UNDERLYING_ONLY",
                "position": None,
                "orders": [],
            },
        )
    if kind != InstrumentKind.OPTION_CONTRACT:
        runtime = _runtime_projection(descriptor)
        return _product_envelope(
            store,
            instrument_id=instrument_id,
            mode=mode,
            account_id=account_id or store.paper_ledger.paper_account_id,
            domain="options",
            payload={
                "status": "UNSUPPORTED_INSTRUMENT",
                "reason": f"NOT_OPTION_CONTRACT:{kind.value}",
                "execution_available": False,
                "runtime": runtime,
                "position": None,
                "orders": [],
            },
        )

    runtime = _runtime_projection(
        descriptor,
        provider="fixture",
    )
    domain_payload = dict(runtime.get("domain_payload") or {})
    greeks = dict(domain_payload.get("greeks") or {})
    position = _portfolio_position_for_instrument(store, instrument_id)
    orders = _orders_for_instrument(store, instrument_id)
    chain_status = str(domain_payload.get("chain_status") or runtime.get("status") or "UNAVAILABLE")
    return _product_envelope(
        store,
        instrument_id=instrument_id,
        mode=mode,
        account_id=account_id or store.paper_ledger.paper_account_id,
        domain="options",
        payload={
            "status": runtime["status"],
            "reason": runtime.get("reason"),
            "execution_available": bool(runtime.get("execution_available")),
            "runtime": runtime,
            "identity": {
                "instrument_id": instrument_id,
                "underlying": descriptor.expiration and _underlying_symbol(descriptor) or None,
                "expiry": descriptor.expiration or None,
                "strike": descriptor.strike or None,
                "right": descriptor.call_put or None,
                "multiplier": descriptor.denomination.contract_multiplier or None,
            },
            "analytics": {
                "iv": domain_payload.get("iv"),
                "open_interest": domain_payload.get("open_interest"),
                "volume": domain_payload.get("volume"),
                "greeks": greeks,
            },
            "chain_status": chain_status,
            "position": position,
            "orders": orders,
            "short_open_risk": "UNSUPPORTED" if descriptor.tradability.value == "TRADABLE" else None,
        },
    )


def _underlying_symbol(descriptor) -> str | None:
    from ..xa01.enums import RelationshipType
    from ..xa01.registry import get_registry

    store = get_registry()
    record = store.get(descriptor.identity.canonical_id)
    for rel in record.relationships:
        if rel.relationship_type == RelationshipType.UNDERLYING:
            underlying = store.get(rel.to_canonical_id)
            return underlying.descriptor.display_name or rel.to_canonical_id
    return None


def build_futures_product_payload(
    store: ReplayStore,
    route_instrument: str,
    *,
    mode: str = "PAPER",
    account_id: str | None = None,
) -> dict[str, Any]:
    route_ref = decode_instrument_route_param(route_instrument)
    descriptor = _resolve_descriptor(route_ref)
    instrument_id = descriptor.identity.canonical_id
    kind = descriptor.identity.instrument_kind
    runtime = _runtime_projection(descriptor)
    observation_time_ns = int(getattr(store, "cursor_index", 0) or 0) * 1_000_000_000 or 1
    margin: dict[str, Any] = {"state": "NOT_APPLICABLE", "reason": None}
    instrument_ref: dict[str, Any] | None = None
    if kind == InstrumentKind.FUTURE_CONTRACT:
        from ..paper.contracts import build_instrument_ref
        from ..portfolio.instrument_economics import economics_from_descriptor

        economics = economics_from_descriptor(descriptor)
        instrument_ref = build_instrument_ref(
            instrument_id=instrument_id,
            symbol=instrument_id,
            asset_class=economics.asset_class,
            currency=economics.settlement_currency,
            contract_multiplier=str(economics.contract_multiplier),
            instrument_kind=economics.instrument_kind,
            tradability=descriptor.tradability.value,
        )
        margin = _margin_status(
            instrument=instrument_ref,
            instrument_id=instrument_id,
            observation_time_ns=observation_time_ns,
        )
    execution_available = kind == InstrumentKind.FUTURE_CONTRACT and bool(runtime.get("execution_available"))
    if kind in {InstrumentKind.FUTURE_FAMILY, InstrumentKind.CONTINUOUS_SERIES}:
        execution_available = False
    position = _portfolio_position_for_instrument(store, instrument_id) if execution_available else None
    orders = _orders_for_instrument(store, instrument_id) if execution_available else []
    domain_payload = dict(runtime.get("domain_payload") or {})
    notional = None
    price = domain_payload.get("price")
    multiplier = descriptor.denomination.contract_multiplier
    if price is not None and multiplier:
        try:
            notional = str(Decimal(str(price)) * Decimal(str(multiplier)))
        except Exception:
            notional = None
    status = runtime["status"]
    reason = runtime.get("reason")
    if kind in {InstrumentKind.FUTURE_FAMILY, InstrumentKind.CONTINUOUS_SERIES}:
        status = "UNSUPPORTED_INSTRUMENT"
        reason = f"NON_EXECUTABLE:{kind.value}"
    return _product_envelope(
        store,
        instrument_id=instrument_id,
        mode=mode,
        account_id=account_id or store.paper_ledger.paper_account_id,
        domain="futures",
        payload={
            "status": status,
            "reason": reason,
            "execution_available": execution_available,
            "runtime": runtime,
            "identity": {
                "instrument_id": instrument_id,
                "instrument_kind": kind.value,
                "root": descriptor.display_name.split()[0] if descriptor.display_name else None,
                "expiry": descriptor.expiration or None,
                "venue": descriptor.venue_id or "CME",
                "multiplier": multiplier or None,
            },
            "exposure": {
                "notional": notional,
                "margin": margin,
                "cash_debit_semantics": "MARGIN_NOT_NOTIONAL" if kind == InstrumentKind.FUTURE_CONTRACT else None,
            },
            "position": position,
            "orders": orders,
            "margin_binding_states": {
                MARGIN_MISSING: "margin facts missing",
                MARGIN_STALE: "margin facts stale",
            },
        },
    )


__all__ = [
    "build_futures_product_payload",
    "build_options_product_payload",
]
