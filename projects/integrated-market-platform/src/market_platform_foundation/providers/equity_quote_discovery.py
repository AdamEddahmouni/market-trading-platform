"""Value-blind equity-quote provider discovery. Never prints secret values.

OpenD reachability is diagnostic only. It never selects Yahoo as the hop
``quote_provider`` — Yahoo remains a distinct delayed overlay via
``delayed_cloud_overlay_provider()``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .adapters.moomoo_opend_equity_quote import opend_sdk_available
from .adapters.yahoo_delayed_equity_quote import YAHOO_PROVIDER_ID
from .contracts import EquityQuoteProvider
from .equity_quote_selection import opend_readiness, primary_equity_quote_provider
from .stubs import UnconfiguredEquityQuoteProvider

_PLACEHOLDERS = frozenset({"", "CHANGEME", "EXAMPLE", "PLACEHOLDER", "NOT_A_SECRET"})

FINVIZ_TOKEN_NAMES = (
    "FINVIZ_API_KEY",
    "FINVIZ_AUTH_TOKEN",
    "FINVIZ_API_TOKEN",
    "FINVIZ_ELITE_TOKEN",
    "IMP_FINVIZ_ELITE_TOKEN",
)

_MOOMOO_CONFIG_NAMES = (
    "IMP_MOOMOO_HOST",
    "IMP_MOOMOO_PORT",
    "IMP_MOOMOO_LIVE",
    "IMP_LIVE_OBSERVATIONAL",
)


def _present(name: str) -> bool:
    value = (os.environ.get(name) or "").strip()
    return value.upper() not in _PLACEHOLDERS


def names_present(names: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(name for name in names if _present(name))


def moomoo_config_names_present() -> tuple[str, ...]:
    return names_present(_MOOMOO_CONFIG_NAMES)


@dataclass(frozen=True, slots=True)
class EquityQuoteDiscovery:
    provider_id: str
    classification: str
    timeliness: str
    reason_code: str
    config_names_present: tuple[str, ...]
    finviz_token_names_present: tuple[str, ...]
    opend_reachable: bool
    overlay_provider_id: str = YAHOO_PROVIDER_ID


def discover_equity_quote_stack() -> tuple[EquityQuoteProvider, EquityQuoteDiscovery]:
    """Always return OpenD as the hop quote provider. Yahoo stays overlay-only.

    Loopback OpenD reachability does not change which adapter occupies the
    primary slot. When the daemon is down, the OpenD adapter fails closed
    (``OPEND_UNAVAILABLE``). When it is up but the vendor SDK is missing,
    discovery reports ``MOOMOO_SDK_MISSING`` — never a fabricated tick.
    SDK present is diagnostic only (``OPEND_SDK_PRESENT``); it is not a quote.
    Yahoo delayed is reported as ``overlay_provider_id`` only — never swapped
    into ``quote_provider``.
    """

    finviz = names_present(FINVIZ_TOKEN_NAMES)
    moomoo_names = moomoo_config_names_present()
    readiness = opend_readiness()
    provider = primary_equity_quote_provider()
    if not readiness.loopback:
        classification = "CONFIGURED_BLOCKED"
        reason_code = "OPEND_NON_LOOPBACK_BLOCKED"
    elif not readiness.reachable:
        classification = "UNAVAILABLE"
        reason_code = "OPEND_UNAVAILABLE"
    elif not opend_sdk_available():
        classification = "CONFIGURED_BLOCKED"
        reason_code = "MOOMOO_SDK_MISSING"
    else:
        classification = "CONFIGURED"
        reason_code = "OPEND_SDK_PRESENT"
    discovery = EquityQuoteDiscovery(
        provider_id=provider.provider_id,
        classification=classification,
        timeliness="REAL_TIME",
        reason_code=reason_code,
        config_names_present=moomoo_names,
        finviz_token_names_present=finviz,
        opend_reachable=readiness.reachable,
        overlay_provider_id=YAHOO_PROVIDER_ID,
    )
    return provider, discovery


def unconfigured_equity_quote() -> EquityQuoteProvider:
    return UnconfiguredEquityQuoteProvider()


__all__ = [
    "EquityQuoteDiscovery",
    "FINVIZ_TOKEN_NAMES",
    "discover_equity_quote_stack",
    "moomoo_config_names_present",
    "names_present",
    "unconfigured_equity_quote",
]
