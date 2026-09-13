"""Value-blind Finviz Elite context discovery. Never prints secret values."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .adapters.finviz_elite_context import (
    FINVIZ_CONTEXT_PROVIDER_ID,
    FINVIZ_CONTEXT_ROLE,
    FINVIZ_CONTEXT_TIMELINESS,
    FINVIZ_TOKEN_NAMES,
    FinvizEliteContextProvider,
    overlay_payload,
    token_names_present,
)
from .contracts import ProviderResult

_YAHOO_IDENTITIES = frozenset({"yahoo.finance.delayed", "yahoo", "YAHOO"})


@dataclass(frozen=True, slots=True)
class FinvizContextDiscovery:
    provider_id: str
    classification: str
    timeliness: str
    reason_code: str
    role: str
    token_names_present: tuple[str, ...]
    live_enabled: bool
    is_l1: bool
    is_paper_comparator: bool

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["token_names_present"] = list(self.token_names_present)
        return payload


def discover_finviz_context_stack(
    *,
    env: Mapping[str, str] | None = None,
    provider: FinvizEliteContextProvider | None = None,
) -> tuple[FinvizEliteContextProvider, FinvizContextDiscovery]:
    """Always return the Finviz context adapter. Never Yahoo-as-Finviz.

    Token absence is ``NOT_CONFIGURED``. A present token without ``IMP_FINVIZ_LIVE``
    and without injected clients is ``CONFIGURED_BLOCKED`` (``LIVE_DISABLED``).
    Classification is never ``REAL_TIME`` and never an ES/L1 identity.
    """

    adapter = provider or FinvizEliteContextProvider(env=env)
    if adapter.provider_id in _YAHOO_IDENTITIES:
        raise ValueError("FINVIZ_YAHOO_IDENTITY_FORBIDDEN")
    names = token_names_present(env)
    live = adapter.live_enabled()
    if not adapter.configured():
        classification = "NOT_CONFIGURED"
        reason = "NOT_CONFIGURED"
    elif not live and not adapter.has_injected_transport():
        classification = "CONFIGURED_BLOCKED"
        reason = "LIVE_DISABLED"
    else:
        classification = "CONFIGURED"
        reason = "FINVIZ_CONTEXT_OVERLAY"
    discovery = FinvizContextDiscovery(
        provider_id=FINVIZ_CONTEXT_PROVIDER_ID,
        classification=classification,
        timeliness=FINVIZ_CONTEXT_TIMELINESS,
        reason_code=reason,
        role=FINVIZ_CONTEXT_ROLE,
        token_names_present=names,
        live_enabled=live,
        is_l1=False,
        is_paper_comparator=False,
    )
    return adapter, discovery


def run_finviz_context_overlay(
    symbol: str,
    *,
    env: Mapping[str, str] | None = None,
    provider: FinvizEliteContextProvider | None = None,
) -> dict[str, Any]:
    """Canonical pipeline overlay: classify, then fetch context fail-closed."""

    adapter, discovery = discover_finviz_context_stack(env=env, provider=provider)
    result: ProviderResult = adapter.fetch_context(symbol)
    return overlay_payload(discovery=discovery.to_dict(), result=result)


__all__ = [
    "FINVIZ_TOKEN_NAMES",
    "FinvizContextDiscovery",
    "discover_finviz_context_stack",
    "run_finviz_context_overlay",
    "token_names_present",
]
