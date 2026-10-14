"""Synthetic provider transports for PF-01 headless supply tests.

Only the transport boundary is replaced: the vendor SDK module and quote
context for OpenD, and the WebSocket connection for Kraken. The feed,
subscription manager, admission, runtimes and writer above them are the real
ones. Nothing here opens a socket, and a passing run says nothing about any
account's entitlement.
"""
from __future__ import annotations

import json
import sys
import threading
import time
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
KRAKEN_PAIRS = {'XA01:00000000000000B7': ('BTC/USD', 1, 8), 'XA01:00000000000000E7': ('ETH/USD', 2, 8)}


def synthetic_probe(path: Path, *, entitled: tuple[str, ...] = ('US_EQUITY_L1', 'US_EQUITY_TICKS', 'US_EQUITY_DEPTH'),
                    verified_at: str | None = None) -> Path:
    """A capability report in the existing probe format. Fixture only; it is not evidence of any account right."""
    stamp = verified_at or datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps({
        'verified_at': stamp, 'sdk_version': 'synthetic', 'connectivity': {'ret': 0, 'opend_version': 'synthetic'},
        'subscription_quota': {'payload': {'total_used': 0, 'remain': 100}},
        'capabilities': {name: {'capability': name, 'account_entitled': name in entitled, 'runtime_tested': True,
                                'evidence_class': 'SYNTHETIC_FIXTURE'}
                         for name in ('US_EQUITY_L1', 'US_EQUITY_TICKS', 'US_EQUITY_DEPTH')}}), encoding='utf-8')
    return path


class _Handler:
    def on_recv_rsp(self, rsp: Any) -> tuple[int, Any]:
        return 0, rsp


def synthetic_sdk() -> types.ModuleType:
    """The few vendor SDK names the existing push feed uses."""
    sdk = types.ModuleType('moomoo')
    sdk.RET_OK, sdk.RET_ERROR = 0, -1
    sdk.SubType = types.SimpleNamespace(QUOTE='QUOTE', TICKER='TICKER', ORDER_BOOK='ORDER_BOOK')
    sdk.Session = types.SimpleNamespace(ALL='ALL')
    sdk.StockQuoteHandlerBase = type('StockQuoteHandlerBase', (_Handler,), {})
    sdk.TickerHandlerBase = type('TickerHandlerBase', (_Handler,), {})
    sdk.OrderBookHandlerBase = type('OrderBookHandlerBase', (_Handler,), {})
    return sdk


class _SDKModulePatch:
    """Restore only our SDK key; runtime imports during a test must survive cleanup."""
    def __init__(self, sdk: types.ModuleType) -> None:
        self.sdk = sdk
        self.previous = None
        self.present = False

    def start(self) -> None:
        self.present = 'moomoo' in sys.modules
        self.previous = sys.modules.get('moomoo')
        sys.modules['moomoo'] = self.sdk

    def stop(self) -> None:
        if self.present:
            sys.modules['moomoo'] = self.previous
        else:
            sys.modules.pop('moomoo', None)


class SyntheticOpenD:
    """One synthetic OpenD: every quote context the feed opens is recorded here."""

    def __init__(self, *, refuse: tuple[tuple[str, str], ...] = (), snapshots: bool = True, quota: int | None = None) -> None:
        self.sdk = synthetic_sdk()
        self.refuse, self.snapshots, self.quota = set(refuse), snapshots, quota
        self.reachable = True
        self.contexts: list[SyntheticQuoteContext] = []
        self.lock = threading.RLock()
        self.sequences: dict[str, int] = {}

    def open(self, _sdk: Any = None, **_kwargs: Any) -> SyntheticQuoteContext | None:
        if not self.reachable:
            return None
        context = SyntheticQuoteContext(self)
        self.contexts.append(context)
        return context

    @property
    def context(self) -> SyntheticQuoteContext | None:
        live = [context for context in self.contexts if not context.closed]
        return live[-1] if live else None

    def subscribed(self) -> set[tuple[str, str]]:
        context = self.context
        return set(context.subscribed) if context is not None else set()

    def push_tick(self, code: str, *, price: float = 190.0, volume: int = 5) -> bool:
        """Synchronously invoke one trade through the feed's own ticker handler, if that stream is subscribed."""
        context = self.context
        if context is None or (code, 'TICKER') not in context.subscribed:
            return False
        with self.lock:
            if context.closed or (code, 'TICKER') not in context.subscribed:
                return False
            # Per instrument and contiguous, as the venue numbers them; a shared counter would look like gaps.
            sequence = self.sequences[code] = self.sequences.get(code, 0) + 1
            context.handlers['TickerHandlerBase'].on_recv_rsp(
                [{'code': code, 'price': price, 'volume': volume, 'sequence': sequence, 'ticker_direction': 'BUY'}])
        return True

    def drop(self) -> None:
        """OpenD goes away: the feed's reachability check fails and its session ends."""
        self.reachable = False

    def restore(self) -> None:
        self.reachable = True

    def install(self) -> list[Any]:
        """Start patches on the existing transport seams. Callers stop them (or the process ends)."""
        tools = str(ROOT / 'tools' / 'moomoo')
        if tools not in sys.path:
            sys.path.insert(0, tools)
        import opend_quote_transport
        import push_feed

        from market_platform_foundation.market_data import live_runtime

        patches = [_SDKModulePatch(self.sdk),
                   patch.object(push_feed, 'opend_reachable', lambda **_k: self.reachable),
                   patch.object(live_runtime, 'opend_reachable', lambda **_k: self.reachable),
                   patch.object(opend_quote_transport, 'open_quote_context', self.open)]
        for item in patches:
            item.start()
        return patches


