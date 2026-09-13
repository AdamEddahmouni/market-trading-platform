"""Value-blind equity-quote provider discovery. Never prints secret values."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .adapters.moomoo_opend_equity_quote import (
    MoomooOpenDEquityQuoteProvider,
    moomoo_config_names_present,
    opend_reachable,
)
from .adapters.yahoo_delayed_equity_quote import YahooDelayedEquityQuoteProvider
from .contracts import EquityQuoteProvider
from .stubs import UnconfiguredEquityQuoteProvider

_PLACEHOLDERS = frozenset({"", "CHANGEME", "EXAMPLE", "PLACEHOLDER", "NOT_A_SECRET"})

FINVIZ_TOKEN_NAMES = (
    "FINVIZ_API_KEY",
    "FINVIZ_AUTH_TOKEN",
    "FINVIZ_API_TOKEN",
    "FINVIZ_ELITE_TOKEN",
    "IMP_FINVIZ_ELITE_TOKEN",
)


def _present(name: str) -> bool:
    value = (os.environ.get(name) or "").strip()
    return value.upper() not in _PLACEHOLDERS


def names_present(names: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(name for name in names if _present(name))


@dataclass(frozen=True, slots=True)
class EquityQuoteDiscovery:
    provider_id: str
    classification: str
    timeliness: str
    reason_code: str
    config_names_present: tuple[str, ...]
    finviz_token_names_present: tuple[str, ...]
    opend_reachable: bool


def discover_equity_quote_stack() -> tuple[EquityQuoteProvider, EquityQuoteDiscovery]:
    """Pick the strongest currently usable quote provider without leaking secrets.

    Moomoo OpenD is preferred when the loopback daemon is up, but in-tree
    transport is still unimplemented — that is CONFIGURED_BLOCKED, not a
    silent Yahoo fallback under the Moomoo identity.
    """

    finviz = names_present(FINVIZ_TOKEN_NAMES)
    moomoo_names = moomoo_config_names_present()
    reachable = opend_reachable()
    if reachable:
        provider = MoomooOpenDEquityQuoteProvider()
        discovery = EquityQuoteDiscovery(
            provider_id=provider.provider_id,
            classification="CONFIGURED_BLOCKED",
            timeliness="REAL_TIME",
            reason_code="MOOMOO_TRANSPORT_NOT_IMPLEMENTED",
            config_names_present=moomoo_names,
            finviz_token_names_present=finviz,
            opend_reachable=True,
        )
        return provider, discovery
    yahoo = YahooDelayedEquityQuoteProvider()
    return yahoo, EquityQuoteDiscovery(
        provider_id=yahoo.provider_id,
        classification="AVAILABLE_NOT_ACTIVE",
        timeliness="DELAYED",
        reason_code="YAHOO_DELAYED_OVERLAY",
        config_names_present=moomoo_names,
        finviz_token_names_present=finviz,
        opend_reachable=False,
    )


def unconfigured_equity_quote() -> EquityQuoteProvider:
    return UnconfiguredEquityQuoteProvider()


__all__ = [
    "EquityQuoteDiscovery",
    "FINVIZ_TOKEN_NAMES",
    "discover_equity_quote_stack",
    "names_present",
    "unconfigured_equity_quote",
]
