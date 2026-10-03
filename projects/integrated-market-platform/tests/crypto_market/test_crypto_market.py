"""Screener S10 public Crypto venue stream: WebSocket client, Kraken book, stream runtime.

No test here opens a network connection: sockets and connections are fakes,
and the Kraken book fixtures are real captured venue messages (2026-09-28)
used only to check the published checksum algorithm.
"""

from __future__ import annotations

import json
import socket
import struct
import unittest
from decimal import Decimal
from pathlib import Path

from market_platform_foundation.crypto_market.kraken_book import (
    KrakenBook, book_checksum, checksum_field, iso_ns, parse_message)
from market_platform_foundation.crypto_market.kraken_stream import BOOK, TRADES, KrakenStreamRuntime
from market_platform_foundation.crypto_market.ws_client import (
    OP_CLOSE, OP_CONTINUATION, OP_PING, OP_PONG, OP_TEXT, WebSocketClient, WebSocketError, accept_key,
    encode_frame, parse_frame)
from market_platform_foundation.order_flow.order_book.contracts import BookLevel, BookStatusReason, BookValidity
from market_platform_foundation.ui_api.screener_specialist import ScreenerSpecialistService

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "crypto_market"


def server_frame(opcode: int, payload: bytes, *, final: bool = True) -> bytes:
    length = len(payload)
    first = (0x80 if final else 0) | opcode
    if length < 126:
        return struct.pack("!BB", first, length) + payload
    if length < 1 << 16:
        return struct.pack("!BBH", first, 126, length) + payload
    return struct.pack("!BBQ", first, 127, length) + payload


def unmask(frame: bytes) -> tuple[int, bytes]:
    buffer = bytearray(frame)
    length, offset = buffer[1] & 0x7F, 2
    if length == 126:
        length, offset = struct.unpack("!H", frame[2:4])[0], 4
    elif length == 127:
        length, offset = struct.unpack("!Q", frame[2:10])[0], 10
    mask = frame[offset:offset + 4]
    body = frame[offset + 4:offset + 4 + length]
    return buffer[0] & 0x0F, bytes(byte ^ mask[index % 4] for index, byte in enumerate(body))


class FakeSocket:
    def __init__(self, chunks: list[bytes] | None = None) -> None:
        self.chunks = list(chunks or [])
        self.sent: list[bytes] = []
        self.closed = False

    def settimeout(self, _value: float) -> None:
        pass

    def sendall(self, data: bytes) -> None:
        self.sent.append(data)

    def recv(self, _size: int) -> bytes:
        if not self.chunks:
            raise socket.timeout()
        chunk = self.chunks.pop(0)
        if chunk == b"<EOF>":
            return b""
        return chunk

    def close(self) -> None:
        self.closed = True


