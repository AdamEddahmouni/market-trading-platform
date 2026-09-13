"""Moomoo OpenD observational equity quote — Primary L1 (DoD item 2).

Loopback OpenD only; never mock. Reachability is checked at call time inside
``fetch_quote`` (not cached at import/composition time), so a daemon that
goes up or down mid-process is reflected on the next call. When the daemon
is unreachable this fails closed with ``OPEND_UNAVAILABLE``. When it is
reachable, the in-tree vendor transport is still not implemented (the
``moomoo-api`` SDK is intentionally not a dependency of this package per
``docs/providers/MOOMOO_OBSERVATIONAL.md``), so this fails closed with
``MOOMOO_TRANSPORT_NOT_IMPLEMENTED`` rather than fabricating a tick. This
adapter never returns ``status="available"``.
"""

from __future__ import annotations

import socket

from ...market_data.live_config import moomoo_host, moomoo_port
from ..contracts import ProviderResult

MOOMOO_OPEND_PROVIDER_ID = "moomoo.opend.observational"
US_EQUITY_L1_CAPABILITY = "US_EQUITY_L1"

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

OPEND_NON_LOOPBACK_BLOCKED = "OPEND_NON_LOOPBACK_BLOCKED"
OPEND_UNAVAILABLE = "OPEND_UNAVAILABLE"
MOOMOO_TRANSPORT_NOT_IMPLEMENTED = "MOOMOO_TRANSPORT_NOT_IMPLEMENTED"


def opend_endpoint() -> tuple[str, int]:
    """Read the configured OpenD endpoint via the canonical live_config accessors."""

    host = (moomoo_host() or "").strip() or "127.0.0.1"
    try:
        port = moomoo_port()
    except (TypeError, ValueError):
        port = 11111
    return host, port


def opend_is_loopback(host: str) -> bool:
    return host in _LOOPBACK_HOSTS


def opend_reachable(*, host: str | None = None, port: int | None = None, timeout_sec: float = 0.4) -> bool:
    """TCP-connect probe only. Never treated as evidence of quote availability."""

    target_host, target_port = (host, port) if host is not None and port is not None else opend_endpoint()
    if not opend_is_loopback(target_host):
        return False
    try:
        with socket.create_connection((target_host, target_port), timeout=timeout_sec):
            return True
    except OSError:
        return False


class MoomooOpenDEquityQuoteProvider:
    """Primary L1 equity quote slot. Fail-closed; never substitutes mock ticks."""

    provider_id = MOOMOO_OPEND_PROVIDER_ID
    capability = US_EQUITY_L1_CAPABILITY
    timeliness = "REAL_TIME"

    def fetch_quote(self, symbol: str) -> ProviderResult:
        del symbol
        host, port = opend_endpoint()
        if not opend_is_loopback(host):
            return ProviderResult(
                status="unavailable",
                reason_code=OPEND_NON_LOOPBACK_BLOCKED,
                provider_id=self.provider_id,
                capability=self.capability,
            )
        if not opend_reachable(host=host, port=port):
            return ProviderResult(
                status="unavailable",
                reason_code=OPEND_UNAVAILABLE,
                provider_id=self.provider_id,
                capability=self.capability,
            )
        # Loopback daemon is up, but the vendor transport is intentionally not
        # wired into `src/` (docs/providers/MOOMOO_OBSERVATIONAL.md). Reaching
        # this branch must still fail closed rather than fabricate a tick.
        return ProviderResult(
            status="unavailable",
            reason_code=MOOMOO_TRANSPORT_NOT_IMPLEMENTED,
            provider_id=self.provider_id,
            capability=self.capability,
        )


__all__ = [
    "MOOMOO_OPEND_PROVIDER_ID",
    "MOOMOO_TRANSPORT_NOT_IMPLEMENTED",
    "MoomooOpenDEquityQuoteProvider",
    "OPEND_NON_LOOPBACK_BLOCKED",
    "OPEND_UNAVAILABLE",
    "US_EQUITY_L1_CAPABILITY",
    "opend_endpoint",
    "opend_is_loopback",
    "opend_reachable",
]
