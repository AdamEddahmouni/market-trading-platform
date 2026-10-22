"""Selected-instrument specialist panels for the Main Screener (S4).

The Screener dock opens Order Flow, CVD, Level 2, Charts, and Futures Context
panels for one canonical selected instrument. This module owns the live-data
side of the first three:

* ``demand`` turns (selected instrument, open panels) into reference-counted
  runtime subscriptions. Each open panel is one logical consumer, so Order
  Flow and CVD share a single provider trade subscription.
* ``order_flow``, ``cvd``, and ``depth`` project the live observational state
  into provider-neutral contracts with their own clocks and states.

Nothing here reads replay, capture, or fixture data. When the live runtime is
fed by a fixture instead of a current provider, every panel is UNAVAILABLE.
"""

from __future__ import annotations

import statistics
import threading
import time
from datetime import UTC, datetime
from typing import Any, Callable

from ..market_data.live_config import depth_freshness_policy, live_observational_enabled
from ..market_data.live_runtime import get_live_runtime
from ..market_data.subscription_manager import SubscriptionPriority
from ..market_sessions import us_equity_session_label
from ..order_flow.cvd import compute_cvd_series
from ..order_flow.history import request_window
from ..order_flow.order_book.contracts import BookValidity, FreshnessStatus
from ..order_flow.order_book.freshness import evaluate_book_freshness

SCHEMA_VERSION = "screener-specialist/1.0.0"
TRADES = "US_EQUITY_TICKS"
DEPTH = "US_EQUITY_DEPTH"
PANEL_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "order_flow": (TRADES,),
    "cvd": (TRADES,),
    "level2": (DEPTH,),
    "charts": (),
    "futures": (),
    # S7: a per-underlying Finviz snapshot; no streaming subscription.
    "options": (),
    # S8: live-confirmation evidence reads the order-flow/CVD projections, so the
    # panel holds the same reference-counted trades capability (one provider
    # subscription however many panels ask).
    "short_squeeze": (TRADES,),
}
CLIENT_TTL_SECONDS = 45
#: OpenD holds a subscription for at least one minute; a released instrument
#: still occupies provider slots for that long.
PROVIDER_HOLD_SECONDS = 60
#: Distinct instruments the specialist panels may occupy (held or still inside
#: the provider hold) at once: at most 6 × 2 provider slots of the 100 quota.
MAX_SPECIALIST_INSTRUMENTS = 6
TAPE_ROWS = 100
FEED_SILENT_SECONDS = 30
RECENT_DELTA_SECONDS = 60
LARGE_PRINT_MULTIPLE = 10
LARGE_PRINT_MIN_TRADES = 20
IMBALANCE_DEPTHS = (5, 10)
DISPLAY_LEVELS = 20
DISCONNECTED_STATES = frozenset(("DISCONNECTED", "RECONNECTING", "DISABLED", "CONNECTING", "ERROR", "MAINTENANCE"))
_UNVERIFIED_REASONS = frozenset(("PROBE_STALE", "PROBE_MISSING"))
_PERMISSION_WORDS = ("permission", "quote card", "entitle", "authority")
_QUOTA_WORDS = ("quota", "subscription limit", "exceed")
#: Provider-supplied side labels, never exchange aggressor truth.
_INFERENCE_METHODS = {
    "PROVIDER_NATIVE": "PROVIDER_TICKER_DIRECTION",
    "LEE_READY": "LEE_READY", "QUOTE_MATCH": "QUOTE_MATCH", "TICK_RULE": "TICK_RULE",
    "BVC": "BVC", "OTHER_INFERENCE": "OTHER_INFERENCE",
}


def _iso(ns: int | None) -> str | None:
    if not ns:
        return None
    return datetime.fromtimestamp(ns / 1_000_000_000, tz=UTC).isoformat().replace("+00:00", "Z")


def _default_runtime() -> Any | None:
    if not live_observational_enabled():
        return None
    return get_live_runtime(create=True)


