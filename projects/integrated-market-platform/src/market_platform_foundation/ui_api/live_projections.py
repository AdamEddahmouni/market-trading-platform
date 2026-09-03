"""UI API projections for live observational mode (P2 / P2.1)."""

from __future__ import annotations

import time
from typing import Any

from ..market_data.live_config import live_observational_enabled, live_internal_simulation_enabled, moomoo_live_enabled
from ..market_data.live_runtime import get_live_runtime
from .store import ReplayStore


def _runtime_or_none():
    if not live_observational_enabled():
        return None
    return get_live_runtime(create=True)


def build_provider_health_payload(store: ReplayStore) -> dict[str, Any]:
    runtime = _runtime_or_none()
    if runtime is None:
        return {
            "available": False,
            "reason": "IMP_LIVE_OBSERVATIONAL not enabled",
        }
    from . import paper_projections

    health = runtime.health_payload()
    health["available"] = True
    health["data_mode"] = store.data_mode
    lifecycle = health.get("lifecycle") if isinstance(health.get("lifecycle"), dict) else {}
    quote_symbol = paper_projections._live_focus_instrument_id(store) or store.instrument_id
    quote = runtime.state.quote_for(quote_symbol)
    trades = runtime.state.trades_for(quote_symbol)
    book = runtime.state.book_for(quote_symbol)
    from .discovery_projections import build_finviz_diagnostics_payload

    health["finviz"] = build_finviz_diagnostics_payload()
    health["provider_summary"] = {
        "provider": "MOOMOO",
        "provider_role": "MARKET_DATA",
        "sdk": lifecycle.get("sdk_version"),
        "opend": lifecycle.get("connection_state"),
        "opend_version": lifecycle.get("opend_version"),
        "provider_generation": lifecycle.get("provider_generation_id"),
        "quote_entitlement": runtime.capability_registry.dimensions.entitled,
        "execution_use": lifecycle.get("execution_use"),
        "execution_eligibility": (
            "INTERNAL PAPER ELIGIBLE"
            if lifecycle.get("execution_use") == "INTERNAL_PAPER_ELIGIBLE"
            else "DISPLAY ONLY"
        ),
        "last_quote": None if quote is None else quote.to_dict(),
        "last_trade": trades[-1] if trades else None,
        "last_book_depth": None if book is None else book.get("returned_depth"),
        "event_lag_ms_p50": (runtime.feed_metrics or {}).get("callback_lag_ms_p50"),
        "event_lag_ms_p95": (runtime.feed_metrics or {}).get("callback_lag_ms_p95"),
        "quote_lag_ms_p50": (runtime.feed_metrics or {}).get("quote_lag_ms_p50"),
        "quote_lag_ms_p95": (runtime.feed_metrics or {}).get("quote_lag_ms_p95"),
        "trade_lag_ms_p50": (runtime.feed_metrics or {}).get("trade_lag_ms_p50"),
        "trade_lag_ms_p95": (runtime.feed_metrics or {}).get("trade_lag_ms_p95"),
        "book_lag_ms_p50": (runtime.feed_metrics or {}).get("book_lag_ms_p50"),
        "book_lag_ms_p95": (runtime.feed_metrics or {}).get("book_lag_ms_p95"),
        "queue_depth": (runtime.feed_metrics or {}).get("queue_depth"),
        "queue_high_water": (runtime.feed_metrics or {}).get("max_depth_observed"),
        "dropped": (runtime.feed_metrics or {}).get("events_dropped"),
        "duplicates": (runtime.feed_metrics or {}).get("duplicate_callbacks"),
        "sequence_anomalies": (runtime.feed_metrics or {}).get("sequence_anomalies"),
        "reconnects": lifecycle.get("reconnect_count"),
        "trade_api_counters": (runtime.feed_metrics or {}).get("trade_api_counters"),
    }
    return health


def build_symbol_search_payload(query: str) -> dict[str, Any]:
    runtime = _runtime_or_none()
    if runtime is None:
        return {"query": query, "results": []}
    return {"query": query, "results": runtime.search_symbols(query)}


def build_instrument_capabilities_payload(instrument_id: str) -> dict[str, Any]:
    runtime = _runtime_or_none()
    if runtime is None:
        return {
            "capabilities": [],
            "instrument_id": instrument_id.upper(),
            "reason": "LIVE_OBSERVATIONAL_DISABLED",
        }
    dimensions = runtime.capability_registry.dimensions
    return {
        "capabilities": runtime.instrument_capabilities(instrument_id),
        "dimensions": {
            "configured": bool(getattr(dimensions, "configured", False)),
            "connected": bool(getattr(dimensions, "connected", False)),
            "entitled": bool(getattr(dimensions, "entitled", False)),
            "healthy": bool(getattr(dimensions, "healthy", False)),
            "receiving": bool(getattr(dimensions, "receiving", False)),
            "subscribed": bool(getattr(dimensions, "subscribed", False)),
        },
        "instrument_id": instrument_id.upper(),
        "probe_stale": runtime.capability_registry.is_stale,
        "verified_at": runtime.capability_registry.verified_at,
    }