# --------------------------------------------------------------- WebSocket
class WebSocketFramingTests(unittest.TestCase):
    def test_client_frames_are_masked_at_every_length_class(self):
        for size in (5, 300, 70_000):
            payload = b"x" * size
            opcode, body = unmask(encode_frame(OP_TEXT, payload, mask=b"\x01\x02\x03\x04"))
            self.assertEqual((opcode, body), (OP_TEXT, payload))
            self.assertTrue(encode_frame(OP_TEXT, payload)[1] & 0x80)

    def test_parse_waits_for_complete_frame_and_consumes_exactly_one(self):
        frame = server_frame(OP_TEXT, b'{"a":1}') + server_frame(OP_TEXT, b"{}")
        buffer = bytearray(frame[:4])
        self.assertIsNone(parse_frame(buffer))
        self.assertEqual(len(buffer), 4)
        buffer.extend(frame[4:])
        self.assertEqual(parse_frame(buffer), (True, OP_TEXT, b'{"a":1}'))
        self.assertEqual(parse_frame(buffer), (True, OP_TEXT, b"{}"))

    def test_masked_server_frame_reserved_bits_and_oversize_are_protocol_errors(self):
        with self.assertRaises(WebSocketError) as masked:
            parse_frame(bytearray(b"\x81\x81abcdx"))
        self.assertEqual(masked.exception.code, "WS_MASKED_SERVER_FRAME")
        with self.assertRaises(WebSocketError):
            parse_frame(bytearray(b"\xc1\x00"))
        with self.assertRaises(WebSocketError) as large:
            parse_frame(bytearray(server_frame(OP_TEXT, b"x" * 200)), max_bytes=100)
        self.assertEqual(large.exception.code, "WS_FRAME_TOO_LARGE")

    def test_timeout_mid_frame_loses_no_bytes(self):
        frame = server_frame(OP_TEXT, b'{"channel":"heartbeat"}')
        sock = FakeSocket([frame[:3]])
        client = WebSocketClient(sock)
        self.assertIsNone(client.receive(0.01))
        sock.chunks.append(frame[3:])
        self.assertEqual(client.receive(0.01), '{"channel":"heartbeat"}')

    def test_fragmented_text_ping_pong_and_close(self):
        sock = FakeSocket([server_frame(OP_TEXT, b'{"a"', final=False) + server_frame(OP_PING, b"hi")
                           + server_frame(OP_CONTINUATION, b':1}'), server_frame(OP_CLOSE, struct.pack("!H", 1000))])
        client = WebSocketClient(sock)
        self.assertEqual(client.receive(0.01), '{"a":1}')
        self.assertEqual(unmask(sock.sent[0]), (OP_PONG, b"hi"))
        with self.assertRaises(WebSocketError) as closed:
            client.receive(0.01)
        self.assertEqual(closed.exception.code, "WS_CLOSED_BY_PEER")
        self.assertTrue(client.closed)

    def test_peer_eof_is_an_error_not_an_empty_message(self):
        client = WebSocketClient(FakeSocket([b"<EOF>"]))
        with self.assertRaises(WebSocketError):
            client.receive(0.01)

    def test_handshake_verifies_accept_key_and_host_allowlist(self):
        with self.assertRaises(WebSocketError) as host:
            WebSocketClient.connect("wss://example.com/v2", connector=lambda *_: FakeSocket())
        self.assertEqual(host.exception.code, "WS_HOST_NOT_ALLOWED")

        class Server(FakeSocket):
            def __init__(self, good: bool) -> None:
                super().__init__()
                self.good = good

            def recv(self, _size: int) -> bytes:
                key = self.sent[0].decode().split("Sec-WebSocket-Key: ")[1].split("\r\n")[0]
                accept = accept_key(key) if self.good else "wrong"
                return (f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                        f"Sec-WebSocket-Accept: {accept}\r\n\r\n").encode() + server_frame(OP_TEXT, b"{}")

        client = WebSocketClient.connect("wss://ws.kraken.com/v2", connector=lambda *_: Server(True))
        self.assertEqual(client.receive(0.01), "{}")
        rejected = Server(False)
        with self.assertRaises(WebSocketError) as bad:
            WebSocketClient.connect("wss://ws.kraken.com/v2", connector=lambda *_: rejected)
        self.assertEqual(bad.exception.code, "WS_HANDSHAKE_REJECTED")
        self.assertTrue(rejected.closed)


# ------------------------------------------------------------- Kraken book
def fixture_lines(name: str) -> list[str]:
    return [line for line in (FIXTURES / name).read_text(encoding="utf-8").splitlines() if line.strip()]