def _default_known(instrument_id: str) -> bool:
    from .screener_projections import screener_service

    row, _error = screener_service().row_for(instrument_id)
    return row is not None


def aggressor_view(trade: dict[str, Any]) -> dict[str, Any]:
    """NATIVE only for exchange-native sides; provider or model labels are INFERRED."""

    side = str(trade.get("aggressor_side") or "UNKNOWN").upper()
    provenance = str(trade.get("aggressor_provenance") or "UNKNOWN").upper()
    if side not in ("BUY", "SELL") or provenance == "UNKNOWN":
        return {"state": "UNKNOWN", "side": None, "method": "UNCLASSIFIED"}
    if provenance == "EXCHANGE_NATIVE":
        return {"state": "NATIVE", "side": side, "method": "EXCHANGE_NATIVE"}
    return {"state": "INFERRED", "side": side, "method": _INFERENCE_METHODS.get(provenance, provenance)}


def _signed(trade: dict[str, Any], aggressor: dict[str, Any]) -> float:
    size = abs(float(trade.get("quantity") or 0))
    if aggressor["side"] == "BUY":
        return size
    if aggressor["side"] == "SELL":
        return -size
    return 0.0


def _sequence(trade: dict[str, Any]) -> int:
    try:
        return int(str(trade.get("trade_id")))
    except (TypeError, ValueError):
        return 0


