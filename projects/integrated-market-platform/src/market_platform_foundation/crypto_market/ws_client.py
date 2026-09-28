"""Minimal standard-library RFC 6455 WebSocket client for public market data.

IMP's dependency lock prohibits third-party WebSocket packages, so the Crypto
venue stream uses this small client over ``socket`` + ``ssl``. It supports
exactly what a public market-data subscription needs: a TLS connection to an
allowlisted host, the HTTP/1.1 upgrade with ``Sec-WebSocket-Accept``
verification, masked client text frames, fragmented server text messages,
ping/pong, and close. Server frames are size-bounded; a protocol violation is
an error, never a best-effort parse.

A receive timeout never loses bytes: frames are parsed only from a complete
buffer, so a partially received frame is completed by a later call.
"""

from __future__ import annotations

import base64
import hashlib
import os
import socket
import ssl
import struct
from typing import Any, Callable
from urllib.parse import urlsplit

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
ALLOWED_HOSTS = frozenset({"ws.kraken.com"})
MAX_MESSAGE_BYTES = 8 * 1024 * 1024
MAX_HANDSHAKE_BYTES = 16 * 1024
USER_AGENT = "IMP-Screener/1.0 (Integrated Market Platform research workstation)"

OP_CONTINUATION, OP_TEXT, OP_BINARY, OP_CLOSE, OP_PING, OP_PONG = 0x0, 0x1, 0x2, 0x8, 0x9, 0xA


