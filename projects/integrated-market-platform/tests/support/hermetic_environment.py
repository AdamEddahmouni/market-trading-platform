"""Inject offline facts for unit tests without stopping a live OpenD collector.

Use unreachable loopback ports and explicit SDK-absence patches so tests stay
deterministic when ``127.0.0.1:11111`` is up and ``moomoo-api`` is installed.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Iterator
from unittest.mock import patch

UNREACHABLE_LOOPBACK_PORT = "1"
_MOOMOO_ENV = ("IMP_MOOMOO_HOST", "IMP_MOOMOO_PORT")


@contextlib.contextmanager
def env(**overrides: str) -> Iterator[None]:
    previous = {name: os.environ.get(name) for name in overrides}
    try:
        os.environ.update(overrides)
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


@contextlib.contextmanager
def unreachable_opend_env(*, host: str = "127.0.0.1", port: str = UNREACHABLE_LOOPBACK_PORT) -> Iterator[None]:
    """Point OpenD at a closed loopback port (default ``1``), not the live daemon."""

    with env(IMP_MOOMOO_HOST=host, IMP_MOOMOO_PORT=port):
        yield


@contextlib.contextmanager
def cleared_moomoo_endpoint_env() -> Iterator[None]:
    """Clear host/port overrides, then force an unreachable loopback port."""

    previous = {name: os.environ.pop(name, None) for name in _MOOMOO_ENV}
    try:
        os.environ["IMP_MOOMOO_HOST"] = "127.0.0.1"
        os.environ["IMP_MOOMOO_PORT"] = UNREACHABLE_LOOPBACK_PORT
        yield
    finally:
        for name in _MOOMOO_ENV:
            os.environ.pop(name, None)
        for name, value in previous.items():
            if value is not None:
                os.environ[name] = value


@contextlib.contextmanager
def vendor_sdk_absent() -> Iterator[None]:
    """Treat the vendor quote SDK as absent regardless of the host venv."""

    from market_platform_foundation.providers.adapters.moomoo_opend_equity_quote import (
        MOOMOO_SDK_MISSING,
        OpenDSnapshotResult,
    )

    def _transport_missing_sdk(self, *, symbol: str, host: str, port: int) -> OpenDSnapshotResult:
        del self, symbol, host, port
        return OpenDSnapshotResult(reason_code=MOOMOO_SDK_MISSING)

    with (
        patch("tools.moomoo.opend_quote_transport.load_vendor_sdk", return_value=None),
        patch(
            "market_platform_foundation.providers.adapters.moomoo_opend_equity_quote.opend_sdk_available",
            return_value=False,
        ),
        patch(
            "market_platform_foundation.providers.equity_quote_discovery.opend_sdk_available",
            return_value=False,
        ),
        patch(
            "market_platform_foundation.providers.adapters.moomoo_opend_equity_quote.VendorSdkOpenDQuoteTransport.fetch_snapshot",
            _transport_missing_sdk,
        ),
    ):
        yield


@contextlib.contextmanager
def hop_interpreter_without_vendor_sdk() -> Iterator[None]:
    with patch("tools.moomoo.opend_hop_interpreter._load_transport") as load_transport:
        transport = load_transport.return_value
        transport.load_vendor_sdk.return_value = None
        transport.is_vendor_sdk.return_value = False
        yield


@contextlib.contextmanager
def ephemeral_loopback_listener() -> Iterator[tuple[str, int]]:
    """Bind an ephemeral TCP port on loopback for reachability-only probes."""

    import socket

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(32)
    host, port = listener.getsockname()
    try:
        yield host, port
    finally:
        listener.close()


__all__ = [
    "UNREACHABLE_LOOPBACK_PORT",
    "cleared_moomoo_endpoint_env",
    "env",
    "ephemeral_loopback_listener",
    "hop_interpreter_without_vendor_sdk",
    "unreachable_opend_env",
    "vendor_sdk_absent",
]