class ScreenerSpecialistService:
    """Panel demand, reference-counted subscriptions, and panel projections."""

    def __init__(
        self,
        *,
        runtime_getter: Callable[[], Any | None] = _default_runtime,
        known_instrument: Callable[[str], bool] = _default_known,
        session_label: Callable[[], str] = us_equity_session_label,
        now_ns: Callable[[], int] = time.time_ns,
        monotonic: Callable[[], float] = time.monotonic,
        schedule_expiry: bool = True,
        trades_capability: str = TRADES,
        depth_capability: str = DEPTH,
        panels: tuple[str, ...] | None = None,
        provider_hold_seconds: float = PROVIDER_HOLD_SECONDS,
    ) -> None:
        # One service per market runtime: US equities/ETFs share the Moomoo/IBKR
        # runtime; Crypto (S10) supplies its own venue runtime and capability names
        # while every panel projection below stays identical.
        self._trades, self._depth = trades_capability, depth_capability
        # How long a released instrument still occupies provider slots (OpenD: 60 s;
        # a venue whose unsubscribe takes effect immediately passes 0).
        self._provider_hold = provider_hold_seconds
        rename = {TRADES: trades_capability, DEPTH: depth_capability}
        self._panel_capabilities = {panel: tuple(rename.get(item, item) for item in capabilities)
                                    for panel, capabilities in PANEL_CAPABILITIES.items()
                                    if panels is None or panel in panels}
        self._runtime_getter = runtime_getter
        self._known = known_instrument
        self._session = session_label
        self._now_ns = now_ns
        self._monotonic = monotonic
        self._schedule = schedule_expiry
        self._lock = threading.RLock()
        #: client_id -> (instrument, held (panel, capability) pairs, last seen, runtime)
        self._clients: dict[str, tuple[str | None, set[tuple[str, str]], float, Any]] = {}
        #: instrument -> monotonic time its last specialist hold was released
        self._released: dict[str, float] = {}
        self._rejected: dict[tuple[str, str], str] = {}
        self._expiry_timer: threading.Timer | None = None

    # ------------------------------------------------------------------ demand

    @staticmethod
    def consumer_id(client_id: str, panel: str) -> str:
        return f"screener-panel:{client_id}:{panel}"

    def _held_instruments(self) -> set[str]:
        return {instrument for instrument, held, _, _ in self._clients.values() if instrument and held}

    def _occupied(self, now: float) -> set[str]:
        for instrument, released in list(self._released.items()):
            if now - released >= self._provider_hold:
                self._released.pop(instrument, None)
        return self._held_instruments() | set(self._released)

    def _release_pairs(self, client_id: str, instrument: str | None, pairs: set[tuple[str, str]], runtime: Any) -> None:
        if not pairs or instrument is None:
            return
        if runtime is not None:
            for panel, capability in sorted(pairs):
                runtime.unsubscribe(instrument_id=instrument, capabilities=[capability],
                                    consumer_id=self.consumer_id(client_id, panel))
                history = getattr(runtime.state, "flow_history", None)
                if capability == self._trades and history is not None and runtime.subscriptions.ref_count(
                        instrument_id=instrument, capability=capability) == 0:
                    history.end(instrument, self._now_ns())
        # The caller has already removed ``pairs`` from this client's record.
        if self._provider_hold > 0 and instrument not in self._held_instruments():
            self._released[instrument] = self._monotonic()

    def _release(self, client_id: str) -> None:
        record = self._clients.pop(client_id, None)
        if record is None:
            return
        instrument, held, _, runtime = record
        self._release_pairs(client_id, instrument, held, runtime)

    def _schedule_expiry(self) -> None:
        if not self._schedule or self._expiry_timer is not None or not self._clients:
            return
        timer = threading.Timer(CLIENT_TTL_SECONDS, self._expire_clients)
        timer.daemon = True
        self._expiry_timer = timer
        timer.start()

    def _expire_clients(self) -> None:
        with self._lock:
            self._expiry_timer = None
            self.expire()
            self._schedule_expiry()

    def expire(self) -> None:
        with self._lock:
            now = self._monotonic()
            for client_id, (_, _, seen, _) in list(self._clients.items()):
                if now - seen >= CLIENT_TTL_SECONDS:
                    self._release(client_id)

    def release(self, client_id: str) -> dict[str, Any]:
        with self._lock:
            self._release(client_id)
        return {"released": True}

    def demand(self, client_id: str, instrument_id: str | None, panels: list[str], *,
               admitted: bool = False) -> dict[str, Any]:
        """``admitted`` means the caller already resolved ``instrument_id`` from a
        current universe catalog (S5 ETFs); otherwise the equity snapshot admits it."""

        if not client_id or len(client_id) > 80 or not all(c.isalnum() or c in "-_" for c in client_id):
            raise ValueError("INVALID_CLIENT_ID")
        if len(set(panels)) != len(panels) or any(panel not in self._panel_capabilities for panel in panels):
            raise ValueError("INVALID_PANELS")
        if instrument_id is not None and (not isinstance(instrument_id, str) or not (admitted or self._known(instrument_id))):
            raise ValueError("UNKNOWN_INSTRUMENT")
        with self._lock:
            self.expire()
            now = self._monotonic()
            runtime = self._runtime_getter()
            previous_instrument, held, _, previous_runtime = self._clients.get(client_id, (None, set(), now, runtime))
            if previous_runtime is not runtime or previous_instrument != instrument_id:
                self._release(client_id)
                held = set()
            desired = ({(panel, capability) for panel in panels for capability in self._panel_capabilities[panel]}
                       if instrument_id else set())
            stale = held - desired
            held = held - stale
            self._clients[client_id] = (instrument_id, held, now, runtime)
            self._release_pairs(client_id, instrument_id, stale, runtime)
            results: list[dict[str, Any]] = []
            for panel, capability in sorted(desired):
                result = {"panel": panel, "capability": capability, "accepted": False, "reason": None,
                          "ref_count": 0, "provider_subscription_active": False}
                if runtime is None:
                    result["reason"] = "LIVE_RUNTIME_UNAVAILABLE"
                elif (panel, capability) in held:
                    result.update(accepted=True, ref_count=runtime.subscriptions.ref_count(instrument_id=instrument_id, capability=capability),
                                  provider_subscription_active=True)
                else:
                    occupied = self._occupied(now) - {instrument_id}
                    new_instrument = not any(pair for pair in held)
                    if new_instrument and instrument_id not in self._held_instruments() and len(occupied) >= MAX_SPECIALIST_INSTRUMENTS:
                        result["reason"] = "SUBSCRIPTION_BUSY"
                    else:
                        acquired = runtime.subscribe(instrument_id=instrument_id, capabilities=[capability],
                                                     consumer_id=self.consumer_id(client_id, panel),
                                                     priority=int(SubscriptionPriority.ACTIVE_WORKSPACE))[0]
                        result.update(accepted=bool(acquired["accepted"]), reason=acquired.get("reason"),
                                      ref_count=int(acquired.get("ref_count") or 0),
                                      provider_subscription_active=bool(acquired.get("provider_subscription_active")))
                        if acquired["accepted"]:
                            held.add((panel, capability))
                            self._released.pop(instrument_id, None)
                if instrument_id is not None:
                    if result["accepted"]:
                        self._rejected.pop((instrument_id, capability), None)
                        history = getattr(runtime.state, "flow_history", None)
                        if capability == self._trades and history is not None:
                            history.begin(instrument_id, runtime.subscriptions.activated_at(
                                instrument_id=instrument_id, capability=capability) or self._now_ns())
                    elif result["reason"]:
                        self._rejected[(instrument_id, capability)] = str(result["reason"])
                results.append(result)
            self._clients[client_id] = (instrument_id, held, now, runtime)
            self._schedule_expiry()
            return {"schema_version": SCHEMA_VERSION, "instrument_id": instrument_id, "panels": list(panels),
                    "capabilities": results, "cap": {"max_instruments": MAX_SPECIALIST_INSTRUMENTS,
                                                     "occupied_instruments": len(self._occupied(now))}}

    # ------------------------------------------------------------- live state

    def _base(self, panel: str, instrument_id: str, capability: str | None) -> dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, "panel": panel, "instrument_id": instrument_id,
                "capability": capability, "provider": None, "generated_at": _iso(self._now_ns()),
                "market_session": self._session(), "state": "UNAVAILABLE", "reason": None}

    @staticmethod
    def _provider(runtime: Any) -> str | None:
        if getattr(runtime, "provider_name", None):
            return str(runtime.provider_name)
        if getattr(runtime, "feed", None) is not None:
            return "MOOMOO"
        if getattr(runtime, "ibkr_transport", None) is not None:
            return "IBKR"
        return None

    def _gate(self, runtime: Any, instrument_id: str, capability: str) -> tuple[str | None, str | None, int | None]:
        """Blocking (state, reason) or (None, None, anchor_ns) when data may be read."""

        if runtime is None:
            return "UNAVAILABLE", "LIVE_RUNTIME_UNAVAILABLE", None
        if self._provider(runtime) is None:
            return "UNAVAILABLE", "NO_CURRENT_FEED", None
        # A stale or missing probe is unverified, not refused: the provider's own
        # subscribe answer (below) decides. Only an observed refusal is NOT_ENTITLED.
        if self._entitlement(runtime, capability) == "NOT_ENTITLED":
            return "NOT_ENTITLED", "ENTITLEMENT_MISSING", None
        if hasattr(runtime, "subscription_refusal"):
            refusal = runtime.subscription_refusal(instrument_id, capability)
        else:
            feed = getattr(runtime, "feed", None)
            errors = getattr(feed, "subscription_errors", {}) or {}
            subtype = {TRADES: "TICKER", DEPTH: "ORDER_BOOK"}[capability]
            refusal = next((value for (code, name), value in errors.items()
                            if name == subtype and code.split(".")[-1].upper() == instrument_id.upper()), None)
        if refusal is not None:
            message = str(refusal.get("message") or "").lower()
            if any(word in message for word in _PERMISSION_WORDS):
                return "NOT_ENTITLED", "ENTITLEMENT_MISSING", None
            if any(word in message for word in _QUOTA_WORDS):
                return "UNAVAILABLE", "PROVIDER_QUOTA_EXHAUSTED", None
            return "UNAVAILABLE", "PROVIDER_SUBSCRIBE_REFUSED", None
        connection = str(getattr(runtime.lifecycle.connection_state, "value", runtime.lifecycle.connection_state)).upper()
        if connection in DISCONNECTED_STATES:
            return "DISCONNECTED", connection, None
        if runtime.subscriptions.ref_count(instrument_id=instrument_id, capability=capability) <= 0:
            rejected = self._rejected.get((instrument_id, capability))
            return ("SUBSCRIPTION_BUSY" if rejected == "SUBSCRIPTION_BUSY" else "CONNECTING"), rejected or "NOT_SUBSCRIBED", None
        activated = runtime.subscriptions.activated_at(instrument_id=instrument_id, capability=capability) or 0
        anchor = max(activated, int(getattr(runtime.lifecycle, "connected_ns", None) or 0))
        return None, None, anchor

    @staticmethod
    def _entitlement(runtime: Any, capability: str) -> str:
        if runtime is not None and hasattr(runtime, "entitlement_for"):
            return str(runtime.entitlement_for(capability))
        registry = getattr(runtime, "capability_registry", None) if runtime is not None else None
        entry = registry.get(capability) if registry is not None else None
        if entry is None:
            return "UNVERIFIED"
        if entry.account_entitled:
            return "PROBE_VERIFIED"
        return "UNVERIFIED" if entry.reason_code in _UNVERIFIED_REASONS else "NOT_ENTITLED"

    def _feed_silent(self, runtime: Any) -> bool:
        last = getattr(runtime.lifecycle, "last_received_ns", None)
        return bool(last) and self._now_ns() - int(last) > FEED_SILENT_SECONDS * 1_000_000_000

    def _trade_window(self, runtime: Any, instrument_id: str, anchor_ns: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        retained = runtime.state.trades_for(instrument_id)
        capacity = int(getattr(runtime.state, "max_trades", 0) or 0)
        unique: dict[str, dict[str, Any]] = {}
        for trade in retained:
            if int(trade.get("available_time_ns") or 0) >= anchor_ns:
                unique[str(trade.get("trade_id"))] = trade
        # Provider pushes can arrive out of order; the window is event-time ordered.
        trades = sorted(unique.values(), key=lambda row: (int(row.get("event_time_ns") or 0), _sequence(row)))
        oldest_retained = min((int(row.get("available_time_ns") or 0) for row in retained), default=0)
        truncated = bool(capacity) and len(retained) >= capacity and oldest_retained > anchor_ns
        window = {
            "basis": "LAST_N_CAPTURED" if truncated else "SINCE_SUBSCRIPTION",
            "anchor_at": _iso(anchor_ns),
            "start": _iso(int(trades[0]["event_time_ns"])) if trades else None,
            "end": _iso(int(trades[-1]["event_time_ns"])) if trades else None,
            "max_records": capacity,
            "truncated": truncated,
        }
        return trades, window

    def _live_state(self, runtime: Any, has_data: bool, *, latest_event_ns: int | None = None) -> tuple[str, str | None]:
        if self._session() == "CLOSED":
            return "SESSION_CLOSED", None if has_data else "NO_CAPTURED_DATA"
        if self._feed_silent(runtime):
            return "STALE", "FEED_SILENT"
        if latest_event_ns is not None and (latest_event_ns > self._now_ns() or self._now_ns() - latest_event_ns > FEED_SILENT_SECONDS * 1_000_000_000):
            return "STALE", "SYMBOL_EVENT_OUTSIDE_POLICY"
        return "CURRENT", None if has_data else "AWAITING_DATA"

    def order_flow(self, instrument_id: str) -> dict[str, Any]:
        payload = self._base("order_flow", instrument_id, self._trades)
        runtime = self._runtime_getter()
        payload["entitlement"] = self._entitlement(runtime, self._trades)
        blocked, reason, anchor = self._gate(runtime, instrument_id, self._trades)
        payload["provider"] = self._provider(runtime) if runtime is not None else None
        if blocked is not None:
            return {**payload, "state": blocked, "reason": reason, "summary": None, "tape": [], "window": None}
        trades, window = self._trade_window(runtime, instrument_id, anchor or 0)
        state, reason = self._live_state(runtime, bool(trades), latest_event_ns=int(trades[-1]["event_time_ns"]) if trades else None)
        views = [aggressor_view(trade) for trade in trades]
        sizes = [abs(float(trade.get("quantity") or 0)) for trade in trades]
        buy = sum(size for size, view in zip(sizes, views) if view["side"] == "BUY")
        sell = sum(size for size, view in zip(sizes, views) if view["side"] == "SELL")
        unknown = sum(size for size, view in zip(sizes, views) if view["side"] is None)
        total = buy + sell + unknown
        span_ns = int(trades[-1]["event_time_ns"]) - int(trades[0]["event_time_ns"]) if len(trades) > 1 else 0
        methods: dict[str, int] = {}
        for view in views:
            methods[view["method"]] = methods.get(view["method"], 0) + 1
        threshold = (statistics.median(sizes) * LARGE_PRINT_MULTIPLE) if len(sizes) >= LARGE_PRINT_MIN_TRADES else None
        tape = []
        for trade, view, size in list(zip(trades, views, sizes))[-TAPE_ROWS:][::-1]:
            tape.append({"trade_id": str(trade.get("trade_id")), "event_time": _iso(int(trade.get("event_time_ns") or 0)),
                         "received_time": _iso(int(trade.get("available_time_ns") or 0)),
                         "price": float(trade.get("price") or 0), "size": size, "aggressor": view,
                         "condition": trade.get("condition") or None,
                         "large": threshold is not None and size >= threshold})
        latest = trades[-1] if trades else None
        return {**payload, "state": state, "reason": reason, "window": window,
                "latest_event_at": _iso(int(latest["event_time_ns"])) if latest else None,
                "latest_received_at": _iso(int(latest["available_time_ns"])) if latest else None,
                "summary": {
                    "trade_count": len(trades), "total_volume": total, "buy_volume": buy, "sell_volume": sell,
                    "unknown_volume": unknown, "net_signed_volume": buy - sell,
                    "classified_volume_pct": (buy + sell) / total * 100 if total else None,
                    "native_count": sum(1 for view in views if view["state"] == "NATIVE"),
                    "inferred_count": sum(1 for view in views if view["state"] == "INFERRED"),
                    "unknown_count": sum(1 for view in views if view["state"] == "UNKNOWN"),
                    "methods": methods,
                    "trades_per_minute": len(trades) / (span_ns / 60_000_000_000) if span_ns >= 60_000_000_000 else None,
                    "large_print_threshold": threshold,
                },
                "tape": tape}

    def cvd(self, instrument_id: str) -> dict[str, Any]:
        payload = self._base("cvd", instrument_id, self._trades)
        runtime = self._runtime_getter()
        payload["entitlement"] = self._entitlement(runtime, self._trades)
        blocked, reason, anchor = self._gate(runtime, instrument_id, self._trades)
        payload["provider"] = self._provider(runtime) if runtime is not None else None
        payload["derivation"] = "DERIVED"
        if blocked is not None:
            return {**payload, "state": blocked, "reason": reason, "summary": None, "points": [], "window": None}
        trades, window = self._trade_window(runtime, instrument_id, anchor or 0)
        state, reason = self._live_state(runtime, bool(trades), latest_event_ns=int(trades[-1]["event_time_ns"]) if trades else None)
        views = [aggressor_view(trade) for trade in trades]
        deltas = [_signed(trade, view) for trade, view in zip(trades, views)]
        series = compute_cvd_series(deltas)
        points = [{"time_ms": int(trade["event_time_ns"]) // 1_000_000, "cvd": value, "delta": delta}
                  for trade, value, delta in zip(trades, series, deltas)]
        sizes = [abs(float(trade.get("quantity") or 0)) for trade in trades]
        classified = sum(size for size, view in zip(sizes, views) if view["side"] is not None)
        unknown = sum(size for size, view in zip(sizes, views) if view["side"] is None)
        total = classified + unknown
        latest_ns = int(trades[-1]["event_time_ns"]) if trades else 0
        recent = sum(delta for trade, delta in zip(trades, deltas)
                     if int(trade["event_time_ns"]) >= latest_ns - RECENT_DELTA_SECONDS * 1_000_000_000)
        states = {name: sum(1 for view in views if view["state"] == name) for name in ("NATIVE", "INFERRED", "UNKNOWN")}
        return {**payload, "state": state, "reason": reason, "window": window,
                "latest_event_at": _iso(latest_ns) if trades else None,
                "latest_received_at": _iso(int(trades[-1]["available_time_ns"])) if trades else None,
                "summary": {
                    "cvd": series[-1] if series else 0.0,
                    "recent_delta": recent if trades else None, "recent_delta_seconds": RECENT_DELTA_SECONDS,
                    "trade_count": len(trades), "classified_volume": classified, "unknown_volume": unknown,
                    "classified_volume_pct": classified / total * 100 if total else None,
                    "aggressor_states": states,
                    "methods": sorted({view["method"] for view in views if view["state"] != "UNKNOWN"}),
                },
                "points": points}

    def order_flow_series(self, instrument_id: str, *, range_name: str = "5m",
                          resolution: str = "auto", start_ms: int | None = None,
                          end_ms: int | None = None) -> dict[str, Any]:
        now = self._now_ns()
        start, end, seconds = request_window(now, self._session(), range_name, start_ms, end_ms, resolution)
        payload = self._base("order_flow_series", instrument_id, self._trades)
        runtime = self._runtime_getter()
        blocked, reason, _anchor = self._gate(runtime, instrument_id, self._trades)
        payload.update(provider=self._provider(runtime) if runtime is not None else None,
                       entitlement=self._entitlement(runtime, self._trades), range=range_name)
        history = getattr(runtime.state, "flow_history", None) if runtime is not None else None
        empty = {"points": [], "coverage": None, "latest": None, "resolution_seconds": seconds}
        if blocked is not None or history is None:
            return {**payload, **empty, "state": blocked or "UNAVAILABLE", "reason": reason or "FLOW_HISTORY_UNAVAILABLE"}
        series = history.project(instrument_id, start=start, end=end, seconds=seconds, now_ns=now)
        state, reason = self._live_state(runtime, bool(series["points"]))
        return {**payload, **series, "state": state, "reason": reason}

    def depth(self, instrument_id: str) -> dict[str, Any]:
        payload = self._base("level2", instrument_id, self._depth)
        runtime = self._runtime_getter()
        payload["entitlement"] = self._entitlement(runtime, self._depth)
        blocked, reason, anchor = self._gate(runtime, instrument_id, self._depth)
        payload["provider"] = self._provider(runtime) if runtime is not None else None
        empty = {"bids": [], "asks": [], "best_bid": None, "best_ask": None, "spread": None, "mid": None,
                 "spread_bps": None, "imbalance": [], "completeness": None, "freshness": None,
                 "latest_event_at": None, "latest_received_at": None, "quality_flags": []}
        if blocked is not None:
            return {**payload, **empty, "state": blocked, "reason": reason}
        engine = runtime.state.book_engine_for(instrument_id)
        received = getattr(engine, "last_received_time_ns", None) if engine is not None else None
        if engine is None or received is None or received < (anchor or 0):
            # A book held from an earlier subscription or connection is never shown.
            state = "SESSION_CLOSED" if self._session() == "CLOSED" else "CONNECTING"
            return {**payload, **empty, "state": state, "reason": "AWAITING_BOOK_SNAPSHOT"}
        clocks = {"latest_event_at": _iso(engine.last_source_time_ns), "latest_received_at": _iso(received)}
        if engine.validity is not BookValidity.VALID:
            return {**payload, **empty, **clocks, "state": "INVALID", "reason": engine.invalidation_reason.value}
        if engine.is_crossed:
            return {**payload, **empty, **clocks, "state": "INVALID", "reason": "CROSSED_BOOK",
                    "quality_flags": ["CROSSED_BOOK"]}
        bids_raw, asks_raw = engine.to_snapshot_rows()
        levels_ok = all(row["price"] > 0 and row["size"] > 0 for row in bids_raw + asks_raw)
        ordered = all(bids_raw[i]["price"] > bids_raw[i + 1]["price"] for i in range(len(bids_raw) - 1)) and \
            all(asks_raw[i]["price"] < asks_raw[i + 1]["price"] for i in range(len(asks_raw) - 1))
        if not levels_ok or not ordered:
            return {**payload, **empty, **clocks, "state": "INVALID", "reason": "MALFORMED_LEVELS"}

        def side(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            total = 0.0
            out = []
            for row in rows[:DISPLAY_LEVELS]:
                total += row["size"]
                out.append({"price": row["price"], "size": row["size"], "cumulative_size": total})
            return out

        bids, asks = side(bids_raw), side(asks_raw)
        best_bid = bids[0]["price"] if bids else None
        best_ask = asks[0]["price"] if asks else None
        spread = best_ask - best_bid if best_bid is not None and best_ask is not None else None
        mid = (best_ask + best_bid) / 2 if spread is not None else None
        imbalance = []
        for depth in IMBALANCE_DEPTHS:
            bid_size = sum(row["size"] for row in bids_raw[:depth])
            ask_size = sum(row["size"] for row in asks_raw[:depth])
            if bid_size + ask_size > 0 and bids_raw and asks_raw:
                imbalance.append({"levels": depth, "bid_levels": min(depth, len(bids_raw)), "ask_levels": min(depth, len(asks_raw)),
                                  "bid_size": bid_size, "ask_size": ask_size,
                                  "bid_share": bid_size / (bid_size + ask_size),
                                  "signed": (bid_size - ask_size) / (bid_size + ask_size),
                                  "complete": len(bids_raw) >= depth and len(asks_raw) >= depth})
        policy = depth_freshness_policy((payload["provider"] or "").lower())
        freshness = evaluate_book_freshness(engine, as_of_time_ns=self._now_ns(), policy=policy)
        flags: list[str] = []
        if not bids_raw or not asks_raw:
            flags.append("ONE_SIDED")
        if self._session() == "CLOSED":
            state, reason = "SESSION_CLOSED", "LAST_CAPTURED_BOOK"
        elif freshness.status is FreshnessStatus.STALE:
            state, reason = "STALE", "NO_BOOK_UPDATE_WITHIN_TTL"
        elif freshness.status is not FreshnessStatus.FRESH:
            state, reason = "UNAVAILABLE", freshness.reason_code or "FRESHNESS_UNAVAILABLE"
        elif flags:
            state, reason = "PARTIAL", "ONE_SIDED_BOOK"
        else:
            state, reason = "CURRENT", None
        return {**payload, **clocks, "state": state, "reason": reason, "quality_flags": flags,
                "bids": bids, "asks": asks, "best_bid": best_bid, "best_ask": best_ask, "spread": spread, "mid": mid,
                "spread_bps": spread / mid * 10_000 if spread is not None and mid else None,
                "imbalance": imbalance,
                "completeness": {"basis": "PROVIDER_MBP_TOP_N", "bid_levels": len(bids_raw), "ask_levels": len(asks_raw),
                                 "venue_scope": "PROVIDER_UNSPECIFIED", "update_semantics": "SNAPSHOT",
                                 **(runtime.depth_completeness() if hasattr(runtime, "depth_completeness") else {})},
                "freshness": {"status": freshness.status.value, "age_ms": None if freshness.age_ns is None else freshness.age_ns // 1_000_000,
                              "ttl_ms": policy.stale_after_ns // 1_000_000, "policy": policy.name}}


_SERVICE: ScreenerSpecialistService | None = None
_SERVICE_LOCK = threading.Lock()


def specialist_service() -> ScreenerSpecialistService:
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            _SERVICE = ScreenerSpecialistService()
    return _SERVICE


__all__ = ["PANEL_CAPABILITIES", "ScreenerSpecialistService", "aggressor_view", "specialist_service"]
