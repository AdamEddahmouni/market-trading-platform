"""Kraken Spot WebSocket v2 selected-pair stream (Screener S10).

One public, unauthenticated connection to ``wss://ws.kraken.com/v2`` carries
the ``trade`` and ``book`` channels for the pairs the Screener dock panels
currently demand. This object is the single subscription authority for that
connection and implements the runtime interface ``ScreenerSpecialistService``
reads, so Order Flow, CVD, and Level 2 reuse the S4 projections unchanged:

* ``subscribe`` / ``unsubscribe`` keep per-consumer reference counts; a venue
  channel is subscribed on the first consumer and unsubscribed after the last;
* each channel has its own acknowledgement clock (``activated_at``); after a
  reconnect every demanded channel is resubscribed and re-anchored, so a
  panel never presents trades from before a gap as one continuous window;
* reconnects use bounded, jittered exponential backoff; a silent connection
  (no heartbeat) is torn down; ``status`` maintenance is its own state;
* a ``book`` checksum failure invalidates that book and resubscribes for a
  fresh snapshot (rate-limited per pair); an invalid book is never shown;
* trades carry Kraken's native taker side (``side``: "The side of the taker
  order") as an exchange-native aggressor;
* with no demand the connection closes after a short linger; ``shutdown``
  stops the worker.

Nothing here reads replay, fixture, or captured data, and nothing places or
authenticates orders.
"""

from __future__ import annotations

import json
import random
import threading
import time
from collections import deque
from typing import Any, Callable

from .kraken_book import BookView, KrakenBook, iso_ns, parse_message
from .ws_client import WebSocketClient, WebSocketError

URL = "wss://ws.kraken.com/v2"
PROVIDER = "KRAKEN"
TRADES = "CRYPTO_TRADES"
BOOK = "CRYPTO_BOOK"
CHANNELS = {TRADES: "trade", BOOK: "book"}
BOOK_DEPTH = 25
MAX_TRADES = 5_000
SILENCE_SECONDS = 15.0
IDLE_LINGER_SECONDS = 30.0
BACKOFF_SECONDS = (1.0, 2.0, 4.0, 8.0, 16.0, 30.0)
RESYNC_MIN_INTERVAL_SECONDS = 2.0
RECEIVE_SLICE_SECONDS = 0.25


class _Lifecycle:
    def __init__(self) -> None:
        self.connection_state = "IDLE"
        self.connected_ns: int | None = None
        self.last_received_ns: int | None = None
        self.reconnects = 0
        self.last_error: str | None = None


class _Subscriptions:
    def __init__(self, runtime: "KrakenStreamRuntime") -> None:
        self._runtime = runtime

    def ref_count(self, *, instrument_id: str, capability: str) -> int:
        with self._runtime._lock:
            return len(self._runtime._consumers.get((instrument_id, capability), ()))

    def activated_at(self, *, instrument_id: str, capability: str) -> int | None:
        runtime = self._runtime
        with runtime._lock:
            symbol = runtime._symbols.get(instrument_id)
            return runtime._acked.get((CHANNELS[capability], symbol)) if symbol else None


class _State:
    def __init__(self, runtime: "KrakenStreamRuntime") -> None:
        self._runtime = runtime
        self.max_trades = runtime.max_trades

    def trades_for(self, instrument_id: str) -> list[dict[str, Any]]:
        with self._runtime._lock:
            return list(self._runtime._trades.get(instrument_id, ()))

    def book_engine_for(self, instrument_id: str) -> BookView | None:
        with self._runtime._lock:
            book = self._runtime._books.get(instrument_id)
            return book.view() if book is not None else None


Resolver = Callable[[str], "tuple[str, int, int] | None"]