def build_market_state_payload(instrument_id: str) -> dict[str, Any]:
    runtime = _runtime_or_none()
    symbol = instrument_id.upper()
    if runtime is None:
        return {"available": False, "instrument_id": symbol}
    quote = runtime.state.quote_for(symbol)
    trades = runtime.state.trades_for(symbol)
    book = runtime.state.book_for(symbol)
    freshness = runtime.state.freshness_ms(symbol)
    return {
        "available": quote is not None or bool(trades) or book is not None,
        "book": book,
        "freshness_ms": freshness,
        "instrument_id": symbol,
        "live_mark": runtime.live_mark_for(symbol),
        "quote": None if quote is None else quote.to_dict(),
        "trade_count": len(trades),
        "trades_tail": trades[-20:],
    }


def build_live_context_overrides(store: ReplayStore) -> dict[str, Any] | None:
    from .operator_instrument import resolve_active_operator_instrument

    runtime = _runtime_or_none()
    if runtime is None:
        return None
    focus, _source = resolve_active_operator_instrument(store)
    quote_symbol = focus or store.instrument_id
    quote = runtime.state.quote_for(quote_symbol) if focus else None
    freshness = runtime.state.freshness_ms(quote_symbol) if focus else None
    quality_state = "PASS"
    if focus is None:
        quality_state = "UNAVAILABLE"
    elif freshness is None:
        quality_state = "UNAVAILABLE"
    elif freshness > 5000:
        quality_state = "STALE"
    elif runtime.lifecycle.connection_state.value in {"DISCONNECTED", "RECONNECTING", "ERROR"}:
        quality_state = "DEGRADED"
    detail_parts = [runtime.lifecycle.connection_state.value]
    if freshness is not None:
        detail_parts.append(f"{freshness} ms since last quote")
    if runtime.capability_registry.is_stale:
        detail_parts.append("probe stale")
    if focus is None:
        detail_parts.append("SELECT AN INSTRUMENT")
    scope_symbols = list(runtime.scope_symbols)
    if not scope_symbols and focus:
        scope_symbols = [focus]
    return {
        "quality_summary": {
            "affected_symbols": scope_symbols,
            "detail": " · ".join(detail_parts),
            "state": quality_state,
        },
        "scope_symbols": scope_symbols,
    }


def build_live_order_flow_payload(instrument_id: str) -> dict[str, Any] | None:
    from ..order_flow.cvd import compute_cvd_series, compute_cvd_state
    from ..order_flow.contracts import cvd_state_to_dict

    runtime = _runtime_or_none()
    if runtime is None:
        return None
    symbol = instrument_id.upper()
    trades = runtime.state.trades_for(symbol)
    book = runtime.state.book_for(symbol)
    metrics = runtime.state.metrics_report()
    if not trades:
        reason = "NO_LIVE_TRADES"
        if book is None and runtime.capability_registry.get("US_EQUITY_DEPTH") and not runtime.capability_registry.get("US_EQUITY_DEPTH").account_entitled:
            reason = "ENTITLEMENT_MISSING"
        return {
            "available": False,
            "disclaimer": "LIVE OBSERVATIONAL · MOOMOO",
            "instrument_id": symbol,
            "provider_id": "MOOMOO",
            "reason": reason,
            "symbol": symbol,
        }
    cvd_input: list[dict[str, Any]] = []
    for trade in trades:
        signed = 0.0
        side = str(trade.get("aggressor_side") or "").upper()
        if side == "SELL":
            signed = -abs(float(trade["quantity"]))
        elif side == "BUY":
            signed = abs(float(trade["quantity"]))
        provenance = str(trade.get("aggressor_provenance") or "")
        quality_label = "mixed" if provenance in {"PROVIDER_NATIVE", "EXCHANGE_NATIVE"} else "neutral"
        cvd_input.append(
            {
                "bar_time": str(trade.get("event_time_ns") or ""),
                "delta": signed,
                "volume": float(trade.get("quantity") or 0),
                "quality": quality_label,
                "source": provenance,
            }
        )
    series = compute_cvd_series([float(row["delta"]) for row in cvd_input])
    cvd_state = compute_cvd_state(cvd_input)
    bars: list[dict[str, Any]] = []
    for idx, trade in enumerate(trades):
        bars.append(
            {
                "aggressor_provenance": trade.get("aggressor_provenance"),
                "available_time_ns": trade.get("available_time_ns"),
                "cumulative_delta": series[idx] if idx < len(series) else 0.0,
                "delta": cvd_input[idx]["delta"],
                "index": idx,
                "price": trade.get("price"),
                "quality": trade.get("quality"),
                "volume": trade.get("quantity"),
            }
        )
    stream_quality = "DEGRADED" if any(trade.get("quality") == "DEGRADED" for trade in trades) else "PASS"
    return {
        "available": True,
        "bar_count": len(bars),
        "bars": bars,
        "classified_count": metrics.get("classified_trades", 0),
        "cvd": None if cvd_state is None else cvd_state_to_dict(cvd_state),
        "disclaimer": "LIVE OBSERVATIONAL · MOOMOO order flow / CVD",
        "duplicates": metrics.get("duplicates", 0),
        "event_count": len(trades),
        "inferred": metrics.get("inferred", 0),
        "instrument_id": symbol,
        "provider_directed": metrics.get("provider_directed", 0),
        "provider_id": "MOOMOO",
        "quality": stream_quality,
        "quality_rejected": metrics.get("quality_rejected", 0),
        "source": "LIVE_OBSERVATIONAL",
        "symbol": symbol,
        "unknown_aggressor": metrics.get("unknown_aggressor", 0),
    }