class SyntheticQuoteContext:
    def __init__(self, opend: SyntheticOpenD) -> None:
        self.opend = opend
        self.handlers: dict[str, Any] = {}
        self.subscribed: set[tuple[str, str]] = set()
        self.subscribe_calls: list[tuple[str, str]] = []
        self.unsubscribe_calls: list[tuple[str, str]] = []
        self.closed = False

    def set_handler(self, handler: Any) -> None:
        self.handlers[type(handler).__mro__[1].__name__] = handler

    def subscribe(self, codes: list[str], subtypes: list[str], **_kwargs: Any) -> tuple[int, str]:
        for code in codes:
            for subtype in subtypes:
                self.subscribe_calls.append((code, subtype))
                if (code, subtype) in self.opend.refuse:
                    return -1, 'synthetic: no quote right'
                if self.opend.quota is not None and len(self.subscribed) >= self.opend.quota:
                    return -1, 'synthetic: subscription quota'
                self.subscribed.add((code, subtype))
        return 0, ''

    def unsubscribe(self, codes: list[str], subtypes: list[str]) -> tuple[int, str]:
        for code in codes:
            for subtype in subtypes:
                self.unsubscribe_calls.append((code, subtype))
                self.subscribed.discard((code, subtype))
        return 0, ''

    def get_market_snapshot(self, codes: list[str]) -> tuple[int, Any]:
        if not self.opend.snapshots:
            return -1, 'synthetic: snapshots off'
        return 0, [{'code': code, 'last_price': 190.5, 'bid_price': 190.4, 'ask_price': 190.6,
                    'bid_vol': 100, 'ask_vol': 200} for code in codes]

    def get_stock_quote(self, _codes: list[str]) -> tuple[int, Any]:
        return -1, 'synthetic: not provided'

    def close(self) -> None:
        with self.opend.lock:
            self.closed = True
            self.subscribed.clear()


