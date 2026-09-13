"""Equity quote source selection — Moomoo OpenD is Primary L1 (DoD item 2).

The no-additional-cost stack's locked decision: **Primary L1 = OpenD
observational**. Loopback OpenD reachability is informational only — it never
changes which adapter is "primary." The primary :class:`EquityQuoteProvider`
slot is always the Moomoo OpenD adapter; when the daemon is down, the
vendor SDK is missing, or the vendor row has no ``last_price``,
``fetch_quote`` fails closed (see ``adapters.moomoo_opend_equity_quote``)
instead of silently substituting Yahoo or a mock tick under the Moomoo
identity.

Yahoo delayed quotes remain reachable only through the explicitly-identified
overlay accessor below — a distinct provider identity, never merged into the
primary slot, never labeled ``REAL_TIME``, and never usable for ES (see
``adapters.yahoo_delayed_equity_quote``).
"""

from __future__ import annotations

from dataclasses import dataclass

from .adapters.moomoo_opend_equity_quote import (
    MOOMOO_OPEND_PROVIDER_ID,
    MoomooOpenDEquityQuoteProvider,
    opend_endpoint,
    opend_is_loopback,
    opend_reachable,
)
from .adapters.yahoo_delayed_equity_quote import (
    YAHOO_PROVIDER_ID,
    YahooDelayedEquityQuoteProvider,
)
from .contracts import EquityQuoteProvider


@dataclass(frozen=True, slots=True)
class OpenDReadiness:
    """Diagnostic snapshot only — never used to swap the primary provider."""

    host: str
    port: int
    loopback: bool
    reachable: bool


def opend_readiness() -> OpenDReadiness:
    host, port = opend_endpoint()
    loopback = opend_is_loopback(host)
    reachable = opend_reachable(host=host, port=port) if loopback else False
    return OpenDReadiness(host=host, port=port, loopback=loopback, reachable=reachable)


def primary_equity_quote_provider() -> EquityQuoteProvider:
    """Primary L1 slot. Always Moomoo OpenD (DoD item 2 — locked stack)."""

    return MoomooOpenDEquityQuoteProvider()


def delayed_cloud_overlay_provider() -> EquityQuoteProvider:
    """Yahoo delayed overlay. Distinct identity; never the primary L1 slot."""

    return YahooDelayedEquityQuoteProvider()


__all__ = [
    "MOOMOO_OPEND_PROVIDER_ID",
    "OpenDReadiness",
    "YAHOO_PROVIDER_ID",
    "delayed_cloud_overlay_provider",
    "opend_readiness",
    "primary_equity_quote_provider",
]