def build_live_order_book_payload(instrument_id: str) -> dict[str, Any] | None:
    runtime = _runtime_or_none()
    if runtime is None:
        return None
    symbol = instrument_id.upper()
    book = runtime.state.book_for(symbol)
    if not book:
        return None
    bids = list(book.get("bids") or [])
    asks = list(book.get("asks") or [])
    best_bid = bids[0] if bids else None
    best_ask = asks[0] if asks else None
    snapshot = {
        "ask_size": None if best_ask is None else best_ask.get("size"),
        "available_time": book.get("available_time_ns"),
        "best_ask": None if best_ask is None else best_ask.get("price"),
        "best_bid": None if best_bid is None else best_bid.get("price"),
        "bid_size": None if best_bid is None else best_bid.get("size"),
        "book_state_valid": True,
        "epistemic_class": "OBSERVATIONAL",
        "event_time": str(book.get("event_time_ns")),
        "level_count": max(len(bids), len(asks)),
        "quality": book.get("quality"),
    }
    return {
        "available": True,
        "disclaimer": "LIVE OBSERVATIONAL · MOOMOO MBP (not MBO)",
        "provider_id": "MOOMOO",
        "snapshot_count": 1,
        "snapshots": [snapshot],
        "symbol": symbol,
    }


def resolve_live_operating_modes(store: ReplayStore) -> tuple[str, str, str, str]:
    if not live_observational_enabled():
        return store.data_mode, store.execution_mode, store.data_provider, store.execution_authority
    data_mode = "LIVE_OBSERVATIONAL"
    data_provider = "MOOMOO" if moomoo_live_enabled() else store.data_provider
    execution_mode = store.execution_mode
    execution_authority = store.execution_authority
    if live_internal_simulation_enabled() and not getattr(store, "execution_deferred", False):
        execution_mode = "INTERNAL_SIMULATION"
        execution_authority = "PAPER_ONLY"
    elif getattr(store, "execution_deferred", False):
        execution_mode = store.paper_ledger.execution_mode
        execution_authority = "BLOCKED"
    elif execution_mode != "NONE":
        execution_mode = "NONE"
        execution_authority = "BLOCKED"
    return data_mode, execution_mode, data_provider, execution_authority


def apply_live_marks_to_ledger(store: ReplayStore) -> None:
    from . import paper_projections

    paper_projections.maybe_release_execution_gate(store)
    runtime = _runtime_or_none()
    if runtime is None:
        return
    focus = paper_projections._live_focus_instrument_id(store)
    if not focus:
        return
    mark = runtime.live_mark_for(focus)
    if mark is None:
        return
    store.paper_ledger.apply_live_mark(
        instrument_id=focus,
        mark_minor=int(mark["mark_minor"]),
        mark_provider=str(mark["mark_provider"]),
        mark_as_of_ns=int(mark["mark_as_of_ns"]),
        mark_quality=str(mark["mark_quality"]),
    )
    from ..local_state.startup import persist_ledger

    persist_ledger(store.paper_ledger)