class SyntheticKraken:
    """Synthetic Kraken WebSocket v2 endpoint: acknowledges subscriptions and carries pushed trades."""

    def __init__(self, *, refuse: tuple[tuple[str, str], ...] = (), fail_connects: int = 0, slice_seconds: float = 0.0) -> None:
        self.refuse, self.fail_connects, self.slice_seconds = set(refuse), fail_connects, slice_seconds
        self.connections: list[SyntheticKrakenConnection] = []
        self.connect_attempts = 0
        self.trade_id = 0
        self.lock = threading.Lock()

    def connect(self, _url: str) -> SyntheticKrakenConnection:
        from market_platform_foundation.crypto_market.ws_client import WebSocketError

        self.connect_attempts += 1
        if self.fail_connects > 0:
            self.fail_connects -= 1
            raise WebSocketError('WS_CONNECT_FAILED')
        connection = SyntheticKrakenConnection(self)
        self.connections.append(connection)
        return connection

    @property
    def connection(self) -> SyntheticKrakenConnection | None:
        live = [connection for connection in self.connections if not connection.closed]
        return live[-1] if live else None

    def subscribed(self) -> set[tuple[str, str]]:
        connection = self.connection
        return set(connection.subscribed) if connection is not None else set()

    def push_trade(self, symbol: str, *, price: float = 83000.1, qty: float = 0.5) -> bool:
        connection = self.connection
        if connection is None or ('trade', symbol) not in connection.subscribed:
            return False
        with self.lock:
            self.trade_id += 1
            trade_id = self.trade_id
        stamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        with connection.lock:
            if connection.closed or ('trade', symbol) not in connection.subscribed:
                return False
            connection.deliver({'channel': 'trade', 'type': 'update', 'data': [{
                'symbol': symbol, 'side': 'buy', 'price': price, 'qty': qty, 'ord_type': 'market',
                'trade_id': trade_id, 'timestamp': stamp}]})
        return True

    def transport_counts(self) -> dict[str, int]:
        """Producer enqueue and receiver return are distinct observable boundaries."""
        totals = {name: 0 for name in ('enqueued_messages', 'received_messages', 'enqueued_bytes',
                  'received_bytes', 'enqueued_trades', 'received_trades', 'backlog_messages', 'backlog_trades')}
        for connection in self.connections:
            with connection.lock:
                for name in totals:
                    if not name.startswith('backlog'):
                        totals[name] += getattr(connection, name)
                totals['backlog_messages'] += len(connection.inbox)
                totals['backlog_trades'] += connection.enqueued_trades - connection.received_trades
        return totals

    def drop(self) -> None:
        """The venue closes the socket; the runtime's own reconnect takes over."""
        connection = self.connection
        if connection is not None:
            connection.broken = True

    def status(self, system: str) -> None:
        connection = self.connection
        if connection is not None:
            connection.deliver({'channel': 'status', 'type': 'update', 'data': [{'system': system}]})


class SyntheticKrakenConnection:
    def __init__(self, venue: SyntheticKraken) -> None:
        self.venue = venue
        self.inbox: list[str] = []
        self.sent: list[dict[str, Any]] = []
        self.subscribed: set[tuple[str, str]] = set()
        self.closed = self.broken = False
        self.lock = threading.RLock()
        self.enqueued_messages = self.received_messages = 0
        self.enqueued_bytes = self.received_bytes = 0
        self.enqueued_trades = self.received_trades = 0

    def deliver(self, message: dict[str, Any]) -> None:
        with self.lock:
            text = json.dumps(message)
            self.inbox.append(text)
            self.enqueued_messages += 1
            self.enqueued_bytes += len(text.encode())
            if message.get('channel') == 'trade':
                self.enqueued_trades += len(message.get('data') or [])

    def send_text(self, text: str) -> None:
        from market_platform_foundation.crypto_market.ws_client import WebSocketError

        if self.broken:
            raise WebSocketError('WS_CLOSED')
        with self.lock:
            request = json.loads(text)
            self.sent.append(request)
            channel, symbol = request['params']['channel'], request['params']['symbol'][0]
            if request['method'] == 'unsubscribe' and (channel, symbol) not in self.subscribed:
                self.deliver({'method': 'unsubscribe', 'req_id': request['req_id'], 'success': False,
                              'error': 'synthetic: subscription not found'})
            elif request['method'] == 'unsubscribe':
                self.subscribed.discard((channel, symbol))
                self.deliver({'method': 'unsubscribe', 'req_id': request['req_id'], 'success': True})
            elif (channel, symbol) in self.venue.refuse:
                self.deliver({'method': 'subscribe', 'req_id': request['req_id'], 'success': False,
                              'error': 'synthetic: currency pair not supported'})
            else:
                self.subscribed.add((channel, symbol))
                self.deliver({'method': 'subscribe', 'req_id': request['req_id'], 'success': True,
                              'result': {'channel': channel, 'symbol': symbol}})

    def receive(self, _timeout: float) -> str | None:
        from market_platform_foundation.crypto_market.ws_client import WebSocketError

        if self.broken:
            raise WebSocketError('WS_CLOSED')
        with self.lock:
            if self.inbox:
                text = self.inbox.pop(0)
                self.received_messages += 1
                self.received_bytes += len(text.encode())
                message = json.loads(text)
                if message.get('channel') == 'trade':
                    self.received_trades += len(message.get('data') or [])
                return text
        if self.venue.slice_seconds:
            time.sleep(self.venue.slice_seconds)  # a threaded runtime must not spin on an empty socket
            return json.dumps({'channel': 'heartbeat'})
        return None

    def close(self) -> None:
        self.closed = True