class KrakenBookTests(unittest.TestCase):
    def test_checksum_field_formatting(self):
        self.assertEqual(checksum_field(Decimal("0.00012000"), 8), "12000")
        self.assertEqual(checksum_field(Decimal("83307.3"), 1), "833073")
        self.assertEqual(checksum_field(Decimal("5.739E-6"), 9), "5739")

    def test_real_venue_snapshot_and_deltas_match_published_checksums(self):
        book = KrakenBook("XA01:BTCUSD", depth=10, price_decimals=1, qty_decimals=8)
        lines = fixture_lines("kraken_book_btcusd_depth10.jsonl")
        self.assertGreater(len(lines), 30)
        for index, line in enumerate(lines):
            message = parse_message(line)
            data = message["data"][0]
            if index == 0:
                self.assertEqual(message["type"], "snapshot")
                self.assertTrue(book.apply_snapshot(data, received_ns=1, subscription_id="s1"))
            else:
                self.assertTrue(book.apply_update(data, received_ns=index + 1), f"message {index}")
            self.assertEqual(book.engine.validity, BookValidity.VALID)
            self.assertLessEqual(len(book.engine.bids), 10)
            self.assertLessEqual(len(book.engine.asks), 10)
        view = book.view()
        self.assertFalse(view.is_crossed)
        self.assertEqual(book.checksum_failures, 0)

    def test_checksum_mismatch_invalidates_and_blocks_further_deltas(self):
        book = KrakenBook("XA01:BTCUSD", depth=10, price_decimals=1, qty_decimals=8)
        lines = fixture_lines("kraken_book_btcusd_depth10.jsonl")
        book.apply_snapshot(parse_message(lines[0])["data"][0], received_ns=1, subscription_id="s1")
        corrupt = parse_message(lines[1])["data"][0]
        corrupt["checksum"] = (corrupt["checksum"] + 1) & 0xFFFFFFFF
        self.assertFalse(book.apply_update(corrupt, received_ns=2))
        self.assertEqual(book.engine.invalidation_reason, BookStatusReason.CHECKSUM_MISMATCH)
        self.assertFalse(book.apply_update(parse_message(lines[2])["data"][0], received_ns=3))
        self.assertEqual(book.engine.validity, BookValidity.INVALID)
        # Only a fresh snapshot recovers.
        self.assertTrue(book.apply_snapshot(parse_message(lines[0])["data"][0], received_ns=4, subscription_id="s2"))

    def test_zero_qty_deletes_and_depth_truncates_levels_the_venue_does_not_remove(self):
        def level(price: str, qty: str) -> dict:
            return {"price": Decimal(price), "qty": Decimal(qty)}

        bids = [level(str(100 - index), "1") for index in range(10)]
        asks = [level(str(101 + index), "1") for index in range(10)]
        book = KrakenBook("X", depth=10, price_decimals=0, qty_decimals=0)

        def checksum(b, a) -> int:
            return book_checksum([BookLevel(x["price"], x["qty"]) for x in b], [BookLevel(x["price"], x["qty"]) for x in a],
                                 price_decimals=0, qty_decimals=0)

        self.assertTrue(book.apply_snapshot({"bids": bids, "asks": asks, "checksum": checksum(bids, asks)},
                                            received_ns=1, subscription_id="s"))
        # A better bid pushes the 10th bid out; the venue sends only the insert.
        new_bids = [level("100.5", "2")] + bids[:9]
        self.assertTrue(book.apply_update({"bids": [level("100.5", "2")], "asks": [],
                                           "checksum": checksum(new_bids, asks)}, received_ns=2))
        self.assertEqual([row.price for row in book.engine.bids][-1], Decimal("92"))
        remaining = [x for x in new_bids if x["price"] != Decimal("99")]
        self.assertTrue(book.apply_update({"bids": [level("99", "0")], "asks": [],
                                           "checksum": checksum(remaining, asks)}, received_ns=3))
        self.assertEqual(len(book.engine.bids), 9)

    def test_malformed_levels_fail_closed(self):
        book = KrakenBook("X", depth=10, price_decimals=0, qty_decimals=0)
        self.assertFalse(book.apply_snapshot({"bids": [{"price": "abc", "qty": 1}], "asks": [], "checksum": 0},
                                             received_ns=1, subscription_id="s"))
        self.assertEqual(book.engine.validity, BookValidity.INVALID)

    def test_iso_timestamps_keep_nanosecond_precision_and_reject_non_utc(self):
        self.assertEqual(iso_ns("2026-09-28T12:35:46.398367Z"), 1790598946398367000)
        self.assertIsNone(iso_ns("2026-09-28T12:35:46+01:00"))
        self.assertIsNone(iso_ns(None))


# ----------------------------------------------------------- stream runtime
class FakeConnection:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.inbox: list[str] = []
        self.closed = False
        self.fail: WebSocketError | None = None

    def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))

    def receive(self, _timeout: float) -> str | None:
        if self.fail:
            raise self.fail
        return self.inbox.pop(0) if self.inbox else None

    def close(self) -> None:
        self.closed = True


