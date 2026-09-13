"""Moomoo OpenD equity snapshot. Fail closed when the local daemon is down."""

from __future__ import annotations

import os
import socket

from ..contracts import ProviderResult

MOOMOO_PROVIDER_ID = "moomoo.opend.observational"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 11111


def _opend_endpoint() -> tuple[str, int]:
    host = (os.environ.get("IMP_MOOMOO_HOST") or DEFAULT_HOST).strip() or DEFAULT_HOST
    if host not in {"127.0.0.1", "localhost"}:
        return host, -1
    raw_port = (os.environ.get("IMP_MOOMOO_PORT") or str(DEFAULT_PORT)).strip()
    try:
        port = int(raw_port)
    except ValueError:
        port = DEFAULT_PORT
    return host, port


def opend_reachable(*, timeout_sec: float = 0.4) -> bool:
    host, port = _opend_endpoint()
    if port <= 0:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True
    except OSError:
        return False


class MoomooOpenDEquityQuoteProvider:
    """One-shot OpenD quote pull. Transport is not implemented in-tree — fail closed."""

    provider_id = MOOMOO_PROVIDER_ID
    capability = "US_EQUITY_L1"
    timeliness = "REAL_TIME"

    def fetch_quote(self, symbol: str) -> ProviderResult:
        del symbol
        host, port = _opend_endpoint()
        if port <= 0:
            return ProviderResult(
                status="unavailable",
                reason_code="OPEND_NON_LOOPBACK_BLOCKED",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        if not opend_reachable():
            return ProviderResult(
                status="unavailable",
                reason_code="OPEND_UNAVAILABLE",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        return ProviderResult(
            status="unavailable",
            reason_code="MOOMOO_TRANSPORT_NOT_IMPLEMENTED",
            provider_id=self.provider_id,
            capability=self.capability,
        )


class UnreachableOpenDEquityQuoteProvider:
    """Explicit disconnected OpenD — never substituted with mock ticks."""

    provider_id = MOOMOO_PROVIDER_ID
    capability = "US_EQUITY_L1"

    def fetch_quote(self, symbol: str) -> ProviderResult:
        del symbol
        return ProviderResult(
            status="unavailable",
            reason_code="OPEND_UNAVAILABLE",
            provider_id=self.provider_id,
            capability=self.capability,
        )


def moomoo_config_names_present() -> tuple[str, ...]:
    names = (
        "IMP_MOOMOO_HOST",
        "IMP_MOOMOO_PORT",
        "IMP_MOOMOO_LIVE",
        "IMP_LIVE_OBSERVATIONAL",
    )
    present = []
    placeholders = {"", "CHANGEME", "EXAMPLE", "PLACEHOLDER", "NOT_A_SECRET"}
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value.upper() not in placeholders:
            present.append(name)
    return tuple(present)


__all__ = [
    "MOOMOO_PROVIDER_ID",
    "MoomooOpenDEquityQuoteProvider",
    "UnreachableOpenDEquityQuoteProvider",
    "moomoo_config_names_present",
    "opend_reachable",
]