class WebSocketError(OSError):
    """A stream failure carrying only a stable code (URLs and bodies are never echoed)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def accept_key(key: str) -> str:
    return base64.b64encode(hashlib.sha1((key + GUID).encode("ascii")).digest()).decode("ascii")


def encode_frame(opcode: int, payload: bytes, *, mask: bytes | None = None) -> bytes:
    """One final client frame; client frames are always masked (RFC 6455 §5.3)."""

    mask = os.urandom(4) if mask is None else mask
    length = len(payload)
    if length < 126:
        header = struct.pack("!BB", 0x80 | opcode, 0x80 | length)
    elif length < 1 << 16:
        header = struct.pack("!BBH", 0x80 | opcode, 0x80 | 126, length)
    else:
        header = struct.pack("!BBQ", 0x80 | opcode, 0x80 | 127, length)
    masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return header + mask + masked


def parse_frame(buffer: bytearray, *, max_bytes: int = MAX_MESSAGE_BYTES) -> tuple[bool, int, bytes] | None:
    """Consume one complete server frame from ``buffer`` or return None if incomplete."""

    if len(buffer) < 2:
        return None
    first, second = buffer[0], buffer[1]
    if first & 0x70:
        raise WebSocketError("WS_RESERVED_BITS")
    if second & 0x80:
        raise WebSocketError("WS_MASKED_SERVER_FRAME")
    length, offset = second & 0x7F, 2
    if length == 126:
        if len(buffer) < 4:
            return None
        length, offset = struct.unpack("!H", bytes(buffer[2:4]))[0], 4
    elif length == 127:
        if len(buffer) < 10:
            return None
        length, offset = struct.unpack("!Q", bytes(buffer[2:10]))[0], 10
    if length > max_bytes:
        raise WebSocketError("WS_FRAME_TOO_LARGE")
    if len(buffer) < offset + length:
        return None
    payload = bytes(buffer[offset:offset + length])
    del buffer[:offset + length]
    return bool(first & 0x80), first & 0x0F, payload


def _default_connector(host: str, port: int, timeout: float) -> Any:
    raw = socket.create_connection((host, port), timeout=timeout)
    try:
        return ssl.create_default_context().wrap_socket(raw, server_hostname=host)
    except Exception:
        raw.close()
        raise


class WebSocketClient:
    """One client connection; not thread-safe (one owner thread drives it)."""

    def __init__(self, sock: Any, *, max_bytes: int = MAX_MESSAGE_BYTES, initial: bytes = b"") -> None:
        self._sock = sock
        self._max = max_bytes
        self._buffer = bytearray(initial)
        self._fragments: list[bytes] = []
        self._fragment_opcode: int | None = None
        self.closed = False

    @classmethod
    def connect(cls, url: str, *, timeout: float = 10.0,
                connector: Callable[[str, int, float], Any] = _default_connector) -> "WebSocketClient":
        parts = urlsplit(url)
        host = parts.hostname or ""
        if parts.scheme != "wss" or host not in ALLOWED_HOSTS:
            raise WebSocketError("WS_HOST_NOT_ALLOWED")
        try:
            sock = connector(host, parts.port or 443, timeout)
        except (OSError, ssl.SSLError):
            raise WebSocketError("WS_CONNECT_FAILED") from None
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (f"GET {parts.path or '/'} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\n"
                   f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
                   f"User-Agent: {USER_AGENT}\r\n\r\n")
        try:
            sock.settimeout(timeout)
            sock.sendall(request.encode("ascii"))
            response = b""
            while b"\r\n\r\n" not in response:
                chunk = sock.recv(4096)
                if not chunk:
                    raise WebSocketError("WS_HANDSHAKE_CLOSED")
                response += chunk
                if len(response) > MAX_HANDSHAKE_BYTES:
                    raise WebSocketError("WS_HANDSHAKE_TOO_LARGE")
        except WebSocketError:
            sock.close()
            raise
        except (OSError, ssl.SSLError):
            sock.close()
            raise WebSocketError("WS_HANDSHAKE_FAILED") from None
        head, _, rest = response.partition(b"\r\n\r\n")
        lines = head.decode("latin-1").split("\r\n")
        headers = {name.strip().lower(): value.strip() for name, _, value in
                   (line.partition(":") for line in lines[1:])}
        if not lines[0].startswith("HTTP/1.1 101") or headers.get("upgrade", "").lower() != "websocket" \
                or headers.get("sec-websocket-accept") != accept_key(key):
            sock.close()
            raise WebSocketError("WS_HANDSHAKE_REJECTED")
        return cls(sock, initial=rest)

    def send_text(self, text: str) -> None:
        self._send(OP_TEXT, text.encode("utf-8"))

    def _send(self, opcode: int, payload: bytes) -> None:
        if self.closed:
            raise WebSocketError("WS_CLOSED")
        try:
            self._sock.sendall(encode_frame(opcode, payload))
        except (OSError, ssl.SSLError):
            self.closed = True
            raise WebSocketError("WS_SEND_FAILED") from None

    def receive(self, timeout: float) -> str | None:
        """The next complete text message, or None when ``timeout`` passes first."""

        while True:
            frame = parse_frame(self._buffer, max_bytes=self._max)
            if frame is None:
                if self.closed:
                    raise WebSocketError("WS_CLOSED")
                try:
                    self._sock.settimeout(timeout)
                    chunk = self._sock.recv(65536)
                except (socket.timeout, TimeoutError):
                    return None
                except (OSError, ssl.SSLError):
                    self.closed = True
                    raise WebSocketError("WS_RECEIVE_FAILED") from None
                if not chunk:
                    self.closed = True
                    raise WebSocketError("WS_CLOSED_BY_PEER")
                self._buffer.extend(chunk)
                continue
            final, opcode, payload = frame
            if opcode == OP_PING:
                self._send(OP_PONG, payload)
                continue
            if opcode == OP_PONG:
                continue
            if opcode == OP_CLOSE:
                try:
                    self._send(OP_CLOSE, payload[:2])
                except WebSocketError:
                    pass
                self.closed = True
                raise WebSocketError("WS_CLOSED_BY_PEER")
            if opcode in (OP_TEXT, OP_BINARY):
                if self._fragment_opcode is not None:
                    raise WebSocketError("WS_INTERLEAVED_FRAGMENT")
                if not final:
                    self._fragment_opcode, self._fragments = opcode, [payload]
                    continue
                message, kind = payload, opcode
            elif opcode == OP_CONTINUATION:
                if self._fragment_opcode is None:
                    raise WebSocketError("WS_UNEXPECTED_CONTINUATION")
                self._fragments.append(payload)
                if sum(len(part) for part in self._fragments) > self._max:
                    raise WebSocketError("WS_MESSAGE_TOO_LARGE")
                if not final:
                    continue
                message, kind = b"".join(self._fragments), self._fragment_opcode
                self._fragment_opcode, self._fragments = None, []
            else:
                raise WebSocketError("WS_UNKNOWN_OPCODE")
            if kind != OP_TEXT:
                raise WebSocketError("WS_BINARY_UNSUPPORTED")
            try:
                return message.decode("utf-8")
            except UnicodeDecodeError:
                raise WebSocketError("WS_INVALID_UTF8") from None

    def close(self) -> None:
        if not self.closed:
            try:
                self._sock.sendall(encode_frame(OP_CLOSE, struct.pack("!H", 1000)))
            except (OSError, ssl.SSLError):
                pass
        self.closed = True
        try:
            self._sock.close()
        except OSError:
            pass