class StreamHarness:
    def __init__(self) -> None:
        self.now = iso_ns("2026-09-28T12:00:00Z")
        self.mono = 0.0
        self.connections: list[FakeConnection] = []
        self.waits: list[float] = []
        self.runtime = KrakenStreamRuntime(
            resolve=lambda instrument: ("BTC/USD", 1, 8) if instrument == "XA01:BTC" else None,
            connect=self._connect, now_ns=lambda: self.now, monotonic=lambda: self.mono,
            start_worker=False, depth=10, jitter=lambda: 0.5, wait=self.waits.append)

    def _connect(self, _url: str) -> FakeConnection:
        connection = FakeConnection()
        self.connections.append(connection)
        return connection

    @property
    def connection(self) -> FakeConnection:
        return self.connections[-1]

    def step(self, *messages: str) -> None:
        if self.runtime._connection is not None:
            self.connection.inbox.extend(messages)
        self.runtime.step()
        while self.runtime._connection is not None and self.connection.inbox:
            self.runtime.step()

    def ack_all(self) -> None:
        pending = list(self.runtime._pending.items())
        self.step(*[json.dumps({"method": method, "req_id": request_id, "success": True,
                                "result": {"channel": channel, "symbol": symbol}})
                    for request_id, (method, channel, symbol) in pending])


def trade_message(trade_id: int, side: str, qty: str = "0.5") -> str:
    return json.dumps({"channel": "trade", "type": "update", "data": [{
        "symbol": "BTC/USD", "side": side, "price": 83000.1, "qty": float(qty), "ord_type": "market",
        "trade_id": trade_id, "timestamp": "2026-09-28T12:00:00.000001Z"}]})


class KrakenStreamRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.h = StreamHarness()
        self.rt = self.h.runtime

    def open(self, capabilities=(TRADES, BOOK)):
        for capability in capabilities:
            self.rt.subscribe(instrument_id="XA01:BTC", capabilities=[capability], consumer_id=f"c:{capability}")
        self.h.step()  # connect
        self.h.step()  # reconcile -> subscribe requests
        self.h.ack_all()

    def test_reference_counted_single_venue_subscription_per_channel(self):
        self.rt.subscribe(instrument_id="XA01:BTC", capabilities=[TRADES], consumer_id="a")
        result = self.rt.subscribe(instrument_id="XA01:BTC", capabilities=[TRADES], consumer_id="b")
        self.assertEqual(result[0]["ref_count"], 2)
        self.h.step()
        self.h.step()
        subscribes = [m for m in self.h.connection.sent if m["method"] == "subscribe"]
        self.assertEqual(len(subscribes), 1)
        self.assertEqual(subscribes[0]["params"], {"channel": "trade", "symbol": ["BTC/USD"], "snapshot": False})
        self.rt.unsubscribe(instrument_id="XA01:BTC", capabilities=[TRADES], consumer_id="a")
        self.h.step()
        self.assertFalse(any(m["method"] == "unsubscribe" for m in self.h.connection.sent))
        self.rt.unsubscribe(instrument_id="XA01:BTC", capabilities=[TRADES], consumer_id="b")
        self.h.step()
        self.assertEqual(self.h.connection.sent[-1]["method"], "unsubscribe")

    def test_unknown_instrument_is_refused_without_a_venue_request(self):
        result = self.rt.subscribe(instrument_id="XA01:NOPE", capabilities=[TRADES], consumer_id="a")
        self.assertEqual(result[0], {"accepted": False, "reason": "UNKNOWN_INSTRUMENT", "ref_count": 0,
                                     "provider_subscription_active": False})

    def test_trades_before_ack_are_ignored_and_taker_side_is_exchange_native(self):
        self.rt.subscribe(instrument_id="XA01:BTC", capabilities=[TRADES], consumer_id="a")
        self.h.step()
        self.h.step(trade_message(1, "buy"))
        self.assertEqual(self.rt.state.trades_for("XA01:BTC"), [])
        self.h.ack_all()
        self.assertEqual(self.rt.subscriptions.activated_at(instrument_id="XA01:BTC", capability=TRADES), self.h.now)
        self.h.step(trade_message(2, "sell"))
        trade = self.rt.state.trades_for("XA01:BTC")[0]
        self.assertEqual((trade["aggressor_side"], trade["aggressor_provenance"], trade["condition"]),
                         ("SELL", "EXCHANGE_NATIVE", "market"))
        self.assertEqual(trade["event_time_ns"], iso_ns("2026-09-28T12:00:00.000001Z"))
        self.assertEqual(self.rt.entitlement_for(TRADES), "PROBE_VERIFIED")

    def test_real_book_fixture_through_runtime_then_checksum_failure_resyncs(self):
        self.open((BOOK,))
        lines = fixture_lines("kraken_book_btcusd_depth10.jsonl")
        self.h.step(*lines[:5])
        self.assertEqual(self.rt.state.book_engine_for("XA01:BTC").validity, BookValidity.VALID)
        checksum = parse_message(lines[5])["data"][0]["checksum"]
        self.h.step(lines[5].replace(f'"checksum":{checksum}', f'"checksum":{(checksum + 1) & 0xFFFFFFFF}'))
        view = self.rt.state.book_engine_for("XA01:BTC")
        self.assertEqual(view.invalidation_reason, BookStatusReason.CHECKSUM_MISMATCH)
        self.h.step()  # due resync: unsubscribe, then reconcile resubscribes for a fresh snapshot
        methods = [m["method"] for m in self.h.connection.sent[-2:]]
        self.assertEqual(methods, ["unsubscribe", "subscribe"])
        # Kraken keys book subscriptions by depth; the unsubscribe must name it.
        self.assertEqual(self.h.connection.sent[-2]["params"], {"channel": "book", "symbol": ["BTC/USD"], "depth": 10})
        self.assertTrue(self.h.connection.sent[-1]["params"]["snapshot"])
        # Late deltas from the old subscription never touch the invalid book or re-trigger a resync.
        before = len(self.h.connection.sent)
        self.h.step(lines[6])
        self.assertEqual(len(self.h.connection.sent), before)
        self.h.ack_all()
        self.h.step(lines[0])
        self.assertEqual(self.rt.state.book_engine_for("XA01:BTC").validity, BookValidity.VALID)

    def test_disconnect_reconnects_with_bounded_backoff_and_reanchors_every_channel(self):
        self.open()
        first_ack = self.rt.subscriptions.activated_at(instrument_id="XA01:BTC", capability=TRADES)
        self.h.step(fixture_lines("kraken_book_btcusd_depth10.jsonl")[0])
        self.h.connection.fail = WebSocketError("WS_CLOSED_BY_PEER")
        self.h.step()
        self.assertEqual(self.rt.lifecycle.connection_state, "RECONNECTING")
        self.assertIsNone(self.rt.state.book_engine_for("XA01:BTC"))
        self.assertIsNone(self.rt.subscriptions.activated_at(instrument_id="XA01:BTC", capability=TRADES))
        self.assertEqual(self.h.waits, [1.0])
        self.h.now += 5_000_000_000
        self.h.step()  # reconnect
        self.h.step()  # resubscribe both channels
        self.assertEqual(len(self.h.connections), 2)
        self.assertEqual({m["params"]["channel"] for m in self.h.connection.sent}, {"trade", "book"})
        self.h.ack_all()
        self.assertGreater(self.rt.subscriptions.activated_at(instrument_id="XA01:BTC", capability=TRADES), first_ack)

    def test_backoff_is_bounded(self):
        def refuse(_url):
            raise WebSocketError("WS_CONNECT_FAILED")

        self.rt._connect = refuse
        self.rt.subscribe(instrument_id="XA01:BTC", capabilities=[TRADES], consumer_id="a")
        for _ in range(9):
            self.rt.step()
        self.assertEqual(self.h.waits, [1.0, 2.0, 4.0, 8.0, 16.0, 30.0, 30.0, 30.0, 30.0])
        self.assertEqual(self.rt.lifecycle.last_error, "WS_CONNECT_FAILED")

    def test_silent_connection_is_torn_down(self):
        self.open((TRADES,))
        self.h.now += 16_000_000_000
        self.h.step()
        self.assertTrue(self.h.connections[0].closed)
        self.assertEqual(self.rt.lifecycle.last_error, "FEED_SILENT")

    def test_maintenance_status_and_refusal_are_explicit(self):
        self.open((TRADES,))
        self.h.step(json.dumps({"channel": "status", "type": "update", "data": [{"system": "maintenance"}]}))
        self.assertEqual(self.rt.lifecycle.connection_state, "MAINTENANCE")
        self.h.step(json.dumps({"channel": "status", "type": "update", "data": [{"system": "cancel_only"}]}))
        self.assertEqual(self.rt.lifecycle.connection_state, "CONNECTED")
        self.rt.subscribe(instrument_id="XA01:BTC", capabilities=[BOOK], consumer_id="b")
        self.h.step()
        request_id = max(self.rt._pending)
        self.h.step(json.dumps({"method": "subscribe", "req_id": request_id, "success": False,
                                "error": "Currency pair not supported"}))
        self.assertEqual(self.rt.subscription_refusal("XA01:BTC", BOOK), {"message": "Currency pair not supported"})

    def test_already_subscribed_is_live_and_a_bookless_channel_resyncs_for_a_snapshot(self):
        self.rt.subscribe(instrument_id="XA01:BTC", capabilities=[BOOK], consumer_id="a")
        self.h.step()
        self.h.step()
        request_id = max(self.rt._pending)
        self.h.step(json.dumps({"method": "subscribe", "req_id": request_id, "success": False, "error": "Already subscribed"}))
        self.assertIsNone(self.rt.subscription_refusal("XA01:BTC", BOOK))
        self.assertIsNotNone(self.rt.subscriptions.activated_at(instrument_id="XA01:BTC", capability=BOOK))
        self.h.step()
        self.assertEqual([m["method"] for m in self.h.connection.sent[-2:]], ["unsubscribe", "subscribe"])

    def test_pair_switch_drops_old_pair_state_and_idle_connection_closes(self):
        self.open((TRADES,))
        self.h.step(trade_message(7, "buy"))
        self.rt.unsubscribe(instrument_id="XA01:BTC", capabilities=[TRADES], consumer_id=f"c:{TRADES}")
        self.h.step()
        self.assertEqual(self.rt.state.trades_for("XA01:BTC"), [])
        self.h.mono += 31
        self.h.step()
        self.assertTrue(self.h.connection.closed)
        self.assertEqual(self.rt.lifecycle.connection_state, "IDLE")