class KrakenStreamRuntime:
    provider_name = PROVIDER

    def __init__(self, *, resolve: Resolver, connect: Callable[[str], Any] | None = None,
                 now_ns: Callable[[], int] = time.time_ns, monotonic: Callable[[], float] = time.monotonic,
                 start_worker: bool = True, max_trades: int = MAX_TRADES, depth: int = BOOK_DEPTH,
                 jitter: Callable[[], float] = random.random,
                 wait: Callable[[float], Any] | None = None) -> None:
        self._resolve = resolve
        self._connect = connect or (lambda url: WebSocketClient.connect(url))
        self._now_ns, self._monotonic, self._jitter = now_ns, monotonic, jitter
        self.max_trades, self.depth = max_trades, depth
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._wait = wait or self._stop.wait
        self.lifecycle = _Lifecycle()
        self.subscriptions = _Subscriptions(self)
        self.state = _State(self)
        #: (instrument, capability) -> consumer ids
        self._consumers: dict[tuple[str, str], set[str]] = {}
        #: instrument -> (symbol, price decimals, qty decimals)
        self._pairs: dict[str, tuple[str, int, int]] = {}
        self._symbols: dict[str, str] = {}
        self._by_symbol: dict[str, str] = {}
        #: per connection: channel/symbol requested, acknowledged (ns), refused (error text)
        self._sent: set[tuple[str, str]] = set()
        self._acked: dict[tuple[str, str], int] = {}
        self._refused: dict[tuple[str, str], str] = {}
        self._pending: dict[int, tuple[str, str, str]] = {}
        #: instrument -> monotonic time its book resubscription is due / last performed
        self._resync_due: dict[str, float] = {}
        self._resync_last: dict[str, float] = {}
        self._trades: dict[str, deque[dict[str, Any]]] = {}
        self._books: dict[str, KrakenBook] = {}
        self._request_id = 0
        self._connection: Any = None
        self._attempt = 0
        self._idle_since: float | None = None
        self._worker: threading.Thread | None = None
        self._start_worker = start_worker

    # ------------------------------------------------------------ demand side

    def subscribe(self, *, instrument_id: str, capabilities: list[str], consumer_id: str,
                  priority: int = 0) -> list[dict[str, Any]]:
        del priority  # one venue connection; the Screener service caps instruments
        results = []
        with self._lock:
            pair = self._pairs.get(instrument_id) or self._resolve(instrument_id)
            for capability in capabilities:
                if capability not in CHANNELS or pair is None:
                    results.append({"accepted": False, "reason": "UNKNOWN_INSTRUMENT" if pair is None else "UNSUPPORTED_CAPABILITY",
                                    "ref_count": 0, "provider_subscription_active": False})
                    continue
                self._pairs[instrument_id] = pair
                self._symbols[instrument_id] = pair[0]
                self._by_symbol[pair[0]] = instrument_id
                consumers = self._consumers.setdefault((instrument_id, capability), set())
                consumers.add(consumer_id)
                results.append({"accepted": True, "reason": None, "ref_count": len(consumers),
                                "provider_subscription_active": (CHANNELS[capability], pair[0]) in self._acked})
            self._idle_since = None
        self._ensure_worker()
        self._wake.set()
        return results

    def unsubscribe(self, *, instrument_id: str, capabilities: list[str], consumer_id: str) -> None:
        with self._lock:
            for capability in capabilities:
                consumers = self._consumers.get((instrument_id, capability))
                if consumers is None:
                    continue
                consumers.discard(consumer_id)
                if not consumers:
                    del self._consumers[(instrument_id, capability)]
        self._wake.set()

    def subscription_refusal(self, instrument_id: str, capability: str) -> dict[str, str] | None:
        with self._lock:
            symbol = self._symbols.get(instrument_id)
            message = self._refused.get((CHANNELS.get(capability, ""), symbol or ""))
            return {"message": message} if message else None

    def entitlement_for(self, capability: str) -> str:
        """Public data needs no account; the venue's own subscribe acknowledgement verifies access."""

        with self._lock:
            return "PROBE_VERIFIED" if any(channel == CHANNELS.get(capability) for channel, _ in self._acked) else "UNVERIFIED"

    def depth_completeness(self) -> dict[str, Any]:
        return {"basis": "VENUE_TOP_N", "venue_scope": "SINGLE_VENUE_KRAKEN",
                "update_semantics": "SNAPSHOT_PLUS_DELTA_CRC32", "subscribed_depth": self.depth}

    def _desired(self) -> set[tuple[str, str]]:
        return {(CHANNELS[capability], self._symbols[instrument]) for (instrument, capability), consumers
                in self._consumers.items() if consumers and instrument in self._symbols}

    # ------------------------------------------------------------ worker loop

    def _ensure_worker(self) -> None:
        if not self._start_worker:
            return
        with self._lock:
            if self._worker is None or not self._worker.is_alive():
                self._stop.clear()
                self._worker = threading.Thread(target=self._run, name="imp-kraken-stream", daemon=True)
                self._worker.start()

    def shutdown(self) -> None:
        self._stop.set()
        self._wake.set()
        worker = self._worker
        if worker is not None and worker is not threading.current_thread():
            worker.join(timeout=5)
        self._disconnect("IDLE")

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.step()
            except Exception:  # noqa: BLE001 — the stream must survive any single malformed event
                self._disconnect("RECONNECTING", error="STREAM_ERROR")

    def step(self) -> None:
        """One bounded iteration: connect/reconcile/receive. Tests drive this directly."""

        with self._lock:
            desired = self._desired()
            if not desired:
                now = self._monotonic()
                self._idle_since = self._idle_since if self._idle_since is not None else now
                if self._connection is not None and now - self._idle_since >= IDLE_LINGER_SECONDS:
                    self._disconnect("IDLE")
                self._drop_undemanded(desired)
            connection = self._connection
        if not desired and connection is None:
            self._wake.wait(1.0)
            self._wake.clear()
            return
        if connection is None:
            self._open()
            return
        self._reconcile(desired)
        try:
            message = connection.receive(RECEIVE_SLICE_SECONDS)
        except WebSocketError as exc:
            self._disconnect("RECONNECTING", error=exc.code)
            return
        now_ns = self._now_ns()
        if message is not None:
            self.handle(message, received_ns=now_ns)
        last = self.lifecycle.last_received_ns or self.lifecycle.connected_ns or now_ns
        if now_ns - last > SILENCE_SECONDS * 1_000_000_000:
            self._disconnect("RECONNECTING", error="FEED_SILENT")

    def _open(self) -> None:
        with self._lock:
            self.lifecycle.connection_state = "CONNECTING" if self._attempt == 0 else "RECONNECTING"
        try:
            connection = self._connect(URL)
        except WebSocketError as exc:
            self._backoff(exc.code)
            return
        except OSError:
            self._backoff("WS_CONNECT_FAILED")
            return
        with self._lock:
            self._connection = connection
            self._sent.clear()
            self._acked.clear()
            self._refused.clear()
            self._pending.clear()
            self.lifecycle.connection_state = "CONNECTED"
            self.lifecycle.connected_ns = self._now_ns()
            self.lifecycle.last_received_ns = None
            self.lifecycle.last_error = None

    def _backoff(self, error: str) -> None:
        delay = BACKOFF_SECONDS[min(self._attempt, len(BACKOFF_SECONDS) - 1)]
        self._attempt += 1
        with self._lock:
            self.lifecycle.connection_state = "RECONNECTING"
            self.lifecycle.last_error = error
            self.lifecycle.reconnects += 1
        # Jitter spreads reconnects across [0.8, 1.2] x the bounded delay.
        self._wait(delay * (0.8 + 0.4 * self._jitter()))

    def _disconnect(self, state: str, *, error: str | None = None) -> None:
        with self._lock:
            connection, self._connection = self._connection, None
            self._sent.clear()
            self._acked.clear()
            self._pending.clear()
            # A book from a previous connection is never continued; trades stay
            # retained but every channel re-anchors on its next acknowledgement.
            self._books.clear()
            self._resync_due.clear()
            self.lifecycle.connection_state = state
            self.lifecycle.last_error = error
            if state == "IDLE":
                self._attempt = 0
        if connection is not None:
            connection.close()
        if state == "RECONNECTING":
            self._backoff(error or "DISCONNECTED")

    def _drop_undemanded(self, desired: set[tuple[str, str]]) -> None:
        demanded = {instrument for instrument, _ in self._consumers}
        for instrument in list(self._trades):
            if instrument not in demanded:
                del self._trades[instrument]
        for instrument in list(self._books):
            if (CHANNELS[BOOK], self._symbols.get(instrument)) not in desired:
                del self._books[instrument]
                self._resync_due.pop(instrument, None)

    def _send(self, method: str, channel: str, symbol: str) -> None:
        self._request_id += 1
        params: dict[str, Any] = {"channel": channel, "symbol": [symbol]}
        if channel == "book":
            # Kraken keys a book subscription by depth: an unsubscribe without the
            # subscribed depth targets depth 10 and leaves this one alive
            # ("Subscription with depth 10 not Found"; observed 2026-09-28).
            params["depth"] = self.depth
        if method == "subscribe":
            # Trades: no snapshot, so the window really is "since subscription".
            params["snapshot"] = channel == "book"
        self._pending[self._request_id] = (method, channel, symbol)
        self._connection.send_text(json.dumps({"method": method, "params": params, "req_id": self._request_id}))

    def _reconcile(self, desired: set[tuple[str, str]]) -> None:
        with self._lock:
            try:
                self._run_resyncs()
                for channel, symbol in sorted(self._sent - desired):
                    self._send("unsubscribe", channel, symbol)
                    self._sent.discard((channel, symbol))
                    self._acked.pop((channel, symbol), None)
                    self._refused.pop((channel, symbol), None)
                for channel, symbol in sorted(desired - self._sent):
                    self._send("subscribe", channel, symbol)
                    self._sent.add((channel, symbol))
            except WebSocketError as exc:
                error = exc.code
            else:
                self._drop_undemanded(desired)
                return
        self._disconnect("RECONNECTING", error=error)

    # --------------------------------------------------------- message intake

    def handle(self, text: str, *, received_ns: int) -> None:
        try:
            message = parse_message(text)
        except ValueError:
            return
        if not isinstance(message, dict):
            return
        with self._lock:
            self.lifecycle.last_received_ns = received_ns
            if "method" in message:
                self._handle_ack(message, received_ns)
                return
            channel = message.get("channel")
            if channel == "heartbeat":
                for book in self._books.values():
                    book.confirm_continuity(received_ns)
            elif channel == "status":
                data = message.get("data")
                system = data[0].get("system") if isinstance(data, list) and data and isinstance(data[0], dict) else None
                if system == "maintenance":
                    self.lifecycle.connection_state = "MAINTENANCE"
                elif system in ("online", "cancel_only", "post_only", "limit_only"):
                    # Order-entry restrictions do not change public market data.
                    self.lifecycle.connection_state = "CONNECTED"
            elif channel == "trade":
                self._handle_trades(message, received_ns)
            elif channel == "book":
                self._handle_book(message, received_ns)

    def _handle_ack(self, message: dict[str, Any], received_ns: int) -> None:
        request = self._pending.pop(message.get("req_id"), None) if isinstance(message.get("req_id"), int) else None
        if request is None:
            return
        method, channel, symbol = request
        if method != "subscribe" or (channel, symbol) not in self._sent:
            return
        error = str(message.get("error") or "")
        if message.get("success") is True or error == "Already subscribed":
            # "Already subscribed" means the venue channel is live on this connection.
            self._acked[(channel, symbol)] = received_ns
            self._refused.pop((channel, symbol), None)
            self._attempt = 0
            instrument = self._by_symbol.get(symbol)
            if message.get("success") is not True and channel == CHANNELS[BOOK] and instrument is not None                     and not (instrument in self._books and self._books[instrument].valid):
                # No snapshot will follow an already-live subscription: resync for one.
                self._resync_due.setdefault(instrument, self._monotonic())
        else:
            self._refused[(channel, symbol)] = (error or "subscribe refused")[:200]

    def _handle_trades(self, message: dict[str, Any], received_ns: int) -> None:
        for item in message.get("data") or []:
            if not isinstance(item, dict):
                continue
            instrument = self._by_symbol.get(item.get("symbol"))
            if instrument is None or (CHANNELS[TRADES], item.get("symbol")) not in self._acked:
                continue
            event_ns = iso_ns(item.get("timestamp"))
            side = item.get("side")
            try:
                price, qty = float(item["price"]), float(item["qty"])
            except (KeyError, TypeError, ValueError):
                continue
            if event_ns is None or price <= 0 or qty <= 0 or not isinstance(item.get("trade_id"), int):
                continue
            self._trades.setdefault(instrument, deque(maxlen=self.max_trades)).append({
                "trade_id": str(item["trade_id"]), "event_time_ns": event_ns, "available_time_ns": received_ns,
                "price": price, "quantity": qty,
                "aggressor_side": {"buy": "BUY", "sell": "SELL"}.get(side, "UNKNOWN"),
                "aggressor_provenance": "EXCHANGE_NATIVE" if side in ("buy", "sell") else "UNKNOWN",
                "condition": item.get("ord_type") if isinstance(item.get("ord_type"), str) else None,
            })

    def _handle_book(self, message: dict[str, Any], received_ns: int) -> None:
        kind = message.get("type")
        for item in message.get("data") or []:
            if not isinstance(item, dict):
                continue
            symbol = item.get("symbol")
            instrument = self._by_symbol.get(symbol)
            if instrument is None or (CHANNELS[BOOK], symbol) not in self._sent:
                continue
            _symbol, price_decimals, qty_decimals = self._pairs[instrument]
            if kind == "snapshot":
                book = KrakenBook(instrument, depth=self.depth, price_decimals=price_decimals, qty_decimals=qty_decimals)
                self._books[instrument] = book
                ok = book.apply_snapshot(item, received_ns=received_ns,
                                         subscription_id=f"kraken:{self.lifecycle.connected_ns}:{symbol}")
            elif kind == "update" and instrument in self._books:
                book = self._books[instrument]
                if not book.valid:
                    continue  # already awaiting a fresh snapshot; late deltas are discarded
                ok = book.apply_update(item, received_ns=received_ns)
            else:
                continue
            if not ok and instrument not in self._resync_due:
                # Rate-limited so a persistent integrity fault cannot spin the connection.
                last = self._resync_last.get(instrument)
                now = self._monotonic()
                self._resync_due[instrument] = now if last is None else max(now, last + RESYNC_MIN_INTERVAL_SECONDS)

    def _run_resyncs(self) -> None:
        """Due invalid books: unsubscribe so reconciliation requests a fresh snapshot."""

        now = self._monotonic()
        for instrument, due in list(self._resync_due.items()):
            if due > now:
                continue
            del self._resync_due[instrument]
            self._resync_last[instrument] = now
            key = (CHANNELS[BOOK], self._symbols.get(instrument, ""))
            if key in self._sent:
                self._send("unsubscribe", *key)
                self._sent.discard(key)
                self._acked.pop(key, None)


_RUNTIME: KrakenStreamRuntime | None = None
_RUNTIME_LOCK = threading.Lock()


def kraken_stream_runtime(resolve: Resolver) -> KrakenStreamRuntime:
    global _RUNTIME
    with _RUNTIME_LOCK:
        if _RUNTIME is None:
            _RUNTIME = KrakenStreamRuntime(resolve=resolve)
    return _RUNTIME
