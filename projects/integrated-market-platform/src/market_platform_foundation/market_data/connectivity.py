"""Stdlib-only OpenD connectivity checks for governed foundation."""

from __future__ import annotations

import socket

from .live_config import moomoo_host, moomoo_port


def opend_reachable(*, host: str | None = None, port: int | None = None, timeout: float = 2.0) -> bool:
    target_host = host or moomoo_host()
    target_port = port or moomoo_port()
    if target_host not in {"127.0.0.1", "localhost", "::1"}:
        return False
    try:
        sock = socket.create_connection((target_host, target_port), timeout=timeout)
        sock.close()
        return True
    except OSError:
        return False