# ------------------------------------------- S4 projections over the stream
class CryptoSpecialistProjectionTests(unittest.TestCase):
    def setUp(self):
        self.h = StreamHarness()
        self.service = ScreenerSpecialistService(
            runtime_getter=lambda: self.h.runtime, known_instrument=lambda _i: True, session_label=lambda: "24_7",
            now_ns=lambda: self.h.now, trades_capability=TRADES, depth_capability=BOOK,
            panels=("order_flow", "cvd", "level2", "charts"), schedule_expiry=False)

    def test_order_flow_cvd_and_depth_use_native_sides_and_never_session_close(self):
        demand = self.service.demand("client", "XA01:BTC", ["order_flow", "cvd", "level2"], admitted=True)
        self.assertEqual({item["capability"] for item in demand["capabilities"]}, {TRADES, BOOK})
        self.h.step()
        self.h.step()
        self.h.ack_all()
        self.h.now += 1_000_000
        self.h.step(trade_message(1, "buy", "0.5"), trade_message(2, "sell", "0.2"),
                    fixture_lines("kraken_book_btcusd_depth10.jsonl")[0])
        flow = self.service.order_flow("XA01:BTC")
        self.assertEqual((flow["state"], flow["provider"], flow["market_session"]), ("CURRENT", "KRAKEN", "24_7"))
        self.assertEqual(flow["summary"]["native_count"], 2)
        self.assertAlmostEqual(flow["summary"]["net_signed_volume"], 0.3)
        cvd = self.service.cvd("XA01:BTC")
        self.assertAlmostEqual(cvd["summary"]["cvd"], 0.3)
        depth = self.service.depth("XA01:BTC")
        self.assertEqual(depth["state"], "CURRENT")
        self.assertEqual(depth["completeness"]["venue_scope"], "SINGLE_VENUE_KRAKEN")
        self.assertEqual(depth["freshness"]["policy"], "kraken_l2")
        # Hours later with no book change, a heartbeat on the live connection keeps it current.
        self.h.now += 10_000_000_000
        self.h.step(json.dumps({"channel": "heartbeat"}))
        self.assertEqual(self.service.depth("XA01:BTC")["state"], "CURRENT")

    def test_maintenance_blocks_panels_as_disconnected(self):
        self.service.demand("client", "XA01:BTC", ["order_flow"], admitted=True)
        self.h.step()
        self.h.step()
        self.h.ack_all()
        self.h.step(json.dumps({"channel": "status", "type": "update", "data": [{"system": "maintenance"}]}))
        flow = self.service.order_flow("XA01:BTC")
        self.assertEqual((flow["state"], flow["reason"]), ("DISCONNECTED", "MAINTENANCE"))

    def test_equity_only_panels_are_not_demandable_for_crypto(self):
        with self.assertRaises(ValueError):
            self.service.demand("client", "XA01:BTC", ["short_squeeze"], admitted=True)


if __name__ == "__main__":
    unittest.main()
